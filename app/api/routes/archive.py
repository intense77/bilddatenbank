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
    batch_name: Optional[str] = Field(default=None, description="Sprechende Bestandsbezeichnung (z. B. 'Nachlass Pfarrer Müller 2026')")
    batch_notes: Optional[str] = Field(default=None, description="Optionale archivische Bemerkungen zum Bestand")
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
    from app.services.indexing_service import get_current_indexing_progress, update_indexing_progress

    state = get_current_indexing_progress()

    # Liveness-Check des Worker-Prozesses (falls Betriebssystem den Prozess beendet hat)
    if state.get("is_running") and state.get("pid"):
        pid = state["pid"]
        alive = False
        try:
            os.kill(pid, 0)
            alive = True
        except ProcessLookupError:
            alive = False
        except PermissionError:
            alive = True
        except OSError:
            alive = False

        if not alive:
            logger.warning("Indexierungs-Worker (PID %d) existiert nicht mehr. Markiere Job als beendet.", pid)
            state["is_running"] = False
            state["finished"] = True
            if not state.get("error"):
                state["error"] = f"Der Hintergrund-Indexierungsprozess (PID {pid}) wurde unerwartet beendet."
            update_indexing_progress(state)

    return state


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

    is_gvfs = "gvfs" in str(target_path).lower() or str(target_path).startswith("/run/user/")
    gvfs_warning = (
        "Hinweis zur Ingest-Performance: Dieser Ordner liegt auf einer GVFS/FUSE-Freigabe. "
        "Für maximale Einlesegeschwindigkeit bei großen Beständen empfiehlt sich ein nativer Linux Kernel-Mount "
        "via CIFS/SMB (z. B. 'sudo mount -t cifs ...')."
        if is_gvfs else None
    )

    return {
        "status": "success",
        "current_path": str(target_path),
        "parent_path": parent_path,
        "breadcrumbs": parts,
        "subdirectories": subdirs,
        "direct_images_count": direct_images_count,
        "quick_links": quick_links,
        "is_gvfs": is_gvfs,
        "gvfs_warning": gvfs_warning,
    }


@router.post("/scan-folder")
def scan_folder(request: ScanFolderRequest):
    """
    Schnelle Ordner-Vorschau: Prüft Pfad-Existenz, zählt vorhandene Bilddateien
    und gleicht sie mit bereits indexierten Aufnahmen in Qdrant ab.
    """
    path = resolve_archive_path(request.folder_path)

    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Pfad existiert nicht: {path}")
    if not path.is_dir():
        raise HTTPException(status_code=400, detail=f"Pfad ist kein Verzeichnis: {path}")

    # Dateien zählen
    iterator = path.rglob("*") if request.recursive else path.glob("*")
    image_files = []
    sample_files = []
    sidecars = 0

    for p in iterator:
        if p.is_file():
            suf = p.suffix.lower()
            if suf in ALLOWED_IMAGE_EXTENSIONS:
                image_files.append(p)
                if len(sample_files) < 10:
                    sample_files.append(p.name)
            elif suf == ".json":
                sidecars += 1

    # Registrierungsstatus prüfen
    allowed_dirs = [str(d.resolve()) for d in get_allowed_base_dirs()]
    abs_path_str = str(path.resolve())
    is_registered = abs_path_str in allowed_dirs or any(
        abs_path_str.startswith(d) for d in allowed_dirs if d != "/"
    )

    image_count = len(image_files)
    already_indexed_count = 0

    if image_count > 0:
        try:
            from app.services.indexing_service import UUID_NAMESPACE
            from app.services.qdrant_service import QdrantService
            import uuid

            qs = QdrantService()
            candidate_ids = []
            for img in image_files:
                try:
                    rel = img.relative_to(path).as_posix()
                except ValueError:
                    rel = img.name
                candidate_ids.append(str(uuid.uuid5(UUID_NAMESPACE, rel)))

            chunk_size = 100
            for i in range(0, len(candidate_ids), chunk_size):
                chunk = candidate_ids[i:i + chunk_size]
                pts = qs.client.retrieve(
                    collection_name=settings.COLLECTION_IMAGES,
                    ids=chunk,
                    with_payload=False,
                    with_vectors=False,
                )
                already_indexed_count += len(pts)
        except Exception as e:
            logger.debug("Fehler beim Prüfen existierender IDs in Qdrant: %s", e)

    new_images_count = max(0, image_count - already_indexed_count)
    is_fully_indexed = (image_count > 0 and already_indexed_count == image_count)
    is_partially_indexed = (image_count > 0 and 0 < already_indexed_count < image_count)

    return {
        "status": "success",
        "folder_path": str(path),
        "exists": True,
        "is_registered": is_registered,
        "image_count": image_count,
        "already_indexed_count": already_indexed_count,
        "new_images_count": new_images_count,
        "is_fully_indexed": is_fully_indexed,
        "is_partially_indexed": is_partially_indexed,
        "sidecar_count": sidecars,
        "sample_files": sample_files,
    }


