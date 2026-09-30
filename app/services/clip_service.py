import logging
from pathlib import Path
from typing import List, Union
import torch
from PIL import Image, ImageFile, UnidentifiedImageError
import open_clip

from app.core.config import settings

# Ermöglicht das Laden leicht beschädigter oder unvollständiger historischer Scans
ImageFile.LOAD_TRUNCATED_IMAGES = True

logger = logging.getLogger(__name__)


def load_image_rgb(image_input: Union[str, Path, Image.Image]) -> Image.Image:
    """
    Lädt ein Bild sicher und konvertiert es robust in den RGB-Farbraum.
    Unterstützt Pfade (TIFF, JPEG, PNG, etc.) und PIL Image-Objekte.
    Fängt CMYK, Transparenzen (Alpha-Kanal mit weißem Hintergrund) und Graustufen ab.
    """
    try:
        if isinstance(image_input, Image.Image):
            img = image_input
        elif isinstance(image_input, (str, Path)):
            path = Path(image_input)
            if not path.is_file():
                raise FileNotFoundError(f"Bilddatei nicht gefunden: {path}")
            img = Image.open(path)
        else:
            raise TypeError(f"Nicht unterstützter Bildtyp: {type(image_input)}")

        # Erzwinge das Laden der Pixeldaten, um korrumpierte Dateien frühzeitig zu erkennen
        img.load()

        if img.mode != "RGB":
            # Transparente Bilder mit weißem Hintergrund verschmelzen (historische Scans/Logos)
            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                alpha_img = img.convert("RGBA")
                background = Image.new("RGB", alpha_img.size, (255, 255, 255))
                background.paste(alpha_img, mask=alpha_img.split()[3])
                img = background
            elif img.mode == "CMYK":
                # CMYK zu RGB Farbprofil-Konvertierung
                img = img.convert("RGB")
            else:
                img = img.convert("RGB")

        return img

    except (UnidentifiedImageError, OSError, ValueError, FileNotFoundError) as e:
        logger.error("Fehler beim Laden/Konvertieren des Bildes (%s): %s", image_input, e)
        raise


class ClipService:
    """Service zur Extraktion von Bild- und Text-Embeddings mit OpenCLIP (512-dim)."""

    def __init__(
        self,
        model_name: str = settings.CLIP_MODEL_NAME,
        pretrained: str = settings.CLIP_PRETRAINED,
    ):
        # Automatische Erkennung und Nutzung von CUDA, ansonsten Fallback auf CPU
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_name = model_name
        self.pretrained = pretrained

        logger.info(
            "Initialisiere OpenCLIP (Modell: %s, Pretrained: %s) auf Device: %s (CUDA verfügbar: %s)",
            self.model_name,
            self.pretrained,
            self.device,
            torch.cuda.is_available(),
        )

        try:
            self.model, _, self.preprocess = open_clip.create_model_and_transforms(
                self.model_name,
                pretrained=self.pretrained,
                device=self.device,
            )
            self.tokenizer = open_clip.get_tokenizer(self.model_name)
            self.model.eval()
            logger.info("OpenCLIP erfolgreich auf %s geladen.", self.device)
        except Exception as e:
            logger.error("Fehler beim Laden des OpenCLIP-Modells: %s", e, exc_info=True)
            raise

    @torch.no_grad()
    def embed_image(self, image_path: Union[str, Path, Image.Image]) -> List[float]:
        """
        Lädt ein Bild via PIL, normalisiert es und gibt einen L2-normalisierten 512-dim Vektor zurück.
        Fängt beschädigte Scans sowie CMYK/TIFF-Formate sauber ab.
        """
        img = load_image_rgb(image_path)
        tensor = self.preprocess(img).unsqueeze(0).to(self.device)
        image_features = self.model.encode_image(tensor)
        # L2-Normalisierung für Cosine-Ähnlichkeitssuche
        image_features /= image_features.norm(dim=-1, keepdim=True)
        return image_features.squeeze(0).cpu().numpy().tolist()

    @torch.no_grad()
    def embed_text(self, query: str) -> List[float]:
        """Vektorisiert einen Suchtext für die Cosine-Suche (L2-normalisiert, 512-dim)."""
        if not query or not query.strip():
            raise ValueError("Der Suchtext darf nicht leer sein.")

        tokens = self.tokenizer([query.strip()]).to(self.device)
        text_features = self.model.encode_text(tokens)
        # L2-Normalisierung für Cosine-Ähnlichkeitssuche
        text_features /= text_features.norm(dim=-1, keepdim=True)
        return text_features.squeeze(0).cpu().numpy().tolist()

    # Alias-Methoden für Kompatibilität mit bestehenden Aufrufen
    def encode_image(self, image: Union[str, Path, Image.Image]) -> List[float]:
        """Kompatibilitäts-Alias für embed_image."""
        return self.embed_image(image)

    def encode_text(self, text: str) -> List[float]:
        """Kompatibilitäts-Alias für embed_text."""
        return self.embed_text(text)
