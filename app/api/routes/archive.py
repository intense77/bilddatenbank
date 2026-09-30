import os
import shutil
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, BackgroundTasks
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.security import (
    ALLOWED_IMAGE_EXTENSIONS,
    register_allowed_archive_dir,
    get_allowed_base_dirs,
    resolve_archive_path,
)
from app.api.deps import get_indexing_service, get_clustering_service
from app.services.indexing_service import IndexingService
from app.services.clustering_service import ClusteringService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/archive", tags=["Archiv-Verwaltung & Upload"])


# --- Pydantic Schemas ---

class ScanFolderRequest(BaseModel):
    folder_path: str = Field(..., min_length=1, description="Absoluter oder relativer Pfad zum Bildordner")
    recursive: bool = Field(default=True, description="Auch Unterordner durchsuchen")


class IndexFolderRequest(BaseModel):
    folder_path: str = Field(..., min_length=1, description="Absoluter oder relativer Pfad zum Bildordner")
    recursive: bool = Field(default=True, description="Auch Unterordner durchsuchen")
    force: bool = Field(default=False, description="Erzwingt Neuindexierung bereits vorhandener Bilder")
    cluster_faces: bool = Field(default=True, description="Führt automatisches Clustering nach dem Einlesen aus")


# --- Endpunkte ---

@router.get("/registered-folders")
async def get_registered_folders():
    """Gibt alle autorisierten Archiv-Verzeichnisse zurück."""
    base_dirs = get_allowed_base_dirs()
    return {
        "primary_dir": str(Path(settings.ARCHIVE_DATA_DIR).resolve()),
        "allowed_dirs": [str(p) for p in base_dirs],
    }


@router.get("/index-progress")
async def get_indexing_progress():
    """Liefert den aktuellen Verarbeitungsstatus der Ordner-Indexierung in Echtzeit."""
    from app.services.indexing_service import INDEXING_PROGRESS
    return INDEXING_PROGRESS


@router.get("/browse-folders")
def browse_folders(path: Optional[str] = None):
    """
    Ermöglicht das grafische Navigieren durch Verzeichnisse im Web-Interface,
    um Archiv-Ordner ohne manuelles Tippen von Pfaden auswählen zu können.
    """
    if not path or not path.strip():
        # Standard: GVFS falls vorhanden, sonst Home
        gvfs_dir = Path(f"/run/user/{os.getuid()}/gvfs")
        if gvfs_dir.exists() and any(gvfs_dir.iterdir()):
            target_path = gvfs_dir
        else:
            target_path = Path.home()
    else:
        try:
            target_path = resolve_archive_path(path)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Ungültiger Pfad: {e}")

    if not target_path.exists():
        target_path = Path.home()
    if not target_path.is_dir():
        target_path = target_path.parent

    # Quick links
    quick_links = []
    
    # 1. GVFS (NAS / SMB-Freigaben)
    gvfs_dir = Path(f"/run/user/{os.getuid()}/gvfs")
    if gvfs_dir.exists():
        quick_links.append({"label": "Netzlaufwerke (NAS/GVFS)", "path": str(gvfs_dir), "icon": "server"})

    # 2. Persönlicher Ordner (Home)
    home_dir = Path.home()
    quick_links.append({"label": "Persönlicher Ordner", "path": str(home_dir), "icon": "home"})

    # 3. Lokales Archiv-Datenverzeichnis
    data_dir = Path(settings.ARCHIVE_DATA_DIR).resolve()
    if data_dir.exists():
        quick_links.append({"label": "Projekt-Daten (data/)", "path": str(data_dir), "icon": "folder"})

    # 4. Externe Medien / Mounts
    for media_candidate in ["/media", "/mnt"]:
        mp = Path(media_candidate)
        try:
            if mp.exists() and any(mp.iterdir()):
                quick_links.append({"label": f"Laufwerke ({media_candidate})", "path": str(mp), "icon": "disc"})
        except Exception:
            pass

    # 5. Root
    quick_links.append({"label": "Wurzelverzeichnis (/)", "path": "/", "icon": "hard-drive"})

    # Unterverzeichnisse und Bilder zählen
    subdirs = []
    direct_images_count = 0
    try:
        for item in sorted(target_path.iterdir(), key=lambda x: x.name.lower()):
            if item.name.startswith("."):
                continue
            try:
                if item.is_dir():
                    has_children = False
                    try:
                        has_children = any(item.iterdir())
                    except Exception:
                        pass
                    subdirs.append({
                        "name": item.name,
                        "path": str(item),
                        "has_subdirs": has_children
                    })
                elif item.is_file() and item.suffix.lower() in ALLOWED_IMAGE_EXTENSIONS:
                    direct_images_count += 1
            except (PermissionError, OSError):
                continue
    except PermissionError:
        raise HTTPException(status_code=403, detail="Keine Leseberechtigung für diesen Ordner.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Lesen des Ordners: {e}")

    parent_path = str(target_path.parent) if target_path.parent != target_path else None

    # Breadcrumbs
    parts = []
    curr = target_path
    while True:
        parts.insert(0, {"name": curr.name if curr.name else "/", "path": str(curr)})
        if curr.parent == curr:
            break
        curr = curr.parent

    return {
        "status": "success",
        "current_path": str(target_path),
        "parent_path": parent_path,
        "breadcrumbs": parts,
        "subdirectories": subdirs,
        "direct_images_count": direct_images_count,
        "quick_links": quick_links,
    }


