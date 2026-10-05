"""
Zweiblatt-Service (Recto / Verso Logik) für historische Bestände.
Erkennt automatisch zusammengehörige Vorder- und Rückseiten-Scans anhand von
archivischen Benennungskonventionen, verknüpft Rückseiten-Notizen als Primär-Metadatum
des Vorderseiten-Fotos und unterstützt interaktive 3D-Karten-Flips.
"""

import os
import re
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from app.core.security import validate_safe_image_path
from app.services.metadata_db import metadata_db

logger = logging.getLogger("archive_app.recto_verso")

# Unterstützte Dateiendungen für Bildsuche
SUPPORTED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"]

# Regex-Muster für Recto (Vorderseite) und Verso (Rückseite)
# Erkennt: _r/_v, _recto/_verso, _vorderseite/_rueckseite, _vs/_rs, _front/_back, _a/_b, _01/_02, _1/_2
PAIR_PATTERNS = [
    # 1. Standardarchiv: _r / _v bzw. _recto / _verso
    (r"(?i)[-_](r|recto)$", r"(?i)[-_](v|verso)$", "r", "v"),
    (r"(?i)[-_](v|verso)$", r"(?i)[-_](r|recto)$", "v", "r"),
    # 2. Deutsch: _vorderseite / _rueckseite bzw. _vs / _rs
    (r"(?i)[-_](vorderseite|vs)$", r"(?i)[-_](rueckseite|rückseite|rs)$", "vorderseite", "rueckseite"),
    (r"(?i)[-_](rueckseite|rückseite|rs)$", r"(?i)[-_](vorderseite|vs)$", "rueckseite", "vorderseite"),
    # 3. Englisch: _front / _back
    (r"(?i)[-_]front$", r"(?i)[-_]back$", "front", "back"),
    (r"(?i)[-_]back$", r"(?i)[-_]front$", "back", "front"),
    # 4. Buchstaben: _a / _b
    (r"(?i)[-_]a$", r"(?i)[-_]b$", "a", "b"),
    (r"(?i)[-_]b$", r"(?i)[-_]a$", "b", "a"),
    # 5. Zweistellige Nummerierung: _01 / _02
    (r"(?i)[-_]01$", r"(?i)[-_]02$", "01", "02"),
    (r"(?i)[-_]02$", r"(?i)[-_]01$", "02", "01"),
    # 6. Einstellige Nummerierung am Ende: _1 / _2
    (r"(?i)[-_]1$", r"(?i)[-_]2$", "1", "2"),
    (r"(?i)[-_]2$", r"(?i)[-_]1$", "2", "1"),
]


class RectoVersoService:
    def __init__(self):
        pass

    def detect_relationship(self, file_path: Union[str, Path]) -> Optional[Dict[str, Any]]:
        """
        Prüft einen Dateinamen auf Zweiblatt-Muster (Recto/Verso) und sucht nach
        der entsprechenden Partner-Datei im selben Verzeichnis.
        """
        path = Path(file_path)
        stem = path.stem
        parent_dir = path.parent
        ext = path.suffix.lower()

        for match_regex, replace_regex, current_tag, target_tag in PAIR_PATTERNS:
            match = re.search(match_regex, stem)
            if match:
                # Basis-Stem ermitteln (ohne Suffix-Tag)
                base_stem = stem[:match.start()]
                delimiter = stem[match.start()]  # '_' oder '-'

                # Rolle bestimmen
                is_front = current_tag.lower() in ["r", "recto", "vorderseite", "vs", "front", "a", "01", "1"]
                role = "recto" if is_front else "verso"
                companion_role = "verso" if is_front else "recto"

                # Erwarteter Partner-Dateiname (z. B. Base + Delimiter + TargetTag)
                expected_companion_stem = f"{base_stem}{delimiter}{target_tag}"

                # Suche Partnerdatei im Elternverzeichnis (zuerst selbe Endung, dann alternative Endungen)
                companion_path = None
                same_ext_candidate = parent_dir / f"{expected_companion_stem}{ext}"
                if same_ext_candidate.is_file():
                    companion_path = same_ext_candidate
                else:
                    # Case-insensitive oder andere Bild-Endung prüfen
                    for candidate_ext in SUPPORTED_EXTENSIONS:
                        cand = parent_dir / f"{expected_companion_stem}{candidate_ext}"
                        if cand.is_file():
                            companion_path = cand
                            break

                return {
                    "is_two_sided": True,
                    "role": role,
                    "companion_role": companion_role,
                    "base_stem": base_stem,
                    "current_path": str(path.resolve()),
                    "current_name": path.name,
                    "companion_path": str(companion_path.resolve()) if companion_path else None,
                    "companion_name": companion_path.name if companion_path else f"{expected_companion_stem}{ext}",
                    "companion_exists": companion_path is not None,
                }

        return None

    def get_two_sided_info(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Liefert alle Zweiblatt-Informationen inklusive Metadaten und Notizen der Rückseite.
        """
        rel = self.detect_relationship(file_path)
        if not rel:
            return {
                "is_two_sided": False,
                "role": "single",
                "companion_exists": False,
            }

        # Primären Pfad (Recto) bestimmen, an dem die Notizen gebündelt werden
        recto_path = rel["current_path"] if rel["role"] == "recto" else rel["companion_path"]
        verso_path = rel["companion_path"] if rel["role"] == "recto" else rel["current_path"]

        # Notizen aus SQLite abrufen
        notes = None
        if recto_path:
            notes = metadata_db.get_verso_notes(recto_path)
        if not notes and verso_path:
            notes = metadata_db.get_verso_notes(verso_path)

        rel["verso_notes"] = notes or ""
        rel["recto_path"] = recto_path
        rel["verso_path"] = verso_path

        # URLs für Frontend-Auslieferung vorbereiten
        if rel["companion_path"]:
            from urllib.parse import quote
            rel["companion_serve_url"] = f"/images/serve?path={quote(rel['companion_path'])}&max_dim=1200"
            rel["companion_thumb_url"] = f"/images/serve?path={quote(rel['companion_path'])}&max_dim=400"
            rel["companion_raw_url"] = f"/images/serve?path={quote(rel['companion_path'])}"

        return rel

    def save_verso_notes(self, file_path: Union[str, Path], notes: str) -> bool:
        """
        Speichert handschriftliche Notizen / Transkriptionen der Rückseite in der Metadatenbank.
        Verknüpft die Notizen sowohl mit der Vorder- als auch der Rückseite.
        """
        path_str = str(Path(file_path).resolve())
        rel = self.detect_relationship(path_str)

        companion_p = rel.get("companion_path") if rel else None
        current_role = rel.get("role") if rel else None
        comp_role = rel.get("companion_role") if rel else None

        # Bei aktuellem Bild hinterlegen
        success = metadata_db.update_verso_notes(
            path_str, notes, companion_path=companion_p, sheet_role=current_role
        )
        # Bei Partner hinterlegen
        if companion_p:
            metadata_db.update_verso_notes(
                companion_p, notes, companion_path=path_str, sheet_role=comp_role
            )

        return success


# Globale Instanz
recto_verso_service = RectoVersoService()
