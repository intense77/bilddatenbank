import io
import time
import math
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
from app.services.metadata_db import metadata_db

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
        mime = "image/webp" if crop_bytes.startswith(b"RIFF") else "image/jpeg"
        encoded = base64.b64encode(crop_bytes).decode("utf-8")
        return f"data:{mime};base64,{encoded}"
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
        self._clusters_cache: Optional[List[Dict[str, Any]]] = None
        self._cache_timestamp: float = 0.0

    def invalidate_clusters_cache(self):
        """Invalidiert den Zwischenspeicher der Cluster-Listen."""
        self._clusters_cache = None
        self._cache_timestamp = 0.0

    def fetch_all_faces(self, batch_size: int = 2000, with_vectors: bool = True) -> List[Dict[str, Any]]:
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

        # DBSCAN mit Raumteilungsbäumen (Ball-Tree) ausführen:
        # Da ArcFace L2-normalisiert ist, gilt: dist_euclid = sqrt(2 * dist_cosine).
        # algorithm='ball_tree' reduziert Speicher und Laufzeit von O(N^2) auf O(N log N).
        # leaf_size und n_jobs werden adaptiv aus dem erkannten Hardware-Profil bezogen.
        from app.core.system_profile import current_hardware_profile
        eps_euclid = float(math.sqrt(2.0 * max(0.0, eps)))
        n_workers = max(1, min(current_hardware_profile.cpu_cores, 8))
        logger.info(
            "Führe DBSCAN(eps_euclid=%.4f [aus cosine=%.2f], min_samples=%d, metric='euclidean', algorithm='ball_tree', leaf_size=%d, n_jobs=%d) aus...",
            eps_euclid,
            eps,
            min_samples,
            current_hardware_profile.clustering_leaf_size,
            n_workers,
        )
        dbscan = DBSCAN(
            eps=eps_euclid,
            min_samples=min_samples,
            metric="euclidean",
            algorithm="ball_tree",
            leaf_size=current_hardware_profile.clustering_leaf_size,
            n_jobs=n_workers,
        )
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

        # 3. Synchronisation in die relationale SQLite-Tabelle für Sub-5ms Frontend-Abfragen
        clusters_to_sync = [
            {
                "cluster_id": c_id,
                "face_count": count,
                "preview_image": f"/faces/clusters/{c_id}/preview",
            }
            for c_id, count in cluster_counts.items()
        ]
        metadata_db.bulk_sync_clusters(clusters_to_sync)

        self.invalidate_clusters_cache()
        return {
            "total_faces": total_faces,
            "clusters_found": len(points_by_cluster),
            "clustered_faces": sum(cluster_counts.values()),
            "noise_faces": len(noise_points),
            "clusters": cluster_counts,
        }

    def get_clusters(self, include_preview: bool = True, include_faces: bool = False) -> List[Dict[str, Any]]:
        """
        Gibt alle gefundenen Personen-Cluster zurück.
        - Liest für die Übersichtsliste primär aus SQLite (< 5 ms Reaktionszeit).
        - Falls SQLite noch leer ist, Fallback auf Qdrant-Aggregation mit anschließendem Sync.
        - include_preview: Wenn True, URL /faces/clusters/{cluster_id}/preview übergeben.
        - include_faces: Wenn True, Gesichts-Details einbetten (für Detailansichten).
        """
        now = time.time()
        if not include_faces:
            if self._clusters_cache is not None and (now - self._cache_timestamp) < 60:
                return self._clusters_cache

            # 1. Primärer Pfad: Blitzschneller Abruf aus SQLite (< 5 ms statt 13,5 s Qdrant-Scroll)
            sqlite_clusters = metadata_db.get_clusters_summary()
            if sqlite_clusters:
                self._clusters_cache = sqlite_clusters
                self._cache_timestamp = now
                return sqlite_clusters

        # 2. Fallback auf vollständige Qdrant-Aggregation falls SQLite noch nicht befüllt ist
        faces = self.fetch_all_faces(batch_size=2000, with_vectors=False)
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
                    "preview_image": f"/faces/clusters/{cluster_id}/preview" if include_preview else None,
                }

            if label and not clusters_map[cluster_id]["label"]:
                clusters_map[cluster_id]["label"] = label

            if include_faces:
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

        # Sortiere nach Häufigkeit (größte Cluster zuerst)
        sorted_clusters = sorted(clusters_map.values(), key=lambda c: c["face_count"], reverse=True)

        # In SQLite persistieren, damit zukünftige Aufrufe sofort aus SQLite geliefert werden
        try:
            metadata_db.bulk_sync_clusters(sorted_clusters)
        except Exception as e:
            logger.warning("Konnte Cluster-Aggregation nicht in SQLite synchronisieren: %s", e)

        self._clusters_cache = sorted_clusters
        self._cache_timestamp = now
        return sorted_clusters

    def get_cluster_details(self, cluster_id: str) -> Optional[Dict[str, Any]]:
        """Lädt alle Gesichter und Metadaten für ein einzelnes Personen-Cluster effizient on demand."""
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
            limit=500,
            with_payload=True,
            with_vectors=False,
        )
        if not records:
            return None

        faces = []
        label = None

        for r in records:
            p = r.payload or {}
            if not label and p.get("label"):
                label = p.get("label")
            file_path = p.get("file_path") or p.get("image_path")
            bbox = p.get("bbox")

            orig_w = p.get("orig_width")
            orig_h = p.get("orig_height")
            bbox_pct = p.get("bbox_percent")
            if not bbox_pct and orig_w and orig_h and bbox and len(bbox) == 4:
                x1, y1, x2, y2 = bbox
                bbox_pct = {
                    "left": round((x1 / orig_w) * 100, 4),
                    "top": round((y1 / orig_h) * 100, 4),
                    "width": round(((x2 - x1) / orig_w) * 100, 4),
                    "height": round(((y2 - y1) / orig_h) * 100, 4),
                }

            faces.append({
                "face_id": str(r.id),
                "file_path": file_path,
                "bbox": bbox,
                "bbox_percent": bbox_pct,
                "orig_width": orig_w,
                "orig_height": orig_h,
                "det_score": p.get("det_score", 1.0),
            })

        return {
            "cluster_id": cluster_id,
            "label": label,
            "face_count": len(faces),
            "preview_image": f"/faces/clusters/{cluster_id}/preview",
            "faces": faces,
        }

    def get_cluster_preview_bytes(self, cluster_id: str) -> Optional[bytes]:
        """Liefert die JPEG-Bytes des Vorschaubildes eines Clusters über den schnellen Thumbnail-Cache."""
        from app.services.thumbnail_service import thumbnail_service
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
            limit=1,
            with_payload=True,
            with_vectors=False,
        )
        if not records:
            return None

        p = records[0].payload or {}
        file_path = p.get("file_path") or p.get("image_path")
        bbox = p.get("bbox")
        if not file_path or not bbox:
            return None

        path = Path(file_path)
        if not path.is_file():
            return None

        return thumbnail_service.get_or_create_face_crop(path, bbox=bbox, target_size=160)


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
        # In SQLite persistieren für sofortige Verfügbarkeit in get_clusters()
        try:
            metadata_db.upsert_cluster(cluster_id, name=clean_label, face_count=len(point_ids))
        except Exception as e:
            logger.warning("Konnte Cluster-Label nicht in SQLite synchronisieren: %s", e)

        self.invalidate_clusters_cache()
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

                # Automatisches Synchronisieren des XMP-Sidecars nach GLAM-Archivstandard
                try:
                    from app.services.xmp_service import xmp_service
                    img_records = self.qdrant.client.retrieve(
                        collection_name=settings.COLLECTION_IMAGES,
                        ids=[img_id],
                        with_payload=True
                    )
                    if img_records and img_records[0].payload:
                        p = img_records[0].payload
                        fp = p.get("file_path") or p.get("image_path")
                        if fp:
                            xmp_service.write_sidecar(
                                image_path=fp,
                                title=p.get("title"),
                                creator=p.get("creator"),
                                date=p.get("date"),
                                signature=p.get("signature"),
                                description=p.get("description"),
                                persons=distinct_labels,
                            )
                except Exception as xmp_err:
                    logger.debug("Automatisches XMP-Sidecar Schreiben übersprungen: %s", xmp_err)

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
        if old_cluster:
            try:
                cluster_info = metadata_db.get_cluster(old_cluster)
                if cluster_info and cluster_info.get("face_count"):
                    new_count = max(0, cluster_info["face_count"] - 1)
                    metadata_db.upsert_cluster(old_cluster, face_count=new_count)
            except Exception as e:
                logger.debug("Konnte face_count in SQLite nicht dekrementieren: %s", e)

        self.invalidate_clusters_cache()
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

        # In SQLite Quell-Cluster löschen und Ziel-Cluster mit neuem Zähler/Label aktualisieren
        try:
            metadata_db.delete_cluster(source_cluster_id)
            total_faces = len(source_point_ids) + len(target_point_ids)
            metadata_db.upsert_cluster(target_cluster_id, name=final_label, face_count=total_faces)
        except Exception as e:
            logger.warning("Konnte Cluster-Merge nicht in SQLite synchronisieren: %s", e)

        self.invalidate_clusters_cache()

        return {
            "status": "success",
            "merged_count": len(source_point_ids),
            "source_cluster_id": source_cluster_id,
            "target_cluster_id": target_cluster_id,
            "total_faces": len(source_point_ids) + len(target_point_ids),
            "label": final_label,
            "affected_images": len(affected_parent_ids),
        }
