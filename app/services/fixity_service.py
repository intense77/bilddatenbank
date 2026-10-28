"""
Fixity-Service & Autonomer Bitrot-Wächter für das Historische Bildarchiv.

Verantwortlich für:
1. Hintergrund-Fixity-Prüfung aller Master-Scans (SHA-256 Bitstream-Preservation).
2. Sofortige Alarmierung bei Bit-Rot, Silent Data Corruption oder fehlenden Dateien.
3. Thread-sicheres Progress-Monitoring für REST-API und Web-UI.
4. Bereitstellung von PREMIS 3.0 Exporten.
"""

import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from app.core.config import settings
from app.services.metadata_db import metadata_db
from app.services.premis_service import premis_service

logger = logging.getLogger("archive_app.fixity_service")


class FixityService:
    def __init__(self):
        self._lock = threading.Lock()
        self._is_running = False
        self._progress = {
            "current": 0,
            "total": 0,
            "current_file": None,
            "status": "idle",
            "percent": 0,
        }
        self._last_result: Optional[Dict[str, Any]] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._is_running

    def get_status(self) -> Dict[str, Any]:
        """Liefert den aktuellen Laufzeit- und Integritätsstatus."""
        with self._lock:
            summary = metadata_db.get_fixity_summary()
            return {
                "is_running": self._is_running,
                "progress": dict(self._progress),
                "summary": summary,
                "last_result": self._last_result,
                "alert_active": summary.get("alert_active", False),
            }

    def get_corrupted_items(self) -> List[Dict[str, Any]]:
        """Liefert alle beschädigten oder vermissten Originale."""
        return metadata_db.get_corrupted_metadata()

    def start_verification(
        self,
        folder_path: Optional[str] = None,
        calculate_missing: bool = True,
        background: bool = True,
    ) -> Dict[str, Any]:
        """
        Startet eine Fixity-Integritätsprüfung.
        Wird standardmäßig in einem separaten Hintergrund-Thread ausgeführt,
        damit die Web-App responsiv bleibt.
        """
        with self._lock:
            if self._is_running:
                return {
                    "success": False,
                    "message": "Eine Fixity-Prüfung läuft bereits.",
                    "status": self.get_status(),
                }
            self._is_running = True
            self._progress = {
                "current": 0,
                "total": 0,
                "current_file": "Initialisiere...",
                "status": "running",
                "percent": 0,
            }

        if background:
            self._thread = threading.Thread(
                target=self._run_verification_thread,
                args=(folder_path, calculate_missing),
                daemon=True,
                name="FixityAuditDaemon",
            )
            self._thread.start()
            return {
                "success": True,
                "message": "Fixity-Integritätsprüfung im Hintergrund gestartet.",
                "is_running": True,
            }
        else:
            return self._run_verification_sync(folder_path, calculate_missing)

    def _progress_callback(self, current: int, total: int, file_path: str, status: str) -> None:
        percent = int((current / max(total, 1)) * 100)
        with self._lock:
            self._progress = {
                "current": current,
                "total": total,
                "current_file": Path(file_path).name,
                "status": status,
                "percent": percent,
            }

    def _run_verification_thread(self, folder_path: Optional[str], calculate_missing: bool) -> None:
        try:
            logger.info("Starte Hintergrund-Fixity-Audit (folder=%s)...", folder_path)
            res = metadata_db.verify_fixity(
                folder_path=folder_path,
                calculate_missing=calculate_missing,
                progress_callback=self._progress_callback,
            )
            with self._lock:
                self._last_result = {
                    "completed_at": datetime.now().isoformat(),
                    **res,
                }
                if res.get("corrupted", 0) > 0 or res.get("missing", 0) > 0:
                    logger.warning(
                        "FIXITY ALARM: %d beschädigte, %d fehlende Dateien!",
                        res.get("corrupted", 0),
                        res.get("missing", 0),
                    )
                else:
                    logger.info("Fixity-Audit erfolgreich abgeschlossen. Alle %d Dateien intakt.", res.get("total_checked", 0))
        except Exception as e:
            logger.error("Fehler im Fixity-Audit-Thread: %s", e)
        finally:
            with self._lock:
                self._is_running = False
                self._progress["status"] = "finished"

    def _run_verification_sync(self, folder_path: Optional[str], calculate_missing: bool) -> Dict[str, Any]:
        try:
            res = metadata_db.verify_fixity(
                folder_path=folder_path,
                calculate_missing=calculate_missing,
                progress_callback=self._progress_callback,
            )
            with self._lock:
                self._last_result = {
                    "completed_at": datetime.now().isoformat(),
                    **res,
                }
                self._is_running = False
                self._progress["status"] = "finished"
            return {
                "success": True,
                "result": self._last_result,
            }
        except Exception as e:
            with self._lock:
                self._is_running = False
                self._progress["status"] = "error"
            raise e

    def export_premis_for_path(self, file_path: str) -> bytes:
        """Erzeugt PREMIS-XML für eine einzelne Archivdatei."""
        meta = metadata_db.get_metadata(file_path) or {}
        return premis_service.generate_premis_for_file(file_path=file_path, metadata=meta)

    def export_premis_batch(self, file_paths: List[str]) -> bytes:
        """Erzeugt PREMIS-XML für eine Liste von Archivdateien."""
        items = []
        for p in file_paths:
            m = metadata_db.get_metadata(p) or {}
            m["file_path"] = p
            if "file_name" not in m:
                m["file_name"] = Path(p).name
            items.append(m)
        return premis_service.generate_premis(items=items)


fixity_service = FixityService()
