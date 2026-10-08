import os
import gc
import uuid
import logging
import queue
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image, ImageOps
from qdrant_client.http import models as rest_models

from app.core.config import settings
from app.core.system_profile import current_hardware_profile, safe_normalize_image_to_rgb
from app.services.qdrant_service import QdrantService
from app.services.clip_service import ClipService
from app.services.face_service import FaceService
from app.services.metadata_service import metadata_service

logger = logging.getLogger(__name__)

# Namespace für deterministische UUID-Generierung anhand des Dateipfads (Idempotenz)
UUID_NAMESPACE = uuid.UUID("3d4b6845-816b-4e45-8b3c-9ad51b5bbfcb")

# Globaler Status für Live-Fortschritt im Frontend
INDEXING_PROGRESS: Dict[str, Any] = {
    "job_id": None,
    "is_running": False,
    "finished": False,
    "folder_path": "",
    "total_found": 0,
    "processed_count": 0,
    "current_file": "",
    "new_indexed": 0,
    "skipped": 0,
    "faces_detected": 0,
    "already_fully_indexed": False,
    "percent": 0,
    "error": None,
    "started_at": None,
    "last_updated": None,
    "clustering_status": None,
    "clustering_message": None,
    "pid": None,
}


def update_indexing_progress(updates: Dict[str, Any]) -> None:
    """Aktualisiert den In-Memory-Status und synchronisiert ihn in SQLite (für isolierte Worker)."""
    global INDEXING_PROGRESS
    INDEXING_PROGRESS.update(updates)
    try:
        from app.services.metadata_db import metadata_db
        metadata_db.set_system_state("indexing_progress", INDEXING_PROGRESS)
    except Exception as e:
        logger.debug("Konnte Indexing-Status nicht in SQLite spiegeln: %s", e)


def get_current_indexing_progress() -> Dict[str, Any]:
    """Liefert den aktuellen Verarbeitungsstatus (vorrangig aus SQLite für Prozess-Isolation)."""
    try:
        from app.services.metadata_db import metadata_db
        db_state = metadata_db.get_system_state("indexing_progress")
        if db_state and isinstance(db_state, dict):
            return db_state
    except Exception:
        pass
    return INDEXING_PROGRESS


