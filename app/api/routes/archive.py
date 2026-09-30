import os
import shutil
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
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
def get_registered_folders():
    """Gibt alle autorisierten Archiv-Verzeichnisse zurück."""
    base_dirs = get_allowed_base_dirs()
    return {
        "primary_dir": str(Path(settings.ARCHIVE_DATA_DIR).resolve()),
        "allowed_dirs": [str(p) for p in base_dirs],
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
def index_existing_folder(
    request: IndexFolderRequest,
    indexing_service: IndexingService = Depends(get_indexing_service),
    clustering_service: ClusteringService = Depends(get_clustering_service),
):
    """
    Bindet einen bestehenden Ordner auf dem Rechner/Server ohne Verschieben ein
    und indexiert alle Bilder inkrementell. Registriert den Pfad sicher in der Sandbox.
    """
    path = resolve_archive_path(request.folder_path)

    if not path.is_dir():
        raise HTTPException(status_code=400, detail=f"Ungültiges Verzeichnis: {path}")

    # 1. Pfad in den erlaubten Archiv-Pfaden registrieren und in .env sichern
    registered_path = register_allowed_archive_dir(path, persist=True)
    logger.info("Ordner '%s' für Bildzugriff registriert.", registered_path)

    # 2. Inkrementelle Indexierung starten
    stats = indexing_service.index_folder(
        folder_path=registered_path,
        recursive=request.recursive,
        force=request.force,
    )

    # 3. Optionales Clustering, falls neue Gesichter gefunden wurden
    clusters_info = None
    if (
        request.cluster_faces
        and settings.ENABLE_FACE_RECOGNITION
        and stats.get("faces_detected", 0) > 0
    ):
        try:
            clusters_info = clustering_service.run_clustering()
        except Exception as e:
            logger.warning("Automatisches Clustering nach Ordnerindexierung fehlgeschlagen: %s", e)

    return {
        "status": "success",
        "indexing_stats": stats,
        "clustering": clusters_info,
        "message": f"{stats.get('new_indexed', 0)} neue Bilder erfolgreich indexiert ({stats.get('skipped', 0)} übersprungen).",
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
