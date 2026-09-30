from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_qdrant_service
from app.core.config import settings
from app.services.qdrant_service import QdrantService

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/health")
def health_check(qdrant: QdrantService = Depends(get_qdrant_service)):
    """Prüft die Erreichbarkeit von Qdrant und gibt Statusinformationen zurück."""
    is_qdrant_healthy = qdrant.check_health()
    status_str = "healthy" if is_qdrant_healthy else "degraded"

    return {
        "status": status_str,
        "device": settings.effective_device,
        "configured_device": settings.DEVICE,
        "qdrant_reachable": is_qdrant_healthy,
        "version": settings.VERSION,
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
