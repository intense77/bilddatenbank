import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from PIL import Image, ImageOps
import imagehash
from sklearn.cluster import DBSCAN
from qdrant_client.http import models as rest_models

from app.core.config import settings
from app.services.qdrant_service import QdrantService
from app.services.clip_service import load_image_rgb

logger = logging.getLogger(__name__)


def compute_image_hashes(img_or_path: Union[Image.Image, Path, str]) -> Dict[str, str]:
    """
    Berechnet deterministische Perceptual Hashes (pHash und dHash) für ein Bild.
    - pHash (Perceptual Hash): Basiert auf Diskreter Kosinustransformation (DCT), extrem robust gegen Skalierung und Kompression.
    - dHash (Difference Hash): Basiert auf Farbgradienten / Kantenverläufen, sehr schnell zu berechnen.
    """
    try:
        if isinstance(img_or_path, (str, Path)):
            pil_img = load_image_rgb(Path(img_or_path))
        else:
            pil_img = img_or_path

        p_hash = str(imagehash.phash(pil_img))
        d_hash = str(imagehash.dhash(pil_img))
        return {
            "phash": p_hash,
            "dhash": d_hash,
        }
    except Exception as e:
        logger.warning("Konnte Image-Hashes nicht berechnen: %s", e)
        return {"phash": "", "dhash": ""}


def calculate_hash_distance(h1: Optional[str], h2: Optional[str]) -> Optional[int]:
    """Berechnet die Hamming-Distanz zweier Hex-Hashes (0 = identisch)."""
    if not h1 or not h2:
        return None
    try:
        hash1 = imagehash.hex_to_hash(h1)
        hash2 = imagehash.hex_to_hash(h2)
        return hash1 - hash2
    except Exception:
        return None


def classify_variant_relation(
    clip_score: float,
    phash_dist: Optional[int] = None,
) -> Tuple[str, str]:
    """
    Klassifiziert das Verhältnis zweier Bildvarianten:
    Gibt (Typ-Code, Menschenlesbares Label) zurück:
    - EXACT_DUPLICATE: Exaktes Duplikat / Identischer Scan
    - FORMAT_VARIANT: Format-, Zuschnitt- oder Kompressionsvariante
    - SERIES_VARIANT: Optische Variante / Serienaufnahme
    """
    # 1. Wenn pHash verfügbar: sehr präzise Unterscheidung
    if phash_dist is not None:
        if phash_dist <= 2 or clip_score >= 0.992:
            return ("EXACT_DUPLICATE", "Exaktes Duplikat / Identischer Scan")
        elif phash_dist <= 7 or clip_score >= 0.955:
            return ("FORMAT_VARIANT", "Format- / Zuschnitt-Variante")
        elif clip_score >= 0.89:
            return ("SERIES_VARIANT", "Serienaufnahme / Motiv-Variante")
    
    # 2. Fallback rein auf CLIP-Vektorähnlichkeit
    if clip_score >= 0.985:
        return ("EXACT_DUPLICATE", "Exaktes Duplikat / Identischer Scan")
    elif clip_score >= 0.945:
        return ("FORMAT_VARIANT", "Format- / Zuschnitt-Variante")
    elif clip_score >= 0.89:
        return ("SERIES_VARIANT", "Serienaufnahme / Motiv-Variante")
    
    return ("RELATED", "Ähnliches Motiv")


