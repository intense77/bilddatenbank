import logging
import re
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from app.api.deps import get_qdrant_service, clear_face_service_cache
from app.core.config import settings
from app.services.qdrant_service import QdrantService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system", tags=["System"])


class FaceRecognitionToggleRequest(BaseModel):
    enabled: bool = Field(..., description="True aktiviert die biometrische Gesichtserkennung, False schaltet sie ab.")


@router.post("/settings/face-recognition")
def toggle_face_recognition(request: FaceRecognitionToggleRequest):
    """
    Schaltet die biometrische Gesichtserkennung zur Laufzeit um und persistiert
    die Einstellung in der .env-Datei für zukünftige Server-Neustarts.
    """
    settings.ENABLE_FACE_RECOGNITION = request.enabled
    clear_face_service_cache()

    # Persistiere Einstellung in .env
    env_path = Path(".env")
    if env_path.exists():
        try:
            content = env_path.read_text(encoding="utf-8")
            val_str = "true" if request.enabled else "false"
            if re.search(r"^\s*ENABLE_FACE_RECOGNITION\s*=", content, flags=re.MULTILINE):
                content = re.sub(
                    r"^\s*ENABLE_FACE_RECOGNITION\s*=.*$",
                    f"ENABLE_FACE_RECOGNITION={val_str}",
                    content,
                    flags=re.MULTILINE,
                )
            else:
                content += f"\nENABLE_FACE_RECOGNITION={val_str}\n"
            env_path.write_text(content, encoding="utf-8")
        except Exception as e:
            logger.warning("Konnte .env nicht aktualisieren: %s", e)

    return {
        "status": "success",
        "face_recognition_enabled": settings.ENABLE_FACE_RECOGNITION,
        "message": "Biometrische Gesichtserkennung aktiviert" if request.enabled else "Biometrische Gesichtserkennung deaktiviert (DSGVO / Ressourcensparen)",
    }



@router.get("/health")
def health_check(qdrant: QdrantService = Depends(get_qdrant_service)):
    """Prüft die Erreichbarkeit von Qdrant und gibt Statusinformationen zurück."""
    is_qdrant_healthy = qdrant.check_health()
    status_str = "healthy" if is_qdrant_healthy else "degraded"

    from app.core.system_profile import current_hardware_profile

    return {
        "status": status_str,
        "device": settings.effective_device,
        "configured_device": settings.DEVICE,
        "qdrant_reachable": is_qdrant_healthy,
        "face_recognition_enabled": settings.ENABLE_FACE_RECOGNITION,
        "version": settings.VERSION,
        "hardware_profile": current_hardware_profile.to_dict(),
    }


@router.get("/collections")
def get_collections_status(qdrant: QdrantService = Depends(get_qdrant_service)):
    """Gibt Metriken zu den Bild- und Gesichts-Collections zurück."""
    try:
        images_info = qdrant.get_collection_info(settings.COLLECTION_IMAGES)
        faces_info = qdrant.get_collection_info(settings.COLLECTION_FACES)
        return {
            settings.COLLECTION_IMAGES: images_info,
            settings.COLLECTION_FACES: faces_info,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Abruf der Collections: {str(e)}")


@router.post("/prune")
def prune_database(
    dry_run: bool = Query(default=True, description="Wenn True, wird nur analysiert ohne zu löschen"),
    qdrant: QdrantService = Depends(get_qdrant_service),
):
    """
    Prüft alle Einträge in Qdrant gegen das Archivverzeichnis und löscht verwaiste Datensätze (Art. 17 DSGVO).
    """
    source_dir = Path(settings.ARCHIVE_DATA_DIR).resolve()
    stats = qdrant.prune_orphaned_records(source_dir=source_dir, dry_run=dry_run)
    return stats