@router.post("/index-folder")
async def index_existing_folder(
    request: IndexFolderRequest,
):
    """
    Bindet einen bestehenden Ordner auf dem Rechner/Server ohne Verschieben ein
    und indexiert alle Bilder in einem vollständig isolierten Hintergrund-Subprozess.
    Schützt den Webserver dauerhaft vor Memory-Lecks, Heap-Fragmentierung und OOM-Kills.
    """
    path = resolve_archive_path(request.folder_path)

    if not path.is_dir():
        raise HTTPException(status_code=400, detail=f"Ungültiges Verzeichnis: {path}")

    from app.services.indexing_service import get_current_indexing_progress, update_indexing_progress

    current_state = get_current_indexing_progress()
    if current_state.get("is_running"):
        worker_pid = current_state.get("pid")
        is_alive = False
        if worker_pid:
            try:
                os.kill(worker_pid, 0)
                is_alive = True
            except OSError:
                is_alive = False

        if is_alive:
            raise HTTPException(
                status_code=409,
                detail="Es läuft bereits eine Indexierung im Hintergrund. Bitte warten Sie, bis diese abgeschlossen ist.",
            )

    # 1. Pfad in den erlaubten Archiv-Pfaden registrieren und in .env sichern
    registered_path = register_allowed_archive_dir(path, persist=True)
    logger.info("Ordner '%s' für Bildzugriff registriert.", registered_path)

    # 2. Status initialisieren
    import uuid
    from datetime import datetime, timezone
    new_job_id = uuid.uuid4().hex[:12]
    now_iso = datetime.now(timezone.utc).isoformat()
    update_indexing_progress({
        "job_id": new_job_id,
        "is_running": True,
        "finished": False,
        "folder_path": str(registered_path),
        "total_found": 0,
        "processed_count": 0,
        "current_file": "Starte isolierten Hintergrund-Worker...",
        "new_indexed": 0,
        "skipped": 0,
        "faces_detected": 0,
        "already_fully_indexed": False,
        "percent": 0,
        "error": None,
        "started_at": now_iso,
        "last_updated": now_iso,
        "clustering_status": None,
        "clustering_message": None,
    })

    # 3. Isolierten Subprozess starten (vollständige RAM-Isolation gegen OOM & Heap-Lecks)
    import subprocess
    import sys

    log_dir = Path(".cache")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "indexing_worker.log"
    log_handle = open(log_file, "a", encoding="utf-8")

    cmd = [
        sys.executable,
        "-m",
        "app.workers.indexing_worker",
        "--folder", str(registered_path),
        "--job-id", new_job_id,
        "--batch-id", f"batch_{new_job_id}",
    ]
    if request.batch_name and request.batch_name.strip():
        cmd.extend(["--batch-name", request.batch_name.strip()])
    if request.batch_notes and request.batch_notes.strip():
        cmd.extend(["--notes", request.batch_notes.strip()])
    if request.recursive:
        cmd.append("--recursive")
    else:
        cmd.append("--no-recursive")
    if request.force:
        cmd.append("--force")
    if request.cluster_faces:
        cmd.append("--cluster-faces")

    process = subprocess.Popen(
        cmd,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,  # Eigenständige Prozessgruppe
    )
    update_indexing_progress({"pid": process.pid})
    logger.info("Isolierter Indexierungs-Prozess gestartet (PID: %d, Job-ID: %s).", process.pid, new_job_id)

    return {
        "status": "started",
        "job_id": new_job_id,
        "pid": process.pid,
        "folder_path": str(registered_path),
        "message": "Indexierung wurde erfolgreich als isolierter Prozess gestartet.",
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

    # Clustering ausführen, falls Gesichter erkannt wurden und Gesamtbestand im Rahmen liegt
    clustering_performed = False
    if (
        enable_clustering
        and settings.ENABLE_FACE_RECOGNITION
        and total_faces > 0
    ):
        total_coll_faces = 0
        try:
            coll_info = clustering_service.qdrant.client.get_collection(settings.COLLECTION_FACES)
            total_coll_faces = coll_info.points_count or 0
        except Exception:
            pass

        max_threshold = getattr(settings, "AUTO_CLUSTER_MAX_FACES", 500000)
        if total_coll_faces <= max_threshold:
            try:
                clustering_service.run_clustering()
                clustering_performed = True
            except Exception as e:
                logger.warning("Clustering nach Upload fehlgeschlagen: %s", e)
        else:
            logger.info(
                "Automatisches Clustering nach Upload übersprungen: Archiv enthält %d Gesichter (Schwelle: %d).",
                total_coll_faces,
                max_threshold,
            )

    return {
        "status": "success",
        "target_directory": str(target_dir),
        "uploaded_images": len(saved_images),
        "uploaded_sidecars": len(saved_sidecars),
        "indexed_images": indexed_count,
        "faces_detected": total_faces,
        "clustering_performed": clustering_performed,
        "items": results,
    }


class TwoSidedNotesRequest(BaseModel):
    path: str = Field(..., description="Dateipfad des Vorder- oder Rückseitenbildes")
    notes: str = Field(..., description="Handschriftliche Notizen, Stempeltext oder Transkription")


@router.get("/two-sided")
def get_two_sided_info(path: str):
    """
    Liefert Zweiblatt-Informationen (Recto/Verso) für ein Archivbild:
    Erkennt automatisch, ob eine zusammengehörige Rückseite existiert, und liefert
    Metadaten sowie Notizen.
    """
    from app.core.security import validate_safe_image_path
    from app.services.recto_verso_service import recto_verso_service

    safe_path = validate_safe_image_path(path)
    info = recto_verso_service.get_two_sided_info(safe_path)
    return info


@router.post("/two-sided/notes")
def save_two_sided_notes(req: TwoSidedNotesRequest):
    """
    Speichert oder aktualisiert Notizen / Transkriptionen der Rückseite
    und verknüpft sie mit beiden Blattseiten.
    """
    from app.core.security import validate_safe_image_path
    from app.services.recto_verso_service import recto_verso_service

    safe_path = validate_safe_image_path(req.path)
    success = recto_verso_service.save_verso_notes(safe_path, req.notes)
    if not success:
        raise HTTPException(status_code=500, detail="Konnte Rückseiten-Notizen nicht speichern.")

    return {
        "success": True,
        "path": str(safe_path),
        "notes": req.notes,
    }


# =========================================================================
# Archivische Import-Historie & Akzessionsjournal (Provenienz & Rollback)
# =========================================================================

class UpdateBatchRequest(BaseModel):
    name: Optional[str] = Field(default=None, description="Aktualisierter Name des Bestands")
    notes: Optional[str] = Field(default=None, description="Aktualisierte archivische Notizen")


@router.get("/batches")
def get_import_batches(limit: int = 100):
    """Gibt die Liste aller erfassten Import-Chargen und Bestände zurück."""
    from app.services.metadata_db import metadata_db
    batches = metadata_db.list_import_batches(limit=limit)
    return {"batches": batches, "count": len(batches)}


@router.get("/batches/{batch_id}")
def get_import_batch_details(batch_id: str):
    """Liefert die Details einer einzelnen Import-Charge."""
    from app.services.metadata_db import metadata_db
    batch = metadata_db.get_import_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail=f"Import-Batch '{batch_id}' nicht gefunden.")
    return batch