class VariantService:
    """
    Service zur Erkennung, Klassifizierung und visuellen Gruppierung (Stacking)
    von Bild-Duplikaten und Motiv-Varianten im Archiv.
    """

    def __init__(self, qdrant_service: Optional[QdrantService] = None):
        self.qdrant = qdrant_service or QdrantService()

    def stack_search_results(
        self,
        hits: List[Any],
        vectors_map: Optional[Dict[str, List[float]]] = None,
        similarity_threshold: float = 0.925,
    ) -> List[Any]:
        """
        Fasst semantisch eng verwandte Treffer (Serienabzüge, Kontaktabzüge, Duplikate)
        in einem Suchergebnis zu virtuellen Bildstapeln (Stacks) zusammen.
        
        Der relevanteste Treffer bleibt an seiner Position als Repräsentant stehen.
        Alle weiteren Varianten werden in `variants` angehängt.
        """
        if not hits or len(hits) <= 1:
            return hits

        # Wenn keine Vektoren übergeben wurden, versuchen wir sie aus den Hits zu ziehen
        has_vectors = False
        vec_by_id: Dict[str, np.ndarray] = {}

        if vectors_map:
            for k, v in vectors_map.items():
                if v:
                    vec_by_id[k] = np.array(v, dtype=np.float32)
            has_vectors = len(vec_by_id) > 0
        else:
            for h in hits:
                v = getattr(h, "vector", None) or (h.get("vector") if isinstance(h, dict) else None)
                h_id = getattr(h, "id", None) or (h.get("id") if isinstance(h, dict) else None)
                if v and h_id:
                    vec_by_id[str(h_id)] = np.array(v, dtype=np.float32)
            has_vectors = len(vec_by_id) > 0

        # Falls keine Vektoren direkt vorhanden sind: Aus Qdrant für diese IDs laden
        if not has_vectors:
            hit_ids = [str(getattr(h, "id", "") or (h.get("id") if isinstance(h, dict) else "")) for h in hits]
            hit_ids = [i for i in hit_ids if i]
            try:
                records = self.qdrant.client.retrieve(
                    collection_name=settings.COLLECTION_IMAGES,
                    ids=hit_ids,
                    with_vectors=True,
                    with_payload=True,
                )
                for rec in records:
                    if rec.vector:
                        vec_by_id[str(rec.id)] = np.array(rec.vector, dtype=np.float32)
                        # Optional: auch pHash merken
                        p = rec.payload or {}
                        if p.get("phash"):
                            # pHash kann in vec_by_id oder separatem dict gemerkt werden
                            pass
            except Exception as e:
                logger.warning("Konnte Vektoren für Stacking nicht laden: %s", e)
                return hits

        stacked_results: List[Any] = []
        consumed_ids = set()

        for i, hit in enumerate(hits):
            h_id = str(getattr(hit, "id", None) or (hit.get("id") if isinstance(hit, dict) else ""))
            if not h_id or h_id in consumed_ids:
                continue

            primary_vec = vec_by_id.get(h_id)
            variants: List[Any] = []

            if primary_vec is not None:
                # Normalisierung sicherstellen für Cosine-Ähnlichkeit
                norm_p = np.linalg.norm(primary_vec)
                if norm_p > 0:
                    normed_primary = primary_vec / norm_p
                else:
                    normed_primary = primary_vec

                for j in range(i + 1, len(hits)):
                    other = hits[j]
                    other_id = str(getattr(other, "id", None) or (other.get("id") if isinstance(other, dict) else ""))
                    if not other_id or other_id in consumed_ids:
                        continue

                    other_vec = vec_by_id.get(other_id)
                    if other_vec is None:
                        continue

                    norm_o = np.linalg.norm(other_vec)
                    if norm_o > 0:
                        normed_other = other_vec / norm_o
                    else:
                        normed_other = other_vec

                    sim = float(np.dot(normed_primary, normed_other))

                    if sim >= similarity_threshold:
                        rel_code, rel_label = classify_variant_relation(sim)
                        
                        # Variant-Attribute auf other setzen
                        if isinstance(other, dict):
                            other["variant_similarity"] = round(sim, 4)
                            other["variant_type"] = rel_code
                            other["variant_label"] = rel_label
                            other["primary_id"] = h_id
                        elif hasattr(other, "model_fields") and "variant_type" in other.model_fields:
                            setattr(other, "variant_similarity", round(sim, 4))
                            setattr(other, "variant_type", rel_code)
                            setattr(other, "variant_label", rel_label)
                            setattr(other, "primary_id", h_id)
                        elif hasattr(other, "payload") and isinstance(other.payload, dict):
                            other.payload["variant_similarity"] = round(sim, 4)
                            other.payload["variant_type"] = rel_code
                            other.payload["variant_label"] = rel_label
                            other.payload["primary_id"] = h_id

                        variants.append(other)
                        consumed_ids.add(other_id)

            consumed_ids.add(h_id)

            if isinstance(hit, dict):
                hit["is_stack"] = len(variants) > 0
                hit["variants_count"] = len(variants)
                hit["variants"] = variants
            elif hasattr(hit, "model_fields") and "is_stack" in hit.model_fields:
                setattr(hit, "is_stack", len(variants) > 0)
                setattr(hit, "variants_count", len(variants))
                setattr(hit, "variants", variants)
            elif hasattr(hit, "payload") and isinstance(hit.payload, dict):
                hit.payload["is_stack"] = len(variants) > 0
                hit.payload["variants_count"] = len(variants)
                hit.payload["variants"] = variants
            else:
                try:
                    setattr(hit, "is_stack", len(variants) > 0)
                    setattr(hit, "variants_count", len(variants))
                    setattr(hit, "variants", variants)
                except Exception:
                    pass

            stacked_results.append(hit)

        return stacked_results

    def find_variants_for_image(
        self,
        image_path: Union[str, Path],
        limit: int = 25,
        score_threshold: float = 0.88,
    ) -> Dict[str, Any]:
        """
        Sucht alle Duplikate und optischen Varianten für ein einzelnes Archivbild
        im Gesamtbestand.
        """
        path = Path(image_path).resolve()
        path_str = str(path)

        # 1. Bildpunkt und Vektor in Qdrant finden
        ref_records, _ = self.qdrant.client.scroll(
            collection_name=settings.COLLECTION_IMAGES,
            scroll_filter=rest_models.Filter(
                should=[
                    rest_models.FieldCondition(key="file_path", match=rest_models.MatchValue(value=path_str)),
                    rest_models.FieldCondition(key="image_path", match=rest_models.MatchValue(value=path_str)),
                ]
            ),
            limit=1,
            with_vectors=True,
            with_payload=True,
        )

        query_vector = None
        ref_payload = {}
        ref_phash = None

        if ref_records:
            ref_point = ref_records[0]
            query_vector = ref_point.vector
            ref_payload = ref_point.payload or {}
            ref_phash = ref_payload.get("phash")

        if query_vector is None:
            # Falls noch nicht indexiert oder Vektor nicht vorhanden: CLIP on the fly
            from app.services.clip_service import ClipService
            clip_service = ClipService()
            query_vector = clip_service.embed_image(path)
            hashes = compute_image_hashes(path)
            ref_phash = hashes.get("phash")

        # 2. Vektorsuche in archive_images
        hits = self.qdrant.search_images(
            query_vector=query_vector,
            limit=limit + 5,
            score_threshold=score_threshold,
        )

        variants = []
        for hit in hits:
            p = hit.payload or {}
            hit_path = p.get("file_path") or p.get("image_path", "")
            
            # Sich selbst ausschließen
            if hit_path and Path(hit_path).resolve() == path:
                continue

            clip_score = float(hit.score)
            hit_phash = p.get("phash")
            
            # Falls Referenzbild oder Hit noch keinen pHash hat und Datei existiert:
            p_dist = None
            if ref_phash and hit_phash:
                p_dist = calculate_hash_distance(ref_phash, hit_phash)

            rel_code, rel_label = classify_variant_relation(clip_score, p_dist)

            variants.append({
                "id": str(hit.id),
                "score": round(clip_score, 4),
                "file_path": hit_path,
                "file_name": p.get("file_name") or p.get("filename") or Path(hit_path).name,
                "title": p.get("title"),
                "creator": p.get("creator"),
                "date": p.get("date"),
                "signature": p.get("signature"),
                "description": p.get("description"),
                "width": p.get("width"),
                "height": p.get("height"),
                "file_size": p.get("file_size"),
                "relation_type": rel_code,
                "relation_label": rel_label,
                "phash_distance": p_dist,
            })

            if len(variants) >= limit:
                break

        return {
            "reference_image": {
                "file_path": path_str,
                "file_name": path.name,
                "title": ref_payload.get("title"),
                "date": ref_payload.get("date"),
                "width": ref_payload.get("width"),
                "height": ref_payload.get("height"),
            },
            "total_variants": len(variants),
            "variants": variants,
        }

    def get_archive_variant_clusters(
        self,
        eps: float = 0.075,
        min_samples: int = 2,
        limit_groups: int = 100,
    ) -> Dict[str, Any]:
        """
        Führt ein bestandsweites Clustering aller Bildvektoren durch, um
        alle Duplikat- und Variantengruppen (Serienaufnahmen, Repros) im Archiv zu finden.
        """
        # 1. Alle Bildvektoren aus archive_images laden
        points = []
        offset = None
        while True:
            records, next_offset = self.qdrant.client.scroll(
                collection_name=settings.COLLECTION_IMAGES,
                limit=1000,
                offset=offset,
                with_vectors=True,
                with_payload=True,
            )
            points.extend(records)
            if next_offset is None or not records:
                break
            offset = next_offset

        if not points:
            return {"total_groups": 0, "total_stacked_images": 0, "groups": []}

        valid_points = [p for p in points if p.vector is not None]
        if len(valid_points) < min_samples:
            return {"total_groups": 0, "total_stacked_images": 0, "groups": []}

        vectors = np.array([p.vector for p in valid_points], dtype=np.float32)

        # 2. DBSCAN mit Cosine Metric
        db = DBSCAN(eps=eps, min_samples=min_samples, metric="cosine")
        cluster_labels = db.fit_predict(vectors)

        unique_clusters = [c for c in sorted(set(cluster_labels)) if c != -1]

        groups = []
        total_images_in_groups = 0

        for c_id in unique_clusters[:limit_groups]:
            indices = np.where(cluster_labels == c_id)[0]
            cluster_points = [valid_points[i] for i in indices]
            total_images_in_groups += len(cluster_points)

            # Sortieren nach Bildauflösung (Master-Scan mit höchster Auflösung zuerst)
            def get_pixels(pt):
                p = pt.payload or {}
                return (p.get("width") or 0) * (p.get("height") or 0)

            cluster_points.sort(key=get_pixels, reverse=True)

            rep = cluster_points[0]
            rep_p = rep.payload or {}

            members = []
            for pt in cluster_points:
                pl = pt.payload or {}
                fp = pl.get("file_path") or pl.get("image_path", "")
                members.append({
                    "id": str(pt.id),
                    "file_path": fp,
                    "file_name": pl.get("file_name") or pl.get("filename") or Path(fp).name,
                    "width": pl.get("width"),
                    "height": pl.get("height"),
                    "date": pl.get("date"),
                    "title": pl.get("title"),
                    "signature": pl.get("signature"),
                })

            groups.append({
                "group_id": f"group_{c_id}",
                "count": len(cluster_points),
                "representative": {
                    "id": str(rep.id),
                    "file_path": rep_p.get("file_path") or rep_p.get("image_path", ""),
                    "file_name": rep_p.get("file_name") or rep_p.get("filename") or "",
                    "title": rep_p.get("title"),
                    "date": rep_p.get("date"),
                    "width": rep_p.get("width"),
                    "height": rep_p.get("height"),
                },
                "items": members,
            })

        return {
            "total_groups": len(unique_clusters),
            "showing_groups": len(groups),
            "total_stacked_images": total_images_in_groups,
            "groups": groups,
        }