class IndexingService:
    """Orchestrierungsdienst für das Extrahieren von Bild- & Gesichtsmerkmalen und das Indexieren in Qdrant."""

    def __init__(
        self,
        qdrant_service: QdrantService,
        clip_service: ClipService,
        face_service: Optional[FaceService] = None,
    ):
        self.qdrant = qdrant_service
        self.clip = clip_service
        self.face = face_service

    def prepare_image_data(
        self,
        file_path: Path,
        base_dir: Optional[Path] = None,
        forced_rel_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        I/O- und EXIF-Phase (kann im Hintergrund-Thread ausgeführt werden):
        1. Datei von Platte/Netzwerk lesen und ins RAM laden
        2. EXIF/IPTC/XMP-Metadaten extrahieren
        3. EXIF-Ausrichtung anwenden und RGB-Pixel dekodieren
        4. Perceptual Hashes (dHash/pHash) berechnen
        """
        abs_path = file_path.resolve()
        path_str = str(abs_path)

        if forced_rel_path:
            rel_path = forced_rel_path
        else:
            resolved_base = (base_dir or Path(settings.ARCHIVE_DATA_DIR)).resolve()
            try:
                rel_path = abs_path.relative_to(resolved_base).as_posix()
            except ValueError:
                rel_path = file_path.name

        file_size = os.path.getsize(abs_path)
        with Image.open(abs_path) as raw_img:
            meta = metadata_service.extract_metadata(file_path, img=raw_img)
            raw_transposed = ImageOps.exif_transpose(raw_img)
            pil_img = safe_normalize_image_to_rgb(raw_transposed)
            pil_img.load()
            if raw_transposed is not pil_img:
                try:
                    raw_transposed.close()
                except Exception:
                    pass
            width, height = pil_img.size

        from app.services.variant_service import compute_image_hashes
        hashes = compute_image_hashes(pil_img)

        return {
            "file_path": file_path,
            "abs_path": abs_path,
            "path_str": path_str,
            "rel_path": rel_path,
            "file_size": file_size,
            "pil_img": pil_img,
            "width": width,
            "height": height,
            "meta": meta,
            "hashes": hashes,
        }

    def process_prepared_image(
        self,
        prepared: Dict[str, Any],
        cluster_id_mapping: Optional[dict[str, str]] = None,
        upsert: bool = True,
    ) -> Tuple[bool, int, Optional[rest_models.PointStruct], List[rest_models.PointStruct]]:
        """
        Inferenz- & Vektorphase (auf GPU/CPU):
        1. CLIP-Embedding berechnen
        2. Gesichter erkennen & ArcFace-Embeddings berechnen
        3. WebP-Thumbnails & Face-Crops direkt aus dem RAM cachen
        4. PointStructs erzeugen und optional sofort upserten
        """
        file_path: Path = prepared["file_path"]
        path_str: str = prepared["path_str"]
        rel_path: str = prepared["rel_path"]
        file_size: int = prepared["file_size"]
        pil_img: Image.Image = prepared["pil_img"]
        width: int = prepared["width"]
        height: int = prepared["height"]
        meta: Dict[str, Any] = prepared["meta"]
        hashes: Dict[str, Any] = prepared["hashes"]

        # 1. CLIP Embedding (512-dim)
        clip_vector = self.clip.embed_image(pil_img)

        # 2. Optionale Gesichtserkennung & ArcFace Embeddings (512-dim)
        if self.face is not None:
            faces_data = self.face.extract_faces(pil_img)
        else:
            faces_data = []

        now_iso = datetime.now(timezone.utc).isoformat()
        image_id = str(uuid.uuid5(UUID_NAMESPACE, rel_path))

        # 3. Proaktives Thumbnail- & Gesichtscrop-Caching (WebP) direkt aus dem RAM
        try:
            from app.services.thumbnail_service import thumbnail_service
            bboxes = [f["bbox"] for f in faces_data if f.get("bbox")]
            thumbnail_service.cache_image_derivatives(file_path, pil_img, face_bboxes=bboxes)
        except Exception as cache_err:
            logger.debug("Proaktives Caching übersprungen für %s: %s", path_str, cache_err)

        # Bild-Pixeldaten im RAM sofort freigeben, da Vektoren, Hashes & Thumbs extrahiert sind
        try:
            pil_img.close()
        except Exception:
            pass
        prepared["pil_img"] = None

        # 4. Bild-Point für archive_images
        image_point = rest_models.PointStruct(
            id=image_id,
            vector=clip_vector,
            payload={
                "file_path": path_str,
                "relative_path": rel_path,
                "file_name": file_path.name,
                "image_path": path_str,
                "filename": file_path.name,
                "width": width,
                "height": height,
                "file_size": file_size,
                "phash": hashes.get("phash"),
                "dhash": hashes.get("dhash"),
                "faces_count": len(faces_data),
                "indexed_at": now_iso,
                "title": meta.get("title"),
                "creator": meta.get("creator"),
                "date": meta.get("date"),
                "description": meta.get("description"),
                "signature": meta.get("signature"),
                "copyright": meta.get("copyright"),
                "keywords": meta.get("keywords", []),
                "metadata": meta,
            },
        )

        # 5. Gesichts-Points für archive_faces
        face_points: List[rest_models.PointStruct] = []
        for idx, face_info in enumerate(faces_data):
            face_id = str(uuid.uuid5(UUID_NAMESPACE, f"{rel_path}#face_{idx}"))
            cluster_id = None
            if cluster_id_mapping and face_id in cluster_id_mapping:
                cluster_id = cluster_id_mapping[face_id]

            orig_w = face_info.get("orig_width") or width
            orig_h = face_info.get("orig_height") or height
            bbox_pct = face_info.get("bbox_percent")
            if not bbox_pct and orig_w and orig_h and face_info.get("bbox") and len(face_info["bbox"]) == 4:
                x1, y1, x2, y2 = face_info["bbox"]
                bbox_pct = {
                    "left": round((x1 / orig_w) * 100, 4),
                    "top": round((y1 / orig_h) * 100, 4),
                    "width": round(((x2 - x1) / orig_w) * 100, 4),
                    "height": round(((y2 - y1) / orig_h) * 100, 4),
                }

            face_point = rest_models.PointStruct(
                id=face_id,
                vector=face_info["embedding"],
                payload={
                    "file_path": path_str,
                    "relative_path": rel_path,
                    "image_path": path_str,
                    "bbox": face_info["bbox"],
                    "bbox_percent": bbox_pct,
                    "orig_width": orig_w,
                    "orig_height": orig_h,
                    "face_id": face_id,
                    "cluster_id": cluster_id,
                    "det_score": face_info["det_score"],
                    "face_index": idx,
                    "parent_image_id": image_id,
                    "indexed_at": now_iso,
                },
            )
            face_points.append(face_point)

        if upsert:
            self.qdrant.upsert_images([image_point], wait=False)
            if face_points:
                self.qdrant.upsert_faces(face_points, wait=False)

        return True, len(faces_data), image_point, face_points

    def index_image_file(
        self,
        file_path: Path,
        cluster_id_mapping: Optional[dict[str, str]] = None,
        base_dir: Optional[Path] = None,
        forced_rel_path: Optional[str] = None,
    ) -> Tuple[bool, int]:
        """
        Verarbeitet eine einzelne Bilddatei:
        1. CLIP-Embedding berechnen und in `archive_images` einfügen
        2. Gesichter erkennen, ArcFace-Embeddings berechnen und in `archive_faces` einfügen (optional)
        3. Archivische Metadaten (EXIF/IPTC/XMP/Sidecar) extrahieren

        Gibt (Erfolg, Anzahl erkannter Gesichter) zurück.
        """
        try:
            prepared = self.prepare_image_data(file_path, base_dir=base_dir, forced_rel_path=forced_rel_path)
            success, num_faces, _, _ = self.process_prepared_image(
                prepared, cluster_id_mapping=cluster_id_mapping, upsert=True
            )
            return success, num_faces
        except Exception as e:
            logger.error("Fehler bei der Indizierung von '%s': %s", file_path, e, exc_info=True)
            return False, 0

    def reindex_single_image(self, file_path: Path) -> Tuple[bool, int]:
        """
        Reindexiert ein einzelnes Bild nach einer Änderung (z.B. verlustfreies Drehen):
        1. Ermittelt existierenden relativen Pfad aus Qdrant
        2. Löscht alte Gesichts-Vektoren aus archive_faces
        3. Führt index_image_file aus (neues CLIP-Embedding, neue Gesichter, neue Dimensionen)
        """
        abs_path = file_path.resolve()
        path_str = str(abs_path)

        # 1. Existierenden relativen Pfad aus Qdrant abrufen (falls vorhanden)
        existing_rel_path = None
        try:
            records, _ = self.qdrant.client.scroll(
                collection_name=settings.COLLECTION_IMAGES,
                scroll_filter=rest_models.Filter(
                    should=[
                        rest_models.FieldCondition(key="file_path", match=rest_models.MatchValue(value=path_str)),
                        rest_models.FieldCondition(key="image_path", match=rest_models.MatchValue(value=path_str)),
                    ]
                ),
                limit=1,
                with_payload=True,
                with_vectors=False,
            )
            if records and records[0].payload:
                existing_rel_path = records[0].payload.get("relative_path")
        except Exception as e:
            logger.debug("Konnte existierenden Bild-Point nicht abrufen: %s", e)

        # 2. Alte Gesichts-Points für dieses Bild aus archive_faces entfernen
        try:
            self.qdrant.client.delete(
                collection_name=settings.COLLECTION_FACES,
                points_selector=rest_models.FilterSelector(
                    filter=rest_models.Filter(
                        should=[
                            rest_models.FieldCondition(key="file_path", match=rest_models.MatchValue(value=path_str)),
                            rest_models.FieldCondition(key="image_path", match=rest_models.MatchValue(value=path_str)),
                        ]
                    )
                ),
            )
        except Exception as e:
            logger.warning("Fehler beim Löschen alter Gesichts-Points für %s: %s", path_str, e)

        # 3. Neu indexieren
        return self.index_image_file(file_path, forced_rel_path=existing_rel_path)

    def index_folder(
        self,
        folder_path: Path,
        recursive: bool = True,
        force: bool = False,
    ) -> dict[str, Any]:
        """
        Scannt ein Verzeichnis nach Bilddateien und indexiert neue Dateien inkrementell
        mittels asynchronem Producer-Consumer-Pipelining (I/O & GPU entkoppelt)
        und gebatchten Qdrant-Upserts.
        """
        abs_folder = folder_path.resolve()
        if not abs_folder.is_dir():
            raise ValueError(f"'{folder_path}' ist kein gültiges Verzeichnis.")

        # Prozess-Priorität für den Hintergrund-Import herabsetzen (QoS),
        # damit interaktive Web- und Suchanfragen des Benutzers Vorrang erhalten
        try:
            os.nice(10)
        except Exception:
            pass

        extensions = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}
        files = []
        iterator = abs_folder.rglob("*") if recursive else abs_folder.glob("*")
        for p in iterator:
            if p.is_file() and p.suffix.lower() in extensions:
                files.append(p)
        files = sorted(files)

        total_found = len(files)
        indexed_count = 0
        skipped_count = 0
        faces_count = 0
        errors = []

        current_job_id = INDEXING_PROGRESS.get("job_id") or uuid.uuid4().hex[:12]
        update_indexing_progress({
            "job_id": current_job_id,
            "is_running": True,
            "finished": False,
            "folder_path": str(abs_folder),
            "total_found": total_found,
            "processed_count": 0,
            "current_file": "Prüfe vorhandene Indizes..." if total_found > 0 else "Keine Bilder gefunden",
            "new_indexed": 0,
            "skipped": 0,
            "faces_detected": 0,
            "percent": 0,
            "error": None,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        })

        try:
            # Ermittle bereits indexierte Point-IDs zur Vermeidung von Doppelarbeit
            existing_ids = set()
            if not force:
                try:
                    candidate_ids = []
                    for f in files:
                        try:
                            rel = f.relative_to(abs_folder).as_posix()
                        except ValueError:
                            rel = f.name
                        candidate_ids.append(str(uuid.uuid5(UUID_NAMESPACE, rel)))

                    chunk_size = 100
                    for i in range(0, len(candidate_ids), chunk_size):
                        chunk = candidate_ids[i:i + chunk_size]
                        points = self.qdrant.client.retrieve(
                            collection_name=settings.COLLECTION_IMAGES,
                            ids=chunk,
                            with_payload=False,
                            with_vectors=False,
                        )
                        for pt in points:
                            existing_ids.add(str(pt.id))
                except Exception as e:
                    logger.debug("Konnte existierende IDs nicht vorab abrufen: %s", e)

            # Liste der zu verarbeitenden Dateien zusammenstellen (Übersprungene direkt zählen)
            items_to_index: List[Tuple[int, Path]] = []
            for idx, file_path in enumerate(files):
                try:
                    rel = file_path.relative_to(abs_folder).as_posix()
                except ValueError:
                    rel = file_path.name
                point_id = str(uuid.uuid5(UUID_NAMESPACE, rel))

                if not force and point_id in existing_ids:
                    skipped_count += 1
                else:
                    items_to_index.append((idx, file_path))

            # Falls Bilder verarbeitet werden müssen: Asynchrones Prefetching & Pipelining
            if items_to_index:
                is_bulk_import = len(items_to_index) >= 500
                if is_bulk_import:
                    logger.info(
                        "Großer Massen-Import erkannt (%d Bilder): Deaktiviere temporär HNSW-Indexierung...",
                        len(items_to_index),
                    )
                    self.qdrant.set_indexing_threshold(settings.COLLECTION_IMAGES, 0)
                    self.qdrant.set_indexing_threshold(settings.COLLECTION_FACES, 0)

                prefetch_queue: queue.Queue = queue.Queue(maxsize=current_hardware_profile.prefetch_queue_size)
                abort_event = threading.Event()

                def _prefetch_worker():
                    for orig_idx, f_path in items_to_index:
                        if abort_event.is_set():
                            break
                        try:
                            prep = self.prepare_image_data(f_path, base_dir=abs_folder)
                            prefetch_queue.put((orig_idx, f_path, prep, None))
                        except Exception as prep_err:
                            prefetch_queue.put((orig_idx, f_path, None, prep_err))
                    prefetch_queue.put(None)

                prefetch_thread = threading.Thread(
                    target=_prefetch_worker,
                    daemon=True,
                    name="IndexingPrefetchWorker",
                )
                prefetch_thread.start()

                batched_images: List[rest_models.PointStruct] = []
                batched_faces: List[rest_models.PointStruct] = []
                BATCH_SIZE = current_hardware_profile.batch_size

                def _flush_batches():
                    if batched_images:
                        self.qdrant.upsert_images(batched_images, wait=False)
                        batched_images.clear()
                    if batched_faces:
                        self.qdrant.upsert_faces(batched_faces, wait=False)
                        batched_faces.clear()

                try:
                    while True:
                        item = prefetch_queue.get()
                        if item is None:
                            break

                        orig_idx, f_path, prepared_data, prep_err = item

                        update_indexing_progress({
                            "processed_count": orig_idx + 1,
                            "current_file": f_path.name,
                            "new_indexed": indexed_count,
                            "skipped": skipped_count,
                            "faces_detected": faces_count,
                            "percent": int(((orig_idx + 1) / max(total_found, 1)) * 100),
                            "last_updated": datetime.now(timezone.utc).isoformat(),
                        })

                        if prep_err is not None:
                            logger.error("Fehler beim Vorbereiten von %s: %s", f_path, prep_err)
                            errors.append(f_path.name)
                            continue

                        try:
                            success, num_faces, img_pt, fc_pts = self.process_prepared_image(
                                prepared_data, upsert=False
                            )
                            if success and img_pt:
                                batched_images.append(img_pt)
                                if fc_pts:
                                    batched_faces.extend(fc_pts)
                                indexed_count += 1
                                faces_count += num_faces

                                if len(batched_images) >= BATCH_SIZE:
                                    _flush_batches()
                            else:
                                errors.append(f_path.name)
                        except Exception as e:
                            logger.error("Fehler beim Verarbeiten von %s: %s", f_path, e)
                            errors.append(f_path.name)
                        finally:
                            del prepared_data
                            del item

                        # Periodische Speicherbereinigung alle 50 Bilder gegen glibc-Heapfragmentierung & PyTorch Caching
                        if indexed_count > 0 and indexed_count % 50 == 0:
                            gc.collect()
                            try:
                                import torch
                                if torch.cuda.is_available():
                                    torch.cuda.empty_cache()
                            except Exception:
                                pass

                    _flush_batches()
                    gc.collect()
                    try:
                        import torch
                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()
                    except Exception:
                        pass
                finally:
                    abort_event.set()
                    prefetch_thread.join(timeout=2.0)
                    if is_bulk_import:
                        logger.info(
                            "Massen-Import abgeschlossen: Reaktiviere HNSW-Indexierung (Schwellenwert: %d)...",
                            current_hardware_profile.hnsw_indexing_threshold,
                        )
                        self.qdrant.set_indexing_threshold(
                            settings.COLLECTION_IMAGES, current_hardware_profile.hnsw_indexing_threshold
                        )
                        self.qdrant.set_indexing_threshold(
                            settings.COLLECTION_FACES, current_hardware_profile.hnsw_indexing_threshold
                        )

            already_fully = (total_found > 0 and indexed_count == 0 and skipped_count == total_found)
            return {
                "folder_path": str(abs_folder),
                "total_found": total_found,
                "new_indexed": indexed_count,
                "skipped": skipped_count,
                "faces_detected": faces_count,
                "already_fully_indexed": already_fully,
                "error_count": len(errors),
                "errors": errors[:20],
            }
        except Exception as e:
            update_indexing_progress({"error": str(e)})
            raise
        finally:
            already_fully = (total_found > 0 and indexed_count == 0 and skipped_count == total_found)
            update_indexing_progress({
                "is_running": False,
                "finished": True,
                "new_indexed": indexed_count,
                "skipped": skipped_count,
                "faces_detected": faces_count,
                "already_fully_indexed": already_fully,
                "percent": 100,
                "last_updated": datetime.now(timezone.utc).isoformat(),
            })

