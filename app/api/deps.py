from functools import lru_cache
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
    return FaceService()


@lru_cache(maxsize=1)
def get_indexing_service() -> IndexingService:
    return IndexingService(
        qdrant_service=get_qdrant_service(),
        clip_service=get_clip_service(),
        face_service=get_face_service(),
    )


@lru_cache(maxsize=1)
def get_clustering_service() -> ClusteringService:
    return ClusteringService(qdrant_service=get_qdrant_service())
