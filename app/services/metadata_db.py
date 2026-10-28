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
from typing import Any, Dict, List, Optional, Union

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

                # Migration: Falls Zweiblatt-Spalten, import_id/persons oder Fixity-Spalten (sha256, last_fixity_check, fixity_status) noch fehlen
                for col in [
                    "companion_path TEXT",
                    "sheet_role TEXT",
                    "verso_notes TEXT",
                    "import_id TEXT",
                    "persons TEXT",
                    "keywords TEXT",
                    "sha256 TEXT",
                    "last_fixity_check TIMESTAMP",
                    "fixity_status TEXT",
                    "ocr_text TEXT",
                ]:
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
                conn.execute("CREATE INDEX IF NOT EXISTS idx_metadata_sha256 ON metadata(sha256);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_metadata_fixity_status ON metadata(fixity_status);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_metadata_ocr_text ON metadata(ocr_text);")
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

                # KDG / DSGVO Audit-Log für Kuration, Berichtigung (§ 18 KDG) und Löschung (§ 19 KDG)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS audit_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        action TEXT NOT NULL,
                        target_type TEXT NOT NULL,
                        target_id TEXT NOT NULL,
                        details TEXT,
                        operator TEXT DEFAULT 'local_archivist'
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp DESC);")
                # Benutzerverwaltung und Sessions für KDG-konforme Rollen (RBAC)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        role TEXT NOT NULL DEFAULT 'viewer',
                        display_name TEXT,
                        is_active INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_login TIMESTAMP
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        token TEXT PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NOT NULL,
                        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);")

                # Kirchliche GND- und Iconclass-Normdatenbank (Offline-First Ontologie)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS gnd_authorities (
                        id TEXT PRIMARY KEY,
                        canonical TEXT NOT NULL,
                        category TEXT NOT NULL,
                        synonyms TEXT,
                        iconclass TEXT,
                        gnd TEXT,
                        description TEXT,
                        clip_prompts TEXT,
                        type TEXT DEFAULT 'subject',
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_gnd_canonical ON gnd_authorities(canonical);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_gnd_category ON gnd_authorities(category);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_gnd_gnd ON gnd_authorities(gnd);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_gnd_iconclass ON gnd_authorities(iconclass);")

                conn.commit()
            self._seed_default_users()
            self._seed_gnd_authorities()
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
                    if res.get("persons") and isinstance(res["persons"], str):
                        import json
                        try:
                            res["persons"] = json.loads(res["persons"])
                        except Exception:
                            res["persons"] = [p.strip() for p in res["persons"].split(",") if p.strip()]
                    if res.get("keywords") and isinstance(res["keywords"], str):
                        import json
                        try:
                            res["keywords"] = json.loads(res["keywords"])
                        except Exception:
                            res["keywords"] = [k.strip() for k in res["keywords"].split(",") if k.strip()]
                    elif not res.get("keywords"):
                        res["keywords"] = []
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
        persons: Optional[Union[List[str], str]] = None,
        keywords: Optional[Union[List[str], str]] = None,
        sha256: Optional[str] = None,
        import_id: Optional[str] = None,
        last_fixity_check: Optional[str] = None,
        fixity_status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Erstellt oder aktualisiert den Metadatensatz eines Archivbildes inklusive PREMIS Fixity-Prüfsumme."""
        import json
        now = datetime.now().isoformat()
        clean_path = str(file_path)
        clean_name = file_name or Path(clean_path).name

        persons_str = None
        if persons is not None:
            if isinstance(persons, list):
                persons_str = json.dumps([p.strip() for p in persons if p and p.strip()], ensure_ascii=False)
            else:
                persons_str = str(persons)

        keywords_str = None
        if keywords is not None:
            if isinstance(keywords, list):
                keywords_str = json.dumps([k.strip() for k in keywords if k and k.strip()], ensure_ascii=False)
            else:
                keywords_str = str(keywords)

        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO metadata (
                        file_path, file_name, signature, title, date, creator, description,
                        persons, keywords, sha256, import_id, last_fixity_check, fixity_status, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(file_path) DO UPDATE SET
                        file_name = excluded.file_name,
                        signature = COALESCE(excluded.signature, metadata.signature),
                        title = COALESCE(excluded.title, metadata.title),
                        date = COALESCE(excluded.date, metadata.date),
                        creator = COALESCE(excluded.creator, metadata.creator),
                        description = COALESCE(excluded.description, metadata.description),
                        persons = COALESCE(excluded.persons, metadata.persons),
                        keywords = COALESCE(excluded.keywords, metadata.keywords),
                        sha256 = COALESCE(excluded.sha256, metadata.sha256),
                        import_id = COALESCE(excluded.import_id, metadata.import_id),
                        last_fixity_check = COALESCE(excluded.last_fixity_check, metadata.last_fixity_check),
                        fixity_status = COALESCE(excluded.fixity_status, metadata.fixity_status),
                        updated_at = excluded.updated_at
                """, (
                    clean_path, clean_name, signature, title, date, creator, description,
                    persons_str, keywords_str, sha256, import_id, last_fixity_check, fixity_status, now
                ))
                conn.commit()

            return {
                "file_path": clean_path,
                "file_name": clean_name,
                "signature": signature,
                "title": title,
                "date": date,
                "creator": creator,
                "description": description,
                "persons": persons,
                "keywords": keywords,
                "sha256": sha256,
                "import_id": import_id,
                "last_fixity_check": last_fixity_check,
                "fixity_status": fixity_status,
                "updated_at": now,
            }
        except Exception as e:
            logger.error("Fehler beim Speichern der Metadaten in SQLite: %s", e)
            raise e

    def delete_metadata(self, file_path: str) -> bool:
        """Löscht einen Metadaten-Datensatz anhand des Dateipfads aus SQLite."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM metadata WHERE file_path = ?",
                    (str(file_path),)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error("Fehler beim Löschen der Metadaten für %s: %s", file_path, e)
            return False

    # ------------------ KDG/DSGVO Audit-Log Operationen ------------------

    def add_audit_log(
        self,
        action: str,
        target_type: str,
        target_id: str,
        details: Optional[Union[Dict[str, Any], str]] = None,
        operator: str = "local_archivist",
    ) -> int:
        """
        Protokolliert archivische und datenschutzrelevante Vorgänge
        (z. B. Löschungen, Umbenennungen, Cluster-Merges) revisionssicher nach § 18/19 KDG.
        """
        import json
        details_str = None
        if details is not None:
            if isinstance(details, (dict, list)):
                details_str = json.dumps(details, ensure_ascii=False)
            else:
                details_str = str(details)

        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO audit_log (action, target_type, target_id, details, operator)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (action, target_type, str(target_id), details_str, operator),
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error("Fehler beim Schreiben des Audit-Logs: %s", e)
            return -1

    def get_audit_logs(
        self,
        limit: int = 100,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Liest die jüngsten Einträge aus dem KDG-Audit-Log."""
        import json
        try:
            with self._get_connection() as conn:
                query = "SELECT * FROM audit_log"
                params: List[Any] = []
                conditions = []
                if target_type:
                    conditions.append("target_type = ?")
                    params.append(target_type)
                if target_id:
                    conditions.append("target_id = ?")
                    params.append(str(target_id))

                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

                query += " ORDER BY id DESC LIMIT ?"
                params.append(limit)

                cursor = conn.execute(query, tuple(params))
                rows = cursor.fetchall()
                result = []
                for r in rows:
                    item = dict(r)
                    if item.get("details"):
                        try:
                            item["details"] = json.loads(item["details"])
                        except Exception:
                            pass
                    result.append(item)
                return result
        except Exception as e:
            logger.error("Fehler beim Lesen des Audit-Logs: %s", e)
            return []

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

    def save_ocr_text(self, file_path: str, ocr_text: str) -> bool:
        """Speichert den per OCR/HTR extrahierten Text für ein Bild oder dessen Rückseite."""
        try:
            with self._get_connection() as conn:
                existing = conn.execute("SELECT file_path FROM metadata WHERE file_path = ?;", (file_path,)).fetchone()
                if existing:
                    conn.execute(
                        "UPDATE metadata SET ocr_text = ?, updated_at = CURRENT_TIMESTAMP WHERE file_path = ?;",
                        (ocr_text, file_path),
                    )
                else:
                    file_name = Path(file_path).name
                    conn.execute(
                        """INSERT INTO metadata (file_path, file_name, ocr_text, updated_at)
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP);""",
                        (file_path, file_name, ocr_text),
                    )
                conn.commit()
                return True
        except Exception as e:
            logger.error("Fehler beim Speichern von ocr_text für %s: %s", file_path, e)
            return False

    def get_ocr_text(self, file_path: str) -> Optional[str]:
        """Liest den gespeicherten OCR-Text für eine Datei aus SQLite."""
        try:
            with self._get_connection() as conn:
                row = conn.execute("SELECT ocr_text FROM metadata WHERE file_path = ?;", (file_path,)).fetchone()
                if row and row["ocr_text"]:
                    return row["ocr_text"]
                return None
        except Exception as e:
            logger.debug("Fehler beim Abruf von ocr_text für %s: %s", file_path, e)
            return None

    def search_metadata(
        self,
        query: str,
        limit: int = 50,
        import_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Sucht nach Bildmetadaten in title, signature, description, creator, file_name, verso_notes und ocr_text (optional gefiltert nach import_id)."""
        clean_q = query.strip()
        if not clean_q:
            return []
        pattern = f"%{clean_q}%"
        try:
            with self._get_connection() as conn:
                where_clauses = [
                    "(title LIKE ? OR signature LIKE ? OR description LIKE ? OR creator LIKE ? OR file_name LIKE ? OR verso_notes LIKE ? OR ocr_text LIKE ?)"
                ]
                params: List[Any] = [pattern, pattern, pattern, pattern, pattern, pattern, pattern]
                if import_id:
                    if import_id == "batch_initial_legacy":
                        where_clauses.append("(import_id = 'batch_initial_legacy' OR import_id IS NULL OR import_id = '')")
                    else:
                        where_clauses.append("import_id = ?")
                        params.append(import_id)

                sql = f"""
                    SELECT * FROM metadata 
                    WHERE {" AND ".join(where_clauses)}
                    ORDER BY updated_at DESC
                    LIMIT ?
                """
                params.append(limit)
                cursor = conn.execute(sql, params)
                return [dict(r) for r in cursor.fetchall()]
        except Exception as e:
            logger.error("Fehler bei der Metadatensuche in SQLite: %s", e)
            return []

    def get_metadata_by_import_id(self, import_id: str, limit: int = 1000) -> List[Dict[str, Any]]:
        """Gibt alle Metadaten-Einträge für einen bestimmten Import-Batch zurück."""
        try:
            with self._get_connection() as conn:
                if import_id == "batch_initial_legacy":
                    cursor = conn.execute(
                        """
                        SELECT * FROM metadata 
                        WHERE import_id = 'batch_initial_legacy' OR import_id IS NULL OR import_id = ''
                        ORDER BY file_name ASC
                        LIMIT ?;
                        """,
                        (limit,),
                    )
                else:
                    cursor = conn.execute(
                        """
                        SELECT * FROM metadata 
                        WHERE import_id = ?
                        ORDER BY file_name ASC
                        LIMIT ?;
                        """,
                        (import_id, limit),
                    )
                return [dict(r) for r in cursor.fetchall()]
        except Exception as e:
            logger.error("Fehler beim Abrufen von Metadaten für import_id=%s: %s", import_id, e)
            return []

    def get_distinct_creators(self, limit: int = 100) -> List[str]:
        """Gibt eine sortierte Liste aller bekannten Fotografen, Urheber und Ateliers zurück."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT DISTINCT TRIM(creator) as c 
                    FROM metadata 
                    WHERE creator IS NOT NULL AND TRIM(creator) != ''
                    ORDER BY c ASC 
                    LIMIT ?;
                    """,
                    (limit,),
                )
                return [r["c"] for r in cursor.fetchall() if r["c"]]
        except Exception as e:
            logger.error("Fehler beim Abrufen bekannter Urheber: %s", e)
            return []

    def get_distinct_signatures(self, limit: int = 100) -> List[str]:
        """Gibt eine sortierte Liste aller bekannten Archivsignaturen zurück."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT DISTINCT TRIM(signature) as s 
                    FROM metadata 
                    WHERE signature IS NOT NULL AND TRIM(signature) != ''
                    ORDER BY s ASC 
                    LIMIT ?;
                    """,
                    (limit,),
                )
                return [r["s"] for r in cursor.fetchall() if r["s"]]
        except Exception as e:
            logger.error("Fehler beim Abrufen bekannter Signaturen: %s", e)
            return []

    def get_facets_summary(self) -> Dict[str, Any]:
        """
        Liefert aggregierte Facetten für die Benutzeroberfläche:
        - Zeitraum (Jahre min/max)
        - Vordefinierte historische Epochen (Kaiserreich, Weimar, Nachkrieg, etc.)
        - Bekannte Fotografen / Ateliers
        - Bekannte Archivsignaturen
        - Vorhandene Import-Bestände / Akzessionen
        """
        creators = self.get_distinct_creators()
        signatures = self.get_distinct_signatures()
        batches = self.list_import_batches(limit=100)

        import re
        year_pattern = r"(?<!\d)(1[5-9]\d\d|20\d\d)(?!\d)"
        years: List[int] = []
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT date, file_path FROM metadata WHERE date IS NOT NULL OR file_path IS NOT NULL LIMIT 2000;")
                for row in cursor.fetchall():
                    d_val = row["date"]
                    if d_val:
                        m = re.search(year_pattern, str(d_val))
                        if m:
                            years.append(int(m.group(1)))
                            continue
                    f_val = row["file_path"]
                    if f_val:
                        m = re.search(year_pattern, str(f_val))
                        if m:
                            years.append(int(m.group(1)))
        except Exception as e:
            logger.debug("Fehler bei Jahres-Aggregierung in SQLite: %s", e)

        min_year = min(years) if years else 1860
        max_year = max(years) if years else 2026
        min_year = max(1840, min(min_year, 1900))
        max_year = min(2030, max(max_year, 2025))

        epochs = [
            {"id": "kaiserreich", "label": "Kaiserreich & Frühe Fotografie", "years": "1860–1914", "from": 1860, "to": 1914, "icon": "🏛️"},
            {"id": "weimar", "label": "Zwischenkriegszeit & Weimar", "years": "1914–1939", "from": 1914, "to": 1939, "icon": "📜"},
            {"id": "nachkrieg", "label": "Nachkriegszeit & Wiederaufbau", "years": "1939–1965", "from": 1939, "to": 1965, "icon": "🕊️"},
            {"id": "konzil", "label": "Konzilsära & Moderne", "years": "1965–1990", "from": 1965, "to": 1990, "icon": "⛪"},
            {"id": "modern", "label": "Zeitgenössisch", "years": "ab 1990", "from": 1990, "to": 2030, "icon": "📸"},
        ]

        return {
            "years": {
                "min": min_year,
                "max": max_year,
            },
            "epochs": epochs,
            "creators": creators,
            "signatures": signatures,
            "batches": [{"id": b.get("id"), "name": b.get("name"), "count": b.get("image_count", 0)} for b in batches],
        }

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

    def update_fixity(
        self,
        file_path: str,
        sha256: Optional[str] = None,
        fixity_status: str = "OK",
        last_fixity_check: Optional[str] = None,
    ) -> None:
        """Aktualisiert Fixity-Status, Checksumme und Zeitstempel für ein Digitalisat."""
        now = last_fixity_check or datetime.now().isoformat()
        try:
            with self._get_connection() as conn:
                if sha256 is not None:
                    conn.execute(
                        """
                        UPDATE metadata
                        SET sha256 = ?, fixity_status = ?, last_fixity_check = ?
                        WHERE file_path = ?;
                        """,
                        (sha256, fixity_status, now, str(file_path)),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE metadata
                        SET fixity_status = ?, last_fixity_check = ?
                        WHERE file_path = ?;
                        """,
                        (fixity_status, now, str(file_path)),
                    )
                conn.commit()
        except Exception as e:
            logger.error("Fehler beim Aktualisieren des Fixity-Status für %s: %s", file_path, e)

    def verify_fixity(
        self,
        folder_path: Optional[str] = None,
        calculate_missing: bool = True,
        progress_callback: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Führt eine vollständige PREMIS-Fixity-Unversehrtheitsprüfung (Bitstream Preservation) durch.
        - Vergleicht den aktuellen SHA-256 Bitstream-Hash mit der archivierten Checksumme.
        - Erkennt Bit-Rot, Datenverfälschungen und gelöschte Master-Dateien.
        - Initialisiert bei Bedarf fehlende Hashes für Altbestände.
        """
        from app.services.metadata_service import compute_file_sha256

        results = {
            "total_checked": 0,
            "intact": 0,
            "corrupted": 0,
            "missing": 0,
            "initialized": 0,
            "unverified": 0,
            "corrupted_items": [],
            "missing_items": [],
        }

        try:
            with self._get_connection() as conn:
                if folder_path:
                    cursor = conn.execute(
                        "SELECT file_path, file_name, sha256, fixity_status FROM metadata WHERE file_path LIKE ? || '%';",
                        (str(folder_path),),
                    )
                else:
                    cursor = conn.execute("SELECT file_path, file_name, sha256, fixity_status FROM metadata;")
                rows = cursor.fetchall()
        except Exception as e:
            logger.error("Fehler beim Laden der Metadaten für Fixity-Prüfung: %s", e)
            return results

        now_iso = datetime.now().isoformat()
        total = len(rows)

        for idx, row in enumerate(rows):
            file_path_str = row["file_path"]
            file_name = row["file_name"] or Path(file_path_str).name
            stored_sha = row["sha256"]
            path_obj = Path(file_path_str)

            results["total_checked"] += 1

            # 1. Existenzprüfung der Datei auf dem Datenträger / Storage
            if not path_obj.exists() or not path_obj.is_file():
                results["missing"] += 1
                results["missing_items"].append({
                    "file_path": file_path_str,
                    "file_name": file_name,
                    "expected_sha256": stored_sha,
                    "error": "Master-Datei existiert nicht auf dem Dateisystem",
                })
                self.update_fixity(file_path_str, fixity_status="MISSING", last_fixity_check=now_iso)
                self.add_audit_log(
                    action="FIXITY_MISSING_ALERT",
                    target_type="IMAGE",
                    target_id=file_path_str,
                    details={"error": "Master-Datei existiert nicht auf dem Dateisystem", "expected_sha": stored_sha},
                    operator="fixity_daemon",
                )
                if progress_callback:
                    progress_callback(idx + 1, total, file_path_str, "MISSING")
                continue

            # 2. SHA-256 Bitstream-Prüfsumme im Streaming-Modus berechnen
            current_sha = compute_file_sha256(path_obj)
            if not current_sha:
                results["corrupted"] += 1
                results["corrupted_items"].append({
                    "file_path": file_path_str,
                    "file_name": file_name,
                    "expected_sha256": stored_sha,
                    "actual_sha256": None,
                    "error": "I/O-Lesefehler beim Berechnen der Prüfsumme (möglicher E/A-Hardwarefehler)",
                })
                self.update_fixity(file_path_str, fixity_status="READ_ERROR", last_fixity_check=now_iso)
                self.add_audit_log(
                    action="FIXITY_READ_ERROR_ALERT",
                    target_type="IMAGE",
                    target_id=file_path_str,
                    details={"error": "I/O-Lesefehler", "expected_sha": stored_sha},
                    operator="fixity_daemon",
                )
                if progress_callback:
                    progress_callback(idx + 1, total, file_path_str, "READ_ERROR")
                continue

            # 3. Fixity-Vergleich
            if not stored_sha:
                if calculate_missing:
                    # Nachträgliche PREMIS-Fixity Baseline für Altbestand generieren
                    self.update_fixity(file_path_str, sha256=current_sha, fixity_status="OK", last_fixity_check=now_iso)
                    results["initialized"] += 1
                    status = "INITIALIZED"
                else:
                    self.update_fixity(file_path_str, fixity_status="UNVERIFIED", last_fixity_check=now_iso)
                    results["unverified"] += 1
                    status = "UNVERIFIED"
            elif current_sha == stored_sha:
                # Bitstream intakt (revisionssicher bestätigt)
                self.update_fixity(file_path_str, fixity_status="OK", last_fixity_check=now_iso)
                results["intact"] += 1
                status = "OK"
            else:
                # Alarm: Bit-Rot oder Manipulation festgestellt!
                self.update_fixity(file_path_str, fixity_status="CORRUPTED", last_fixity_check=now_iso)
                self.add_audit_log(
                    action="FIXITY_BITROT_ALERT",
                    target_type="IMAGE",
                    target_id=file_path_str,
                    details={
                        "error": "Prüfsummen-Mismatch (Bit-Rot oder Dateimanipulation erkannt)",
                        "expected_sha": stored_sha,
                        "actual_sha": current_sha,
                    },
                    operator="fixity_daemon",
                )
                results["corrupted"] += 1
                results["corrupted_items"].append({
                    "file_path": file_path_str,
                    "file_name": file_name,
                    "expected_sha256": stored_sha,
                    "actual_sha256": current_sha,
                    "error": "Prüfsummen-Mismatch (Bit-Rot oder Dateimanipulation erkannt)",
                })
                status = "CORRUPTED"

            if progress_callback:
                progress_callback(idx + 1, total, file_path_str, status)

        return results

    def get_fixity_summary(self) -> Dict[str, Any]:
        """Gibt eine aggregierte Übersicht über den Fixity- und Integritätsstatus aller Bestände zurück."""
        try:
            with self._get_connection() as conn:
                row = conn.execute("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN fixity_status = 'OK' THEN 1 ELSE 0 END) as intact,
                        SUM(CASE WHEN fixity_status = 'CORRUPTED' OR fixity_status = 'READ_ERROR' THEN 1 ELSE 0 END) as corrupted,
                        SUM(CASE WHEN fixity_status = 'MISSING' THEN 1 ELSE 0 END) as missing,
                        SUM(CASE WHEN fixity_status = 'UNVERIFIED' OR fixity_status IS NULL THEN 1 ELSE 0 END) as unverified,
                        MAX(last_fixity_check) as last_check
                    FROM metadata;
                """).fetchone()
                if row:
                    res = dict(row)
                    res["corrupted"] = res.get("corrupted") or 0
                    res["intact"] = res.get("intact") or 0
                    res["missing"] = res.get("missing") or 0
                    res["unverified"] = res.get("unverified") or 0
                    res["total"] = res.get("total") or 0
                    res["alert_active"] = (res["corrupted"] > 0 or res["missing"] > 0)
                    return res
        except Exception as e:
            logger.error("Fehler beim Abrufen der Fixity-Zusammenfassung: %s", e)
        return {
            "total": 0, "intact": 0, "corrupted": 0, "missing": 0,
            "unverified": 0, "last_check": None, "alert_active": False,
        }

    def get_corrupted_metadata(self) -> List[Dict[str, Any]]:
        """Liefert alle Digitalisate mit Status CORRUPTED, READ_ERROR oder MISSING für Revisionszwecke."""
        try:
            with self._get_connection() as conn:
                rows = conn.execute("""
                    SELECT file_path, file_name, signature, title, sha256, fixity_status, last_fixity_check
                    FROM metadata
                    WHERE fixity_status IN ('CORRUPTED', 'MISSING', 'READ_ERROR')
                    ORDER BY last_fixity_check DESC;
                """).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error("Fehler beim Laden beschädigter Fixity-Datensätze: %s", e)
            return []

    # ========================================================
    # KDG-konforme Benutzerverwaltung & Session-Management (RBAC)
    # ========================================================

    def _seed_default_users(self) -> None:
        """Legt Standardbenutzer (Admin, Archivar, Lesesaal) an, falls noch keine existieren."""
        try:
            with self._get_connection() as conn:
                count = conn.execute("SELECT COUNT(*) FROM users;").fetchone()[0]
                if count == 0:
                    from app.core.config import settings
                    from app.core.auth import hash_password

                    defaults = [
                        (settings.AUTH_DEFAULT_ADMIN_USER, hash_password(settings.AUTH_DEFAULT_ADMIN_PASSWORD), "admin", "Archiv-Administrator"),
                        (settings.AUTH_DEFAULT_CURATOR_USER, hash_password(settings.AUTH_DEFAULT_CURATOR_PASSWORD), "curator", "Archivar / Wissenschaftl. Mitarbeiter"),
                        (settings.AUTH_DEFAULT_VIEWER_USER, hash_password(settings.AUTH_DEFAULT_VIEWER_PASSWORD), "viewer", "Lesesaal-Arbeitsplatz"),
                    ]
                    for username, p_hash, role, display in defaults:
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO users (username, password_hash, role, display_name)
                            VALUES (?, ?, ?, ?);
                            """,
                            (username, p_hash, role, display),
                        )
                    conn.commit()
                    logger.info("Standard-Benutzer (admin, archivar, lesesaal) erfolgreich initialisiert.")
        except Exception as e:
            logger.debug("Initialisierung der Standardbenutzer übersprungen/fehlgeschlagen: %s", e)

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Sucht einen Benutzer anhand des Benutzernamens."""
        try:
            with self._get_connection() as conn:
                row = conn.execute("SELECT * FROM users WHERE username = ?;", (username.strip(),)).fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error("Fehler beim Abruf von Benutzer '%s': %s", username, e)
            return None

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Sucht einen Benutzer anhand der numerischen ID."""
        try:
            with self._get_connection() as conn:
                row = conn.execute("SELECT * FROM users WHERE id = ?;", (user_id,)).fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error("Fehler beim Abruf von Benutzer ID %d: %s", user_id, e)
            return None

    def list_users(self) -> List[Dict[str, Any]]:
        """Liefert alle registrierten Benutzer (ohne Passwort-Hash)."""
        try:
            with self._get_connection() as conn:
                rows = conn.execute(
                    "SELECT id, username, role, display_name, is_active, created_at, last_login FROM users ORDER BY id ASC;"
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error("Fehler beim Auflisten der Benutzer: %s", e)
            return []

    def create_user(self, username: str, password_hash: str, role: str = "curator", display_name: Optional[str] = None) -> int:
        """Erstellt einen neuen Benutzer in der Datenbank."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (username, password_hash, role, display_name)
                VALUES (?, ?, ?, ?);
                """,
                (username.strip(), password_hash, role, display_name or username.strip()),
            )
            conn.commit()
            return cursor.lastrowid

    def update_user(
        self,
        user_id: int,
        password_hash: Optional[str] = None,
        role: Optional[str] = None,
        display_name: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> bool:
        """Aktualisiert Benutzerdaten."""
        updates = []
        params = []
        if password_hash is not None:
            updates.append("password_hash = ?")
            params.append(password_hash)
        if role is not None:
            updates.append("role = ?")
            params.append(role)
        if display_name is not None:
            updates.append("display_name = ?")
            params.append(display_name)
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if is_active else 0)

        if not updates:
            return False

        params.append(user_id)
        with self._get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE id = ?;",
                params,
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_user(self, username: str) -> bool:
        """Löscht einen Benutzer anhand des Benutzernamens."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM users WHERE username = ?;", (username.strip(),))
            conn.commit()
            return cursor.rowcount > 0

    def update_user_last_login(self, user_id: int) -> None:
        """Setzt den Zeitstempel des letzten erfolgreichen Logins."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?;",
                    (user_id,),
                )
                conn.commit()
        except Exception as e:
            logger.debug("Fehler beim Aktualisieren von last_login für User %d: %s", user_id, e)

    def create_session(self, token: str, user_id: int, expires_at: datetime) -> None:
        """Speichert eine neue Anmeldesitzung in SQLite."""
        expires_str = expires_at.isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO sessions (token, user_id, expires_at)
                VALUES (?, ?, ?);
                """,
                (token, user_id, expires_str),
            )
            conn.commit()

    def get_session(self, token: str) -> Optional[Dict[str, Any]]:
        """Gibt eine aktive, nicht abgelaufene Sitzung zurück."""
        try:
            now_iso = datetime.now().isoformat()
            with self._get_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM sessions WHERE token = ? AND expires_at > ?;",
                    (token, now_iso),
                ).fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.debug("Fehler beim Abruf von Session: %s", e)
            return None

    def delete_session(self, token: str) -> bool:
        """Löscht ein Session-Token (Logout)."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM sessions WHERE token = ?;", (token,))
            conn.commit()
            return cursor.rowcount > 0

    def delete_user_sessions(self, user_id: int) -> None:
        """Invalidiert alle aktiven Sitzungen eines Benutzers."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM sessions WHERE user_id = ?;", (user_id,))
            conn.commit()

    def cleanup_expired_sessions(self) -> int:
        """Entfernt abgelaufene Sitzungen zur Speicherbereinigung."""
        try:
            now_iso = datetime.now().isoformat()
            with self._get_connection() as conn:
                cursor = conn.execute("DELETE FROM sessions WHERE expires_at <= ?;", (now_iso,))
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.debug("Fehler bei cleanup_expired_sessions: %s", e)
            return 0

    # =========================================================================
    # Gemeinsame Normdatei (GND) & Iconclass-Fachontologie (Offline-First)
    # =========================================================================

    def _seed_gnd_authorities(self) -> None:
        """Initialisiert die lokale GND- und Iconclass-Normdatenbank aus dem Basisthesaurus."""
        try:
            with self._get_connection() as conn:
                count = conn.execute("SELECT COUNT(*) AS cnt FROM gnd_authorities;").fetchone()["cnt"]
                if count > 0:
                    return

                from app.core.thesaurus_data import CHURCH_THESAURUS
                import json

                for item in CHURCH_THESAURUS:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO gnd_authorities (
                            id, canonical, category, synonyms, iconclass, gnd, description, clip_prompts, type
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            item["id"],
                            item["canonical"],
                            item["category"],
                            json.dumps(item.get("synonyms", []), ensure_ascii=False),
                            item.get("iconclass"),
                            item.get("gnd"),
                            item.get("description", ""),
                            json.dumps(item.get("clip_prompts", []), ensure_ascii=False),
                            item.get("type", "subject"),
                        ),
                    )
                conn.commit()
                logger.info("GND- und Iconclass-Normdatenbank erfolgreich mit %d Begriffen initialisiert.", len(CHURCH_THESAURUS))
        except Exception as e:
            logger.error("Fehler beim Seeding der GND-Normdatenbank: %s", e)

    def search_gnd_authorities(
        self,
        query: str,
        limit: int = 20,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Sucht in der lokalen GND-Normdatenbank nach Begriffen, Synonymen, GND-ID oder Iconclass."""
        import json
        q = f"%{query.strip()}%"
        try:
            with self._get_connection() as conn:
                if category:
                    rows = conn.execute(
                        """
                        SELECT * FROM gnd_authorities
                        WHERE category = ? AND (
                            canonical LIKE ? OR synonyms LIKE ? OR description LIKE ? OR gnd LIKE ? OR iconclass LIKE ?
                        )
                        ORDER BY (CASE WHEN canonical LIKE ? THEN 1 ELSE 2 END), canonical ASC
                        LIMIT ?;
                        """,
                        (category, q, q, q, q, q, q, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT * FROM gnd_authorities
                        WHERE canonical LIKE ? OR synonyms LIKE ? OR description LIKE ? OR gnd LIKE ? OR iconclass LIKE ?
                        ORDER BY (CASE WHEN canonical LIKE ? THEN 1 ELSE 2 END), canonical ASC
                        LIMIT ?;
                        """,
                        (q, q, q, q, q, q, limit),
                    ).fetchall()

                result = []
                for r in rows:
                    item = dict(r)
                    item["synonyms"] = json.loads(item["synonyms"]) if item.get("synonyms") else []
                    item["clip_prompts"] = json.loads(item["clip_prompts"]) if item.get("clip_prompts") else []
                    result.append(item)
                return result
        except Exception as e:
            logger.error("Fehler bei search_gnd_authorities: %s", e)
            return []

    def get_gnd_authority(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Ermittelt einen GND-Normdatensatz anhand seiner ID, kanonischen Bezeichnung oder GND-Nummer."""
        import json
        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    """
                    SELECT * FROM gnd_authorities
                    WHERE id = ? OR canonical = ? OR gnd = ? OR iconclass = ?
                    LIMIT 1;
                    """,
                    (identifier, identifier, identifier, identifier),
                ).fetchone()
                if row:
                    item = dict(row)
                    item["synonyms"] = json.loads(item["synonyms"]) if item.get("synonyms") else []
                    item["clip_prompts"] = json.loads(item["clip_prompts"]) if item.get("clip_prompts") else []
                    return item
                return None
        except Exception as e:
            logger.error("Fehler bei get_gnd_authority: %s", e)
            return None

    def get_all_gnd_authorities(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Gibt alle GND-Normdatensätze zurück, optional nach Kategorie gefiltert."""
        import json
        try:
            with self._get_connection() as conn:
                if category:
                    rows = conn.execute(
                        "SELECT * FROM gnd_authorities WHERE category = ? ORDER BY canonical ASC;",
                        (category,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM gnd_authorities ORDER BY category ASC, canonical ASC;"
                    ).fetchall()

                result = []
                for r in rows:
                    item = dict(r)
                    item["synonyms"] = json.loads(item["synonyms"]) if item.get("synonyms") else []
                    item["clip_prompts"] = json.loads(item["clip_prompts"]) if item.get("clip_prompts") else []
                    result.append(item)
                return result
        except Exception as e:
            logger.error("Fehler bei get_all_gnd_authorities: %s", e)
            return []

    def upsert_gnd_authority(self, item: Dict[str, Any]) -> bool:
        """Fügt einen neuen GND-Normdatensatz hinzu oder aktualisiert einen bestehenden."""
        import json
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO gnd_authorities (
                        id, canonical, category, synonyms, iconclass, gnd, description, clip_prompts, type, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(id) DO UPDATE SET
                        canonical = excluded.canonical,
                        category = excluded.category,
                        synonyms = excluded.synonyms,
                        iconclass = excluded.iconclass,
                        gnd = excluded.gnd,
                        description = excluded.description,
                        clip_prompts = excluded.clip_prompts,
                        type = excluded.type,
                        updated_at = CURRENT_TIMESTAMP;
                    """,
                    (
                        item["id"],
                        item["canonical"],
                        item["category"],
                        json.dumps(item.get("synonyms", []), ensure_ascii=False),
                        item.get("iconclass"),
                        item.get("gnd"),
                        item.get("description", ""),
                        json.dumps(item.get("clip_prompts", []), ensure_ascii=False),
                        item.get("type", "subject"),
                    ),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error("Fehler beim Speichern von gnd_authority: %s", e)
            return False


metadata_db = MetadataDatabase()

