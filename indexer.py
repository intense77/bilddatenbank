#!/usr/bin/env python3
"""
CLI-Skript zur Batch-Indexierung historischer Bildbestände in Qdrant.

Unterstützt:
- Rekursives Scannen nach .jpg, .jpeg, .png, .tif, .tiff
- Deterministische UUIDv5-Generierung (relativer Pfad)
- Inkrementelle Updates (Überspringen bereits indexierter Dateien)
- CLIP-Embeddings (archive_images)
- Optionale Gesichtserkennung via InsightFace (archive_faces)
- Fortschrittsanzeige via tqdm und strukturierte Logs
"""

import argparse
import logging
import sys
import uuid
from pathlib import Path
from typing import List, Tuple

# Logger Setup mit strukturiertem Format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("indexer")

# Namespace für deterministische UUIDv5-Generierung anhand des relativen Dateipfads
UUID_NAMESPACE = uuid.UUID("3d4b6845-816b-4e45-8b3c-9ad51b5bbfcb")

# Unterstützte Archiv-Bildformate
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def scan_source_directory(source_dir: Path) -> List[Path]:
    """Scannt das Verzeichnis rekursiv nach unterstützten Bilddateien."""
    found_files = []
    for file_path in source_dir.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
            found_files.append(file_path)
    return sorted(found_files)


def chunked(iterable: list, n: int):
    """Teilt eine Liste in Chunks der Größe n auf."""
    for i in range(0, len(iterable), n):
        yield iterable[i : i + n]


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch-Indexierung historischer Scans für Bild- und Gesichtssuche."
    )
    parser.add_argument(
        "--source-dir",
        "-s",
        type=Path,
        required=True,
        help="Pfad zum Quellordner historischer Scans (.jpg, .jpeg, .png, .tif, .tiff).",
    )
    parser.add_argument(
        "--batch-size",
        "-b",
        type=int,
        default=32,
        help="Batch-Größe für die Verarbeitung und das Upserting nach Qdrant (Standard: 32).",
    )
    parser.add_argument(
        "--skip-faces",
        action="store_true",
        default=False,
        help="Deaktiviert die Gesichtserkennung (nur semantische CLIP-Bildsuche).",
    )
    parser.add_argument(
        "--cluster-faces",
        action="store_true",
        default=False,
        help="Führt nach Abschluss der Indexierung automatisch das DBSCAN-Personen-Clustering aus.",
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        default=False,
        help="Erzwingt Neuindexierung aller Dateien (überspringt existierende IDs nicht).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Dateien nur scannen und auflisten, keine Embeddings berechnen.",
    )
    return parser.parse_args()


