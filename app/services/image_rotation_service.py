import os
import shutil
import uuid
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Union, Optional
from PIL import Image, ImageOps

from app.core.config import settings
from app.services.indexing_service import IndexingService
from app.services.thumbnail_service import ThumbnailService, thumbnail_service

logger = logging.getLogger(__name__)


class ImageRotationService:
    """
    Dienst zum verlustfreien Drehen von Archivbildern (JPEG, PNG, TIFF).
    - JPEG: Physikalisches, verlustfreies DCT-Transponieren via jpegtran mit Erhalt aller
      Metadatenmarker (EXIF, IPTC, XMP, ICC) und anschließender Normalisierung des EXIF-Orientation-Tags.
      Fallback auf verlustfreie EXIF-Orientierungsanpassung via piexif.
    - PNG / TIFF: Mathematisch verlustfreie 90°/180°/270°-Transformationen.
    - Automatische Aktualisierung des Thumbnail-Caches und Reindexierung in Qdrant (CLIP-Vektor & Gesichter).
    """

    def __init__(
        self,
        indexing_service: IndexingService,
        thumbnail_service_instance: Optional[ThumbnailService] = None,
    ):
        self.indexing = indexing_service
        self.thumbnails = thumbnail_service_instance or thumbnail_service
        self._jpegtran_bin = self._find_jpegtran_binary()

    def _find_jpegtran_binary(self) -> Optional[str]:
        """Sucht nach dem jpegtran-Executable in der virtuellen Umgebung oder im Systempfad."""
        venv_bin = Path(__file__).resolve().parent.parent.parent / ".venv" / "bin" / "jpegtran"
        if venv_bin.is_file() and os.access(venv_bin, os.X_OK):
            return str(venv_bin)
        
        system_bin = shutil.which("jpegtran")
        if system_bin:
            return system_bin
        return None

    def rotate_image(self, file_path: Union[str, Path], angle: int = 90) -> Dict[str, Any]:
        """
        Dreht ein Bild verlustfrei um den angegebenen Winkel (90, 180, 270 bzw. -90 Grad).
        Führt anschließend eine Reindexierung durch.
        """
        path = Path(file_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Bilddatei nicht gefunden: {path}")

        # Schreibrechte prüfen
        if not os.access(path, os.W_OK):
            raise PermissionError(f"Keine Schreibberechtigung für die Datei: {path}")

        # Winkel normalisieren (z.B. -90 -> 270)
        norm_angle = angle % 360
        if norm_angle not in (90, 180, 270):
            raise ValueError(f"Ungültiger Drehwinkel: {angle}°. Erlaubt sind 90°, 180°, 270° bzw. -90°.")

        suffix = path.suffix.lower()
        method_used = "unknown"

        # Vorübergehendes Arbeitsverzeichnis für atomare Ersetzung
        # Bevorzugt im selben Verzeichnis (damit atomic rename klappt), mit Fallback auf Temp
        temp_dir = path.parent
        temp_file = None
        try:
            temp_name = f".rot_tmp_{uuid.uuid4().hex[:8]}_{path.name}"
            temp_file = temp_dir / temp_name
            # Testen, ob wir im Elternverzeichnis schreiben können
            temp_file.touch(exist_ok=True)
            temp_file.unlink()
        except OSError:
            # Fallback falls Elternverzeichnis keine neuen Dateien annehmen will
            temp_file = Path(f"/tmp/rot_tmp_{uuid.uuid4().hex[:8]}_{path.name}")

        try:
            if suffix in (".jpg", ".jpeg"):
                method_used = self._rotate_jpeg(path, temp_file, norm_angle)
            elif suffix == ".png":
                method_used = self._rotate_png(path, temp_file, norm_angle)
            elif suffix in (".tif", ".tiff"):
                method_used = self._rotate_tiff(path, temp_file, norm_angle)
            elif suffix == ".webp":
                method_used = self._rotate_webp(path, temp_file, norm_angle)
            else:
                raise ValueError(f"Nicht unterstütztes Bildformat für verlustfreie Drehung: {suffix}")

            # Atomares oder sicheres Ersetzen der Originaldatei
            self._safe_replace(temp_file, path)

            # Prüfen der neuen Dimensionen (inkl. EXIF-Orientierung)
            with Image.open(path) as img:
                transposed = ImageOps.exif_transpose(img)
                new_w, new_h = transposed.size

            # Thumbnail-Cache für dieses Bild invalidieren
            self.thumbnails.invalidate_cache_for_file(path)

            # Reindexierung in Qdrant (CLIP-Embedding + Gesichter)
            success, faces_count = self.indexing.reindex_single_image(path)

            # Warmup: Neues Thumbnail sofort vorbereiten
            try:
                self.thumbnails.get_or_create_thumbnail(path, max_dim=400)
            except Exception as e:
                logger.warning("Konnte neues Thumbnail nach Drehung nicht vorbereiten: %s", e)

            return {
                "success": True,
                "message": f"Bild verlustfrei um {angle}° gedreht ({method_used}).",
                "file_path": str(path),
                "file_name": path.name,
                "angle": angle,
                "normalized_angle": norm_angle,
                "rotation_method": method_used,
                "width": new_w,
                "height": new_h,
                "faces_detected": faces_count,
            }

        finally:
            if temp_file and temp_file.is_file():
                try:
                    temp_file.unlink(missing_ok=True)
                except OSError:
                    pass

    def _rotate_jpeg(self, src: Path, dst: Path, angle: int) -> str:
        """
        Führt verlustfreies JPEG-Drehen durch:
        1. Primär: jpegtran mit DCT-Koeffizienten-Transponierung (-rotate {angle} -copy all).
        2. Normalisierung des EXIF-Orientation-Tags auf 1 (normal), da die Pixel physisch gedreht wurden.
        3. Fallback: Reines verlustfreies Ändern des EXIF-Orientation-Tags via piexif.
        """
        if self._jpegtran_bin:
            cmd = [
                self._jpegtran_bin,
                "-rotate", str(angle),
                "-copy", "all",
                "-outfile", str(dst),
                str(src)
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0 and dst.is_file() and dst.stat().st_size > 0:
                # Da die Pixel nun physisch gedreht sind, setzen wir das EXIF-Orientation-Tag auf 1 (normal),
                # damit externe Bildbetrachter nicht fälschlich ein zweites Mal rotieren.
                self._reset_exif_orientation(dst)
                return "lossless_jpegtran_dct"
            else:
                logger.warning("jpegtran schlug fehl (%s): %s. Versuche EXIF-Fallback.", res.returncode, res.stderr)

        # Fallback: Nur EXIF Orientation Tag anpassen (100% verlustfrei ohne Pixelmodifikation)
        return self._rotate_jpeg_exif_only(src, dst, angle)

    def _reset_exif_orientation(self, jpeg_path: Path):
        """Setzt das EXIF Orientation Tag eines JPEGs auf 1 (Normal / Upright)."""
        try:
            import piexif
            exif_dict = piexif.load(str(jpeg_path))
            if "0th" in exif_dict and piexif.ImageIFD.Orientation in exif_dict["0th"]:
                exif_dict["0th"][piexif.ImageIFD.Orientation] = 1
                exif_bytes = piexif.dump(exif_dict)
                piexif.insert(exif_bytes, str(jpeg_path))
        except Exception as e:
            logger.debug("EXIF-Orientation konnte nicht zurückgesetzt werden (evtl. kein EXIF vorhanden): %s", e)

    def _rotate_jpeg_exif_only(self, src: Path, dst: Path, angle: int) -> str:
        """Fallback: Passt ausschließlich das EXIF-Orientation-Tag an."""
        import piexif
        shutil.copy2(src, dst)
        try:
            exif_dict = piexif.load(str(dst))
        except Exception:
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

        current_orient = exif_dict.get("0th", {}).get(piexif.ImageIFD.Orientation, 1)
        # EXIF Orientation Mapping nach Drehung im Uhrzeigersinn
        # 1: 0°, 6: 90° CW, 3: 180°, 8: 270° CW
        cw_transitions = {
            90: {1: 6, 6: 3, 3: 8, 8: 1, 2: 7, 7: 4, 4: 5, 5: 2},
            180: {1: 3, 3: 1, 6: 8, 8: 6, 2: 4, 4: 2, 5: 7, 7: 5},
            270: {1: 8, 8: 3, 3: 6, 6: 1, 2: 5, 5: 4, 4: 7, 7: 2},
        }
        new_orient = cw_transitions.get(angle, {}).get(current_orient, 1)
        if "0th" not in exif_dict:
            exif_dict["0th"] = {}
        exif_dict["0th"][piexif.ImageIFD.Orientation] = new_orient

        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, str(dst))
        return "lossless_exif_orientation_tag"

    def _rotate_png(self, src: Path, dst: Path, angle: int) -> str:
        """Mathematisch verlustfreie PNG-Drehung via Deflate."""
        rot_map = {
            90: Image.Transpose.ROTATE_270,   # Pillow ROTATE_270 = 90° im Uhrzeigersinn (oder 90 = counter-clockwise)
            180: Image.Transpose.ROTATE_180,
            270: Image.Transpose.ROTATE_90,
        }
        # In Pillow ist ROTATE_90 90° gegen den Uhrzeigersinn.
        # Für Drehung im Uhrzeigersinn: 90° CW = ROTATE_270.
        with Image.open(src) as img:
            rotated = img.transpose(rot_map[angle])
            rotated.save(dst, format="PNG", optimize=True)
        return "lossless_png"

    def _rotate_tiff(self, src: Path, dst: Path, angle: int) -> str:
        """Mathematisch verlustfreie TIFF-Drehung unter Erhalt der Kompression."""
        rot_map = {
            90: Image.Transpose.ROTATE_270,
            180: Image.Transpose.ROTATE_180,
            270: Image.Transpose.ROTATE_90,
        }
        with Image.open(src) as img:
            compression = img.info.get("compression", "raw")
            rotated = img.transpose(rot_map[angle])
            rotated.save(dst, format="TIFF", compression=compression)
        return "lossless_tiff"

    def _rotate_webp(self, src: Path, dst: Path, angle: int) -> str:
        """Verlustfreie WebP-Drehung."""
        rot_map = {
            90: Image.Transpose.ROTATE_270,
            180: Image.Transpose.ROTATE_180,
            270: Image.Transpose.ROTATE_90,
        }
        with Image.open(src) as img:
            rotated = img.transpose(rot_map[angle])
            rotated.save(dst, format="WEBP", lossless=True)
        return "lossless_webp"

    def _safe_replace(self, src: Path, dst: Path):
        """Ersetzt die Zieldatei sicher und erhält Berechtigungen."""
        try:
            shutil.copymode(dst, src)
        except Exception:
            pass

        try:
            # Atomarer Versuch
            os.replace(src, dst)
        except OSError:
            # Cross-device move fallback (z.B. zwischen /tmp und SMB-Mount)
            shutil.move(str(src), str(dst))
