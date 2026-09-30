import os
import re
import json
import logging
from pathlib import Path
from typing import Set, Union
from fastapi import HTTPException
from app.core.config import settings

logger = logging.getLogger(__name__)

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


def resolve_archive_path(path_input: Union[str, Path]) -> Path:
    """
    Normalisiert und bereinigt eine Pfadangabe:
    - Entfernt umgebende Anführungszeichen und Whitespaces
    - Normalisiert Windows-Backslashes (z.B. aus SMB/Netzlaufwerken)
    - Löst die Tilde `~` zum Home-Verzeichnis des Nutzers auf
    - Wandelt relative Pfade in absolute Pfade relativ zu ARCHIVE_DATA_DIR um
    - Löst Symlinks und '..' kanonisch auf (.resolve())
    """
    if isinstance(path_input, str):
        cleaned = path_input.strip().strip("'\"")
        cleaned = cleaned.replace("\\", "/")
        cleaned = os.path.expanduser(cleaned)
        p = Path(cleaned)
    else:
        p = Path(os.path.expanduser(str(path_input)))

    if not p.is_absolute():
        p = (Path(settings.ARCHIVE_DATA_DIR) / p).resolve()
    else:
        p = p.resolve()

    return p


def register_allowed_archive_dir(new_dir: Union[str, Path], persist: bool = True) -> Path:
    """
    Registriert ein externes Archiv-Verzeichnis zur Laufzeit in settings.ALLOWED_IMAGE_DIRS,
    sodass Dateien darin autorisiert und vor Path-Traversal geschützt ausgeliefert werden können.
    Persistiert die Liste optional in der .env-Datei.
    """
    p = resolve_archive_path(new_dir)
    if not p.is_dir():
        raise HTTPException(status_code=400, detail=f"Das angegebene Verzeichnis existiert nicht: {p}")

    p_str = str(p)
    if p_str not in settings.ALLOWED_IMAGE_DIRS:
        settings.ALLOWED_IMAGE_DIRS.append(p_str)

    if persist:
        env_path = Path(".env")
        if env_path.exists():
            try:
                content = env_path.read_text(encoding="utf-8")
                dirs_json = json.dumps(settings.ALLOWED_IMAGE_DIRS)
                if re.search(r"^\s*ALLOWED_IMAGE_DIRS\s*=", content, flags=re.MULTILINE):
                    content = re.sub(
                        r"^\s*ALLOWED_IMAGE_DIRS\s*=.*$",
                        f"ALLOWED_IMAGE_DIRS={dirs_json}",
                        content,
                        flags=re.MULTILINE,
                    )
                else:
                    content += f"\nALLOWED_IMAGE_DIRS={dirs_json}\n"
                env_path.write_text(content, encoding="utf-8")
            except Exception as e:
                logger.warning("Konnte ALLOWED_IMAGE_DIRS nicht in .env sichern: %s", e)

    return p


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
        candidate_path = resolve_archive_path(path_input)
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
