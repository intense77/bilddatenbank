import io
import base64
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
from PIL import Image
from sklearn.cluster import DBSCAN
from qdrant_client.http import models as rest_models

from app.core.config import settings
from app.services.qdrant_service import QdrantService
from app.services.clip_service import load_image_rgb

logger = logging.getLogger(__name__)


def generate_face_crop_base64(
    file_path: str,
    bbox: List[int],
    target_size: int = 160,
    padding_pct: float = 0.15,
) -> Optional[str]:
    """
    Schneidet das Gesicht basierend auf der Bounding Box aus und gibt einen
    Base64-kodierten JPEG-String (Data URL) für Vorschaubilder zurück.
    Nutzt den Thumbnail-Cache, um wiederholte Dekodierungen großer Scans zu vermeiden.
    """
    try:
        from app.services.thumbnail_service import thumbnail_service
        path = Path(file_path)
        crop_bytes = thumbnail_service.get_or_create_face_crop(
            file_path=path,
            bbox=bbox,
            target_size=target_size,
            padding_pct=padding_pct,
        )
        if not crop_bytes:
            return None
        encoded = base64.b64encode(crop_bytes).decode("utf-8")
        return f"data:image/jpeg;base64,{encoded}"
    except Exception as e:
        logger.warning("Vorschaubild konnte nicht generiert werden (%s, bbox=%s): %s", file_path, bbox, e)
        return None


