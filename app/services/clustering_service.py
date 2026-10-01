import io
import base64
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
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

            orig_w = payload.get("orig_width")
            orig_h = payload.get("orig_height")
            bbox_pct = payload.get("bbox_percent")
            if not bbox_pct and orig_w and orig_h and bbox and len(bbox) == 4:
                x1, y1, x2, y2 = bbox
                bbox_pct = {
                    "left": round((x1 / orig_w) * 100, 4),
                    "top": round((y1 / orig_h) * 100, 4),
                    "width": round(((x2 - x1) / orig_w) * 100, 4),
                    "height": round(((y2 - y1) / orig_h) * 100, 4),
                }

            face_entry = {
                "face_id": str(face["id"]),
                "file_path": file_path,
                "bbox": bbox,
                "bbox_percent": bbox_pct,
                "orig_width": orig_w,
                "orig_height": orig_h,
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
        Aktualisiert den Payload in Qdrant (sowohl in archive_faces als auch in archive_images).
        """
        clean_label = label.strip()

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
            with_payload=True,
            with_vectors=False,
        )

        point_ids = [r.id for r in records]
        if not point_ids:
            return 0

        # 1. Label in archive_faces aktualisieren
        self.qdrant.client.set_payload(
            collection_name=settings.COLLECTION_FACES,
            payload={"label": clean_label},
            points=point_ids,
        )

        # 2. Zugehörige Bilder in archive_images ermitteln und deren Personen-Liste synchronisieren
        parent_img_ids = {
            r.payload.get("parent_image_id")
            for r in records
            if r.payload and r.payload.get("parent_image_id")
        }
        self._sync_parent_images_persons(parent_img_ids)

        logger.info(
            "Cluster '%s' mit Label '%s' versehen (%d Gesichter, %d Bilder aktualisiert).",
            cluster_id,
            clean_label,
            len(point_ids),
            len(parent_img_ids),
        )
        return len(point_ids)

    def _sync_parent_images_persons(self, parent_img_ids: Set[str]) -> None:
        """
        Synchronisiert das 'persons'-Feld in archive_images für eine Menge von Elternbildern
        anhand aller verbleibenden gelabelten Gesichter in archive_faces.
        """
        for img_id in parent_img_ids:
            try:
                img_faces, _ = self.qdrant.client.scroll(
                    collection_name=settings.COLLECTION_FACES,
                    scroll_filter=rest_models.Filter(
                        must=[
                            rest_models.FieldCondition(
                                key="parent_image_id",
                                match=rest_models.MatchValue(value=img_id),
                            )
                        ]
                    ),
                    limit=100,
                    with_payload=True,
                    with_vectors=False,
                )
                distinct_labels = sorted(list({
                    f.payload.get("label").strip()
                    for f in img_faces
                    if f.payload and f.payload.get("label") and f.payload.get("label").strip()
                }))
                self.qdrant.client.set_payload(
                    collection_name=settings.COLLECTION_IMAGES,
                    payload={"persons": distinct_labels},
                    points=[img_id],
                )
            except Exception as e:
                logger.warning("Konnte Elternbild %s nicht mit Personenliste aktualisieren: %s", img_id, e)

    def remove_face_from_cluster(self, face_id: str) -> bool:
        """
        Entfernt ein Gesicht aus einem Personen-Cluster (Ausschluss / 'Nicht diese Person').
        Löscht cluster_id und label aus dem Qdrant-Payload und synchronisiert das Elternbild.
        """
        records = self.qdrant.client.retrieve(
            collection_name=settings.COLLECTION_FACES,
            ids=[face_id],
            with_payload=True,
            with_vectors=False,
        )
        if not records:
            return False

        point = records[0]
        payload = point.payload or {}
        parent_img_id = payload.get("parent_image_id")
        old_cluster = payload.get("cluster_id")

        # Aus Cluster entfernen: cluster_id und label aus dem Payload löschen
        self.qdrant.client.delete_payload(
            collection_name=settings.COLLECTION_FACES,
            keys=["cluster_id", "label"],
            points=[face_id],
        )

        if parent_img_id:
            self._sync_parent_images_persons({parent_img_id})

        logger.info("Gesicht %s aus Cluster '%s' entfernt.", face_id, old_cluster)
        return True

    def merge_clusters(
        self,
        source_cluster_id: str,
        target_cluster_id: str,
        target_label: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Führt zwei Personen-Cluster zusammen:
        - Weist allen Gesichtern von source_cluster_id die target_cluster_id zu.
        - Bestimmt ein konsolidiertes Label (target_label, Ziel-Label oder Quell-Label).
        - Aktualisiert das Label für alle Gesichter im zusammengeführten Ziel-Cluster.
        - Synchronisiert die Personen-Metadaten aller betroffenen Elternbilder in archive_images.
        """
        if source_cluster_id == target_cluster_id:
            return {"status": "error", "message": "Quell- und Zielcluster dürfen nicht identisch sein.", "merged_count": 0}

        # Alle Gesichter des Quell-Clusters laden
        source_records, _ = self.qdrant.client.scroll(
            collection_name=settings.COLLECTION_FACES,
            scroll_filter=rest_models.Filter(
                must=[rest_models.FieldCondition(key="cluster_id", match=rest_models.MatchValue(value=source_cluster_id))]
            ),
            limit=10000,
            with_payload=True,
            with_vectors=False,
        )
        if not source_records:
            return {"status": "not_found", "merged_count": 0}

        source_point_ids = [r.id for r in source_records]

        # Alle Gesichter des Ziel-Clusters laden
        target_records, _ = self.qdrant.client.scroll(
            collection_name=settings.COLLECTION_FACES,
            scroll_filter=rest_models.Filter(
                must=[rest_models.FieldCondition(key="cluster_id", match=rest_models.MatchValue(value=target_cluster_id))]
            ),
            limit=10000,
            with_payload=True,
            with_vectors=False,
        )
        target_point_ids = [r.id for r in target_records]

        # Konsolidiertes Label bestimmen
        final_label = None
        if target_label and target_label.strip():
            final_label = target_label.strip()
        else:
            # 1. Prüfe ob Ziel-Cluster bereits ein Label hat
            for r in target_records:
                l = (r.payload or {}).get("label")
                if l and l.strip():
                    final_label = l.strip()
                    break
            # 2. Falls nicht, prüfe ob Quell-Cluster ein Label hatte
            if not final_label:
                for r in source_records:
                    l = (r.payload or {}).get("label")
                    if l and l.strip():
                        final_label = l.strip()
                        break

        # Quell-Punkte auf Ziel-Cluster aktualisieren
        source_payload: Dict[str, Any] = {"cluster_id": target_cluster_id}
        if final_label:
            source_payload["label"] = final_label
        self.qdrant.client.set_payload(
            collection_name=settings.COLLECTION_FACES,
            payload=source_payload,
            points=source_point_ids,
        )

        # Falls ein final_label vorliegt, auch alle bestehenden Ziel-Punkte aktualisieren
        if final_label and target_point_ids:
            self.qdrant.client.set_payload(
                collection_name=settings.COLLECTION_FACES,
                payload={"label": final_label},
                points=target_point_ids,
            )

        # Alle betroffenen Elternbilder sammeln und synchronisieren
        affected_parent_ids = set()
        for r in source_records + target_records:
            pid = (r.payload or {}).get("parent_image_id")
            if pid:
                affected_parent_ids.add(pid)

        self._sync_parent_images_persons(affected_parent_ids)

        logger.info(
            "Cluster '%s' (%d Gesichter) erfolgreich in '%s' zusammengeführt (Label: '%s', %d Bilder aktualisiert).",
            source_cluster_id,
            len(source_point_ids),
            target_cluster_id,
            final_label,
            len(affected_parent_ids),
        )

        return {
            "status": "success",
            "merged_count": len(source_point_ids),
            "source_cluster_id": source_cluster_id,
            "target_cluster_id": target_cluster_id,
            "total_faces": len(source_point_ids) + len(target_point_ids),
            "label": final_label,
            "affected_images": len(affected_parent_ids),
        }
