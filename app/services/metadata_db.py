"""
SQLite-Metadaten- & Cluster-Service für das Historische Bildarchiv.
Bietet eine leichtgewichtige, transaktionssichere relationale Speicherung
für Metadaten (Signatur, Datum, Bestandsbezeichnung, Bildpfad) und
Personen-Cluster (ID, Name, Vorschau, Notizen) neben der Qdrant-Vektordatenbank.
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("archive_app.metadata_db")

DEFAULT_DB_PATH = Path("data/archive_metadata.db")


class MetadataDatabase:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialisiert die relationalen Tabellen für Metadaten und Cluster."""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS metadata (
                        file_path TEXT PRIMARY KEY,
                        file_name TEXT,
                        signature TEXT,
                        title TEXT,
                        date TEXT,
                        creator TEXT,
                        description TEXT,
                        edit_settings TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                # Migration: Falls edit_settings noch fehlt
                try:
                    conn.execute("ALTER TABLE metadata ADD COLUMN edit_settings TEXT;")
                except Exception:
                    pass

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS clusters (
                        id TEXT PRIMARY KEY,
                        name TEXT,
                        preview_image TEXT,
                        notes TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                conn.commit()
            logger.info("SQLite-Archivdatenbank erfolgreich initialisiert: %s", self.db_path)
        except Exception as e:
            logger.error("Fehler beim Initialisieren der SQLite-Datenbank: %s", e)

    # ------------------ Metadaten-Operationen ------------------

    def get_metadata(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Liest die archivischen Metadaten für einen Bildpfad aus SQLite."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM metadata WHERE file_path = ?",
                    (str(file_path),)
                )
                row = cursor.fetchone()
                if row:
                    res = dict(row)
                    if res.get("edit_settings") and isinstance(res["edit_settings"], str):
                        import json
                        try:
                            res["edit_settings"] = json.loads(res["edit_settings"])
                        except Exception:
                            pass
                    return res
        except Exception as e:
            logger.error("Fehler beim Abrufen der Metadaten aus SQLite für %s: %s", file_path, e)
        return None

    def get_edit_settings(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Liest die gespeicherten Transformations-Parameter für ein Bild."""
        meta = self.get_metadata(file_path)
        if meta and meta.get("edit_settings"):
            return meta["edit_settings"]
        return None

    def save_edit_settings(self, file_path: str, edit_settings: Dict[str, Any]) -> Dict[str, Any]:
        """Speichert non-destruktive Transformations-Parameter in SQLite."""
        import json
        now = datetime.now().isoformat()
        clean_path = str(file_path)
        clean_name = Path(clean_path).name
        settings_json = json.dumps(edit_settings)

        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO metadata (file_path, file_name, edit_settings, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(file_path) DO UPDATE SET
                        edit_settings = excluded.edit_settings,
                        updated_at = excluded.updated_at
                """, (clean_path, clean_name, settings_json, now))
                conn.commit()
            return {"file_path": clean_path, "edit_settings": edit_settings, "updated_at": now}
        except Exception as e:
            logger.error("Fehler beim Speichern der edit_settings in SQLite: %s", e)
            raise e

    def upsert_metadata(
        self,
        file_path: str,
        file_name: Optional[str] = None,
        signature: Optional[str] = None,
        title: Optional[str] = None,
        date: Optional[str] = None,
        creator: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Erstellt oder aktualisiert den Metadatensatz eines Archivbildes."""
        now = datetime.now().isoformat()
        clean_path = str(file_path)
        clean_name = file_name or Path(clean_path).name

        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO metadata (file_path, file_name, signature, title, date, creator, description, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(file_path) DO UPDATE SET
                        file_name = excluded.file_name,
                        signature = COALESCE(excluded.signature, metadata.signature),
                        title = COALESCE(excluded.title, metadata.title),
                        date = COALESCE(excluded.date, metadata.date),
                        creator = COALESCE(excluded.creator, metadata.creator),
                        description = COALESCE(excluded.description, metadata.description),
                        updated_at = excluded.updated_at
                """, (clean_path, clean_name, signature, title, date, creator, description, now))
                conn.commit()

            return {
                "file_path": clean_path,
                "file_name": clean_name,
                "signature": signature,
                "title": title,
                "date": date,
                "creator": creator,
                "description": description,
                "updated_at": now,
            }
        except Exception as e:
            logger.error("Fehler beim Speichern der Metadaten in SQLite: %s", e)
            raise e

    # ------------------ Cluster-Operationen ------------------

    def get_cluster(self, cluster_id: str) -> Optional[Dict[str, Any]]:
        """Liest Cluster-Metadaten (Name, Notizen, Vorschau) aus SQLite."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM clusters WHERE id = ?",
                    (str(cluster_id),)
                )
                row = cursor.fetchone()
                if row:
                    return dict(row)
        except Exception as e:
            logger.error("Fehler beim Abrufen von Cluster %s aus SQLite: %s", cluster_id, e)
        return None

    def upsert_cluster(
        self,
        cluster_id: str,
        name: Optional[str] = None,
        preview_image: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Erstellt oder aktualisiert Cluster-Informationen."""
        now = datetime.now().isoformat()
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO clusters (id, name, preview_image, notes, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = COALESCE(excluded.name, clusters.name),
                        preview_image = COALESCE(excluded.preview_image, clusters.preview_image),
                        notes = COALESCE(excluded.notes, clusters.notes),
                        updated_at = excluded.updated_at
                """, (str(cluster_id), name, preview_image, notes, now))
                conn.commit()

            return {
                "id": str(cluster_id),
                "name": name,
                "preview_image": preview_image,
                "notes": notes,
                "updated_at": now,
            }
        except Exception as e:
            logger.error("Fehler beim Speichern des Clusters in SQLite: %s", e)
            raise e

    def list_all_clusters(self) -> List[Dict[str, Any]]:
        """Liefert alle gespeicherten Cluster mit Notizen und Namen."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT * FROM clusters ORDER BY updated_at DESC")
                return [dict(r) for r in cursor.fetchall()]
        except Exception as e:
            logger.error("Fehler beim Abfragen aller Cluster: %s", e)
            return []


metadata_db = MetadataDatabase()