class ClusteringService:
    """
    Service zur automatischen Personen-Clusterung aus Gesichts-Embeddings.
    Lädt alle Gesichter aus Qdrant, wendet DBSCAN an und aktualisiert die cluster_id.
    """

    def __init__(self, qdrant_service: Optional[QdrantService] = None):
        self.qdrant = qdrant_service or QdrantService()

    def fetch_all_faces(self, batch_size: int = 500, with_vectors: bool = True) -> List[Dict[str, Any]]:
        """Lädt Punkte aus der Collection archive_faces, optional ohne Vektoren zur Speicherschonung."""
        faces = []
        offset = None

        while True:
            records, next_offset = self.qdrant.client.scroll(
                collection_name=settings.COLLECTION_FACES,
                limit=batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=with_vectors,
            )

            for record in records:
                faces.append({
                    "id": record.id,
                    "vector": getattr(record, "vector", None),
                    "payload": record.payload or {},
                })

            if next_offset is None or len(records) == 0:
                break
            offset = next_offset

        return faces

    def run_clustering(
        self,
        eps: float = 0.55,
        min_samples: int = 2,
    ) -> Dict[str, Any]:
        """
        Führt das DBSCAN-Clustering für alle Gesichter durch:
        - DBSCAN(eps=0.55, min_samples=2, metric='cosine')
        - Aktualisiert cluster_id im Qdrant-Payload
        """
        logger.info("Lade Gesichts-Embeddings aus Qdrant ('%s')...", settings.COLLECTION_FACES)
        faces = self.fetch_all_faces()
        total_faces = len(faces)
        logger.info("%d Gesichts-Punkte aus Qdrant geladen.", total_faces)

        if total_faces < min_samples:
            logger.info("Zu wenige Gesichter (%d) für Clustering (min_samples=%d).", total_faces, min_samples)
            return {
                "total_faces": total_faces,
                "clusters_found": 0,
                "clustered_faces": 0,
                "noise_faces": total_faces,
                "message": "Zu wenige Gesichter für die Clusterung vorhanden.",
            }

        # Embeddings als Matrix vorbereiten
        vectors = np.array([f["vector"] for f in faces], dtype=np.float32)

        # DBSCAN ausführen
        logger.info("Führe DBSCAN(eps=%.2f, min_samples=%d, metric='cosine') aus...", eps, min_samples)
        dbscan = DBSCAN(eps=eps, min_samples=min_samples, metric="cosine")
        labels = dbscan.fit_predict(vectors)

        cluster_counts: Dict[str, int] = {}
        points_by_cluster: Dict[str, List[Any]] = {}
        noise_points: List[Any] = []

        for face, label in zip(faces, labels):
            point_id = face["id"]
            if label == -1:
                noise_points.append(point_id)
            else:
                c_id = f"cluster_{label}"
                points_by_cluster.setdefault(c_id, []).append(point_id)
                cluster_counts[c_id] = cluster_counts.get(c_id, 0) + 1

        logger.info(
            "Clustering abgeschlossen: %d Cluster identifiziert, %d Gesichter zugeordnet, %d Einzelgänger/Rauschen.",
            len(points_by_cluster),
            sum(cluster_counts.values()),
            len(noise_points),
        )

        # Qdrant Payload aktualisieren
        # 1. Geclusterte Punkte
        for c_id, point_ids in points_by_cluster.items():
            self.qdrant.client.set_payload(
                collection_name=settings.COLLECTION_FACES,
                payload={"cluster_id": c_id},
                points=point_ids,
            )

        # 2. Rauschen / Ungeclusterte Punkte auf None setzen
        if noise_points:
            self.qdrant.client.set_payload(
                collection_name=settings.COLLECTION_FACES,
                payload={"cluster_id": None},
                points=noise_points,
            )

        return {
            "total_faces": total_faces,
            "clusters_found": len(points_by_cluster),
            "clustered_faces": sum(cluster_counts.values()),
            "noise_faces": len(noise_points),
            "clusters": cluster_counts,
        }

    def get_clusters(self, include_preview: bool = True) -> List[Dict[str, Any]]:
        """
        Gibt alle gefundenen Personen-Cluster zurück, aggregiert aus Qdrant.
        Enthält Anzahl, Label sowie Vorschaubilder via Bounding-Box-Crop.
        """
        faces = self.fetch_all_faces(with_vectors=False)
        clusters_map: Dict[str, Dict[str, Any]] = {}

        for face in faces:
            payload = face["payload"]
            cluster_id = payload.get("cluster_id")
            if not cluster_id:
                continue

            file_path = payload.get("file_path") or payload.get("image_path")
            bbox = payload.get("bbox")
            det_score = payload.get("det_score", 1.0)
            label = payload.get("label")

            if cluster_id not in clusters_map:
                clusters_map[cluster_id] = {
                    "cluster_id": cluster_id,
                    "label": label,
                    "face_count": 0,
                    "faces": [],
                    "preview_image": None,
                }

            # Wenn ein Punkt ein Label hat, für den Cluster übernehmen
            if label and not clusters_map[cluster_id]["label"]:
                clusters_map[cluster_id]["label"] = label

            face_entry = {
                "face_id": str(face["id"]),
                "file_path": file_path,
                "bbox": bbox,
                "det_score": det_score,
            }

            clusters_map[cluster_id]["faces"].append(face_entry)
            clusters_map[cluster_id]["face_count"] += 1

            # Erstes valides Vorschaubild als Repräsentant für den Cluster setzen
            if include_preview and clusters_map[cluster_id]["preview_image"] is None and file_path and bbox:
                preview = generate_face_crop_base64(file_path, bbox)
                if preview:
                    clusters_map[cluster_id]["preview_image"] = preview

        # Sortiere nach Häufigkeit (größte Cluster zuerst)
        sorted_clusters = sorted(clusters_map.values(), key=lambda c: c["face_count"], reverse=True)
        return sorted_clusters

    def label_cluster(self, cluster_id: str, label: str) -> int:
        """
        Weist allen Gesichtern eines Personen-Clusters einen Klarnamen zu.
        Aktualisiert den Payload in Qdrant.
        """
        # Suche alle Punkte des Clusters
        records, _ = self.qdrant.client.scroll(
            collection_name=settings.COLLECTION_FACES,
            scroll_filter=rest_models.Filter(
                must=[
                    rest_models.FieldCondition(
                        key="cluster_id",
                        match=rest_models.MatchValue(value=cluster_id),
                    )
                ]
            ),
            limit=10000,
            with_payload=False,
            with_vectors=False,
        )

        point_ids = [r.id for r in records]
        if not point_ids:
            return 0

        self.qdrant.client.set_payload(
            collection_name=settings.COLLECTION_FACES,
            payload={"label": label.strip()},
            points=point_ids,
        )
        logger.info("Cluster '%s' mit Label '%s' versehen (%d Gesichter).", cluster_id, label, len(point_ids))
        return len(point_ids)
