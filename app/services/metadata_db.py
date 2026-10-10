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

                # Migration: Falls Zweiblatt-Spalten (companion_path, sheet_role, verso_notes) oder import_id noch fehlen
                for col in ["companion_path TEXT", "sheet_role TEXT", "verso_notes TEXT", "import_id TEXT"]:
                    try:
                        conn.execute(f"ALTER TABLE metadata ADD COLUMN {col};")
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

                # Tabelle für archivische Import-Chargen & Akzessionsjournal (Provenienz & Rollback)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS import_batches (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        folder_path TEXT NOT NULL,
                        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        finished_at TIMESTAMP,
                        image_count INTEGER DEFAULT 0,
                        face_count INTEGER DEFAULT 0,
                        skipped_count INTEGER DEFAULT 0,
                        status TEXT DEFAULT 'running',
                        notes TEXT
                    );
                """)

                # Performance-Indizes für schnelle Suche und Lookups
                conn.execute("CREATE INDEX IF NOT EXISTS idx_metadata_filename ON metadata(file_name);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_metadata_title ON metadata(title);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_metadata_signature ON metadata(signature);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_metadata_companion ON metadata(companion_path);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_metadata_import_id ON metadata(import_id);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_clusters_name ON clusters(name);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_clusters_face_count ON clusters(face_count DESC);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_import_batches_started ON import_batches(started_at DESC);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_import_batches_status ON import_batches(status);")

                # Tabelle für systemweiten Job- und Verarbeitungsstatus (Prozess-übergreifend)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS system_state (
                        key TEXT PRIMARY KEY,
                        value TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                conn.commit()
            logger.info("SQLite-Archivdatenbank erfolgreich initialisiert (WAL-Modus aktiv): %s", self.db_path)
        except Exception as e:
            logger.error("Fehler beim Initialisieren der SQLite-Datenbank: %s", e)

    def set_system_state(self, key: str, value: Any) -> None:
        """Speichert beliebigen Zustand (z. B. Job-Fortschritt) atomar als JSON-String in SQLite."""
        try:
            import json
            serialized = json.dumps(value, ensure_ascii=False)
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO system_state (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP;
                    """,
                    (key, serialized),
                )
                conn.commit()
        except Exception as e:
            logger.debug("Fehler beim Speichern von system_state[%s]: %s", key, e)

    def get_system_state(self, key: str, default: Any = None) -> Any:
        """Liest einen Zustand als geparstes JSON-Objekt aus SQLite."""
        try:
            import json
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT value FROM system_state WHERE key = ?", (key,))
                row = cursor.fetchone()
                if row and row["value"]:
                    return json.loads(row["value"])
        except Exception as e:
            logger.debug("Fehler beim Lesen von system_state[%s]: %s", key, e)
        return default

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

    def bulk_sync_clusters(self, clusters: List[Dict[str, Any]], preserve_existing_names: bool = False) -> None:
        """
        Synchronisiert eine Liste aggregierter Personen-Cluster atomar per Batch in SQLite.
        Ermöglicht Sub-5ms Reaktionszeiten für get_clusters() im Frontend.
        preserve_existing_names: Wenn False, werden Labels exakt übernommen bzw. auf NULL gesetzt,
        um Namens-Verschiebungen bei Cluster-Neuberechnungen zu verhindern.
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
        name_clause = "COALESCE(excluded.name, clusters.name)" if preserve_existing_names else "excluded.name"
        try:
            with self._get_connection() as conn:
                conn.executemany(f"""
                    INSERT INTO clusters (id, name, face_count, preview_image, notes, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = {name_clause},
                        face_count = excluded.face_count,
                        preview_image = COALESCE(excluded.preview_image, clusters.preview_image),
                        notes = COALESCE(excluded.notes, clusters.notes),
                        updated_at = excluded.updated_at
                """, rows)
                conn.commit()
            logger.info("Erfolgreich %d Cluster in SQLite synchronisiert (preserve_names=%s).", len(rows), preserve_existing_names)
        except Exception as e:
            logger.error("Fehler beim Bulk-Sync der Cluster in SQLite: %s", e)

    def sync_exact_cluster_labels(self, cluster_to_label: Dict[str, str]) -> None:
        """
        Gleicht die Klarnamen der Personen-Cluster in SQLite exakt mit den echten Labels aus Qdrant ab.
        Entfernt alte, verschobene Namen und setzt verifizierte Klarnamen für die aktuellen Cluster_IDs.
        """
        now = datetime.now().isoformat()
        try:
            with self._get_connection() as conn:
                # 1. Bestehende Namen leeren, um Geisternamen aus alten Clusterungen zu beseitigen
                conn.execute("UPDATE clusters SET name = NULL WHERE name IS NOT NULL;")

                # 2. Die aktuellen Labels für die tatsächlichen Cluster-IDs setzen
                for cid, label in cluster_to_label.items():
                    if not label or not str(label).strip():
                        continue
                    conn.execute("""
                        INSERT INTO clusters (id, name, face_count, preview_image, updated_at)
                        VALUES (?, ?, 0, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            name = excluded.name,
                            updated_at = excluded.updated_at
                    """, (str(cid), str(label).strip(), f"/faces/clusters/{cid}/preview", now))
                conn.commit()
            logger.info("Erfolgreich %d Personen-Labels aus Qdrant in SQLite synchronisiert.", len(cluster_to_label))
        except Exception as e:
            logger.error("Fehler beim Synchronisieren der Cluster-Labels in SQLite: %s", e)
            raise e

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

    def update_verso_notes(
        self,
        file_path: str,
        notes: str,
        companion_path: Optional[str] = None,
        sheet_role: Optional[str] = None,
    ) -> bool:
        """Speichert oder aktualisiert Rückseiten-Notizen / Transkriptionen und optionale Zweiblatt-Verknüpfungen."""
        try:
            with self._get_connection() as conn:
                row = conn.execute("SELECT file_path FROM metadata WHERE file_path = ?;", (file_path,)).fetchone()
                if row:
                    conn.execute(
                        """UPDATE metadata SET 
                            verso_notes = ?,
                            companion_path = COALESCE(?, companion_path),
                            sheet_role = COALESCE(?, sheet_role),
                            updated_at = CURRENT_TIMESTAMP
                        WHERE file_path = ?;""",
                        (notes, companion_path, sheet_role, file_path),
                    )
                else:
                    file_name = Path(file_path).name
                    conn.execute(
                        """INSERT INTO metadata (file_path, file_name, verso_notes, companion_path, sheet_role, updated_at)
                        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP);""",
                        (file_path, file_name, notes, companion_path, sheet_role),
                    )
                conn.commit()
                return True
        except Exception as e:
            logger.error("Fehler beim Speichern der Verso-Notizen für %s: %s", file_path, e)
            return False

    def get_verso_notes(self, file_path: str) -> Optional[str]:
        """Liest Rückseiten-Notizen aus der Datenbank."""
        try:
            with self._get_connection() as conn:
                row = conn.execute("SELECT verso_notes FROM metadata WHERE file_path = ?;", (file_path,)).fetchone()
                if row and row["verso_notes"]:
                    return row["verso_notes"]
                return None
        except Exception as e:
            logger.debug("Fehler beim Lesen der Verso-Notizen: %s", e)
            return None

    def search_metadata(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Sucht nach Bildmetadaten in title, signature, description, creator, file_name und verso_notes."""
        clean_q = query.strip()
        if not clean_q:
            return []
        pattern = f"%{clean_q}%"
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT * FROM metadata 
                    WHERE title LIKE ? OR signature LIKE ? OR description LIKE ? OR creator LIKE ? OR file_name LIKE ? OR verso_notes LIKE ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (pattern, pattern, pattern, pattern, pattern, pattern, limit)
                )
                return [dict(r) for r in cursor.fetchall()]
        except Exception as e:
            logger.error("Fehler bei der Metadatensuche in SQLite: %s", e)
            return []

    # ------------------ Import-Batches & Akzessionsjournal ------------------

    def create_import_batch(
        self,
        batch_id: str,
        name: str,
        folder_path: str,
        notes: Optional[str] = None,
        status: str = "running",
    ) -> Dict[str, Any]:
        """Legt einen neuen Import-Batch im Akzessionsjournal an."""
        now_iso = datetime.now().isoformat()
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO import_batches (id, name, folder_path, started_at, status, notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        folder_path = excluded.folder_path,
                        notes = COALESCE(excluded.notes, import_batches.notes),
                        status = excluded.status;
                    """,
                    (batch_id, name.strip(), folder_path.strip(), now_iso, status, notes),
                )
                conn.commit()
            return self.get_import_batch(batch_id) or {
                "id": batch_id,
                "name": name,
                "folder_path": folder_path,
                "started_at": now_iso,
                "status": status,
                "notes": notes,
            }
        except Exception as e:
            logger.error("Fehler beim Anlegen des Import-Batches %s: %s", batch_id, e)
            raise

    def update_import_batch(
        self,
        batch_id: str,
        status: Optional[str] = None,
        image_count: Optional[int] = None,
        face_count: Optional[int] = None,
        skipped_count: Optional[int] = None,
        notes: Optional[str] = None,
        finished_at: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Aktualisiert die Statistiken und den Status eines Import-Batches."""
        updates = []
        params = []
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if image_count is not None:
            updates.append("image_count = ?")
            params.append(image_count)
        if face_count is not None:
            updates.append("face_count = ?")
            params.append(face_count)
        if skipped_count is not None:
            updates.append("skipped_count = ?")
            params.append(skipped_count)
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)
        if finished_at is not None:
            updates.append("finished_at = ?")
            params.append(finished_at)

        if not updates:
            return self.get_import_batch(batch_id)

        params.append(batch_id)
        sql = f"UPDATE import_batches SET {', '.join(updates)} WHERE id = ?;"
        try:
            with self._get_connection() as conn:
                conn.execute(sql, params)
                conn.commit()
            return self.get_import_batch(batch_id)
        except Exception as e:
            logger.error("Fehler beim Aktualisieren des Import-Batches %s: %s", batch_id, e)
            return None

    def get_import_batch(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Gibt die Details eines einzelnen Import-Batches zurück."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT * FROM import_batches WHERE id = ?;", (batch_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error("Fehler beim Abrufen des Import-Batches %s: %s", batch_id, e)
            return None

    def list_import_batches(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Liefert alle erfassten Import-Chargen sortiert nach Startdatum (neueste zuerst)."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM import_batches ORDER BY started_at DESC LIMIT ?;",
                    (limit,),
                )
                return [dict(r) for r in cursor.fetchall()]
        except Exception as e:
            logger.error("Fehler beim Abrufen der Import-Batches: %s", e)
            return []

    def delete_import_batch(self, batch_id: str) -> bool:
        """Löscht einen Import-Batch und entfernt verknüpfte SQLite-Metadateneinträge."""
        try:
            with self._get_connection() as conn:
                # 1. Metadateneinträge bereinigen
                conn.execute("DELETE FROM metadata WHERE import_id = ?;", (batch_id,))
                # 2. Batch-Eintrag löschen
                cursor = conn.execute("DELETE FROM import_batches WHERE id = ?;", (batch_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error("Fehler beim Löschen des Import-Batches %s aus SQLite: %s", batch_id, e)
            return False

    def update_metadata_import_id(self, file_path: str, import_id: str) -> None:
        """Verknüpft ein Bild in der SQLite-Metadatentabelle mit einer Import-ID."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "UPDATE metadata SET import_id = ? WHERE file_path = ?;",
                    (import_id, file_path),
                )
                conn.commit()
        except Exception as e:
            logger.debug("Konnte import_id nicht für Metadaten (%s) setzen: %s", file_path, e)

    def seed_legacy_batch_if_empty(self, folder_path: str, image_count: int, face_count: int) -> None:
        """Erstellt einen initialen Legacy-Batch, falls noch keine Import-Batches existieren aber Daten vorliegen."""
        try:
            with self._get_connection() as conn:
                count = conn.execute("SELECT COUNT(*) FROM import_batches;").fetchone()[0]
                if count == 0 and image_count > 0:
                    conn.execute(
                        """
                        INSERT INTO import_batches (id, name, folder_path, started_at, finished_at, image_count, face_count, status, notes)
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, ?, 'completed', ?);
                        """,
                        (
                            "batch_initial_legacy",
                            "Hauptbestand (Initialer Archivimport)",
                            folder_path,
                            image_count,
                            face_count,
                            "Vorhandener Archivbestand vor Einführung des Akzessionsjournals.",
                        ),
                    )
                    conn.commit()
                    logger.info("Initialer Legacy-Batch 'batch_initial_legacy' für %d Bilder angelegt.", image_count)
        except Exception as e:
            logger.debug("Fehler beim Anlegen des Legacy-Batches: %s", e)


metadata_db = MetadataDatabase()

