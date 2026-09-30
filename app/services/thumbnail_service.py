import io
import os
import hashlib
import logging
from pathlib import Path
from typing import List, Optional
from PIL import Image

from app.core.config import settings
from app.services.clip_service import load_image_rgb

logger = logging.getLogger(__name__)


class ThumbnailService:
    """
    Ressourcenschonender Caching-Dienst für Bild-Thumbnails und Gesichts-Ausschnitte.
    Vermeidet das wiederholte Dekodieren großer historischer Master-Scans (TIFF/RAW/High-Res JPEG).
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path(settings.THUMBNAIL_CACHE_DIR)
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning("Konnte Thumbnail-Cache-Verzeichnis nicht anlegen: %s", e)

    def _get_cache_key(self, file_path: Path, bbox: Optional[List[int]] = None, max_dim: Optional[int] = None) -> str:
        """Erzeugt einen eindeutigen MD5-Cache-Key basierend auf Dateipfad, Änderungszeit und Zuschnitt."""
        try:
            mtime = os.path.getmtime(file_path)
            size = os.path.getsize(file_path)
        except OSError:
            mtime = 0
            size = 0
        raw_key = f"{file_path.resolve()}_{mtime}_{size}_{bbox}_{max_dim}"
        return hashlib.md5(raw_key.encode("utf-8")).hexdigest()

    def get_or_create_thumbnail(
        self,
        file_path: Path,
        max_dim: int = 400,
        quality: int = 80,
    ) -> bytes:
        """Liefert die komprimierten JPEG-Bytes für ein Thumbnail aus dem Cache oder erzeugt sie."""
        cache_key = self._get_cache_key(file_path, max_dim=max_dim)
        cache_file = self.cache_dir / f"thumb_{cache_key}_{max_dim}.jpg"

        if cache_file.is_file():
            try:
                return cache_file.read_bytes()
            except Exception:
                pass

        # Neu erzeugen
        with Image.open(file_path) as raw_img:
            img = load_image_rgb(raw_img)
            if img.width > max_dim or img.height > max_dim:
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=quality, optimize=True)
            data = buffer.getvalue()

        # In Cache ablegen
        try:
            cache_file.write_bytes(data)
        except Exception as e:
            logger.warning("Thumbnail konnte nicht gecacht werden: %s", e)

        return data

    def get_or_create_face_crop(
        self,
        file_path: Path,
        bbox: List[int],
        target_size: int = 160,
        padding_pct: float = 0.15,
        quality: int = 85,
    ) -> Optional[bytes]:
        """
        Schneidet ein Gesicht aus dem Master-Bild aus, skaliert es und speichert es im Cache.
        Gibt JPEG-Bytes zurück.
        """
        if not file_path.is_file() or len(bbox) != 4:
            return None

        cache_key = self._get_cache_key(file_path, bbox=bbox, max_dim=target_size)
        cache_file = self.cache_dir / f"crop_{cache_key}.jpg"

        if cache_file.is_file():
            try:
                return cache_file.read_bytes()
            except Exception:
                pass

        try:
            with Image.open(file_path) as raw_img:
                img = load_image_rgb(raw_img)
                w, h = img.size

                x1, y1, x2, y2 = bbox
                bw = x2 - x1
                bh = y2 - y1

                pad_x = int(bw * padding_pct)
                pad_y = int(bh * padding_pct)

                crop_x1 = max(0, x1 - pad_x)
                crop_y1 = max(0, y1 - pad_y)
                crop_x2 = min(w, x2 + pad_x)
                crop_y2 = min(h, y2 + pad_y)

                if crop_x2 <= crop_x1 or crop_y2 <= crop_y1:
                    return None

                crop = img.crop((crop_x1, crop_y1, crop_x2, crop_y2))
                crop.thumbnail((target_size, target_size), Image.Resampling.LANCZOS)

                buffer = io.BytesIO()
                crop.save(buffer, format="JPEG", quality=quality, optimize=True)
                data = buffer.getvalue()

            try:
                cache_file.write_bytes(data)
            except Exception as e:
                logger.warning("Face-Crop konnte nicht gecacht werden: %s", e)

            return data

        except Exception as e:
            logger.warning("Fehler beim Erzeugen des Gesichts-Crops (%s, bbox=%s): %s", file_path, bbox, e)
            return None


thumbnail_service = ThumbnailService()
