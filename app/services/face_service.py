import logging
from pathlib import Path
from typing import Any, Dict, List, Union
import numpy as np
from PIL import Image, ImageFile, ImageOps, UnidentifiedImageError

from app.core.config import settings

# Ermöglicht das Laden leicht beschädigter oder unvollständiger historischer Scans
ImageFile.LOAD_TRUNCATED_IMAGES = True

logger = logging.getLogger(__name__)


def load_image_rgb(image_input: Union[str, Path, Image.Image]) -> Image.Image:
    """
    Lädt ein Bild sicher und konvertiert es robust in den RGB-Farbraum.
    Unterstützt Pfade (TIFF, JPEG, PNG, etc.) und PIL Image-Objekte.
    Entzerrt die EXIF-Orientierung, damit Pixelkoordinaten mit der Browser-Darstellung übereinstimmen.
    Fängt CMYK, Transparenzen und Graustufen ab.
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

        # EXIF-Orientierung (Drehung/Spiegelung) entzerren
        img = ImageOps.exif_transpose(img)
        img.load()

        if img.mode != "RGB":
            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                alpha_img = img.convert("RGBA")
                background = Image.new("RGB", alpha_img.size, (255, 255, 255))
                background.paste(alpha_img, mask=alpha_img.split()[3])
                img = background
            elif img.mode == "CMYK":
                img = img.convert("RGB")
            else:
                img = img.convert("RGB")

        return img

    except (UnidentifiedImageError, OSError, ValueError, FileNotFoundError) as e:
        logger.error("Fehler beim Laden/Konvertieren des Bildes (%s): %s", image_input, e)
        raise


class FaceService:
    """Service zur Gesichtserkennung und Extraktion von ArcFace-Embeddings (512-dim) via InsightFace."""

    def __init__(
        self,
        model_name: str = settings.INSIGHTFACE_MODEL_NAME,
        det_size: int = settings.INSIGHTFACE_DET_SIZE,
    ):
        try:
            from insightface.app import FaceAnalysis
        except ImportError as e:
            logger.error("InsightFace konnte nicht importiert werden: %s", e)
            raise

        self.model_name = model_name
        self.det_size = (det_size, det_size)

        # Provider Konfiguration für ONNX Runtime (bevorzuge CUDA, Fallback CPU)
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]

        logger.info(
            "Initialisiere InsightFace (%s, det_size=%s) mit Providern: %s...",
            self.model_name,
            self.det_size,
            providers,
        )

        try:
            self.app = FaceAnalysis(
                name=self.model_name,
                allowed_modules=["detection", "recognition"],
                providers=providers,
            )
            # ctx_id=0 für GPU (sofern CUDAExecutionProvider greift), ansonsten CPU
            self.app.prepare(ctx_id=0, det_size=self.det_size)
            logger.info("InsightFace erfolgreich initialisiert (Module: detection, recognition).")
        except Exception as e:
            logger.warning(
                "Initialisierung mit CUDAExecutionProvider fehlgeschlagen (%s). Versuche reines CPUExecutionProvider...",
                e,
            )
            self.app = FaceAnalysis(
                name=self.model_name,
                allowed_modules=["detection", "recognition"],
                providers=["CPUExecutionProvider"],
            )
            self.app.prepare(ctx_id=-1, det_size=self.det_size)
            logger.info("InsightFace erfolgreich im CPU-Modus initialisiert.")

    def extract_faces(self, image_path: Union[str, Path, Image.Image]) -> List[Dict[str, Any]]:
        """
        Detektiert alle Gesichter im Bild und liefert pro Gesicht ein Dictionary mit:
        - bbox: [x1, y1, x2, y2] (int)
        - det_score: Konfidenz (float)
        - embedding: 512-dim Vektor (L2-normalisiert)

        Fängt beschädigte Scans sowie CMYK/TIFF-Formate sauber ab.
        """
        try:
            img = load_image_rgb(image_path)
        except Exception as e:
            logger.warning("Bild konnte nicht geladen werden (%s): %s", image_path, e)
            return []

        orig_w, orig_h = img.size

        # Vorab-Downsampling für InsightFace:
        # Falls die Kantenlänge 2000 px übersteigt, für die Inferenz herunterskalieren.
        # Spart bis zu 90 % Inferenzzeit und RAM. Bounding Boxes werden exakt auf Originalmaße zurückgerechnet.
        max_edge = max(orig_w, orig_h)
        if max_edge > 2000:
            scale_factor = 2000.0 / max_edge
            scaled_w = int(round(orig_w * scale_factor))
            scaled_h = int(round(orig_h * scale_factor))
            infer_img = img.resize((scaled_w, scaled_h), Image.Resampling.BILINEAR)
        else:
            scale_factor = 1.0
            infer_img = img

        # InsightFace erwartet BGR numpy-Array (OpenCV / numpy)
        rgb_array = np.array(infer_img)
        bgr_array = rgb_array[:, :, ::-1]

        try:
            faces = self.app.get(bgr_array)
        except Exception as e:
            logger.error("Fehler bei der Gesichtserkennung für '%s': %s", image_path, e, exc_info=True)
            return []
        finally:
            del rgb_array
            del bgr_array
            if infer_img is not img:
                try:
                    infer_img.close()
                except Exception:
                    pass
            # Falls image_path ein Pfad/String war, wurde img in load_image_rgb neu geöffnet
            if not isinstance(image_path, Image.Image):
                try:
                    img.close()
                except Exception:
                    pass

        results = []
        for face in faces:
            # ArcFace Embeddings (512-dimensional, L2-normalisiert)
            emb = face.normed_embedding
            if emb is None:
                norm = np.linalg.norm(face.embedding)
                emb = face.embedding / norm if norm > 0 else face.embedding

            # Bei herunterskaliertem Bild Bounding-Box auf Originalmaße zurückskalieren
            raw_bbox = face.bbox.tolist()
            if scale_factor != 1.0:
                inv_scale = 1.0 / scale_factor
                x1 = int(round(raw_bbox[0] * inv_scale))
                y1 = int(round(raw_bbox[1] * inv_scale))
                x2 = int(round(raw_bbox[2] * inv_scale))
                y2 = int(round(raw_bbox[3] * inv_scale))
            else:
                x1, y1, x2, y2 = [int(round(coord)) for coord in raw_bbox]

            bbox_coords = [x1, y1, x2, y2]

            # Normalisierte Prozentwerte für Browser-Overlay berechnen:
            left_pct = (x1 / orig_w) * 100 if orig_w > 0 else 0.0
            top_pct = (y1 / orig_h) * 100 if orig_h > 0 else 0.0
            width_pct = ((x2 - x1) / orig_w) * 100 if orig_w > 0 else 0.0
            height_pct = ((y2 - y1) / orig_h) * 100 if orig_h > 0 else 0.0

            bbox_percent = {
                "left": round(left_pct, 4),
                "top": round(top_pct, 4),
                "width": round(width_pct, 4),
                "height": round(height_pct, 4),
            }

            results.append({
                "bbox": bbox_coords,
                "bbox_percent": bbox_percent,
                "orig_width": orig_w,
                "orig_height": orig_h,
                "det_score": float(face.det_score) if hasattr(face, "det_score") else 1.0,
                "embedding": [float(val) for val in emb.tolist()],
            })

        return results

    # Alias-Methode für Rückwärtskompatibilität
    def detect_and_embed(self, image: Union[str, Path, Image.Image]) -> List[Dict[str, Any]]:
        """Kompatibilitäts-Alias für extract_faces."""
        return self.extract_faces(image)
