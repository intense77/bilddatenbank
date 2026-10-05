"""
IIIF Image API 3.0 Service für hochauflösende Archivscans.
Bietet konforme info.json Metadaten, dynamische Kachelung,
Regionszuschnitte, Skalierung und lokales Caching für Deep-Zoom-Viewer (OpenSeadragon / Mirador).
"""

import os
import io
import base64
import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import unquote
from PIL import Image, ImageOps
from fastapi import HTTPException

from app.core.config import settings
from app.core.security import validate_safe_image_path

logger = logging.getLogger("archive_app.iiif_service")

# Lokales Cache-Verzeichnis für gerenderte IIIF-Kacheln
IIIF_CACHE_DIR = Path(".cache/iiif_tiles")


class IIIFService:
    def __init__(self, cache_dir: Path = IIIF_CACHE_DIR):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def encode_identifier(self, file_path: Union[str, Path]) -> str:
        """Kodiert einen Dateipfad in einen URL-sicheren IIIF-Identifier (Base64url)."""
        path_obj = Path(file_path)
        path_str = str(path_obj.resolve() if path_obj.exists() else path_obj)
        return base64.urlsafe_b64encode(path_str.encode("utf-8")).decode("ascii").rstrip("=")

    def resolve_identifier(self, identifier: str) -> Path:
        """
        Löst einen IIIF-Identifier in einen sicheren, validierten Dateipfad auf:
        1. Versucht Base64url-Dekodierung
        2. Versucht URL-Dekodierung / direkten Pfad
        3. Validiert gegen Verzeichnisgrenzen und erlaubte Formate
        """
        if not identifier:
            raise HTTPException(status_code=400, detail="Kein IIIF-Identifier übergeben.")

        candidate_str = identifier
        # 1. Base64url dekodieren (mit Padding-Kompensation)
        try:
            padded = identifier + "=" * ((4 - len(identifier) % 4) % 4)
            decoded_bytes = base64.urlsafe_b64decode(padded)
            decoded_str = decoded_bytes.decode("utf-8")
            # Prüfen, ob dekodierter String wie ein Dateipfad aussieht
            if "/" in decoded_str or "\\" in decoded_str or "." in decoded_str:
                candidate_str = decoded_str
        except Exception:
            candidate_str = unquote(identifier)

        # Falls relativer Pfad bereits mit ARCHIVE_DATA_DIR beginnt
        candidate_p = Path(candidate_str)
        if not candidate_p.is_absolute():
            archive_dir_name = Path(settings.ARCHIVE_DATA_DIR).name
            if candidate_p.parts and candidate_p.parts[0] == archive_dir_name:
                try:
                    candidate_str = str(candidate_p.relative_to(archive_dir_name))
                except Exception:
                    pass

        # 2. Prüfen über Sicherheitsvalidierung
        try:
            file_path = validate_safe_image_path(candidate_str)
            return file_path
        except HTTPException:
            # Fallback: Eventuell relative Pfadangabe zum Archivverzeichnis
            try:
                base_dir = Path(settings.ARCHIVE_DATA_DIR).resolve()
                alt_path = base_dir / candidate_str.lstrip("/\\")
                return validate_safe_image_path(alt_path)
            except Exception:
                raise HTTPException(status_code=404, detail=f"IIIF-Bild '{identifier}' nicht gefunden.")

    def get_image_info(self, identifier: str, base_url: str) -> Dict[str, Any]:
        """
        Erzeugt das konforme IIIF Image API 3.0 (und 2.1 kompatible) info.json Dokument.
        Ermittelt Bildmaße blitzschnell aus dem Datei-Header.
        """
        file_path = self.resolve_identifier(identifier)
        
        try:
            with Image.open(file_path) as img:
                # Berücksichtige EXIF-Orientierung für korrekte Ausmaße
                width, height = img.size
                exif = img.getexif()
                if exif:
                    orientation = exif.get(0x0112)
                    if orientation in [5, 6, 7, 8]:
                        width, height = height, width
        except Exception as e:
            logger.error("Fehler beim Lesen der Bildmaße für %s: %s", file_path, e)
            raise HTTPException(status_code=500, detail=f"Bildmaße konnten nicht ermittelt werden: {e}")

        # Standard-Kachelgröße für flüssiges Streaming (512x512)
        tile_size = 512
        max_dim = max(width, height)
        scale_factors = [1]
        s = 2
        while s * tile_size <= max_dim * 2:
            scale_factors.append(s)
            s *= 2

        # Vorberechnete Vorschaustufen (Sizes)
        sizes = []
        for target_dim in [256, 512, 1024, 2048]:
            if target_dim < max_dim:
                ratio = target_dim / float(max_dim)
                sizes.append({
                    "width": max(1, int(round(width * ratio))),
                    "height": max(1, int(round(height * ratio))),
                })

        iiif_id = f"{base_url.rstrip('/')}/api/iiif/{identifier}"

        return {
            "@context": "http://iiif.io/api/image/3/context.json",
            "id": iiif_id,
            "@id": iiif_id,  # Abwärtskompatibilität IIIF 2.x
            "type": "ImageService3",
            "protocol": "http://iiif.io/api/image",
            "profile": "level2",
            "width": width,
            "height": height,
            "sizes": sizes,
            "tiles": [
                {
                    "width": tile_size,
                    "height": tile_size,
                    "scaleFactors": scale_factors,
                }
            ],
            "preferredFormats": ["webp", "jpg", "png"],
            "rights": "https://creativecommons.org/publicdomain/mark/1.0/",
        }

    def render_tile(
        self,
        identifier: str,
        region: str,
        size: str,
        rotation: str,
        quality: str,
        fmt: str,
    ) -> Tuple[bytes, str]:
        """
        Rendert eine einzelne IIIF-Bildkachel bzw. liest sie aus dem lokalen SSD-Cache:
        - region: full | square | x,y,w,h | pct:x,y,w,h
        - size: max | full | w, | ,h | pct:n | w,h | !w,h
        - rotation: n | !n
        - quality: default | color | gray | bitonal
        - fmt: jpg | jpeg | png | webp
        """
        fmt_clean = fmt.lower()
        if fmt_clean == "jpeg":
            fmt_clean = "jpg"
        if fmt_clean not in ["jpg", "png", "webp", "tif", "tiff"]:
            raise HTTPException(status_code=400, detail=f"Nicht unterstütztes Format: '{fmt}'")

        # Cache-Prüfung
        cache_key = hashlib.sha256(
            f"{identifier}:{region}:{size}:{rotation}:{quality}:{fmt_clean}".encode("utf-8")
        ).hexdigest()
        sub_dir = self.cache_dir / cache_key[:2]
        cache_file = sub_dir / f"{cache_key}.{fmt_clean}"

        media_types = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "webp": "image/webp",
            "png": "image/png",
            "tif": "image/tiff",
            "tiff": "image/tiff",
        }
        media_type = media_types.get(fmt_clean, "image/jpeg")

        if cache_file.is_file():
            try:
                return cache_file.read_bytes(), media_type
            except Exception as e:
                logger.debug("Cache-Read miss für %s: %s", cache_file, e)

        # Datei laden und aufbereiten
        file_path = self.resolve_identifier(identifier)
        try:
            with Image.open(file_path) as raw_img:
                img = ImageOps.exif_transpose(raw_img)
                orig_w, orig_h = img.size

                # 1. REGION Zuschneiden
                img = self._apply_region(img, region, orig_w, orig_h)

                # 2. SIZE Skalieren
                img = self._apply_size(img, size)

                # 3. ROTATION & Spiegelung
                img = self._apply_rotation(img, rotation)

                # 4. QUALITY (Farbraum)
                img = self._apply_quality(img, quality)

                # 5. Format-Serialisierung
                buf = io.BytesIO()
                if fmt_clean == "jpg":
                    if img.mode in ("RGBA", "LA", "P"):
                        img = img.convert("RGB")
                    img.save(buf, format="JPEG", quality=85, optimize=True)
                elif fmt_clean == "webp":
                    img.save(buf, format="WEBP", quality=85, method=4)
                elif fmt_clean == "png":
                    img.save(buf, format="PNG", optimize=True)
                elif fmt_clean in ["tif", "tiff"]:
                    img.save(buf, format="TIFF")

                tile_bytes = buf.getvalue()

            # Atomares Schreiben in den Cache
            try:
                sub_dir.mkdir(parents=True, exist_ok=True)
                tmp_file = sub_dir / f"{cache_key}.tmp_{os.getpid()}"
                tmp_file.write_bytes(tile_bytes)
                tmp_file.replace(cache_file)
            except Exception as cache_err:
                logger.debug("Fehler beim Cachen der IIIF-Kachel: %s", cache_err)

            return tile_bytes, media_type

        except HTTPException:
            raise
        except Exception as e:
            logger.error("Fehler beim Generieren der IIIF-Kachel: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Fehler bei Kachelerstellung: {e}")

    def _apply_region(self, img: Image.Image, region: str, orig_w: int, orig_h: int) -> Image.Image:
        """Schneidet den gewünschten IIIF-Bildausschnitt zu."""
        reg = region.strip().lower()
        if reg in ["full", ""]:
            return img

        if reg == "square":
            dim = min(orig_w, orig_h)
            x1 = (orig_w - dim) // 2
            y1 = (orig_h - dim) // 2
            return img.crop((x1, y1, x1 + dim, y1 + dim))

        if reg.startswith("pct:"):
            parts = [float(p) for p in reg[4:].split(",")]
            if len(parts) != 4:
                raise HTTPException(status_code=400, detail=f"Ungültige pct-Region: {region}")
            x = int(round(parts[0] * orig_w / 100.0))
            y = int(round(parts[1] * orig_h / 100.0))
            w = int(round(parts[2] * orig_w / 100.0))
            h = int(round(parts[3] * orig_h / 100.0))
        else:
            parts = [float(p) for p in reg.split(",")]
            if len(parts) != 4:
                raise HTTPException(status_code=400, detail=f"Ungültige Region: {region}")
            x, y, w, h = int(round(parts[0])), int(round(parts[1])), int(round(parts[2])), int(round(parts[3]))

        if w <= 0 or h <= 0:
            raise HTTPException(status_code=400, detail="Regionsbreite und -höhe müssen positiv sein.")

        x1 = max(0, min(orig_w, x))
        y1 = max(0, min(orig_h, y))
        x2 = max(0, min(orig_w, x + w))
        y2 = max(0, min(orig_h, y + h))

        if x2 <= x1 or y2 <= y1:
            raise HTTPException(status_code=400, detail="Region liegt außerhalb des Bildes.")

        return img.crop((x1, y1, x2, y2))

    def _apply_size(self, img: Image.Image, size_str: str) -> Image.Image:
        """Skaliert den Ausschnitt nach IIIF Image API 3.0 Spezifikation."""
        s = size_str.strip().lower()
        if s.startswith("^"):
            s = s[1:]  # Upscaling-Erlaubnis-Präfix

        if s in ["max", "full", ""]:
            return img

        curr_w, curr_h = img.size

        if s.startswith("pct:"):
            pct = float(s[4:])
            if pct <= 0:
                raise HTTPException(status_code=400, detail="Ungültiger Prozentsatz.")
            target_w = max(1, int(round(curr_w * (pct / 100.0))))
            target_h = max(1, int(round(curr_h * (pct / 100.0))))
            return img.resize((target_w, target_h), Image.Resampling.LANCZOS)

        if s.endswith(","):
            target_w = int(s[:-1])
            if target_w <= 0:
                raise HTTPException(status_code=400, detail="Ungültige Breite.")
            target_h = max(1, int(round(curr_h * (target_w / curr_w))))
            return img.resize((target_w, target_h), Image.Resampling.LANCZOS)

        if s.startswith(","):
            target_h = int(s[1:])
            if target_h <= 0:
                raise HTTPException(status_code=400, detail="Ungültige Höhe.")
            target_w = max(1, int(round(curr_w * (target_h / curr_h))))
            return img.resize((target_w, target_h), Image.Resampling.LANCZOS)

        best_fit = False
        if s.startswith("!"):
            best_fit = True
            s = s[1:]

        if "," in s:
            w_str, h_str = s.split(",")
            req_w, req_h = int(w_str), int(h_str)
            if best_fit:
                # Skaliert so, dass das Bild in (req_w, req_h) hineinpasst
                scale = min(req_w / curr_w, req_h / curr_h)
                target_w = max(1, int(round(curr_w * scale)))
                target_h = max(1, int(round(curr_h * scale)))
            else:
                target_w, target_h = req_w, req_h
            return img.resize((target_w, target_h), Image.Resampling.LANCZOS)

        return img

    def _apply_rotation(self, img: Image.Image, rotation_str: str) -> Image.Image:
        """Rotiert und spiegelt das Bild nach IIIF-Vorgabe."""
        r = rotation_str.strip()
        mirror = False
        if r.startswith("!"):
            mirror = True
            r = r[1:]

        try:
            deg = float(r)
        except ValueError:
            deg = 0.0

        if mirror:
            img = ImageOps.mirror(img)

        # IIIF definiert Drehung im Uhrzeigersinn (+deg) -> Pillow dreht gegen Uhrzeigersinn (-deg)
        if deg % 360 != 0:
            img = img.rotate(-deg, expand=True)

        return img

    def _apply_quality(self, img: Image.Image, quality_str: str) -> Image.Image:
        """Konvertiert den Farbraum gemäß IIIF-Quality-Parameter."""
        q = quality_str.strip().lower()
        if q in ["default", "color", ""]:
            return img
        if q == "gray":
            return img.convert("L")
        if q == "bitonal":
            return img.convert("1")
        return img


# Globale Instanz des IIIF-Services
iiif_service = IIIFService()
