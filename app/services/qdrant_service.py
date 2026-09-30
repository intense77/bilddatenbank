import logging
from typing import Any, List, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest_models
from app.core.config import settings

logger = logging.getLogger(__name__)


class QdrantService:
    """Service zur Verwaltung und Abfrage der lokalen Qdrant-Vektordatenbank."""

    def __init__(self):
        self.client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            grpc_port=settings.QDRANT_GRPC_PORT,
            prefer_grpc=settings.QDRANT_PREFER_GRPC,
            api_key=settings.QDRANT_API_KEY,
            timeout=10.0,
        )

    def init_collections(self) -> None:
        """
        Initialisiert die Collections:
        - archive_images (512-dim, Cosine) für OpenCLIP ViT-B-32
        - archive_faces (512-dim, Cosine) für InsightFace/ArcFace
        """
        existing_collections = [c.name for c in self.client.get_collections().collections]

        # 1. Image Collection
        if settings.COLLECTION_IMAGES not in existing_collections:
            logger.info("Erstelle Collection '%s'...", settings.COLLECTION_IMAGES)
            self.client.create_collection(
                collection_name=settings.COLLECTION_IMAGES,
                vectors_config=rest_models.VectorParams(
                    size=settings.CLIP_VECTOR_SIZE,
                    distance=rest_models.Distance.COSINE,
                ),
            )
            # Payload Index für schnelle Pfad-Suchen
            for field in ["file_path", "image_path"]:
                self.client.create_payload_index(
                    collection_name=settings.COLLECTION_IMAGES,
                    field_name=field,
                    field_schema=rest_models.PayloadSchemaType.KEYWORD,
                )
            logger.info("Collection '%s' erfolgreich erstellt.", settings.COLLECTION_IMAGES)
        else:
            logger.info("Collection '%s' existiert bereits.", settings.COLLECTION_IMAGES)

        # 2. Face Collection
        if settings.COLLECTION_FACES not in existing_collections:
            logger.info("Erstelle Collection '%s'...", settings.COLLECTION_FACES)
            self.client.create_collection(
                collection_name=settings.COLLECTION_FACES,
                vectors_config=rest_models.VectorParams(
                    size=settings.FACE_VECTOR_SIZE,
                    distance=rest_models.Distance.COSINE,
                ),
            )
            # Payload Indizes für Metadaten: file_path, image_path, face_id, cluster_id
            for field in ["file_path", "image_path", "face_id", "cluster_id"]:
                self.client.create_payload_index(
                    collection_name=settings.COLLECTION_FACES,
                    field_name=field,
                    field_schema=rest_models.PayloadSchemaType.KEYWORD,
                )
            logger.info("Collection '%s' erfolgreich erstellt.", settings.COLLECTION_FACES)
        else:
            logger.info("Collection '%s' existiert bereits.", settings.COLLECTION_FACES)

    def upsert_images(self, points: List[rest_models.PointStruct]) -> None:
        """Fügt Bild-Embeddings in archive_images ein oder aktualisiert diese."""
        if not points:
            return
        self.client.upsert(
            collection_name=settings.COLLECTION_IMAGES,
            points=points,
        )

    def upsert_faces(self, points: List[rest_models.PointStruct]) -> None:
        """Fügt Gesichts-Embeddings in archive_faces ein oder aktualisiert diese."""
        if not points:
            return
        self.client.upsert(
            collection_name=settings.COLLECTION_FACES,
            points=points,
        )

    def search_images(
        self,
        query_vector: List[float],
        limit: int = 20,
        score_threshold: Optional[float] = None,
    ) -> List[rest_models.ScoredPoint]:
        """Sucht ähnliche Bilder anhand eines CLIP-Vektors."""
        if hasattr(self.client, "query_points"):
            res = self.client.query_points(
                collection_name=settings.COLLECTION_IMAGES,
                query=query_vector,
                limit=limit,
                score_threshold=score_threshold,
            )
            return res.points
        return self.client.search(
            collection_name=settings.COLLECTION_IMAGES,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
        )

    def search_faces(
        self,
        query_vector: List[float],
        limit: int = 20,
        score_threshold: Optional[float] = None,
        cluster_id: Optional[str] = None,
    ) -> List[rest_models.ScoredPoint]:
        """Sucht ähnliche Gesichter anhand eines ArcFace-Vektors."""
        query_filter = None
        if cluster_id:
            query_filter = rest_models.Filter(
                must=[
                    rest_models.FieldCondition(
                        key="cluster_id",
                        match=rest_models.MatchValue(value=cluster_id),
                    )
                ]
            )

        if hasattr(self.client, "query_points"):
            res = self.client.query_points(
                collection_name=settings.COLLECTION_FACES,
                query=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=query_filter,
            )
            return res.points

        return self.client.search(
            collection_name=settings.COLLECTION_FACES,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=query_filter,
        )

    def get_collection_info(self, collection_name: str) -> dict[str, Any]:
        """Gibt Status- und Zählerinformationen einer Collection zurück."""
        info = self.client.get_collection(collection_name=collection_name)
        return {
            "status": info.status,
            "vectors_count": info.vectors_count,
            "points_count": info.points_count,
            "indexed_vectors_count": info.indexed_vectors_count,
        }

    def get_existing_ids(self, collection_name: str, ids: List[str]) -> set[str]:
        """Ermittelt, welche der übergebenen IDs bereits in der Collection existieren."""
        if not ids:
            return set()
        try:
            records = self.client.retrieve(
                collection_name=collection_name,
                ids=ids,
                with_payload=False,
                with_vectors=False,
            )
            return {str(record.id) for record in records}
        except Exception as e:
            logger.warning("Konnte existierende IDs in Collection '%s' nicht abrufen: %s", collection_name, e)
            return set()

    def check_health(self) -> bool:
        """Prüft, ob der Qdrant-Server erreichbar ist."""
        try:
            self.client.get_collections()
            return True
        except Exception as e:
            logger.error("Fehler bei Qdrant-Verbindungsprüfung: %s", e)
            return False
