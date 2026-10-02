"""
XMP Sidecar Service für das Historische Bildarchiv.
Erzeugt und verwaltet standardkonforme Adobe XMP / Dublin Core / IPTC Extension
Sidecar-Dateien (.xmp) für Archiv- und Museumssysteme (Lightroom, Photoshop, DigiCult, Faust).
Gewährleistet 100%ige Metadaten-Portabilität nach dem Prinzip 'Never touch the master!'.
"""

import io
import logging
import os
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from xml.dom import minidom

from app.core.config import settings
from app.core.security import validate_safe_image_path

logger = logging.getLogger("archive_app.xmp_service")

# Lokales Fallback-Verzeichnis für XMP-Dateien, falls Quellordner schreibgeschützt ist
DEFAULT_XMP_MIRROR_DIR = Path("data/xmp_sidecars")

# Registriere Standard-Namensräume für saubere Adobe-kompatible Tags
ET.register_namespace("x", "adobe:ns:meta/")
ET.register_namespace("rdf", "http://www.w3.org/1999/02/22-rdf-syntax-ns#")
ET.register_namespace("dc", "http://purl.org/dc/elements/1.1/")
ET.register_namespace("photoshop", "http://schemas.adobe.com/photoshop/1.0/")
ET.register_namespace("xmp", "http://ns.adobe.com/xap/1.0/")
ET.register_namespace("Iptc4xmpExt", "http://iptc.org/std/Iptc4xmpExt/2008-02-29/")


