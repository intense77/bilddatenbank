"""
PREMIS 3.0 XML Export Service für das Historische Bildarchiv (ISO 14721 / OAIS-konform).

Preservation Metadata: Implementation Strategies (PREMIS) ist der internationale
De-facto-Standard zur Dokumentation der Langzeitarchivierung digitaler Kulturgüter,
Fixity-Prüfungen (Prüfsummen-Validierung), Bitstream-Erhaltung und Datenintegrität.
100% lokal, offline-fähig und ohne externe Abhängigkeiten über xml.etree.ElementTree.
"""

import hashlib
import mimetypes
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from xml.dom import minidom

from app.services.metadata_service import compute_file_sha256


def _indent_xml(elem: ET.Element) -> str:
    """Erzeugt sauber formatiertes, eingerücktes XML mit XML-Deklaration."""
    rough_string = ET.tostring(elem, encoding="utf-8")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")


class PremisService:
    """Generiert standardkonforme PREMIS 3.0 XML-Daten zur Langzeit-Bestandserhaltung."""

    PREMIS_NS = "http://www.loc.gov/premis/v3"
    XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

    def generate_premis(
        self,
        items: List[Dict[str, Any]],
        archive_name: str = "Historisches Archiv",
    ) -> bytes:
        """
        Erzeugt ein vollständiges PREMIS 3.0 XML-Dokument für eine Liste von Archivobjekten
        inklusive Object-, Event- und Agent-Entities nach ISO 14721 (OAIS).
        """
        ET.register_namespace("premis", self.PREMIS_NS)
        ET.register_namespace("xsi", self.XSI_NS)

        root = ET.Element(
            f"{{{self.PREMIS_NS}}}premis",
            {
                "version": "3.0",
                f"{{{self.XSI_NS}}}schemaLocation": (
                    f"{self.PREMIS_NS} https://www.loc.gov/standards/premis/v3/premis.xsd"
                ),
            },
        )

        agent_id = "agent-archive-fixity-daemon-v2"

        for item in items:
            file_path_str = str(item.get("file_path", ""))
            file_name = item.get("file_name") or Path(file_path_str).name
            sha256_hash = item.get("sha256")
            fixity_status = item.get("fixity_status") or "OK"
            last_check = item.get("last_fixity_check") or datetime.now().isoformat()
            title = item.get("title") or file_name

            path_obj = Path(file_path_str) if file_path_str else None
            file_size = 0
            if path_obj and path_obj.is_file():
                try:
                    file_size = path_obj.stat().st_size
                    if not sha256_hash:
                        sha256_hash = compute_file_sha256(path_obj)
                except Exception:
                    pass

            # 1. <premis:object xsi:type="premis:file">
            obj = ET.SubElement(
                root,
                f"{{{self.PREMIS_NS}}}object",
                {f"{{{self.XSI_NS}}}type": "premis:file"},
            )

            # Identifier
            obj_id = ET.SubElement(obj, f"{{{self.PREMIS_NS}}}objectIdentifier")
            obj_id_type = ET.SubElement(obj_id, f"{{{self.PREMIS_NS}}}objectIdentifierType")
            obj_id_type.text = "local-filepath"
            obj_id_val = ET.SubElement(obj_id, f"{{{self.PREMIS_NS}}}objectIdentifierValue")
            obj_id_val.text = file_path_str

            # Characteristics
            chars = ET.SubElement(obj, f"{{{self.PREMIS_NS}}}objectCharacteristics")
            comp_level = ET.SubElement(chars, f"{{{self.PREMIS_NS}}}compositionLevel")
            comp_level.text = "0"

            # Fixity
            if sha256_hash:
                fixity = ET.SubElement(chars, f"{{{self.PREMIS_NS}}}fixity")
                algo = ET.SubElement(fixity, f"{{{self.PREMIS_NS}}}messageDigestAlgorithm")
                algo.text = "SHA-256"
                digest = ET.SubElement(fixity, f"{{{self.PREMIS_NS}}}messageDigest")
                digest.text = sha256_hash
                originator = ET.SubElement(fixity, f"{{{self.PREMIS_NS}}}messageDigestOriginator")
                originator.text = "Archiv-Fixity-Daemon"

            if file_size > 0:
                size_elem = ET.SubElement(chars, f"{{{self.PREMIS_NS}}}size")
                size_elem.text = str(file_size)

            # Format
            mime_type, _ = mimetypes.guess_type(file_name)
            mime_str = mime_type or "image/jpeg"
            fmt = ET.SubElement(chars, f"{{{self.PREMIS_NS}}}format")
            fmt_des = ET.SubElement(fmt, f"{{{self.PREMIS_NS}}}formatDesignation")
            fmt_name = ET.SubElement(fmt_des, f"{{{self.PREMIS_NS}}}formatName")
            fmt_name.text = mime_str

            # Original Name & Storage
            orig_name = ET.SubElement(obj, f"{{{self.PREMIS_NS}}}originalName")
            orig_name.text = file_name

            storage = ET.SubElement(obj, f"{{{self.PREMIS_NS}}}storage")
            storage_loc = ET.SubElement(storage, f"{{{self.PREMIS_NS}}}contentLocation")
            storage_type = ET.SubElement(storage_loc, f"{{{self.PREMIS_NS}}}contentLocationType")
            storage_type.text = "filepath"
            storage_val = ET.SubElement(storage_loc, f"{{{self.PREMIS_NS}}}contentLocationValue")
            storage_val.text = file_path_str

            # 2. <premis:event> (Fixity Check Event)
            event = ET.SubElement(root, f"{{{self.PREMIS_NS}}}event")
            event_id = ET.SubElement(event, f"{{{self.PREMIS_NS}}}eventIdentifier")
            event_id_type = ET.SubElement(event_id, f"{{{self.PREMIS_NS}}}eventIdentifierType")
            event_id_type.text = "UUID"
            event_id_val = ET.SubElement(event_id, f"{{{self.PREMIS_NS}}}eventIdentifierValue")
            event_id_val.text = f"urn:uuid:{uuid.uuid4()}"

            event_type = ET.SubElement(event, f"{{{self.PREMIS_NS}}}eventType")
            event_type.text = "fixity check"

            event_dt = ET.SubElement(event, f"{{{self.PREMIS_NS}}}eventDateTime")
            event_dt.text = str(last_check)

            event_detail = ET.SubElement(event, f"{{{self.PREMIS_NS}}}eventDetailInformation")
            event_detail.text = (
                f"Kryptographische SHA-256 Bitstream-Validierung für {file_name} "
                f"(Integritätsprüfung gegen Bit-Rot nach ISO 14721 OAIS)"
            )

            outcome_info = ET.SubElement(event, f"{{{self.PREMIS_NS}}}eventOutcomeInformation")
            outcome = ET.SubElement(outcome_info, f"{{{self.PREMIS_NS}}}eventOutcome")
            outcome.text = fixity_status

            outcome_detail = ET.SubElement(outcome_info, f"{{{self.PREMIS_NS}}}eventOutcomeDetail")
            note = ET.SubElement(outcome_detail, f"{{{self.PREMIS_NS}}}eventOutcomeDetailNote")
            if fixity_status == "OK":
                note.text = "Prüfsumme verifiziert. Bitstream ist unversehrt und intakt."
            elif fixity_status == "CORRUPTED":
                note.text = "WARNUNG: Prüfsummen-Mismatch festgestellt. Bit-Rot oder Dateimanipulation erkannt!"
            elif fixity_status == "MISSING":
                note.text = "FEHLER: Datei existiert nicht mehr auf dem Primärspeicher."
            else:
                note.text = f"Status: {fixity_status}"

            # Verknüpfung zu Objekt & Agent
            link_obj = ET.SubElement(event, f"{{{self.PREMIS_NS}}}linkingObjectIdentifier")
            link_obj_type = ET.SubElement(link_obj, f"{{{self.PREMIS_NS}}}linkingObjectIdentifierType")
            link_obj_type.text = "local-filepath"
            link_obj_val = ET.SubElement(link_obj, f"{{{self.PREMIS_NS}}}linkingObjectIdentifierValue")
            link_obj_val.text = file_path_str

            link_agent = ET.SubElement(event, f"{{{self.PREMIS_NS}}}linkingAgentIdentifier")
            link_agent_type = ET.SubElement(link_agent, f"{{{self.PREMIS_NS}}}linkingAgentIdentifierType")
            link_agent_type.text = "local-id"
            link_agent_val = ET.SubElement(link_agent, f"{{{self.PREMIS_NS}}}linkingAgentIdentifierValue")
            link_agent_val.text = agent_id

        # 3. <premis:agent> (Software Agent)
        agent = ET.SubElement(root, f"{{{self.PREMIS_NS}}}agent")
        ag_id = ET.SubElement(agent, f"{{{self.PREMIS_NS}}}agentIdentifier")
        ag_id_type = ET.SubElement(ag_id, f"{{{self.PREMIS_NS}}}agentIdentifierType")
        ag_id_type.text = "local-id"
        ag_id_val = ET.SubElement(ag_id, f"{{{self.PREMIS_NS}}}agentIdentifierValue")
        ag_id_val.text = agent_id

        ag_name = ET.SubElement(agent, f"{{{self.PREMIS_NS}}}agentName")
        ag_name.text = f"{archive_name} - Fixity Preservation Daemon"

        ag_type = ET.SubElement(agent, f"{{{self.PREMIS_NS}}}agentType")
        ag_type.text = "software"

        ag_note = ET.SubElement(agent, f"{{{self.PREMIS_NS}}}agentNote")
        ag_note.text = "Autonomer Hintergrund-Prüfsummen- und Bitrot-Wächter (ISO 14721 OAIS)"

        xml_str = _indent_xml(root)
        return xml_str.encode("utf-8")

    def generate_premis_for_file(
        self,
        file_path: Union[str, Path],
        metadata: Optional[Dict[str, Any]] = None,
        archive_name: str = "Historisches Archiv",
    ) -> bytes:
        """Erzeugt ein PREMIS 3.0 XML für ein einzelnes Digitalisat."""
        p_str = str(file_path)
        item = dict(metadata or {})
        item["file_path"] = p_str
        if "file_name" not in item:
            item["file_name"] = Path(p_str).name
        return self.generate_premis([item], archive_name=archive_name)


premis_service = PremisService()
