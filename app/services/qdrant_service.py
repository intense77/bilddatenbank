import logging
from pathlib import Path
from typing import Any, List, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest_models
from app.core.config import settings

logger = logging.getLogger(__name__)


class QdrantService:
    """Service zur Verwaltung und Abfrage der lokalen Qdrant-Vektordatenbank."""

    def __init__(self):
        try:
            self.client = QdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
                grpc_port=settings.QDRANT_GRPC_PORT,
                prefer_grpc=settings.QDRANT_PREFER_GRPC,
                https=settings.QDRANT_HTTPS,
                api_key=settings.QDRANT_API_KEY if settings.QDRANT_API_KEY else None,
                timeout=10.0,
            )
            if settings.QDRANT_PREFER_GRPC:
                logger.info("QdrantClient mit prefer_grpc=True initialisiert (Host: %s, Port: %s, gRPC: %s).",
                            settings.QDRANT_HOST, settings.QDRANT_PORT, settings.QDRANT_GRPC_PORT)
        except Exception as e:
            if settings.QDRANT_PREFER_GRPC:
                logger.warning("gRPC-Initialisierung für Qdrant fehlgeschlagen (%s), falle auf HTTP-REST zurück...", e)
                self.client = QdrantClient(
                    host=settings.QDRANT_HOST,
                    port=settings.QDRANT_PORT,
                    prefer_grpc=False,
                    https=settings.QDRANT_HTTPS,
                    api_key=settings.QDRANT_API_KEY if settings.QDRANT_API_KEY else None,
                    timeout=10.0,
                )
            else:
                raise

    def init_collections(self) -> None:
        """
        Initialisiert die Collections:
        - archive_images (512-dim, Cosine) für OpenCLIP ViT-B-32
        - archive_faces (512-dim, Cosine) für InsightFace/ArcFace
        """
        existing_collections = [c.name for c in self.client.get_collections().collections]

        # 1. Image Collection
        if settings.COLLECTION_IMAGES not in existing_collections:
            logger.info("Erstelle Collection '%s' mit skalarer INT8-Quantisierung...", settings.COLLECTION_IMAGES)
            self.client.create_collection(
                collection_name=settings.COLLECTION_IMAGES,
                vectors_config=rest_models.VectorParams(
                    size=settings.CLIP_VECTOR_SIZE,
                    distance=rest_models.Distance.COSINE,
                ),
                quantization_config=rest_models.ScalarQuantization(
                    scalar=rest_models.ScalarQuantizationConfig(
                        type=rest_models.ScalarType.INT8,
                        quantile=0.99,
                        always_ram=True,
                    )
                ),
            )
            # Payload Index für schnelle Pfad-Suchen und Metadaten-Filter
            for field in ["file_path", "image_path", "relative_path", "title", "creator", "date", "signature", "keywords"]:
                self.client.create_payload_index(
                    collection_name=settings.COLLECTION_IMAGES,
                    field_name=field,
                    field_schema=rest_models.PayloadSchemaType.KEYWORD,
                )
            logger.info("Collection '%s' erfolgreich erstellt.", settings.COLLECTION_IMAGES)
        else:
            logger.info("Collection '%s' existiert bereits. Aktiviere INT8-Quantisierung falls nötig...", settings.COLLECTION_IMAGES)
            self.enable_scalar_quantization(settings.COLLECTION_IMAGES)

        # 2. Face Collection
        if settings.COLLECTION_FACES not in existing_collections:
            logger.info("Erstelle Collection '%s' mit skalarer INT8-Quantisierung...", settings.COLLECTION_FACES)
            self.client.create_collection(
                collection_name=settings.COLLECTION_FACES,
                vectors_config=rest_models.VectorParams(
                    size=settings.FACE_VECTOR_SIZE,
                    distance=rest_models.Distance.COSINE,
                ),
                quantization_config=rest_models.ScalarQuantization(
                    scalar=rest_models.ScalarQuantizationConfig(
                        type=rest_models.ScalarType.INT8,
                        quantile=0.99,
                        always_ram=True,
                    )
                ),
            )
            # Payload Indizes für Metadaten: file_path, image_path, relative_path, face_id, cluster_id, label
            for field in ["file_path", "image_path", "relative_path", "face_id", "cluster_id", "label"]:
                self.client.create_payload_index(
                    collection_name=settings.COLLECTION_FACES,
                    field_name=field,
                    field_schema=rest_models.PayloadSchemaType.KEYWORD,
                )
            logger.info("Collection '%s' erfolgreich erstellt.", settings.COLLECTION_FACES)
        else:
            logger.info("Collection '%s' existiert bereits. Aktiviere INT8-Quantisierung falls nötig...", settings.COLLECTION_FACES)
            self.enable_scalar_quantization(settings.COLLECTION_FACES)

    def enable_scalar_quantization(self, collection_name: str) -> bool:
        """Aktiviert skalare INT8-Quantisierung (75% RAM-Ersparnis, 3-4x schnellere Distanzsuche)."""
        try:
            self.client.update_collection(
                collection_name=collection_name,
                quantization_config=rest_models.ScalarQuantization(
                    scalar=rest_models.ScalarQuantizationConfig(
                        type=rest_models.ScalarType.INT8,
                        quantile=0.99,
                        always_ram=True,
                    )
                ),
            )
            return True
        except Exception as e:
            logger.debug("Skalare Quantisierung für '%s' konnte nicht aktualisiert werden: %s", collection_name, e)
            return False

    def set_indexing_threshold(self, collection_name: str, threshold: int) -> bool:
        """
        Steuert den HNSW-Indexbau-Schwellenwert (OptimizersConfigDiff.indexing_threshold):
        - threshold = 0: Deaktiviert den HNSW-Indexbau während großer Massen-Imports vollständig
          (spart bis zu 70 % Rechenzeit und verhindert ständiges Reorganisieren von HNSW-Segmenten).
        - threshold > 0 (z.B. 20000): Reaktiviert die automatische Hintergrund-Indexierung und startet
          den einmaligen optimierten Aufbau des Vektor-Index.
        """
        try:
            self.client.update_collection(
                collection_name=collection_name,
                optimizer_config=rest_models.OptimizersConfigDiff(
                    indexing_threshold=threshold
                ),
            )
            logger.info("HNSW-Indexierungsschwellenwert für '%s' auf %d gesetzt.", collection_name, threshold)
            return True
        except Exception as e:
            logger.warning("Konnte Indexierungs-Schwellenwert für '%s' nicht anpassen: %s", collection_name, e)
            return False

    def upsert_images(self, points: List[rest_models.PointStruct], wait: bool = False) -> None:
        """Fügt Bild-Embeddings in archive_images ein (asynchron/nicht-blockierend via wait=False)."""
        if not points:
            return
        self.client.upsert(
            collection_name=settings.COLLECTION_IMAGES,
            points=points,
            wait=wait,
        )

    def upsert_faces(self, points: List[rest_models.PointStruct], wait: bool = False) -> None:
        """Fügt Gesichts-Embeddings in archive_faces ein (asynchron/nicht-blockierend via wait=False)."""
        if not points:
            return
        self.client.upsert(
            collection_name=settings.COLLECTION_FACES,
            points=points,
            wait=wait,
        )

    def delete_images(self, image_ids: List[str]) -> None:
        """Löscht Bild-Points aus archive_images anhand ihrer IDs."""
        if not image_ids:
            return
        self.client.delete(
            collection_name=settings.COLLECTION_IMAGES,
            points_selector=rest_models.PointIdsList(points=image_ids),
        )

    def delete_faces_by_parent_images(self, parent_image_ids: List[str], file_paths: Optional[List[str]] = None) -> None:
        """Löscht Gesichts-Points aus archive_faces, die zu den angegebenen Bild-IDs oder Pfaden gehören."""
        if not parent_image_ids and not file_paths:
            return

        conditions = []
        for p_id in parent_image_ids:
            conditions.append(rest_models.FieldCondition(key="parent_image_id", match=rest_models.MatchValue(value=p_id)))
        if file_paths:
            for fp in file_paths:
                conditions.append(rest_models.FieldCondition(key="file_path", match=rest_models.MatchValue(value=fp)))
                conditions.append(rest_models.FieldCondition(key="image_path", match=rest_models.MatchValue(value=fp)))

        if conditions:
            self.client.delete(
                collection_name=settings.COLLECTION_FACES,
                points_selector=rest_models.FilterSelector(
                    filter=rest_models.Filter(should=conditions)
                ),
            )

    def prune_orphaned_records(
        self,
        source_dir: Optional[Path] = None,
        dry_run: bool = False,
        batch_size: int = 250,
    ) -> dict[str, Any]:
        """
        Prüft alle Einträge in archive_images gegen das lokale Dateisystem.
        Löscht verwaiste Einträge aus archive_images und archive_faces, falls
        die Bilddatei nicht mehr existiert (Art. 17 DSGVO / Datenhygiene).
        """
        offset = None
        total_scanned = 0
        orphaned_ids: List[str] = []
        orphaned_paths: List[str] = []

        while True:
            records, next_offset = self.client.scroll(
                collection_name=settings.COLLECTION_IMAGES,
                limit=batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )

            for record in records:
                total_scanned += 1
                payload = record.payload or {}
                file_path_str = payload.get("file_path") or payload.get("image_path")
                rel_path_str = payload.get("relative_path")

                exists = False
                # 1. Absolute Pfadprüfung
                if file_path_str and Path(file_path_str).is_file():
                    exists = True
                # 2. Relative Pfadprüfung gegen source_dir
                elif source_dir and rel_path_str:
                    resolved = (source_dir / rel_path_str).resolve()
                    if resolved.is_file():
                        exists = True

                if not exists:
                    orphaned_ids.append(str(record.id))
                    if file_path_str:
                        orphaned_paths.append(file_path_str)

            if next_offset is None or len(records) == 0:
                break
            offset = next_offset

        # Bereinigung ausführen, falls kein Dry-Run
        if not dry_run and orphaned_ids:
            logger.info("Lösche %d verwaiste Bild-Points aus Qdrant...", len(orphaned_ids))
            self.delete_images(orphaned_ids)
            self.delete_faces_by_parent_images(orphaned_ids, file_paths=orphaned_paths)

        return {
            "total_scanned": total_scanned,
            "orphaned_count": len(orphaned_ids),
            "orphaned_ids": orphaned_ids,
            "orphaned_paths": orphaned_paths,
            "pruned": not dry_run,
        }

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
            "status": str(info.status),
            "points_count": getattr(info, "points_count", 0),
            "indexed_vectors_count": getattr(info, "indexed_vectors_count", 0),
            "segments_count": getattr(info, "segments_count", 0),
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
