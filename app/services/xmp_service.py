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
from typing import Any, Dict, List, Optional, Tuple, Union
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
ET.register_namespace("mwg-rs", "http://www.metadataworkinggroup.com/schemas/regions/")
ET.register_namespace("stDim", "http://ns.adobe.com/xap/1.0/sType/Dimensions#")
ET.register_namespace("stArea", "http://ns.adobe.com/xmp/sType/Area#")


class XmpService:

    def __init__(self, mirror_dir: Optional[Path] = None):
        self.mirror_dir = mirror_dir or DEFAULT_XMP_MIRROR_DIR

    def get_image_regions(
        self,
        image_path: Union[str, Path],
    ) -> Tuple[List[Dict[str, Any]], Optional[int], Optional[int]]:
        """
        Liest alle biometrisch detektierten Gesichts-Regionen und Bilddimensionen
        aus der Qdrant-Vektordatenbank aus.
        """
        try:
            from app.api.deps import get_qdrant_service
            from qdrant_client.http import models as rest_models
            qdrant = get_qdrant_service()
            path_str = str(Path(image_path).resolve())
            records, _ = qdrant.client.scroll(
                collection_name=settings.COLLECTION_FACES,
                scroll_filter=rest_models.Filter(
                    should=[
                        rest_models.FieldCondition(key="file_path", match=rest_models.MatchValue(value=path_str)),
                        rest_models.FieldCondition(key="image_path", match=rest_models.MatchValue(value=path_str)),
                    ]
                ),
                limit=100,
                with_payload=True,
                with_vectors=False,
            )
            regions: List[Dict[str, Any]] = []
            img_w = None
            img_h = None
            for r in records:
                p = r.payload or {}
                if not img_w:
                    img_w = p.get("orig_width")
                if not img_h:
                    img_h = p.get("orig_height")
                label = p.get("label")
                cur_status = p.get("curation_status") or ("VERIFIED" if label else "KI_AUTO")
                regions.append({
                    "name": label or "",
                    "type": "Face",
                    "bbox": p.get("bbox"),
                    "bbox_percent": p.get("bbox_percent"),
                    "orig_width": p.get("orig_width"),
                    "orig_height": p.get("orig_height"),
                    "curation_status": cur_status,
                })
            return regions, img_w, img_h
        except Exception as e:
            logger.debug("Konnte Regionen für %s nicht abrufen: %s", image_path, e)
            return [], None, None

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
        iconclass: Optional[str] = None,
        regions: Optional[List[Dict[str, Any]]] = None,
        image_width: Optional[int] = None,
        image_height: Optional[int] = None,
    ) -> str:
        """
        Erzeugt einen standardkonformen Adobe XMP (RDF/XML) Metadaten-String.
        Unterstützt Dublin Core (dc), Photoshop, IPTC Extension (PersonInImage),
        Metadata Working Group (MWG) Regionen (mwg-rs:Regions) und Iconclass-Notationen.
        """
        p = Path(file_path)
        persons_list = [p.strip() for p in (persons or []) if p and p.strip()]
        kw_list = [k.strip() for k in (keywords or []) if k and k.strip()]

        # Falls keine Regionen übergeben wurden: Automatisch aus Qdrant nachladen
        if regions is None:
            queried_regions, q_w, q_h = self.get_image_regions(file_path)
            regions = queried_regions
            if not image_width:
                image_width = q_w
            if not image_height:
                image_height = q_h

        # Regionen-Namen auch in persons_list übernehmen (Verhinderung von Redundanzen)
        for reg in (regions or []):
            reg_name = (reg.get("name") or "").strip()
            if reg_name and reg_name not in persons_list:
                persons_list.append(reg_name)

        # Iconclass Notation in Schlagworte einbetten
        if iconclass and iconclass.strip():
            ic_clean = iconclass.strip()
            ic_tag = f"Iconclass: {ic_clean}"
            if ic_tag not in kw_list:
                kw_list.append(ic_tag)

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

        # 8. Metadata Working Group (MWG) Regions (mwg-rs:Regions)
        if regions:
            mwg_regions = ET.SubElement(desc, "{http://www.metadataworkinggroup.com/schemas/regions/}Regions")
            mwg_regions.set("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}parseType", "Resource")

            eff_w = image_width
            eff_h = image_height
            if (not eff_w or not eff_h) and regions:
                eff_w = regions[0].get("orig_width")
                eff_h = regions[0].get("orig_height")

            if eff_w and eff_h:
                applied_dim = ET.SubElement(mwg_regions, "{http://www.metadataworkinggroup.com/schemas/regions/}AppliedToDimensions")
                applied_dim.set("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}parseType", "Resource")
                dim_w = ET.SubElement(applied_dim, "{http://ns.adobe.com/xap/1.0/sType/Dimensions#}w")
                dim_w.text = str(eff_w)
                dim_h = ET.SubElement(applied_dim, "{http://ns.adobe.com/xap/1.0/sType/Dimensions#}h")
                dim_h.text = str(eff_h)
                dim_unit = ET.SubElement(applied_dim, "{http://ns.adobe.com/xap/1.0/sType/Dimensions#}unit")
                dim_unit.text = "pixel"

            reg_list = ET.SubElement(mwg_regions, "{http://www.metadataworkinggroup.com/schemas/regions/}RegionList")
            bag = ET.SubElement(reg_list, "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Bag")

            for reg in regions:
                name = (reg.get("name") or "").strip()
                reg_type = reg.get("type") or "Face"
                status = reg.get("curation_status") or ("VERIFIED" if name else "KI_AUTO")

                # Bounding-Box Berechnung in normalisierte MWG-Koordinaten (0.0 .. 1.0)
                # stArea:x = Zentrum X, stArea:y = Zentrum Y, stArea:w = Breite, stArea:h = Höhe
                norm_x = None
                norm_y = None
                norm_w = None
                norm_h = None

                bbox_pct = reg.get("bbox_percent")
                if bbox_pct and "left" in bbox_pct and "top" in bbox_pct and "width" in bbox_pct and "height" in bbox_pct:
                    l = float(bbox_pct["left"]) / 100.0
                    t = float(bbox_pct["top"]) / 100.0
                    w = float(bbox_pct["width"]) / 100.0
                    h = float(bbox_pct["height"]) / 100.0
                    norm_x = round(l + (w / 2.0), 6)
                    norm_y = round(t + (h / 2.0), 6)
                    norm_w = round(w, 6)
                    norm_h = round(h, 6)
                elif reg.get("bbox") and len(reg["bbox"]) == 4:
                    x1, y1, x2, y2 = reg["bbox"]
                    img_w_ref = reg.get("orig_width") or eff_w
                    img_h_ref = reg.get("orig_height") or eff_h
                    if img_w_ref and img_h_ref and img_w_ref > 0 and img_h_ref > 0:
                        w = float(x2 - x1) / float(img_w_ref)
                        h = float(y2 - y1) / float(img_h_ref)
                        norm_x = round((float(x1 + x2) / 2.0) / float(img_w_ref), 6)
                        norm_y = round((float(y1 + y2) / 2.0) / float(img_h_ref), 6)
                        norm_w = round(w, 6)
                        norm_h = round(h, 6)

                if norm_x is not None and norm_y is not None and norm_w is not None and norm_h is not None:
                    li = ET.SubElement(bag, "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}li")
                    li.set("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}parseType", "Resource")

                    if name:
                        r_name = ET.SubElement(li, "{http://www.metadataworkinggroup.com/schemas/regions/}Name")
                        r_name.text = name

                    r_type = ET.SubElement(li, "{http://www.metadataworkinggroup.com/schemas/regions/}Type")
                    r_type.text = reg_type

                    r_desc = ET.SubElement(li, "{http://www.metadataworkinggroup.com/schemas/regions/}Description")
                    r_desc.text = status  # 'VERIFIED' oder 'KI_AUTO'

                    area = ET.SubElement(li, "{http://www.metadataworkinggroup.com/schemas/regions/}Area")
                    area.set("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}parseType", "Resource")

                    ax = ET.SubElement(area, "{http://ns.adobe.com/xmp/sType/Area#}x")
                    ax.text = f"{norm_x:.6f}"
                    ay = ET.SubElement(area, "{http://ns.adobe.com/xmp/sType/Area#}y")
                    ay.text = f"{norm_y:.6f}"
                    aw = ET.SubElement(area, "{http://ns.adobe.com/xmp/sType/Area#}w")
                    aw.text = f"{norm_w:.6f}"
                    ah = ET.SubElement(area, "{http://ns.adobe.com/xmp/sType/Area#}h")
                    ah.text = f"{norm_h:.6f}"
                    aunit = ET.SubElement(area, "{http://ns.adobe.com/xmp/sType/Area#}unit")
                    aunit.text = "normalized"

        # 9. xmp:MetadataDate
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
        iconclass: Optional[str] = None,
        regions: Optional[List[Dict[str, Any]]] = None,
        image_width: Optional[int] = None,
        image_height: Optional[int] = None,
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
            iconclass=iconclass,
            regions=regions,
            image_width=image_width,
            image_height=image_height,
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