@router.patch("/batches/{batch_id}")
def update_import_batch(batch_id: str, req: UpdateBatchRequest):
    """Aktualisiert die Bestandsbezeichnung oder Notizen einer Charge."""
    from app.services.metadata_db import metadata_db
    batch = metadata_db.get_import_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail=f"Import-Batch '{batch_id}' nicht gefunden.")
    updated = metadata_db.update_import_batch(batch_id, notes=req.notes)
    if req.name and req.name.strip():
        try:
            with metadata_db._get_connection() as conn:
                conn.execute("UPDATE import_batches SET name = ? WHERE id = ?;", (req.name.strip(), batch_id))
                conn.commit()
            updated = metadata_db.get_import_batch(batch_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Fehler beim Umbenennen des Bestands: {e}")
    return updated


@router.delete("/batches/{batch_id}")
def rollback_import_batch(batch_id: str):
    """
    Führt ein selektives Rollback für einen Import-Batch aus:
    Löscht alle zugehörigen Bild- und Gesichts-Vektorpunkte aus Qdrant
    sowie die Metadateneinträge aus SQLite.
    """
    from app.services.metadata_db import metadata_db
    from app.services.qdrant_service import QdrantService
    batch = metadata_db.get_import_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail=f"Import-Batch '{batch_id}' nicht gefunden.")

    qs = QdrantService()
    # 1. Aus Qdrant entfernen
    qdrant_res = qs.delete_by_import_id(batch_id)
    # 2. Aus SQLite entfernen
    deleted_from_db = metadata_db.delete_import_batch(batch_id)

    logger.info("Rollback für Batch '%s' ('%s') erfolgreich durchgeführt.", batch_id, batch.get("name"))
    return {
        "status": "deleted",
        "batch_id": batch_id,
        "batch_name": batch.get("name"),
        "deleted_from_db": deleted_from_db,
        "qdrant": qdrant_res,
    }