class XmpService:

    def __init__(self, mirror_dir: Optional[Path] = None):
        self.mirror_dir = mirror_dir or DEFAULT_XMP_MIRROR_DIR

    def generate_xmp_content(
        self,
        file_path: Union[str, Path],
        title: Optional[str] = None,
        description: Optional[str] = None,
        creator: Optional[str] = None,
        date: Optional[str] = None,
        signature: Optional[str] = None,
        persons: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
    ) -> str:
        """
        Erzeugt einen standardkonformen Adobe XMP (RDF/XML) Metadaten-String.
        Unterstützt Dublin Core (dc), Photoshop und IPTC Extension (PersonInImage).
        """
        p = Path(file_path)
        persons_list = [p.strip() for p in (persons or []) if p and p.strip()]
        kw_list = [k.strip() for k in (keywords or []) if k and k.strip()]
        
        # Dublin Core Subject vereint Personen und Schlagwörter
        all_subjects = list(dict.fromkeys(persons_list + kw_list))

        clean_title = (title or "").strip()
        clean_desc = (description or "").strip()
        clean_creator = (creator or "").strip()
        clean_date = (date or "").strip()
        clean_signature = (signature or "").strip()

        # XML-Root & Namespaces
        xmpmeta = ET.Element(
            "{adobe:ns:meta/}xmpmeta",
            attrib={
                "{adobe:ns:meta/}xmptk": f"Historisches Bildarchiv v{settings.VERSION} XMP Service",
            },
        )
        rdf = ET.SubElement(
            xmpmeta,
            "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF",
        )
        desc = ET.SubElement(
            rdf,
            "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description",
            attrib={
                "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about": "",
            },
        )

        # 1. dc:title (Alt mit x-default)
        if clean_title:
            dc_title = ET.SubElement(desc, "{http://purl.org/dc/elements/1.1/}title")
            alt = ET.SubElement(dc_title, "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Alt")
            li = ET.SubElement(alt, "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}li", attrib={"xml:lang": "x-default"})
            li.text = clean_title

        # 2. dc:description (Alt mit x-default)
        if clean_desc:
            dc_desc = ET.SubElement(desc, "{http://purl.org/dc/elements/1.1/}description")
            alt = ET.SubElement(dc_desc, "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Alt")
            li = ET.SubElement(alt, "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}li", attrib={"xml:lang": "x-default"})
            li.text = clean_desc

        # 3. dc:creator (Seq)
        if clean_creator:
            dc_creator = ET.SubElement(desc, "{http://purl.org/dc/elements/1.1/}creator")
            seq = ET.SubElement(dc_creator, "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Seq")
            li = ET.SubElement(seq, "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}li")
            li.text = clean_creator

        # 4. dc:date (Seq) & photoshop:DateCreated
        if clean_date:
            dc_date = ET.SubElement(desc, "{http://purl.org/dc/elements/1.1/}date")
            seq = ET.SubElement(dc_date, "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Seq")
            li = ET.SubElement(seq, "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}li")
            li.text = clean_date

            ps_date = ET.SubElement(desc, "{http://schemas.adobe.com/photoshop/1.0/}DateCreated")
            ps_date.text = clean_date

        # 5. dc:identifier (Archivsignatur)
        if clean_signature:
            dc_id = ET.SubElement(desc, "{http://purl.org/dc/elements/1.1/}identifier")
            dc_id.text = clean_signature
            ps_ref = ET.SubElement(desc, "{http://schemas.adobe.com/photoshop/1.0/}TransmissionReference")
            ps_ref.text = clean_signature

        # 6. dc:subject (Bag für alle Schlagworte und Personennamen)
        if all_subjects:
            dc_subject = ET.SubElement(desc, "{http://purl.org/dc/elements/1.1/}subject")
            bag = ET.SubElement(dc_subject, "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Bag")
            for subj in all_subjects:
                li = ET.SubElement(bag, "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}li")
                li.text = subj

        # 7. IPTC Extension Person in Image (Standard für Lightroom/DAMs)
        if persons_list:
            person_in_img = ET.SubElement(desc, "{http://iptc.org/std/Iptc4xmpExt/2008-02-29/}PersonInImage")
            bag = ET.SubElement(person_in_img, "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Bag")
            for person in persons_list:
                li = ET.SubElement(bag, "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}li")
                li.text = person

        # 8. xmp:MetadataDate
        now_iso = datetime.now().isoformat()
        meta_date = ET.SubElement(desc, "{http://ns.adobe.com/xap/1.0/}MetadataDate")
        meta_date.text = now_iso

        # XML-Formatierung mit minidom (lesbar eingerückt)
        raw_xml = ET.tostring(xmpmeta, encoding="utf-8")
        parsed = minidom.parseString(raw_xml)
        pretty_xml = parsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")

        # Bereinige redundante Leerzeilen von minidom
        lines = [line for line in pretty_xml.split("\n") if line.strip()]
        return "\n".join(lines) + "\n"

    def get_sidecar_path(self, image_path: Union[str, Path]) -> Path:
        """Ermittelt den Standardpfad für die .xmp Sidecar-Datei (neben dem Bild)."""
        p = Path(image_path)
        # Standard: dateiname.xmp oder dateiname.ext.xmp (Standard in Adobe Lightroom: dateiname.xmp)
        return p.with_suffix(".xmp")

    def write_sidecar(
        self,
        image_path: Union[str, Path],
        title: Optional[str] = None,
        description: Optional[str] = None,
        creator: Optional[str] = None,
        date: Optional[str] = None,
        signature: Optional[str] = None,
        persons: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        force_mirror: bool = False,
    ) -> Dict[str, Any]:
        """
        Schreibt die XMP-Sidecar-Datei.
        Versucht zunächst, die .xmp-Datei direkt neben das Originalbild zu legen.
        Falls das Verzeichnis schreibgeschützt ist oder force_mirror=True gesetzt ist,
        wird die Datei im lokalen Spiegelordner abgelegt.
        """
        validated_path = validate_safe_image_path(image_path)
        xmp_content = self.generate_xmp_content(
            file_path=validated_path,
            title=title,
            description=description,
            creator=creator,
            date=date,
            signature=signature,
            persons=persons,
            keywords=keywords,
        )

        target_path = self.get_sidecar_path(validated_path)
        written_location = "alongside_master"

        if not force_mirror:
            try:
                # Prüfe Schreibberechtigung im Ordner
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(xmp_content)
                logger.info("XMP-Sidecar erfolgreich neben Master gespeichert: %s", target_path)
                return {
                    "success": True,
                    "target_path": str(target_path),
                    "location": written_location,
                    "bytes": len(xmp_content.encode("utf-8")),
                }
            except (PermissionError, OSError) as e:
                logger.warning("Keine Schreibrechte neben Master (%s). Weiche auf Spiegelordner aus: %s", target_path, e)

        # Fallback: Lokaler Spiegelordner
        written_location = "mirror_directory"
        # Bilde relativen Pfad unter dem Spiegelordner nach
        rel_key = str(validated_path).lstrip("/").replace(":", "_").replace(",", "_")
        mirror_target = self.mirror_dir / Path(rel_key).with_suffix(".xmp")
        mirror_target.parent.mkdir(parents=True, exist_ok=True)

        with open(mirror_target, "w", encoding="utf-8") as f:
            f.write(xmp_content)

        logger.info("XMP-Sidecar im Spiegelordner gespeichert: %s", mirror_target)
        return {
            "success": True,
            "target_path": str(mirror_target),
            "location": written_location,
            "bytes": len(xmp_content.encode("utf-8")),
        }

    def generate_zip_export(self, items: List[Dict[str, Any]]) -> bytes:
        """
        Bündelt XMP-Sidecar-Dateien für eine Liste ausgewählter Bilder in ein ZIP-Archiv.
        Ideal für den schnellen Export des gesamten Leuchttischs oder eines Personen-Clusters.
        """
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            used_names = set()

            for item in items:
                fp = item.get("file_path", "")
                if not fp:
                    continue

                orig_name = item.get("file_name") or Path(fp).name
                base_name = Path(orig_name).stem
                xmp_name = f"{base_name}.xmp"

                # Verhindere Namenskonflikte im ZIP
                counter = 1
                while xmp_name in used_names:
                    xmp_name = f"{base_name}_{counter}.xmp"
                    counter += 1
                used_names.add(xmp_name)

                content = self.generate_xmp_content(
                    file_path=fp,
                    title=item.get("title"),
                    description=item.get("notes") or item.get("description"),
                    creator=item.get("creator"),
                    date=item.get("date"),
                    signature=item.get("signature"),
                    persons=item.get("persons") or [],
                    keywords=item.get("keywords") or [],
                )

                zf.writestr(xmp_name, content.encode("utf-8"))

        return zip_buffer.getvalue()


xmp_service = XmpService()
