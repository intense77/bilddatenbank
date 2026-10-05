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
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        # WAL-Modus und Performance-PRAGMAs für maximale Lese-/Schreib-Entkopplung
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA cache_size = -64000;")  # 64 MB RAM Cache
        conn.execute("PRAGMA busy_timeout = 10000;") # 10s Timeout bei parallelen Zugriffen
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
                        face_count INTEGER DEFAULT 0,
                        preview_image TEXT,
                        notes TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                # Migration: Falls face_count noch fehlt
                try:
                    conn.execute("ALTER TABLE clusters ADD COLUMN face_count INTEGER DEFAULT 0;")
                except Exception:
                    pass

                # Performance-Indizes für schnelle Suche und Lookups
                conn.execute("CREATE INDEX IF NOT EXISTS idx_metadata_filename ON metadata(file_name);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_metadata_title ON metadata(title);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_metadata_signature ON metadata(signature);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_clusters_name ON clusters(name);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_clusters_face_count ON clusters(face_count DESC);")

                conn.commit()
            logger.info("SQLite-Archivdatenbank erfolgreich initialisiert (WAL-Modus aktiv): %s", self.db_path)
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
        face_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Erstellt oder aktualisiert Cluster-Informationen."""
        now = datetime.now().isoformat()
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO clusters (id, name, preview_image, notes, face_count, updated_at)
                    VALUES (?, ?, ?, ?, COALESCE(?, 0), ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = COALESCE(excluded.name, clusters.name),
                        preview_image = COALESCE(excluded.preview_image, clusters.preview_image),
                        notes = COALESCE(excluded.notes, clusters.notes),
                        face_count = CASE WHEN ? IS NOT NULL THEN ? ELSE clusters.face_count END,
                        updated_at = excluded.updated_at
                """, (str(cluster_id), name, preview_image, notes, face_count, now, face_count, face_count))
                conn.commit()

            return {
                "id": str(cluster_id),
                "name": name,
                "preview_image": preview_image,
                "notes": notes,
                "face_count": face_count,
                "updated_at": now,
            }
        except Exception as e:
            logger.error("Fehler beim Speichern des Clusters in SQLite: %s", e)
            raise e

    def delete_cluster(self, cluster_id: str) -> bool:
        """Löscht ein Cluster aus der SQLite-Datenbank (z. B. nach Cluster-Merge)."""
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM clusters WHERE id = ?", (str(cluster_id),))
                conn.commit()
            return True
        except Exception as e:
            logger.error("Fehler beim Löschen des Clusters %s: %s", cluster_id, e)
            return False

    def bulk_sync_clusters(self, clusters: List[Dict[str, Any]]) -> None:
        """
        Synchronisiert eine Liste aggregierter Personen-Cluster atomar per Batch in SQLite.
        Ermöglicht Sub-5ms Reaktionszeiten für get_clusters() im Frontend.
        """
        if not clusters:
            return
        now = datetime.now().isoformat()
        rows = [
            (
                str(c["cluster_id"]),
                c.get("label") or c.get("name"),
                int(c.get("face_count", 0)),
                c.get("preview_image"),
                c.get("notes"),
                now,
            )
            for c in clusters
        ]
        try:
            with self._get_connection() as conn:
                conn.executemany("""
                    INSERT INTO clusters (id, name, face_count, preview_image, notes, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = COALESCE(excluded.name, clusters.name),
                        face_count = excluded.face_count,
                        preview_image = COALESCE(excluded.preview_image, clusters.preview_image),
                        notes = COALESCE(excluded.notes, clusters.notes),
                        updated_at = excluded.updated_at
                """, rows)
                conn.commit()
            logger.info("Erfolgreich %d Cluster in SQLite synchronisiert.", len(rows))
        except Exception as e:
            logger.error("Fehler beim Bulk-Sync der Cluster in SQLite: %s", e)

    def get_clusters_summary(self) -> List[Dict[str, Any]]:
        """
        Liefert alle Personen-Cluster sortiert nach Häufigkeit (face_count DESC)
        blitzschnell aus der lokalen SQLite-Datenbank (< 5 ms statt 13 s Qdrant-Scroll).
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT id AS cluster_id, name AS label, face_count, preview_image, notes, updated_at
                    FROM clusters
                    WHERE face_count > 0 OR name IS NOT NULL
                    ORDER BY face_count DESC, id ASC
                """)
                clusters = []
                for r in cursor.fetchall():
                    d = dict(r)
                    d["faces"] = []
                    if not d.get("preview_image"):
                        d["preview_image"] = f"/faces/clusters/{d['cluster_id']}/preview"
                    clusters.append(d)
                return clusters
        except Exception as e:
            logger.error("Fehler beim Abrufen der Cluster-Übersicht aus SQLite: %s", e)
            return []

    def list_all_clusters(self) -> List[Dict[str, Any]]:
        """Liefert alle gespeicherten Cluster mit Notizen und Namen."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT * FROM clusters ORDER BY updated_at DESC")
                return [dict(r) for r in cursor.fetchall()]
        except Exception as e:
            logger.error("Fehler beim Abfragen aller Cluster: %s", e)
            return []

    def search_clusters(self, query: str) -> List[Dict[str, Any]]:
        """Sucht nach Clustern anhand des Namens oder der Notizen."""
        clean_q = query.strip()
        if not clean_q:
            return []
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM clusters WHERE name LIKE ? OR notes LIKE ? ORDER BY name ASC",
                    (f"%{clean_q}%", f"%{clean_q}%")
                )
                return [dict(r) for r in cursor.fetchall()]
        except Exception as e:
            logger.error("Fehler bei der Clustersuche in SQLite: %s", e)
            return []

    def search_metadata(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Sucht nach Bildmetadaten in title, signature, description, creator, file_name."""
        clean_q = query.strip()
        if not clean_q:
            return []
        pattern = f"%{clean_q}%"
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT * FROM metadata 
                    WHERE title LIKE ? OR signature LIKE ? OR description LIKE ? OR creator LIKE ? OR file_name LIKE ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (pattern, pattern, pattern, pattern, pattern, limit)
                )
                return [dict(r) for r in cursor.fetchall()]
        except Exception as e:
            logger.error("Fehler bei der Metadatensuche in SQLite: %s", e)
            return []


metadata_db = MetadataDatabase()

