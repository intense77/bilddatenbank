import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional
from PIL import Image, ExifTags, IptcImagePlugin

logger = logging.getLogger(__name__)


def _sanitize_for_json(val: Any) -> Any:
    """Wandelt Bytes, Tupel und nicht-JSON-serialisierbare Werte in saubere Strings/Listen um."""
    if isinstance(val, (bytes, bytearray)):
        try:
            return val.decode("utf-8", errors="replace").strip("\x00").strip()
        except Exception:
            return str(val)
    elif isinstance(val, tuple):
        return [_sanitize_for_json(v) for v in val]
    elif isinstance(val, dict):
        return {str(k): _sanitize_for_json(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [_sanitize_for_json(v) for v in val]
    return val


class MetadataService:
    """
    Extraktionsdienst für archivische Metadaten aus:
    - EXIF & TIFF Header (Datierung, Urheber, Signatur, Beschreibung)
    - IPTC Core (Titel, Autor, Rechte, Schlagwörter)
    - XMP (Dublin Core)
    - JSON-Sidecar-Dateien (z. B. bild.tif -> bild.json)
    """

    def extract_exif(self, img: Image.Image) -> Dict[str, Any]:
        """Extrahiert EXIF- und TIFF-Header-Tags."""
        exif_data: Dict[str, Any] = {}
        try:
            # getexif() liefert moderne Exif-Struktur für JPEG, TIFF, WebP, PNG
            raw_exif = img.getexif()
            if not raw_exif:
                return {}

            for tag_id, value in raw_exif.items():
                tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                clean_val = _sanitize_for_json(value)
                if clean_val:
                    exif_data[tag_name] = clean_val

            # Untergeordnete Exif-IFD (z. B. DateTimeOriginal)
            if hasattr(ExifTags, "IFD") and hasattr(raw_exif, "get_ifd"):
                for ifd_enum in (ExifTags.IFD.Exif, ExifTags.IFD.GPSInfo):
                    try:
                        ifd_data = raw_exif.get_ifd(ifd_enum)
                        for tag_id, value in ifd_data.items():
                            tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                            clean_val = _sanitize_for_json(value)
                            if clean_val and tag_name not in exif_data:
                                exif_data[tag_name] = clean_val
                    except Exception:
                        pass

        except Exception as e:
            logger.debug("Keine EXIF-Daten extrahierbar: %s", e)

        return exif_data

    def extract_iptc(self, img: Image.Image) -> Dict[str, Any]:
        """Extrahiert IPTC Core Metadaten (Photoshop/IPTC Block)."""
        iptc_data: Dict[str, Any] = {}
        try:
            iptc_dict = IptcImagePlugin.getiptcinfo(img)
            if not iptc_dict:
                return {}

            # Bekannte IPTC Dataset-IDs
            iptc_mapping = {
                (2, 5): "object_name",        # Titel
                (2, 105): "headline",         # Überschrift
                (2, 120): "caption",          # Beschreibung / Abstract
                (2, 80): "byline",            # Urheber / Fotograf
                (2, 116): "copyright_notice", # Urheberrecht
                (2, 110): "credit",           # Nachweis / Institution
                (2, 115): "source",           # Quelle / Herkunft
                (2, 25): "keywords",          # Schlagwörter
                (2, 55): "date_created",      # Erstellungsdatum
            }

            for dataset_id, field_name in iptc_mapping.items():
                if dataset_id in iptc_dict:
                    val = _sanitize_for_json(iptc_dict[dataset_id])
                    if val:
                        iptc_data[field_name] = val

        except Exception as e:
            logger.debug("Keine IPTC-Daten extrahierbar: %s", e)

        return iptc_data

    def extract_xmp(self, img: Image.Image) -> Dict[str, Any]:
        """Extrahiert Dublin-Core-Felder aus eingebetteten XMP-XML-Blöcken."""
        xmp_data: Dict[str, Any] = {}
        xmp_raw = img.info.get("xmp") or img.info.get("XML:com.adobe.xmp")
        if not xmp_raw:
            return {}

        try:
            if isinstance(xmp_raw, (bytes, bytearray)):
                xmp_str = xmp_raw.decode("utf-8", errors="replace")
            else:
                xmp_str = str(xmp_raw)

            # ElementTree XML Parsing
            root = ET.fromstring(xmp_str)
            # Namensräume durchsuchen (Dublin Core: http://purl.org/dc/elements/1.1/)
            namespaces = {
                "dc": "http://purl.org/dc/elements/1.1/",
            }

            for elem in root.iter():
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                text = elem.text.strip() if elem.text else None
                if text and tag in {"title", "creator", "description", "date", "rights", "subject"}:
                    xmp_data[f"dc_{tag}"] = text

        except Exception as e:
            logger.debug("Keine XMP-Daten parsebar: %s", e)

        return xmp_data

    def extract_sidecar(self, file_path: Path) -> Dict[str, Any]:
        """
        Sucht nach Begleitdateien im gleichen Verzeichnis:
        - datei.json (z. B. bild_001.json für bild_001.tif)
        - datei.ext.json (z. B. bild_001.tif.json)
        """
        candidates = [
            file_path.with_suffix(".json"),
            file_path.with_name(f"{file_path.name}.json"),
        ]

        for sidecar_path in candidates:
            if sidecar_path.is_file():
                try:
                    with open(sidecar_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            logger.info("Sidecar-Metadaten geladen aus: %s", sidecar_path.name)
                            return data
                except Exception as e:
                    logger.warning("Fehler beim Lesen der Sidecar-Datei '%s': %s", sidecar_path, e)

        return {}

    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Konsolidierte archivische Metadaten-Extraktion.
        Führt EXIF, IPTC, XMP und JSON-Sidecars zusammen zu einem standardisierten Schema:
        - title: Bildtitel / Objektbezeichnung
        - creator: Urheber / Fotograf / Künstler
        - date: Entstehungsdatum / Datierung
        - description: Beschreibung / Inhalt
        - signature: Archivsignatur / Inventarnummer
        - copyright: Lizenz / Rechteinhaber
        - keywords: Liste an Schlagwörtern
        - sidecar_data: Rohe Sidecar-Zusatzfelder
        """
        title: Optional[str] = None
        creator: Optional[str] = None
        date: Optional[str] = None
        description: Optional[str] = None
        signature: Optional[str] = None
        copyright_notice: Optional[str] = None
        keywords: List[str] = []

        # 1. Bildheader auslesen (EXIF, IPTC, XMP)
        try:
            with Image.open(file_path) as img:
                exif = self.extract_exif(img)
                iptc = self.extract_iptc(img)
                xmp = self.extract_xmp(img)

                # Datum ermitteln
                date = (
                    exif.get("DateTimeOriginal")
                    or exif.get("DateTime")
                    or iptc.get("date_created")
                    or xmp.get("dc_date")
                )

                # Urheber / Autor
                creator = (
                    exif.get("Artist")
                    or iptc.get("byline")
                    or xmp.get("dc_creator")
                )

                # Titel
                title = (
                    iptc.get("object_name")
                    or iptc.get("headline")
                    or xmp.get("dc_title")
                    or exif.get("DocumentName")
                )

                # Beschreibung
                description = (
                    exif.get("ImageDescription")
                    or exif.get("UserComment")
                    or iptc.get("caption")
                    or xmp.get("dc_description")
                )

                # Signatur / Inventarnummer
                signature = exif.get("ImageID") or exif.get("DocumentName")

                # Copyright
                copyright_notice = (
                    exif.get("Copyright")
                    or iptc.get("copyright_notice")
                    or xmp.get("dc_rights")
                )

                # Schlagwörter
                kw = iptc.get("keywords")
                if kw:
                    if isinstance(kw, list):
                        keywords.extend([str(k) for k in kw])
                    else:
                        keywords.append(str(kw))

        except Exception as e:
            logger.debug("Header-Metadaten konnten für '%s' nicht gelesen werden: %s", file_path, e)

        # 2. Sidecar JSON auslesen (hat Vorrang bzw. reichert an)
        sidecar = self.extract_sidecar(file_path)
        if sidecar:
            title = sidecar.get("title") or sidecar.get("titel") or title
            creator = sidecar.get("creator") or sidecar.get("urheber") or sidecar.get("fotograf") or creator
            date = sidecar.get("date") or sidecar.get("datum") or sidecar.get("datierung") or date
            description = sidecar.get("description") or sidecar.get("beschreibung") or description
            signature = sidecar.get("signature") or sidecar.get("signatur") or sidecar.get("inventarnummer") or signature
            copyright_notice = sidecar.get("copyright") or sidecar.get("lizenz") or copyright_notice
            sidecar_tags = sidecar.get("keywords") or sidecar.get("tags") or sidecar.get("schlagwoerter")
            if sidecar_tags:
                if isinstance(sidecar_tags, list):
                    keywords.extend([str(t) for t in sidecar_tags])
                elif isinstance(sidecar_tags, str):
                    keywords.extend([t.strip() for t in sidecar_tags.split(",")])

        # Bereinigte Liste an eindeutigen Schlagwörtern
        unique_keywords = sorted(list({k.strip() for k in keywords if k and k.strip()}))

        return {
            "title": str(title).strip() if title else None,
            "creator": str(creator).strip() if creator else None,
            "date": str(date).strip() if date else None,
            "description": str(description).strip() if description else None,
            "signature": str(signature).strip() if signature else None,
            "copyright": str(copyright_notice).strip() if copyright_notice else None,
            "keywords": unique_keywords,
        }


metadata_service = MetadataService()
