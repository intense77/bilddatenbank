from functools import lru_cache
from typing import Optional
from fastapi import HTTPException
from app.core.config import settings
from app.services.qdrant_service import QdrantService
from app.services.clip_service import ClipService
from app.services.face_service import FaceService
from app.services.indexing_service import IndexingService
from app.services.clustering_service import ClusteringService


@lru_cache(maxsize=1)
def get_qdrant_service() -> QdrantService:
    return QdrantService()


@lru_cache(maxsize=1)
def get_clip_service() -> ClipService:
    return ClipService()


@lru_cache(maxsize=1)
def get_face_service() -> FaceService:
    if not settings.ENABLE_FACE_RECOGNITION:
        raise HTTPException(
            status_code=403,
            detail="Biometrische Gesichtserkennung ist in der Systemkonfiguration deaktiviert (ENABLE_FACE_RECOGNITION=false). "
                   "Aktivieren Sie die Option in der .env-Datei, um biometrische Personensuchen durchzuführen.",
        )
    return FaceService()


@lru_cache(maxsize=1)
def get_indexing_service() -> IndexingService:
    face_svc = None
    if settings.ENABLE_FACE_RECOGNITION:
        try:
            face_svc = get_face_service()
        except HTTPException:
            face_svc = None

    return IndexingService(
        qdrant_service=get_qdrant_service(),
        clip_service=get_clip_service(),
        face_service=face_svc,
    )


@lru_cache(maxsize=1)
def get_clustering_service() -> ClusteringService:
    return ClusteringService(qdrant_service=get_qdrant_service())


@lru_cache(maxsize=1)
def get_variant_service():
    from app.services.variant_service import VariantService
    return VariantService(qdrant_service=get_qdrant_service())


@lru_cache(maxsize=1)
def get_image_rotation_service():
    from app.services.image_rotation_service import ImageRotationService
    from app.services.thumbnail_service import thumbnail_service
    return ImageRotationService(
        indexing_service=get_indexing_service(),
        thumbnail_service_instance=thumbnail_service,
    )


@lru_cache(maxsize=1)
def get_network_service():
    from app.services.network_service import NetworkService
    return NetworkService(qdrant_service=get_qdrant_service())


def clear_face_service_cache():
    """Löscht den Cache für get_face_service und get_indexing_service bei Schalterwechsel."""
    get_face_service.cache_clear()
    get_indexing_service.cache_clear()

