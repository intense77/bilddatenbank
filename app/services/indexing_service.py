import os
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image
from qdrant_client.http import models as rest_models

from app.services.qdrant_service import QdrantService
from app.services.clip_service import ClipService
from app.services.face_service import FaceService

logger = logging.getLogger(__name__)

# Namespace für deterministische UUID-Generierung anhand des Dateipfads (Idempotenz)
UUID_NAMESPACE = uuid.UUID("3d4b6845-816b-4e45-8b3c-9ad51b5bbfcb")


class IndexingService:
    """Orchestrierungsdienst für das Extrahieren von Bild- & Gesichtsmerkmalen und das Indexieren in Qdrant."""

    def __init__(
        self,
        qdrant_service: QdrantService,
        clip_service: ClipService,
        face_service: FaceService,
    ):
        self.qdrant = qdrant_service
        self.clip = clip_service
        self.face = face_service

    def index_image_file(
        self,
        file_path: Path,
        cluster_id_mapping: Optional[dict[str, str]] = None,
    ) -> Tuple[bool, int]:
        """
        Verarbeitet eine einzelne Bilddatei:
        1. CLIP-Embedding berechnen und in `archive_images` einfügen
        2. Gesichter erkennen, ArcFace-Embeddings berechnen und in `archive_faces` einfügen

        Gibt (Erfolg, Anzahl erkannter Gesichter) zurück.
        """
        abs_path = file_path.resolve()
        path_str = str(abs_path)

        try:
            # 1. CLIP Embedding (512-dim)
            clip_vector = self.clip.embed_image(path_str)

            # 2. Gesichtserkennung & ArcFace Embeddings (512-dim)
            faces_data = self.face.extract_faces(path_str)

            file_size = os.path.getsize(abs_path)
            with Image.open(abs_path) as img:
                width, height = img.size

            # Bild-ID deterministisch aus Dateipfad bilden (ermöglicht Re-Indizierung ohne Duplikate)
            image_id = str(uuid.uuid5(UUID_NAMESPACE, path_str))

            # 3. Bild-Point für archive_images
            image_point = rest_models.PointStruct(
                id=image_id,
                vector=clip_vector,
                payload={
                    "image_path": path_str,
                    "filename": file_path.name,
                    "width": width,
                    "height": height,
                    "file_size": file_size,
                    "faces_count": len(faces_data),
                    "indexed_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            self.qdrant.upsert_images([image_point])

            # 4. Gesichts-Points für archive_faces
            face_points = []
            for idx, face_info in enumerate(faces_data):
                face_id = str(uuid.uuid5(UUID_NAMESPACE, f"{path_str}#face_{idx}"))
                cluster_id = None
                if cluster_id_mapping and face_id in cluster_id_mapping:
                    cluster_id = cluster_id_mapping[face_id]

                face_point = rest_models.PointStruct(
                    id=face_id,
                    vector=face_info["embedding"],
                    payload={
                        "image_path": path_str,
                        "bbox": face_info["bbox"],
                        "face_id": face_id,
                        "cluster_id": cluster_id,
                        "det_score": face_info["det_score"],
                        "face_index": idx,
                        "parent_image_id": image_id,
                        "indexed_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                face_points.append(face_point)

            if face_points:
                self.qdrant.upsert_faces(face_points)

            return True, len(faces_data)

        except Exception as e:
            logger.error("Fehler bei der Indizierung von '%s': %s", path_str, e, exc_info=True)
            return False, 0
