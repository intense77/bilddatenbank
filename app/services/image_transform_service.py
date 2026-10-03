"""
Image Transformation Service für das Historische Bildarchiv.
Führt non-destruktive Bildtransformationen (Helligkeit, Kontrast, Gamma,
Schärfung, 90°-Drehung, Negativ-Invertierung, Crop) serverseitig via Pillow aus.
Das Originalbild auf dem Speichermedium bleibt stets 100% unverändert.
"""

import io
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from PIL import Image, ImageEnhance, ImageOps

logger = logging.getLogger("archive_app.image_transform_service")


class ImageTransformService:

    @staticmethod
    def apply_transformations(image: Image.Image, settings: Dict[str, Any]) -> Image.Image:
        """
        Wendet die Transformations-Parameter non-destruktiv auf das übergebene PIL-Image an.
        """
        img = ImageOps.exif_transpose(image)

        # 1. Ausschnitt (Crop)
        crop = settings.get("crop")
        if crop and isinstance(crop, dict):
            w, h = img.size
            cx = float(crop.get("x", 0))
            cy = float(crop.get("y", 0))
            cw = float(crop.get("width", w))
            ch = float(crop.get("height", h))

            if crop.get("is_percent", False) or (cw <= 100.0 and ch <= 100.0 and (cx + cw) <= 100.0):
                left = int((cx / 100.0) * w)
                top = int((cy / 100.0) * h)
                right = int(((cx + cw) / 100.0) * w)
                bottom = int(((cy + ch) / 100.0) * h)
            else:
                left = int(cx)
                top = int(cy)
                right = int(cx + cw)
                bottom = int(cy + ch)

            # Grenzen absichern
            left = max(0, min(left, w - 1))
            top = max(0, min(top, h - 1))
            right = max(left + 1, min(right, w))
            bottom = max(top + 1, min(bottom, h))

            if (right - left) > 5 and (bottom - top) > 5:
                img = img.crop((left, top, right, bottom))

        # 2. Rotation (im Uhrzeigersinn: 90, 180, 270)
        rotation = int(settings.get("rotation", 0)) % 360
        if rotation in (90, 180, 270):
            # PIL .rotate() dreht gegen den Uhrzeigersinn -> -rotation dreht im Uhrzeigersinn
            img = img.rotate(-rotation, expand=True)

        # Farbformat sicherstellen
        if img.mode not in ("RGB", "RGBA", "L"):
            img = img.convert("RGB")

        # 3. Negativ-Invertierung (z. B. für Glasplattennegative)
        if settings.get("invert", False):
            if img.mode == "RGBA":
                r, g, b, a = img.split()
                rgb = Image.merge("RGB", (r, g, b))
                inv = ImageOps.invert(rgb)
                r2, g2, b2 = inv.split()
                img = Image.merge("RGBA", (r2, g2, b2, a))
            else:
                img = ImageOps.invert(img.convert("RGB"))

        # 4. Helligkeit (-50% bis +50% -> Faktor 0.5 bis 1.5)
        brightness_pct = float(settings.get("brightness", 0))
        if brightness_pct != 0:
            factor = 1.0 + (brightness_pct / 100.0)
            factor = max(0.1, min(3.0, factor))
            img = ImageEnhance.Brightness(img).enhance(factor)

        # 5. Kontrast (-50% bis +50% -> Faktor 0.5 bis 1.5)
        contrast_pct = float(settings.get("contrast", 0))
        if contrast_pct != 0:
            factor = 1.0 + (contrast_pct / 100.0)
            factor = max(0.1, min(3.0, factor))
            img = ImageEnhance.Contrast(img).enhance(factor)

        # 6. Gamma-Korrektur (0.5 bis 2.0, Standard 1.0)
        gamma = float(settings.get("gamma", 1.0))
        if gamma != 1.0 and 0.2 <= gamma <= 3.0:
            inv_gamma = 1.0 / gamma
            lut = [int(((i / 255.0) ** inv_gamma) * 255) for i in range(256)]
            if img.mode == "RGB":
                lut = lut * 3
            elif img.mode == "RGBA":
                lut = lut * 3 + list(range(256))
            img = img.point(lut)

        # 7. Schärfung (0 bis 100 -> Faktor 1.0 bis 3.0)
        sharpness = float(settings.get("sharpness", 0))
        if sharpness > 0:
            factor = 1.0 + (sharpness / 50.0)
            img = ImageEnhance.Sharpness(img).enhance(factor)

        return img

    @classmethod
    def export_processed_image(
        cls,
        file_path: Path,
        settings: Dict[str, Any],
        output_format: str = "jpg",
    ) -> Tuple[bytes, str, str]:
        """
        Lädt das Originalbild schreibgeschützt, wendet die Transformationen an
        und gibt (bytes, media_type, filename) zurück.
        """
        with Image.open(file_path) as raw_img:
            processed = cls.apply_transformations(raw_img, settings)

            buf = io.BytesIO()
            fmt = output_format.lower()

            stem = file_path.stem
            if fmt in ("tiff", "tif"):
                # TIFF (unkomprimiert oder Deflate für Archivstandard)
                if processed.mode not in ("RGB", "RGBA", "L"):
                    processed = processed.convert("RGB")
                processed.save(buf, format="TIFF", compression="tiff_deflate")
                media_type = "image/tiff"
                filename = f"{stem}_bearbeitet.tif"
            else:
                # Standard: Hochwertiges JPEG (95% Qualität)
                if processed.mode in ("RGBA", "P"):
                    processed = processed.convert("RGB")
                processed.save(buf, format="JPEG", quality=95, optimize=True)
                media_type = "image/jpeg"
                filename = f"{stem}_bearbeitet.jpg"

            return buf.getvalue(), media_type, filename


image_transform_service = ImageTransformService()