@router.post("/scan-folder")
def scan_folder(request: ScanFolderRequest):
    """
    Schnelle Ordner-Vorschau: Prüft Pfad-Existenz und zählt vorhandene Bilddateien vor der Indexierung.
    """
    path = resolve_archive_path(request.folder_path)

    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Pfad existiert nicht: {path}")
    if not path.is_dir():
        raise HTTPException(status_code=400, detail=f"Pfad ist kein Verzeichnis: {path}")

    # Dateien zählen
    iterator = path.rglob("*") if request.recursive else path.glob("*")
    images = []
    sidecars = 0

    for p in iterator:
        if p.is_file():
            suf = p.suffix.lower()
            if suf in ALLOWED_IMAGE_EXTENSIONS:
                images.append(p.name)
            elif suf == ".json":
                sidecars += 1

    return {
        "status": "success",
        "folder_path": str(path),
        "exists": True,
        "image_count": len(images),
        "sidecar_count": sidecars,
        "sample_files": images[:10],
    }


@router.post("/index-folder")
async def index_existing_folder(
    request: IndexFolderRequest,
    background_tasks: BackgroundTasks,
    indexing_service: IndexingService = Depends(get_indexing_service),
    clustering_service: ClusteringService = Depends(get_clustering_service),
):
    """
    Bindet einen bestehenden Ordner auf dem Rechner/Server ohne Verschieben ein
    und indexiert alle Bilder asynchron im Hintergrund. Registriert den Pfad sicher in der Sandbox.
    """
    path = resolve_archive_path(request.folder_path)

    if not path.is_dir():
        raise HTTPException(status_code=400, detail=f"Ungültiges Verzeichnis: {path}")

    # 1. Pfad in den erlaubten Archiv-Pfaden registrieren und in .env sichern
    registered_path = register_allowed_archive_dir(path, persist=True)
    logger.info("Ordner '%s' für Bildzugriff registriert.", registered_path)

    # 2. Asynchrone Indexierung im Hintergrund starten
    def run_indexing_job():
        try:
            stats = indexing_service.index_folder(
                folder_path=registered_path,
                recursive=request.recursive,
                force=request.force,
            )
            if (
                request.cluster_faces
                and settings.ENABLE_FACE_RECOGNITION
                and stats.get("faces_detected", 0) > 0
            ):
                try:
                    clustering_service.run_clustering()
                except Exception as ce:
                    logger.warning("Clustering nach Hintergrund-Indexierung fehlgeschlagen: %s", ce)
        except Exception as e:
            logger.error("Hintergrund-Indexierung für '%s' fehlgeschlagen: %s", registered_path, e, exc_info=True)

    background_tasks.add_task(run_indexing_job)

    return {
        "status": "started",
        "folder_path": str(registered_path),
        "message": "Indexierung wurde erfolgreich im Hintergrund gestartet.",
    }


@router.post("/upload")
async def upload_archive_images(
    files: List[UploadFile] = File(..., description="Eine oder mehrere Bilddateien oder Sidecar-JSONs"),
    subfolder: Optional[str] = Form(None, description="Optionaler Unterordner innerhalb des Archivs"),
    enable_clustering: bool = Form(default=True, description="Clustering nach Upload ausführen"),
    indexing_service: IndexingService = Depends(get_indexing_service),
    clustering_service: ClusteringService = Depends(get_clustering_service),
):
    """
    Nimmt per Drag-and-Drop hochgeladene Bilder (und optionale .json-Sidecars) entgegen,
    speichert sie im Archivordner und indexiert sie sofort.
    """
    base_target = Path(settings.ARCHIVE_DATA_DIR).resolve()
    if subfolder and subfolder.strip():
        # Verhindere Path-Traversal im Subfolder
        safe_sub = Path(subfolder.strip()).name
        target_dir = base_target / safe_sub
    else:
        target_dir = base_target / "uploads"

    target_dir.mkdir(parents=True, exist_ok=True)

    saved_images: List[Path] = []
    saved_sidecars: List[Path] = []

    for file in files:
        if not file.filename:
            continue
        # Dateiname bereinigen
        safe_name = Path(file.filename).name
        target_path = target_dir / safe_name
        suffix = target_path.suffix.lower()

        if suffix not in ALLOWED_IMAGE_EXTENSIONS and suffix != ".json":
            continue

        try:
            content = await file.read()
            with open(target_path, "wb") as f:
                f.write(content)

            if suffix == ".json":
                saved_sidecars.append(target_path)
            else:
                saved_images.append(target_path)
        except Exception as e:
            logger.error("Fehler beim Speichern der Datei '%s': %s", safe_name, e)

    indexed_count = 0
    total_faces = 0
    results = []

    for img_path in saved_images:
        success, num_faces = indexing_service.index_image_file(img_path, base_dir=base_target)
        if success:
            indexed_count += 1
            total_faces += num_faces
            results.append({
                "file_name": img_path.name,
                "file_path": str(img_path),
                "faces_detected": num_faces,
            })

    # Clustering ausführen, falls Gesichter erkannt wurden
    if (
        enable_clustering
        and settings.ENABLE_FACE_RECOGNITION
        and total_faces > 0
    ):
        try:
            clustering_service.run_clustering()
        except Exception as e:
            logger.warning("Clustering nach Upload fehlgeschlagen: %s", e)

    return {
        "status": "success",
        "target_directory": str(target_dir),
        "uploaded_images": len(saved_images),
        "uploaded_sidecars": len(saved_sidecars),
        "indexed_images": indexed_count,
        "faces_detected": total_faces,
        "items": results,
    }
