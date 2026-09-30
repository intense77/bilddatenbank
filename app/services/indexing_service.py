import os
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image
from qdrant_client.http import models as rest_models

from app.core.config import settings
from app.services.qdrant_service import QdrantService
from app.services.clip_service import ClipService
from app.services.face_service import FaceService
from app.services.metadata_service import metadata_service

logger = logging.getLogger(__name__)

# Namespace für deterministische UUID-Generierung anhand des Dateipfads (Idempotenz)
UUID_NAMESPACE = uuid.UUID("3d4b6845-816b-4e45-8b3c-9ad51b5bbfcb")


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

    def index_image_file(
        self,
        file_path: Path,
        cluster_id_mapping: Optional[dict[str, str]] = None,
        base_dir: Optional[Path] = None,
    ) -> Tuple[bool, int]:
        """
        Verarbeitet eine einzelne Bilddatei:
        1. CLIP-Embedding berechnen und in `archive_images` einfügen
        2. Gesichter erkennen, ArcFace-Embeddings berechnen und in `archive_faces` einfügen (optional)
        3. Archivische Metadaten (EXIF/IPTC/XMP/Sidecar) extrahieren

        Gibt (Erfolg, Anzahl erkannter Gesichter) zurück.
        """
        abs_path = file_path.resolve()
        path_str = str(abs_path)

        try:
            # Relativen Pfad bestimmen (für stabile UUIDv5-Identifikation)
            resolved_base = (base_dir or Path(settings.ARCHIVE_DATA_DIR)).resolve()
            try:
                rel_path = abs_path.relative_to(resolved_base).as_posix()
            except ValueError:
                rel_path = file_path.name

            # 1. CLIP Embedding (512-dim)
            clip_vector = self.clip.embed_image(path_str)

            # 2. Optionale Gesichtserkennung & ArcFace Embeddings (512-dim)
            if self.face is not None:
                faces_data = self.face.extract_faces(path_str)
            else:
                faces_data = []

            file_size = os.path.getsize(abs_path)
            with Image.open(abs_path) as img:
                width, height = img.size

            now_iso = datetime.now(timezone.utc).isoformat()

            # 3. Metadaten extrahieren (EXIF, IPTC, XMP, Sidecar JSON)
            meta = metadata_service.extract_metadata(file_path)

            # Bild-ID deterministisch aus relativem Pfad bilden (Idempotenz analog indexer.py)
            image_id = str(uuid.uuid5(UUID_NAMESPACE, rel_path))

            # 4. Bild-Point für archive_images mit einheitlichem Payload-Schema
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
            self.qdrant.upsert_images([image_point])

            # 4. Gesichts-Points für archive_faces
            face_points = []
            for idx, face_info in enumerate(faces_data):
                face_id = str(uuid.uuid5(UUID_NAMESPACE, f"{rel_path}#face_{idx}"))
                cluster_id = None
                if cluster_id_mapping and face_id in cluster_id_mapping:
                    cluster_id = cluster_id_mapping[face_id]

                face_point = rest_models.PointStruct(
                    id=face_id,
                    vector=face_info["embedding"],
                    payload={
                        "file_path": path_str,
                        "relative_path": rel_path,
                        "image_path": path_str,
                        "bbox": face_info["bbox"],
                        "face_id": face_id,
                        "cluster_id": cluster_id,
                        "det_score": face_info["det_score"],
                        "face_index": idx,
                        "parent_image_id": image_id,
                        "indexed_at": now_iso,
                    },
                )
                face_points.append(face_point)

            if face_points:
                self.qdrant.upsert_faces(face_points)

            return True, len(faces_data)

        except Exception as e:
            logger.error("Fehler bei der Indizierung von '%s': %s", path_str, e, exc_info=True)
            return False, 0

    def index_folder(
        self,
        folder_path: Path,
        recursive: bool = True,
        force: bool = False,
    ) -> dict[str, Any]:
        """
        Scannt ein Verzeichnis nach Bilddateien und indexiert neue Dateien inkrementell.
        """
        abs_folder = folder_path.resolve()
        if not abs_folder.is_dir():
            raise ValueError(f"'{folder_path}' ist kein gültiges Verzeichnis.")

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

        for file_path in files:
            try:
                rel = file_path.relative_to(abs_folder).as_posix()
            except ValueError:
                rel = file_path.name
            point_id = str(uuid.uuid5(UUID_NAMESPACE, rel))

            if not force and point_id in existing_ids:
                skipped_count += 1
                continue

            try:
                success, num_faces = self.index_image_file(file_path, base_dir=abs_folder)
                if success:
                    indexed_count += 1
                    faces_count += num_faces
                else:
                    errors.append(file_path.name)
            except Exception as e:
                logger.error("Fehler beim Indexieren von %s: %s", file_path, e)
                errors.append(file_path.name)

        return {
            "folder_path": str(abs_folder),
            "total_found": total_found,
            "new_indexed": indexed_count,
            "skipped": skipped_count,
            "faces_detected": faces_count,
            "error_count": len(errors),
            "errors": errors[:20],
        }

