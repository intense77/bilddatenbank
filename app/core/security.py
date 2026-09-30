import os
from pathlib import Path
from typing import Set, Union
from fastapi import HTTPException
from app.core.config import settings

ALLOWED_IMAGE_EXTENSIONS: Set[str] = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}


def get_allowed_base_dirs() -> list[Path]:
    """
    Gibt eine Liste aller erlaubten Basisverzeichnisse für Bilddateien zurück.
    Beinhaltet ARCHIVE_DATA_DIR und optionale Verzeichnisse aus ALLOWED_IMAGE_DIRS.
    """
    allowed_dirs = []
    
    # Primäres Archiv-Verzeichnis
    primary_dir = Path(settings.ARCHIVE_DATA_DIR).resolve()
    allowed_dirs.append(primary_dir)

    # Zusätzliche erlaubte Verzeichnisse
    for d in getattr(settings, "ALLOWED_IMAGE_DIRS", []):
        try:
            p = Path(d).resolve()
            if p not in allowed_dirs:
                allowed_dirs.append(p)
        except Exception:
            continue

    return allowed_dirs


def validate_safe_image_path(path_input: Union[str, Path]) -> Path:
    """
    Validiert einen Dateipfad gegen Path-Traversal und nicht erlaubte Dateitypen:
    1. Wandelt den Pfad in einen absoluten, aufgelösten kanonischen Pfad um (eliminiert '../').
    2. Prüft, ob die Datei existiert und eine reguläre Datei ist.
    3. Prüft, ob die Dateiendung ein zulässiges Bildformat ist.
    4. Prüft, ob die Datei innerhalb eines der erlaubten Archiv-Verzeichnisse liegt.
    
    Wirft HTTPException (400, 403 oder 404) bei Verstößen.
    """
    if not path_input:
        raise HTTPException(status_code=400, detail="Kein Dateipfad angegeben.")

    try:
        candidate_path = Path(path_input)
        # Wenn relativ, relativ zu ARCHIVE_DATA_DIR auflösen
        if not candidate_path.is_absolute():
            candidate_path = (Path(settings.ARCHIVE_DATA_DIR) / candidate_path).resolve()
        else:
            candidate_path = candidate_path.resolve()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ungültiger Dateipfad: {e}")

    # Prüfung 1: Existenz
    if not candidate_path.is_file():
        raise HTTPException(status_code=404, detail="Bilddatei nicht gefunden.")

    # Prüfung 2: Erlaubtes Bildformat
    if candidate_path.suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=403,
            detail=f"Dateiformat '{candidate_path.suffix}' ist aus Sicherheitsgründen nicht zugelassen.",
        )

    # Prüfung 3: Sandboxing (Verzeichnisgrenzen)
    allowed_dirs = get_allowed_base_dirs()
    is_allowed = False
    for base_dir in allowed_dirs:
        try:
            # candidate_path.is_relative_to(base_dir) in Python >= 3.9
            if candidate_path == base_dir or candidate_path.is_relative_to(base_dir):
                is_allowed = True
                break
        except AttributeError:
            # Fallback für ältere APIs
            try:
                candidate_path.relative_to(base_dir)
                is_allowed = True
                break
            except ValueError:
                continue

    if not is_allowed:
        raise HTTPException(
            status_code=403,
            detail="Zugriff verweigert: Der angeforderte Pfad liegt außerhalb der autorisierten Archivverzeichnisse.",
        )

    return candidate_path
