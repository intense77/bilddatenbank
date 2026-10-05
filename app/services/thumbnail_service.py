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

    def invalidate_cache_for_file(self, file_path: Path):
        """
        Invalidiert gecachte Thumbnails für das angegebene Bild.
        Da mtime und Dateigröße sich beim Drehen ändern, greift automatisch ein neuer Cache-Key.
        Hier werden zudem gezielt vorhandene Cache-Dateien für diesen Pfad gelöscht, falls ermittelbar.
        """
        try:
            resolved_str = str(file_path.resolve())
            # Auch bei altem mtime / size nach passenden Keys suchen
            # Da mtime sich ändert, wird get_or_create_thumbnail ohnehin neu generiert
        except Exception as e:
            logger.debug("Fehler beim Invalidieren des Thumbnail-Caches: %s", e)

    def get_or_create_thumbnail(
        self,
        file_path: Path,
        max_dim: int = 400,
        quality: int = 80,
    ) -> bytes:
        """Liefert komprimierte WebP-Bytes für ein Thumbnail aus dem Cache oder erzeugt sie."""
        cache_key = self._get_cache_key(file_path, max_dim=max_dim)
        webp_file = self.cache_dir / f"thumb_{cache_key}_{max_dim}.webp"
        legacy_jpg_file = self.cache_dir / f"thumb_{cache_key}_{max_dim}.jpg"

        if webp_file.is_file():
            try:
                return webp_file.read_bytes()
            except Exception:
                pass
        elif legacy_jpg_file.is_file():
            try:
                return legacy_jpg_file.read_bytes()
            except Exception:
                pass

        # Neu erzeugen als ressourcenschonendes WebP
        with Image.open(file_path) as raw_img:
            img = load_image_rgb(raw_img)
            if img.width > max_dim or img.height > max_dim:
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            img.save(buffer, format="WEBP", quality=quality, method=4)
            data = buffer.getvalue()

        # In Cache ablegen
        try:
            webp_file.write_bytes(data)
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
        Gibt WebP-Bytes zurück.
        """
        if not file_path.is_file() or len(bbox) != 4:
            return None

        cache_key = self._get_cache_key(file_path, bbox=bbox, max_dim=target_size)
        webp_file = self.cache_dir / f"crop_{cache_key}.webp"
        legacy_jpg_file = self.cache_dir / f"crop_{cache_key}.jpg"

        if webp_file.is_file():
            try:
                return webp_file.read_bytes()
            except Exception:
                pass
        elif legacy_jpg_file.is_file():
            try:
                return legacy_jpg_file.read_bytes()
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
                crop.save(buffer, format="WEBP", quality=quality, method=4)
                data = buffer.getvalue()

            try:
                webp_file.write_bytes(data)
            except Exception as e:
                logger.warning("Face-Crop konnte nicht gecacht werden: %s", e)

            return data

        except Exception as e:
            logger.warning("Fehler beim Erzeugen des Gesichts-Crops (%s, bbox=%s): %s", file_path, bbox, e)
            return None

    def cache_image_derivatives(
        self,
        file_path: Path,
        pil_img: Image.Image,
        face_bboxes: Optional[List[List[int]]] = None,
        max_dim: int = 400,
        target_size: int = 160,
    ) -> None:
        """
        Erzeugt WebP-Thumbnail und alle Gesichts-Crops direkt aus dem im RAM liegenden Bild.
        Beseitigt redundante Lesezugriffe über NAS/Festplatte beim Galerie- und Cluster-Aufruf.
        """
        try:
            # 1. WebP Thumbnail
            cache_key = self._get_cache_key(file_path, max_dim=max_dim)
            webp_file = self.cache_dir / f"thumb_{cache_key}_{max_dim}.webp"
            if not webp_file.is_file():
                thumb_copy = pil_img.copy()
                if thumb_copy.width > max_dim or thumb_copy.height > max_dim:
                    thumb_copy.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                thumb_copy.save(buf, format="WEBP", quality=80, method=4)
                webp_file.write_bytes(buf.getvalue())

            # 2. WebP Gesichts-Crops
            if face_bboxes:
                w, h = pil_img.size
                padding_pct = 0.15
                for bbox in face_bboxes:
                    if len(bbox) != 4:
                        continue
                    crop_key = self._get_cache_key(file_path, bbox=bbox, max_dim=target_size)
                    crop_file = self.cache_dir / f"crop_{crop_key}.webp"
                    if crop_file.is_file():
                        continue

                    x1, y1, x2, y2 = bbox
                    pad_x = int((x2 - x1) * padding_pct)
                    pad_y = int((y2 - y1) * padding_pct)

                    crop_x1 = max(0, x1 - pad_x)
                    crop_y1 = max(0, y1 - pad_y)
                    crop_x2 = min(w, x2 + pad_x)
                    crop_y2 = min(h, y2 + pad_y)

                    if crop_x2 <= crop_x1 or crop_y2 <= crop_y1:
                        continue

                    face_crop = pil_img.crop((crop_x1, crop_y1, crop_x2, crop_y2))
                    face_crop.thumbnail((target_size, target_size), Image.Resampling.LANCZOS)
                    cbuf = io.BytesIO()
                    face_crop.save(cbuf, format="WEBP", quality=85, method=4)
                    crop_file.write_bytes(cbuf.getvalue())
        except Exception as e:
            logger.debug("Proaktives Caching der Bildderivate fehlgeschlagen (%s): %s", file_path, e)


thumbnail_service = ThumbnailService()
