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

    def __init__(self, cache_dir: Optional[Path] = None, max_cache_mb: Optional[int] = None):
        self.cache_dir = cache_dir or Path(settings.THUMBNAIL_CACHE_DIR)
        self.max_cache_mb = max_cache_mb if max_cache_mb is not None else getattr(settings, "MAX_THUMBNAIL_CACHE_MB", 5000)
        self._write_count = 0
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning("Konnte Thumbnail-Cache-Verzeichnis nicht anlegen: %s", e)

    def _touch_file(self, file_path: Path) -> None:
        """Aktualisiert mtime für echtes LRU-Tracking bei Cache-Hits."""
        try:
            os.utime(file_path, None)
        except Exception:
            pass

    def _record_write_and_maybe_prune(self) -> None:
        """Inkrementiert den Schreibzähler und stößt alle 100 Schreibvorgänge die LRU-Prüfung an."""
        self._write_count += 1
        if self._write_count % 100 == 0:
            try:
                self.prune_lru()
            except Exception as e:
                logger.debug("Automatische LRU-Bereinigung fehlgeschlagen: %s", e)

    def get_cache_stats(self) -> dict:
        """Liefert Metriken zum aktuellen Füllstand des Thumbnail-Caches."""
        total_files = 0
        total_bytes = 0
        try:
            for item in self.cache_dir.iterdir():
                if item.is_file() and (item.suffix.lower() in (".webp", ".jpg")):
                    total_files += 1
                    total_bytes += item.stat().st_size
        except Exception as e:
            logger.debug("Fehler beim Ermitteln der Cache-Statistik: %s", e)

        total_mb = round(total_bytes / (1024 * 1024), 2)
        max_mb = self.max_cache_mb
        usage_pct = round((total_mb / max_mb) * 100, 1) if max_mb > 0 else 0.0

        return {
            "cache_dir": str(self.cache_dir.resolve()),
            "total_files": total_files,
            "total_bytes": total_bytes,
            "total_mb": total_mb,
            "max_cache_mb": max_mb,
            "usage_percent": usage_pct,
            "limit_exceeded": total_mb > max_mb,
        }

    def prune_lru(self, target_mb: Optional[int] = None, force: bool = False) -> dict:
        """
        Bereinigt älteste Cache-Dateien (LRU: Least Recently Used).
        Greift automatisch, wenn der Cache max_cache_mb überschreitet,
        und bereinigt auf 80 % des Limits (bzw. auf target_mb).
        """
        stats = self.get_cache_stats()
        current_mb = stats["total_mb"]
        max_mb = self.max_cache_mb

        if not force and current_mb <= max_mb:
            return {
                "status": "ok",
                "pruned_count": 0,
                "freed_mb": 0.0,
                "current_mb": current_mb,
                "max_cache_mb": max_mb,
            }

        effective_target_mb = target_mb if target_mb is not None else max_mb * 0.8
        target_bytes = int(effective_target_mb * 1024 * 1024)

        file_entries = []
        try:
            for item in self.cache_dir.iterdir():
                if item.is_file() and (item.suffix.lower() in (".webp", ".jpg")):
                    try:
                        st = item.stat()
                        file_entries.append((item, st.st_mtime, st.st_size))
                    except (OSError, FileNotFoundError):
                        continue
        except Exception as e:
            logger.error("Fehler beim Scannen des Thumbnail-Caches für LRU: %s", e)
            return {"status": "error", "message": str(e)}

        # Älteste zuerst
        file_entries.sort(key=lambda x: x[1])

        current_bytes = stats["total_bytes"]
        pruned_count = 0
        freed_bytes = 0

        for f_path, _, f_size in file_entries:
            if current_bytes <= target_bytes:
                break
            try:
                f_path.unlink(missing_ok=True)
                current_bytes -= f_size
                freed_bytes += f_size
                pruned_count += 1
            except Exception:
                pass

        freed_mb = round(freed_bytes / (1024 * 1024), 2)
        remaining_mb = round(current_bytes / (1024 * 1024), 2)
        logger.info(
            "LRU-Cache-Bereinigung durchgeführt: %d Dateien gelöscht, %.2f MB freigegeben. Verbleibend: %.2f MB",
            pruned_count,
            freed_mb,
            remaining_mb,
        )

        return {
            "status": "pruned",
            "pruned_count": pruned_count,
            "freed_mb": freed_mb,
            "remaining_files": len(file_entries) - pruned_count,
            "remaining_mb": remaining_mb,
            "max_cache_mb": max_mb,
        }

    def _get_cache_key(
        self,
        file_path: Path,
        bbox: Optional[List[int]] = None,
        max_dim: Optional[int] = None,
        rotation: Optional[int] = None,
    ) -> str:
        """Erzeugt einen eindeutigen MD5-Cache-Key basierend auf Dateipfad, Änderungszeit, Zuschnitt und Rotation."""
        try:
            mtime = os.path.getmtime(file_path)
            size = os.path.getsize(file_path)
        except OSError:
            mtime = 0
            size = 0
        raw_key = f"{file_path.resolve()}_{mtime}_{size}_{bbox}_{max_dim}_{rotation}"
        return hashlib.md5(raw_key.encode("utf-8")).hexdigest()

    def invalidate_cache_for_file(self, file_path: Path):
        """
        Invalidiert gecachte Thumbnails für das angegebene Bild.
        Löscht vorhandene Cache-Dateien für diesen Pfad, um sofortige Aktualisierungen zu gewährleisten.
        """
        try:
            resolved_str = str(file_path.resolve())
            prefix_hash = hashlib.md5(resolved_str.encode("utf-8")).hexdigest()[:8]
            # Schnelle Bereinigung passender Cache-Dateien
            for item in self.cache_dir.glob(f"*{prefix_hash}*"):
                try:
                    item.unlink(missing_ok=True)
                except Exception:
                    pass
        except Exception as e:
            logger.debug("Fehler beim Invalidieren des Thumbnail-Caches: %s", e)

    def get_or_create_thumbnail(
        self,
        file_path: Path,
        max_dim: int = 400,
        quality: int = 80,
        rotation: Optional[int] = None,
    ) -> bytes:
        """Liefert komprimierte WebP-Bytes für ein Thumbnail aus dem Cache oder erzeugt sie."""
        from app.core.security import resolve_archive_path
        file_path = resolve_archive_path(file_path)

        # Falls rotation nicht explizit übergeben wurde: Aus SQLite edit_settings nachschlagen
        if rotation is None:
            try:
                from app.services.metadata_db import metadata_db
                es = metadata_db.get_edit_settings(str(file_path.resolve()))
                if es and es.get("rotation"):
                    rotation = int(es["rotation"]) % 360
            except Exception:
                rotation = 0
        else:
            rotation = int(rotation) % 360

        cache_key = self._get_cache_key(file_path, max_dim=max_dim, rotation=rotation)
        webp_file = self.cache_dir / f"thumb_{cache_key}_{max_dim}.webp"
        legacy_jpg_file = self.cache_dir / f"thumb_{cache_key}_{max_dim}.jpg"

        if webp_file.is_file():
            try:
                self._touch_file(webp_file)
                return webp_file.read_bytes()
            except Exception:
                pass
        elif legacy_jpg_file.is_file():
            try:
                self._touch_file(legacy_jpg_file)
                return legacy_jpg_file.read_bytes()
            except Exception:
                pass

        # Neu erzeugen als ressourcenschonendes WebP
        with Image.open(file_path) as raw_img:
            img = load_image_rgb(raw_img)
            # Revisionssichere virtuelle Drehung anwenden
            if rotation in (90, 180, 270):
                if rotation == 90:
                    img = img.transpose(Image.Transpose.ROTATE_270)
                elif rotation == 180:
                    img = img.transpose(Image.Transpose.ROTATE_180)
                elif rotation == 270:
                    img = img.transpose(Image.Transpose.ROTATE_90)

            if img.width > max_dim or img.height > max_dim:
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            img.save(buffer, format="WEBP", quality=quality, method=4)
            data = buffer.getvalue()

        # In Cache ablegen
        try:
            webp_file.write_bytes(data)
            self._record_write_and_maybe_prune()
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
        from app.core.security import resolve_archive_path
        file_path = resolve_archive_path(file_path)

        if not file_path.is_file() or len(bbox) != 4:
            return None

        cache_key = self._get_cache_key(file_path, bbox=bbox, max_dim=target_size)
        webp_file = self.cache_dir / f"crop_{cache_key}.webp"
        legacy_jpg_file = self.cache_dir / f"crop_{cache_key}.jpg"

        if webp_file.is_file():
            try:
                self._touch_file(webp_file)
                return webp_file.read_bytes()
            except Exception:
                pass
        elif legacy_jpg_file.is_file():
            try:
                self._touch_file(legacy_jpg_file)
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
                self._record_write_and_maybe_prune()
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
                try:
                    if thumb_copy.width > max_dim or thumb_copy.height > max_dim:
                        thumb_copy.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
                    buf = io.BytesIO()
                    try:
                        thumb_copy.save(buf, format="WEBP", quality=80, method=4)
                        webp_file.write_bytes(buf.getvalue())
                        self._record_write_and_maybe_prune()
                    finally:
                        buf.close()
                finally:
                    thumb_copy.close()

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
                    try:
                        face_crop.thumbnail((target_size, target_size), Image.Resampling.LANCZOS)
                        cbuf = io.BytesIO()
                        try:
                            face_crop.save(cbuf, format="WEBP", quality=85, method=4)
                            crop_file.write_bytes(cbuf.getvalue())
                            self._record_write_and_maybe_prune()
                        finally:
                            cbuf.close()
                    finally:
                        face_crop.close()
        except Exception as e:
            logger.debug("Proaktives Caching der Bildderivate fehlgeschlagen (%s): %s", file_path, e)


thumbnail_service = ThumbnailService()
