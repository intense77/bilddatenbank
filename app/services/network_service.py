"""
Netzwerk- und Co-Occurrence-Service für historische Personen-Cluster.
Analysiert, welche Personen gemeinsam auf denselben Archivfotos abgebildet sind,
ermöglicht direkte Schnittmengen-Filter und generiert Beziehungs-Graphen für vis-network.
"""

import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import quote

from app.core.config import settings
from app.services.qdrant_service import QdrantService
from qdrant_client.http import models as rest_models

logger = logging.getLogger("archive_app.network_service")


def normalize_cluster_id(cid: Union[str, int]) -> str:
    """Normalisiert eine Cluster-ID (z. B. 83 -> 'cluster_83', '83' -> 'cluster_83')."""
    s = str(cid).strip()
    if s.isdigit():
        return f"cluster_{s}"
    return s


class NetworkService:
    def __init__(self, qdrant_service: Optional[QdrantService] = None):
        self.qdrant = qdrant_service or QdrantService()
        self._cluster_info_cache: Dict[str, Dict[str, Any]] = {}

    def _get_cluster_faces(self, cluster_id: str, limit: int = 1000) -> Tuple[Set[str], Optional[str], int]:
        """
        Holt alle Bildpfade, den Namen und die Gesichtsanzahl für einen Personen-Cluster.
        Nutzt den schnellen Keyword-Index auf 'cluster_id' in archive_faces.
        """
        c_id = normalize_cluster_id(cluster_id)
        try:
            records, _ = self.qdrant.client.scroll(
                collection_name=settings.COLLECTION_FACES,
                scroll_filter=rest_models.Filter(
                    must=[
                        rest_models.FieldCondition(
                            key="cluster_id",
                            match=rest_models.MatchValue(value=c_id),
                        )
                    ]
                ),
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
            paths = set()
            label = None
            for r in records:
                p = r.payload or {}
                fp = p.get("file_path") or p.get("image_path")
                if fp:
                    paths.add(fp)
                if not label and p.get("label"):
                    label = p["label"]

            # Fallback: Aus SQLite prüfen, falls Label dort gesetzt wurde
            if not label:
                try:
                    from app.services.metadata_db import metadata_db
                    c_row = metadata_db.get_cluster(c_id)
                    if c_row and c_row.get("name"):
                        label = c_row["name"]
                except Exception:
                    pass

            return paths, label, len(records)
        except Exception as e:
            logger.error("Fehler beim Abruf von Gesichtern für %s: %s", c_id, e)
            return set(), None, 0

    def get_co_occurrences(self, cluster_id: Union[int, str], limit: int = 15) -> List[Dict[str, Any]]:
        """
        Ermittelt alle Personen, die auf denselben Bildern wie cluster_id vorkommen.
        Rückgabe: Liste von dicts sortiert nach gemeinsamen Fotos absteigend.
        """
        c_id = normalize_cluster_id(cluster_id)
        img_paths, root_label, root_count = self._get_cluster_faces(c_id)
        if not img_paths:
            return []

        shared_map: Dict[str, Set[str]] = defaultdict(set)
        labels_map: Dict[str, str] = {}
        path_list = list(img_paths)

        # In Blöcken von 100 abfragen (MatchAny auf indiziertem Keyword 'file_path')
        for i in range(0, min(len(path_list), 600), 100):
            chunk = path_list[i : i + 100]
            try:
                other_faces, _ = self.qdrant.client.scroll(
                    collection_name=settings.COLLECTION_FACES,
                    scroll_filter=rest_models.Filter(
                        must=[
                            rest_models.FieldCondition(
                                key="file_path",
                                match=rest_models.MatchAny(any=chunk),
                            )
                        ]
                    ),
                    limit=2000,
                    with_payload=True,
                    with_vectors=False,
                )
                for f in other_faces:
                    p = f.payload or {}
                    other_cid = p.get("cluster_id")
                    if not other_cid or other_cid == c_id:
                        continue
                    fp = p.get("file_path") or p.get("image_path")
                    if fp:
                        shared_map[other_cid].add(fp)
                    lbl = p.get("label")
                    if lbl and other_cid not in labels_map:
                        labels_map[other_cid] = lbl
            except Exception as e:
                logger.warning("Fehler beim Abruf von Co-Occurrences Chunk %d: %s", i, e)

        # Aus SQLite fehlende Labels ergänzen
        try:
            from app.services.metadata_db import metadata_db
            for other_cid in shared_map:
                if other_cid not in labels_map:
                    row = metadata_db.get_cluster(other_cid)
                    if row and row.get("name"):
                        labels_map[other_cid] = row["name"]
        except Exception:
            pass

        results: List[Dict[str, Any]] = []
        for other_cid, paths in shared_map.items():
            num_clean = other_cid.replace("cluster_", "")
            name = labels_map.get(other_cid) or f"Person #{num_clean}"
            results.append({
                "cluster_id": other_cid,
                "name": name,
                "shared_count": len(paths),
                "thumbnail_url": f"/faces/clusters/{other_cid}/preview",
            })

        results.sort(key=lambda x: x["shared_count"], reverse=True)
        return results[:limit]

    def get_shared_images(
        self,
        cluster_a: Union[int, str],
        cluster_b: Union[int, str],
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Liefert die Schnittmenge aller Bilder, auf denen beide Personen gleichzeitig markiert sind.
        """
        cid_a = normalize_cluster_id(cluster_a)
        cid_b = normalize_cluster_id(cluster_b)

        paths_a, label_a, _ = self._get_cluster_faces(cid_a)
        paths_b, label_b, _ = self._get_cluster_faces(cid_b)

        shared_paths = list(paths_a & paths_b)
        if not shared_paths:
            return []

        # Metadaten für die gemeinsamen Bilder ermitteln
        images_info: List[Dict[str, Any]] = []
        for fp in shared_paths[:limit]:
            p = Path(fp)
            fn = p.name
            safe_path = quote(fp)

            item = {
                "file_path": fp,
                "file_name": fn,
                "preview_url": f"/images/serve?path={safe_path}&max_dim=600",
                "raw_url": f"/images/serve?path={safe_path}",
                "title": fn,
                "date": None,
                "persons": [
                    label_a or f"Person #{cid_a.replace('cluster_', '')}",
                    label_b or f"Person #{cid_b.replace('cluster_', '')}",
                ],
            }

            # Optional archivische Metadaten aus SQLite
            try:
                from app.services.metadata_db import metadata_db
                meta = metadata_db.get_metadata(fp)
                if meta:
                    if meta.get("title"):
                        item["title"] = meta["title"]
                    if meta.get("date"):
                        item["date"] = meta["date"]
            except Exception:
                pass

            images_info.append(item)

        return images_info

    def get_network_graph(
        self,
        cluster_id: Union[int, str],
        depth: int = 1,
        min_shared: int = 2,
    ) -> Dict[str, Any]:
        """
        Baut ein Knoten-Kanten-JSON (nodes, edges) für vis-network:
        - nodes: id, label, image, size, shape
        - edges: from, to, value (gemeinsame Fotos)
        Berechnet auch inter-personelle Kanten zwischen Nachbarn (Cliquen/Dreiecke).
        """
        root_cid = normalize_cluster_id(cluster_id)
        root_paths, root_label, root_count = self._get_cluster_faces(root_cid)

        clean_root_num = root_cid.replace("cluster_", "")
        root_name = root_label or f"Person #{clean_root_num}"

        # Co-Occurrences ermitteln
        co_list = self.get_co_occurrences(root_cid, limit=25)

        # Filter nach min_shared
        filtered_neighbors = [c for c in co_list if c["shared_count"] >= min_shared]
        if not filtered_neighbors and co_list:
            # Fallback, falls keine >= min_shared existieren
            filtered_neighbors = co_list[:5]

        # Wenn depth == 2, expandiere für die Top 3 Nachbarn
        active_clusters: Dict[str, Set[str]] = {root_cid: root_paths}
        names_map: Dict[str, str] = {root_cid: root_name}

        for n in filtered_neighbors[:15]:
            cid = n["cluster_id"]
            paths, lbl, _ = self._get_cluster_faces(cid)
            active_clusters[cid] = paths
            names_map[cid] = n["name"]

        if depth >= 2:
            top_neighbors = filtered_neighbors[:3]
            for n in top_neighbors:
                second_degree = self.get_co_occurrences(n["cluster_id"], limit=6)
                for s in second_degree:
                    s_cid = s["cluster_id"]
                    if s_cid not in active_clusters and s["shared_count"] >= min_shared:
                        paths, lbl, _ = self._get_cluster_faces(s_cid)
                        active_clusters[s_cid] = paths
                        names_map[s_cid] = s["name"]

        # Knoten (Nodes) aufbauen
        nodes: List[Dict[str, Any]] = []
        for cid, paths in active_clusters.items():
            is_root = cid == root_cid
            name = names_map.get(cid) or f"Person #{cid.replace('cluster_', '')}"
            face_cnt = len(paths)

            nodes.append({
                "id": cid,
                "label": name,
                "image": f"/faces/clusters/{cid}/preview",
                "shape": "circularImage",
                "size": 38 if is_root else max(18, min(32, 16 + face_cnt // 10)),
                "borderWidth": 4 if is_root else 2,
                "color": {
                    "border": "#f59e0b" if is_root else "#64748b",
                    "background": "#1e293b",
                    "highlight": {"border": "#fbbf24", "background": "#334155"},
                },
                "font": {
                    "color": "#fbbf24" if is_root else "#e2e8f0",
                    "size": 13 if is_root else 11,
                    "face": "system-ui, sans-serif",
                    "bold": is_root,
                },
                "title": f"<b>{name}</b><br>{face_cnt} Aufnahmen im Archiv",
                "face_count": face_cnt,
                "is_root": is_root,
            })

        # Kanten (Edges) aufbauen: Zwischen allen Paaren in active_clusters
        edges: List[Dict[str, Any]] = []
        cluster_keys = list(active_clusters.keys())
        for idx_a in range(len(cluster_keys)):
            for idx_b in range(idx_a + 1, len(cluster_keys)):
                cid_a = cluster_keys[idx_a]
                cid_b = cluster_keys[idx_b]
                shared = len(active_clusters[cid_a] & active_clusters[cid_b])

                if shared >= (min_shared if root_cid in (cid_a, cid_b) else max(2, min_shared)):
                    is_direct_root = root_cid in (cid_a, cid_b)
                    edges.append({
                        "from": cid_a,
                        "to": cid_b,
                        "value": shared,
                        "title": f"{shared} gemeinsame Fotos",
                        "color": {
                            "color": "rgba(245, 158, 11, 0.7)" if is_direct_root else "rgba(100, 116, 139, 0.35)",
                            "highlight": "#fbbf24",
                            "hover": "#f59e0b",
                        },
                        "smooth": {"type": "continuous"},
                    })

        return {
            "center_cluster_id": root_cid,
            "center_name": root_name,
            "nodes": nodes,
            "edges": edges,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
        }
