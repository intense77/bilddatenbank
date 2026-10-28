"""
EAD3 & LIDO Export Service für das Historische Bildarchiv.
Erzeugt standardkonforme XML-Daten für:
1. EAD3 (Encoded Archival Description) nach ISAD(G) für Archivportale (Archivportal-D, Bundesarchiv)
   und Archivinformationssysteme (ACTApro, ScopeArchiv, Augias, Faust).
2. LIDO 1.1 (Lightweight Information Describing Objects) für Museen, Sammlungen,
   die Deutsche Digitale Bibliothek (DDB) und Europeana.
100% lokal, offline-fähig und ohne externe Abhängigkeiten über xml.etree.ElementTree.
"""

import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from xml.dom import minidom


def _indent_xml(elem: ET.Element) -> str:
    """Erzeugt sauber formatiertes, eingerücktes XML mit XML-Deklaration."""
    rough_string = ET.tostring(elem, encoding="utf-8")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")


class EadLidoService:
    """Dienst zur Generierung standardkonformer EAD3- und LIDO-1.1-XML-Metadatenpakete."""

    def generate_ead3(
        self,
        items: List[Dict[str, Any]],
        archive_name: str = "Historisches Archiv",
        collection_title: str = "Archivischer Bildbestand",
    ) -> bytes:
        """
        Erzeugt valides EAD3-XML nach archivischem ISAD(G)-Standard.
        """
        now_str = datetime.now().strftime("%Y-%m-%d")
        now_dt = datetime.now().strftime("%Y%m%d_%H%M%S")

        # EAD3 Root-Element
        ead = ET.Element(
            "ead",
            {
                "xmlns": "http://ead3.archivists.org/schema/",
                "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
                "xsi:schemaLocation": "http://ead3.archivists.org/schema/ http://ead3.archivists.org/schema/ead3.xsd",
            },
        )

        # <control> Bereich
        control = ET.SubElement(ead, "control")
        recordid = ET.SubElement(control, "recordid", {"instanceurl": f"urn:archive:findbuch:{now_dt}"})
        recordid.text = f"findbuch_{now_dt}"

        filedesc = ET.SubElement(control, "filedesc")
        titlestmt = ET.SubElement(filedesc, "titlestmt")
        titleproper = ET.SubElement(titlestmt, "titleproper")
        titleproper.text = f"Findbuch: {collection_title}"
        author = ET.SubElement(titlestmt, "author")
        author.text = f"{archive_name} (Elektronisch generiert)"

        publicationstmt = ET.SubElement(filedesc, "publicationstmt")
        publisher = ET.SubElement(publicationstmt, "publisher")
        publisher.text = archive_name
        date_pub = ET.SubElement(publicationstmt, "date")
        date_pub.text = now_str

        maintenancestatus = ET.SubElement(control, "maintenancestatus", {"value": "derived"})
        maintenanceagency = ET.SubElement(control, "maintenanceagency")
        agencyname = ET.SubElement(maintenanceagency, "agencyname")
        agencyname.text = archive_name

        # <archdesc> Bereich (Bestandsbeschreibung nach ISAD(G))
        archdesc = ET.SubElement(ead, "archdesc", {"level": "collection"})
        did_top = ET.SubElement(archdesc, "did")
        unitid_top = ET.SubElement(did_top, "unitid")
        unitid_top.text = f"BESTAND-{now_dt[:8]}"
        unittitle_top = ET.SubElement(did_top, "unittitle")
        unittitle_top.text = collection_title
        unitdate_top = ET.SubElement(did_top, "unitdate")
        unitdate_top.text = now_str
        repository = ET.SubElement(did_top, "repository")
        corpname = ET.SubElement(repository, "corpname")
        corpname.text = archive_name

        scopecontent_top = ET.SubElement(archdesc, "scopecontent")
        p_top = ET.SubElement(scopecontent_top, "p")
        p_top.text = f"Verzeichnis von {len(items)} digital erschlossenen Bilddokumenten und Master-Scans."

        # <dsc> Bestandsklassifikation und Verzeichnungseinheiten
        dsc = ET.SubElement(archdesc, "dsc", {"dsctype": "combined"})

        for idx, it in enumerate(items, start=1):
            c01 = ET.SubElement(dsc, "c01", {"level": "item", "id": f"item_{idx:04d}"})
            did = ET.SubElement(c01, "did")

            # Signatur
            unitid = ET.SubElement(did, "unitid", {"label": "Archivsignatur"})
            unitid.text = it.get("signature") or f"POS-{idx:04d}"

            # Titel
            unittitle = ET.SubElement(did, "unittitle")
            unittitle.text = it.get("title") or it.get("file_name") or f"Fotodokument {idx}"

            # Datierung
            if it.get("date"):
                unitdate = ET.SubElement(did, "unitdate")
                unitdate.text = str(it.get("date"))

            # Urheber / Fotograf
            if it.get("creator"):
                origination = ET.SubElement(did, "origination", {"label": "Fotograf / Urheber"})
                persname = ET.SubElement(origination, "persname", {"role": "photographer"})
                persname.text = str(it.get("creator"))

            # Physische Beschaffenheit
            physdesc = ET.SubElement(did, "physdesc")
            physfacet = ET.SubElement(physdesc, "physfacet")
            physfacet.text = "Digitalisat / Master-Scan"

            # Digitales Archiv-Objekt (DAO)
            if it.get("file_path"):
                daoset = ET.SubElement(did, "daoset")
                dao = ET.SubElement(
                    daoset,
                    "dao",
                    {
                        "daotype": "derived",
                        "href": str(it.get("file_path")),
                    },
                )
                descriptivenote = ET.SubElement(dao, "descriptivenote")
                p_dao = ET.SubElement(descriptivenote, "p")
                p_dao.text = it.get("file_name") or Path(str(it.get("file_path"))).name

            # Notizen & Transkriptionen
            if it.get("notes"):
                scopecontent = ET.SubElement(c01, "scopecontent")
                p_notes = ET.SubElement(scopecontent, "p")
                p_notes.text = str(it.get("notes"))

            # Dargestellte Personen (Indexeinträge / Normdatei-Ansätze)
            persons = it.get("persons") or []
            if persons:
                controlaccess = ET.SubElement(c01, "controlaccess")
                for p_name in persons:
                    pers_elem = ET.SubElement(controlaccess, "persname", {"relator": "dep"})
                    pers_elem.text = str(p_name)

        xml_string = _indent_xml(ead)
        return xml_string.encode("utf-8")

    def generate_lido(
        self,
        items: List[Dict[str, Any]],
        archive_name: str = "Historisches Archiv",
        collection_title: str = "Archivischer Bildbestand",
    ) -> bytes:
        """
        Erzeugt valides LIDO 1.1 XML für Museen, Sammlungen, DDB und Europeana.
        """
        now_str = datetime.now().strftime("%Y-%m-%d")

        # LIDO Root
        lido_wrap = ET.Element(
            "lido:lidoWrap",
            {
                "xmlns:lido": "http://www.lido-schema.org",
                "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
                "xsi:schemaLocation": "http://www.lido-schema.org http://www.lido-schema.org/schema/v1.1/lido-v1.1.xsd",
            },
        )

        for idx, it in enumerate(items, start=1):
            lido = ET.SubElement(lido_wrap, "lido:lido")

            # Eindeutige LIDO-ID
            rec_id = it.get("signature") or it.get("file_name") or f"obj_{idx:04d}"
            lido_rec_id = ET.SubElement(lido, "lido:lidoRecID", {"lido:source": archive_name, "lido:type": "local"})
            lido_rec_id.text = rec_id

            # 1. Deskriptive Metadaten
            desc_meta = ET.SubElement(lido, "lido:descriptiveMetadata", {"xml:lang": "de"})

            # Objektklassifikation
            obj_class_wrap = ET.SubElement(desc_meta, "lido:objectClassificationWrap")
            obj_work_type_wrap = ET.SubElement(obj_class_wrap, "lido:objectWorkTypeWrap")
            obj_work_type = ET.SubElement(obj_work_type_wrap, "lido:objectWorkType")
            term_work_type = ET.SubElement(obj_work_type, "lido:term")
            term_work_type.text = "Fotografie"

            # Objektidentifikation
            obj_ident_wrap = ET.SubElement(desc_meta, "lido:objectIdentificationWrap")

            # Titel
            title_wrap = ET.SubElement(obj_ident_wrap, "lido:titleWrap")
            title_set = ET.SubElement(title_wrap, "lido:titleSet")
            app_val = ET.SubElement(title_set, "lido:appellationValue")
            app_val.text = it.get("title") or it.get("file_name") or f"Fotodokument {idx}"

            # Aufbewahrungsort / Signatur
            repo_wrap = ET.SubElement(obj_ident_wrap, "lido:repositoryWrap")
            repo_set = ET.SubElement(repo_wrap, "lido:repositorySet")
            repo_name = ET.SubElement(repo_set, "lido:repositoryName")
            legal_body = ET.SubElement(repo_name, "lido:legalBodyName")
            legal_val = ET.SubElement(legal_body, "lido:appellationValue")
            legal_val.text = archive_name

            if it.get("signature"):
                work_id = ET.SubElement(repo_set, "lido:workID", {"lido:type": "Archivsignatur"})
                work_id.text = str(it.get("signature"))

            # Archivalische Notizen / Rückseite
            if it.get("notes"):
                disp_state_wrap = ET.SubElement(obj_ident_wrap, "lido:displayStateEditionWrap")
                disp_state = ET.SubElement(disp_state_wrap, "lido:displayState")
                disp_state.text = str(it.get("notes"))

            # Ereignisse (Entstehung / Aufnahme)
            event_wrap = ET.SubElement(desc_meta, "lido:eventWrap")
            event_set = ET.SubElement(event_wrap, "lido:eventSet")
            event = ET.SubElement(event_set, "lido:event")
            event_type = ET.SubElement(event, "lido:eventType")
            term_event = ET.SubElement(event_type, "lido:term")
            term_event.text = "Herstellung / Aufnahme"

            if it.get("creator"):
                event_actor = ET.SubElement(event, "lido:eventActor")
                actor_in_role = ET.SubElement(event_actor, "lido:actorInRole")
                actor = ET.SubElement(actor_in_role, "lido:actor")
                actor_set = ET.SubElement(actor, "lido:nameActorSet")
                app_actor = ET.SubElement(actor_set, "lido:appellationValue")
                app_actor.text = str(it.get("creator"))
                role_actor = ET.SubElement(actor_in_role, "lido:roleActor")
                term_role = ET.SubElement(role_actor, "lido:term")
                term_role.text = "Fotograf / Bildurheber"

            if it.get("date"):
                event_date = ET.SubElement(event, "lido:eventDate")
                disp_date = ET.SubElement(event_date, "lido:displayDate")
                disp_date.text = str(it.get("date"))

            # Dargestellte Personen (Sujet / Themenbezug)
            persons = it.get("persons") or []
            if persons:
                obj_rel_wrap = ET.SubElement(desc_meta, "lido:objectRelationWrap")
                subj_wrap = ET.SubElement(obj_rel_wrap, "lido:subjectWrap")
                for p_name in persons:
                    subj_set = ET.SubElement(subj_wrap, "lido:subjectSet")
                    subj = ET.SubElement(subj_set, "lido:subject")
                    subj_actor = ET.SubElement(subj, "lido:subjectActor")
                    actor_p = ET.SubElement(subj_actor, "lido:actor")
                    actor_p_set = ET.SubElement(actor_p, "lido:nameActorSet")
                    actor_p_val = ET.SubElement(actor_p_set, "lido:appellationValue")
                    actor_p_val.text = str(p_name)

            # 2. Administrative Metadaten (Rechte & Ressource / Master-Scan)
            admin_meta = ET.SubElement(lido, "lido:administrativeMetadata", {"xml:lang": "de"})
            rights_wrap = ET.SubElement(admin_meta, "lido:rightsWorkWrap")
            rights_set = ET.SubElement(rights_wrap, "lido:rightsSet")
            rights_type = ET.SubElement(rights_set, "lido:rightsType")
            term_rights = ET.SubElement(rights_type, "lido:term")
            term_rights.text = "Gemeinfrei / Bildbestand im kirchlichen Archiv"

            res_wrap = ET.SubElement(admin_meta, "lido:resourceWrap")
            res_set = ET.SubElement(res_wrap, "lido:resourceSet")
            res_rep = ET.SubElement(res_set, "lido:resourceRepresentation", {"lido:type": "Master-Digitalisat"})
            link_res = ET.SubElement(res_rep, "lido:linkResource")
            link_res.text = str(it.get("file_path") or it.get("file_name") or "")

        xml_string = _indent_xml(lido_wrap)
        return xml_string.encode("utf-8")


ead_lido_service = EadLidoService()