def main():
    args = parse_arguments()

    source_dir: Path = args.source_dir.resolve()
    if not source_dir.exists() or not source_dir.is_dir():
        logger.error("Quellverzeichnis existiert nicht oder ist kein Ordner: %s", source_dir)
        sys.exit(1)

    logger.info("Starte Dateisuche in: %s", source_dir)
    image_files = scan_source_directory(source_dir)
    total_images = len(image_files)
    logger.info("%d Bilddateien gefunden.", total_images)

    if total_images == 0:
        logger.info("Keine passenden Bilddateien gefunden. Beende.")
        return

    if args.dry_run:
        logger.info("[Dry-Run] Die ersten gefundenen Dateien:")
        for p in image_files[:10]:
            logger.info(" - %s (relativ: %s)", p, p.relative_to(source_dir).as_posix())
        if total_images > 10:
            logger.info(" ... und %d weitere Dateien.", total_images - 10)
        return

    # Lade Qdrant- und Service-Abhängigkeiten
    try:
        from qdrant_client.http import models as rest_models
        from app.core.config import settings
        from app.services.clip_service import ClipService
        from app.services.face_service import FaceService
        from app.services.qdrant_service import QdrantService
    except ImportError as e:
        logger.error(
            "Benötigte Abhängigkeiten fehlen (%s). Bitte zuerst 'pip install -r requirements.txt' ausführen.",
            e,
        )
        sys.exit(1)

    # Optionaler TQDM-Import mit Fallback
    try:
        from tqdm import tqdm
    except ImportError:
        class tqdm:
            def __init__(self, total=None, desc="", unit="", **kwargs):
                self.total = total
                self.desc = desc
                self.n = 0
            def update(self, n=1):
                self.n += n
                if self.total and (self.n % 25 == 0 or self.n == self.total):
                    logger.info("%s: %d/%d verarbeitet", self.desc, self.n, self.total)
            def set_postfix(self, mapping=None, **kwargs):
                pass
            def close(self):
                pass

    # Qdrant Client verbinden und Collections initialisieren
    logger.info("Verbinde mit Qdrant (%s:%d)...", settings.QDRANT_HOST, settings.QDRANT_PORT)
    qdrant_service = QdrantService()
    if not qdrant_service.check_health():
        logger.error(
            "Verbindung zu Qdrant fehlgeschlagen! Bitte prüfen Sie, ob Qdrant läuft "
            "(z. B. via 'docker compose up -d')."
        )
        sys.exit(1)

    logger.info("Prüfe / initialisiere Qdrant-Collections...")
    qdrant_service.init_collections()

    # Modelle laden
    logger.info("Lade CLIP-Modell auf Device '%s'...", settings.effective_device)
    clip_service = ClipService()

    face_service = None
    if not args.skip_faces:
        logger.info("Lade InsightFace-Modell auf Device '%s'...", settings.effective_device)
        face_service = FaceService()
    else:
        logger.info("Gesichtserkennung übersprungen (--skip-faces aktiv).")

    # Statistiken
    total_indexed = 0
    total_skipped = 0
    total_faces = 0
    total_errors = 0

    logger.info(
        "Starte Batch-Indexierung (Batch-Größe: %d, Skip-Faces: %s, Force: %s)...",
        args.batch_size,
        args.skip_faces,
        args.force,
    )

    progress_bar = tqdm(total=total_images, desc="Indexiere Scans", unit="Bild")

    for batch in chunked(image_files, args.batch_size):
        # 1. Deterministische IDs für den Batch generieren
        batch_entries: List[Tuple[Path, str, str]] = []  # (file_path, rel_path_str, image_id)
        batch_ids: List[str] = []

        for file_path in batch:
            rel_path = file_path.relative_to(source_dir).as_posix()
            image_id = str(uuid.uuid5(UUID_NAMESPACE, rel_path))
            batch_entries.append((file_path, rel_path, image_id))
            batch_ids.append(image_id)

        # 2. Inkrementelles Update: Prüfe vorab, welche IDs bereits in Qdrant existieren
        if not args.force:
            existing_ids = qdrant_service.get_existing_ids(
                collection_name=settings.COLLECTION_IMAGES,
                ids=batch_ids,
            )
        else:
            existing_ids = set()

        image_points: List[rest_models.PointStruct] = []
        face_points: List[rest_models.PointStruct] = []

        for file_path, rel_path, image_id in batch_entries:
            if image_id in existing_ids:
                total_skipped += 1
                progress_bar.update(1)
                continue

            abs_path_str = str(file_path.resolve())

            try:
                # 3. CLIP-Embedding berechnen (archive_images)
                clip_vector = clip_service.embed_image(file_path)
                image_point = rest_models.PointStruct(
                    id=image_id,
                    vector=clip_vector,
                    payload={
                        "file_path": abs_path_str,
                        "file_name": file_path.name,
                    },
                )
                image_points.append(image_point)

                # 4. Optionale Gesichtserkennung (archive_faces)
                if face_service is not None:
                    detected_faces = face_service.extract_faces(file_path)
                    for face_idx, face in enumerate(detected_faces):
                        face_id = str(uuid.uuid5(UUID_NAMESPACE, f"{rel_path}#face_{face_idx}"))
                        face_point = rest_models.PointStruct(
                            id=face_id,
                            vector=face["embedding"],
                            payload={
                                "file_path": abs_path_str,
                                "bbox": face["bbox"],
                                "det_score": face["det_score"],
                            },
                        )
                        face_points.append(face_point)
                    total_faces += len(detected_faces)

                total_indexed += 1

            except Exception as e:
                total_errors += 1
                logger.error("Fehler beim Indexieren von '%s': %s", rel_path, e)

            progress_bar.update(1)

        # 5. Batch-Upsert in Qdrant
        try:
            if image_points:
                qdrant_service.upsert_images(image_points)
            if face_points:
                qdrant_service.upsert_faces(face_points)
        except Exception as e:
            logger.error("Fehler beim Qdrant-Batch-Upsert: %s", e, exc_info=True)
            total_errors += len(image_points)
            total_indexed -= len(image_points)

        progress_bar.set_postfix({
            "Neu": total_indexed,
            "Übersprungen": total_skipped,
            "Gesichter": total_faces,
            "Fehler": total_errors,
        })

    progress_bar.close()

    # Strukturierte Zusammenfassung ausgeben
    logger.info("=" * 50)
    logger.info("BATCH-INDEXIERUNG ABGESCHLOSSEN")
    logger.info("Gesamt gefundene Scans: %d", total_images)
    logger.info("Neu indexierte Bilder:  %d", total_indexed)
    logger.info("Übersprungen (bereits da): %d", total_skipped)
    logger.info("Erfasste Gesichter:     %d", total_faces)
    logger.info("Fehlerhafte Dateien:    %d", total_errors)
    logger.info("=" * 50)

    # Optionales automatisches Clustering
    if args.cluster_faces and not args.skip_faces:
        logger.info("Starte anschließendes DBSCAN-Personen-Clustering (eps=0.55, min_samples=2)...")
        from app.services.clustering_service import ClusteringService
        clustering_service = ClusteringService(qdrant_service=qdrant_service)
        cluster_stats = clustering_service.run_clustering()
        logger.info(
            "Clustering abgeschlossen: %d Cluster gebildet, %d Gesichter zugeordnet (%d Rauschen/Einzelgänger).",
            cluster_stats.get("clusters_found", 0),
            cluster_stats.get("clustered_faces", 0),
            cluster_stats.get("noise_faces", 0),
        )


if __name__ == "__main__":
    main()
