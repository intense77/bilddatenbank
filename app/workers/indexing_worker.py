#!/usr/bin/env python3
"""
Isolierter Hintergrund-Worker für die Bildarchiv-Indexierung.
Läuft als vollständig separater Betriebssystem-Prozess (Subprozess), um den
FastAPI/Uvicorn-Webserver vor Speicherlecks, C-Heap-Fragmentierung und OOM-Kills
zu schützen. Nach Abschluss wird der gesamte Prozess-Speicher restlos vom Kernel freigegeben.
"""

import os
import sys
import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

# Sicherstellen, dass das Projektverzeichnis im PYTHONPATH liegt
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.core.config import settings
from app.services.metadata_db import metadata_db
from app.services.qdrant_service import QdrantService
from app.services.clip_service import ClipService
from app.services.face_service import FaceService
from app.services.indexing_service import IndexingService, update_indexing_progress
from app.services.clustering_service import ClusteringService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [Worker-%(process)d] %(name)s: %(message)s",
)
logger = logging.getLogger("indexing_worker")


def main():
    parser = argparse.ArgumentParser(description="Isolierter Hintergrund-Indexierungs-Worker")
    parser.add_argument("--folder", type=str, required=True, help="Absoluter Pfad zum Bildordner")
    parser.add_argument("--job-id", type=str, required=True, help="Eindeutige Job-ID")
    parser.add_argument("--batch-id", type=str, default=None, help="Eindeutige Import-Batch-ID")
    parser.add_argument("--batch-name", type=str, default=None, help="Sprechende Bestandsbezeichnung")
    parser.add_argument("--notes", type=str, default=None, help="Optionale Bemerkungen zum Bestand")
    parser.add_argument("--recursive", action="store_true", default=True, help="Rekursiv scannen")
    parser.add_argument("--no-recursive", dest="recursive", action="store_false")
    parser.add_argument("--force", action="store_true", default=False, help="Neuindexierung erzwingen")
    parser.add_argument("--cluster-faces", action="store_true", default=False, help="Clustering nach Import ausführen")

    args = parser.parse_args()

    # Prozess-Priorität für den Hintergrund-Import herabsetzen (QoS),
    # damit interaktive Web- und Suchanfragen des Benutzers Vorrang erhalten
    try:
        os.nice(10)
    except Exception:
        pass

    pid = os.getpid()
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()
    folder_path = Path(args.folder).resolve()

    batch_id = args.batch_id or f"batch_{args.job_id}"
    batch_name = args.batch_name.strip() if args.batch_name and args.batch_name.strip() else f"Import {folder_path.name} ({now_dt.strftime('%d.%m.%Y %H:%M')})"

    logger.info("Starte isolierten Indexierungs-Worker (PID %d, Job %s, Batch '%s' [%s]) für '%s'...",
                pid, args.job_id, batch_name, batch_id, folder_path)

    # Import-Batch im Akzessionsjournal anlegen
    try:
        metadata_db.create_import_batch(
            batch_id=batch_id,
            name=batch_name,
            folder_path=str(folder_path),
            notes=args.notes,
            status="running",
        )
    except Exception as be:
        logger.warning("Konnte Import-Batch %s nicht in SQLite initialisieren: %s", batch_id, be)

    update_indexing_progress({
        "job_id": args.job_id,
        "batch_id": batch_id,
        "batch_name": batch_name,
        "pid": pid,
        "is_running": True,
        "finished": False,
        "folder_path": str(folder_path),
        "total_found": 0,
        "processed_count": 0,
        "current_file": "Initialisiere KI-Modelle & Vektordatenbank...",
        "new_indexed": 0,
        "skipped": 0,
        "faces_detected": 0,
        "already_fully_indexed": False,
        "percent": 0,
        "error": None,
        "started_at": now_iso,
        "last_updated": now_iso,
        "clustering_status": None,
        "clustering_message": None,
    })

    try:
        qdrant_service = QdrantService()
        clip_service = ClipService()
        face_service = None
        if settings.ENABLE_FACE_RECOGNITION:
            try:
                face_service = FaceService()
            except Exception as fe:
                logger.warning("FaceService konnte nicht geladen werden: %s", fe)

        indexing_service = IndexingService(
            qdrant_service=qdrant_service,
            clip_service=clip_service,
            face_service=face_service,
        )

        stats = indexing_service.index_folder(
            folder_path=folder_path,
            recursive=args.recursive,
            force=args.force,
            import_id=batch_id,
        )

        # Batch-Statistiken in SQLite aktualisieren
        try:
            metadata_db.update_import_batch(
                batch_id=batch_id,
                status="completed",
                image_count=stats.get("new_indexed", 0),
                face_count=stats.get("faces_detected", 0),
                skipped_count=stats.get("skipped", 0),
                finished_at=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as ue:
            logger.warning("Konnte Import-Batch-Abschluss nicht aktualisieren: %s", ue)

        # Sicheres Clustering mit Schwellenwert-Prüfung
        if (
            args.cluster_faces
            and settings.ENABLE_FACE_RECOGNITION
            and stats.get("faces_detected", 0) > 0
        ):
            clustering_service = ClusteringService(qdrant_service=qdrant_service)
            total_faces_count = 0
            try:
                coll_info = qdrant_service.client.get_collection(settings.COLLECTION_FACES)
                total_faces_count = coll_info.points_count or 0
            except Exception:
                pass

            max_threshold = getattr(settings, "AUTO_CLUSTER_MAX_FACES", 500000)
            if total_faces_count > max_threshold:
                msg = (
                    f"Automatisches Clustering nach Import übersprungen: Archiv enthält {total_faces_count:,} Gesichter "
                    f"(Sicherheitslimit für Inline-Clustering: {max_threshold:,}). "
                    "Bitte führen Sie das Personen-Clustering gezielt im Personen-Tab aus, um Speicherüberlastung zu vermeiden."
                )
                logger.info(msg)
                update_indexing_progress({
                    "clustering_status": "skipped_large_collection",
                    "clustering_message": msg,
                })
            else:
                try:
                    update_indexing_progress({
                        "current_file": f"Führe automatisches Personen-Clustering aus ({total_faces_count} Gesichter)...",
                        "clustering_status": "running",
                    })
                    clustering_service.run_clustering()
                    update_indexing_progress({
                        "clustering_status": "completed",
                        "clustering_message": "Automatisches Personen-Clustering erfolgreich abgeschlossen.",
                    })
                except Exception as ce:
                    logger.warning("Clustering nach Import fehlgeschlagen: %s", ce)
                    update_indexing_progress({
                        "clustering_status": "failed",
                        "clustering_message": f"Clustering-Fehler: {ce}",
                    })

        logger.info("Isolierter Indexierungs-Worker (PID %d) erfolgreich beendet.", pid)

    except Exception as e:
        logger.error("Fehler im isolierten Indexierungs-Worker: %s", e, exc_info=True)
        try:
            metadata_db.update_import_batch(
                batch_id=batch_id,
                status="failed",
                notes=f"Fehler: {e}",
                finished_at=datetime.now(timezone.utc).isoformat(),
            )
        except Exception:
            pass
        update_indexing_progress({
            "is_running": False,
            "finished": True,
            "error": str(e),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        })
        sys.exit(1)


if __name__ == "__main__":
    main()
