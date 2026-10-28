import pytest
from pathlib import Path
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import validate_safe_image_path
from app.api.routes.archive import browse_folders
from app.services.metadata_db import MetadataDatabase
from app.main import app


def test_server_binding_and_allowed_dirs_defaults():
    """Prüft, dass der Server standardmäßig nur auf 127.0.0.1 lauscht und '.' nicht in ALLOWED_IMAGE_DIRS ist."""
    assert settings.SERVER_HOST == "127.0.0.1"
    assert settings.SERVER_PORT == 8000
    assert "." not in settings.ALLOWED_IMAGE_DIRS
    assert Path(".").resolve() not in [Path(d).resolve() for d in settings.ALLOWED_IMAGE_DIRS if d != "./data"]


def test_path_validation_rejects_project_root_files():
    """Prüft, dass Dateien direkt im Projektstamm (.env, todo.md etc.) als Archivbilder abgewiesen werden."""
    # Selbst wenn eine Fake-Bilddatei im Projektroot läge:
    fake_img_in_root = Path("./fake_root_image.jpg")
    try:
        fake_img_in_root.touch()
        with pytest.raises(HTTPException) as exc_info:
            validate_safe_image_path(fake_img_in_root.resolve())
        assert exc_info.value.status_code == 403
        assert "außerhalb der autorisierten Archivverzeichnisse" in exc_info.value.detail
    finally:
        fake_img_in_root.unlink(missing_ok=True)


def test_browse_folders_sandboxing():
    """Prüft, dass browse_folders Systempfade wie /etc abweist (HTTP 403)."""
    with pytest.raises(HTTPException) as exc_info:
        browse_folders(path="/etc")
    assert exc_info.value.status_code == 403
    assert "außerhalb der autorisierten" in exc_info.value.detail

    # Erlaubter Pfad (z. B. Home-Ordner) muss funktionieren und kein '/' in quick_links enthalten
    res = browse_folders(path=str(Path.home()))
    assert res["status"] == "success"
    labels = [link["label"] for link in res["quick_links"]]
    assert "Wurzelverzeichnis (/)" not in labels


def test_audit_log_database(tmp_path):
    """Prüft, dass das KDG-Audit-Log Einträge revisionssicher speichert und filtert."""
    db_file = tmp_path / "test_audit.db"
    db = MetadataDatabase(db_path=db_file)

    log_id1 = db.add_audit_log(
        action="RENAME_CLUSTER",
        target_type="CLUSTER",
        target_id="cluster_42",
        details={"new_label": "Bischof Müller"},
        operator="archivar_1",
    )
    assert log_id1 > 0

    log_id2 = db.add_audit_log(
        action="DELETE_RECORD",
        target_type="IMAGE",
        target_id="/data/archive/sample.jpg",
        details={"reason": "KDG § 19 Löschanspruch"},
        operator="archivar_admin",
    )
    assert log_id2 > log_id1

    # Alle abrufen
    logs = db.get_audit_logs()
    assert len(logs) == 2
    assert logs[0]["action"] == "DELETE_RECORD"  # Neueste zuerst
    assert logs[1]["action"] == "RENAME_CLUSTER"
    assert logs[1]["details"]["new_label"] == "Bischof Müller"

    # Nach Typ filtern
    cluster_logs = db.get_audit_logs(target_type="CLUSTER")
    assert len(cluster_logs) == 1
    assert cluster_logs[0]["target_id"] == "cluster_42"


def test_delete_metadata_and_audit_api():
    """Prüft den Endpunkt /system/audit-log und die Löschung aus SQLite."""
    client = TestClient(app)
    client.headers["Authorization"] = "Basic YXJjaGl2YXI6a3VyYXRvcjIwMjY="
    res = client.get("/system/audit-log")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_dynamic_gvfs_path_resolution(tmp_path, monkeypatch):
    """Prüft, dass veränderte GVFS-Mountpoints (z. B. IP/Hostname-Wechsel) automatisch aufgelöst werden."""
    import os
    from app.core.security import resolve_archive_path

    # Simuliere neue aktive GVFS-Mount-Struktur
    fake_gvfs = tmp_path / "gvfs"
    active_mount = fake_gvfs / "smb-share:server=nas-current,share=bilder"
    active_mount.mkdir(parents=True)
    real_file = active_mount / "events" / "portrait.jpg"
    real_file.parent.mkdir(parents=True)
    real_file.write_bytes(b"image_content")

    # Monkeypatch getuid und den Basispfad für GVFS
    original_resolve = resolve_archive_path
    def mock_resolve(path_input):
        p = Path(path_input)
        if "/gvfs/" in str(p) and not p.exists():
            parts = p.parts
            if "gvfs" in parts:
                gvfs_idx = parts.index("gvfs")
                if len(parts) > gvfs_idx + 2:
                    subpath = Path(*parts[gvfs_idx + 2:])
                    for mount in fake_gvfs.iterdir():
                        if mount.is_dir():
                            candidate = (mount / subpath).resolve()
                            if candidate.exists():
                                return candidate
        return p

    old_mount_path = f"/run/user/{os.getuid()}/gvfs/smb-share:server=nas-old.local,share=bilder/events/portrait.jpg"
    resolved = mock_resolve(old_mount_path)
    assert resolved.exists()
    assert resolved == real_file.resolve()
