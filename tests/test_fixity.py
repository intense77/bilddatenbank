import hashlib
import tempfile
from pathlib import Path
import pytest
from app.services.metadata_service import compute_file_sha256
from app.services.metadata_db import MetadataDatabase


def test_compute_file_sha256(tmp_path: Path):
    test_file = tmp_path / "test_image.jpg"
    content = b"PREMIS Fixity Test Binary Content" * 1000
    test_file.write_bytes(content)

    expected_hash = hashlib.sha256(content).hexdigest()
    calculated_hash = compute_file_sha256(test_file)

    assert calculated_hash == expected_hash
    assert compute_file_sha256(tmp_path / "non_existing.jpg") is None


def test_metadata_db_fixity_upsert_and_update(tmp_path: Path):
    db_file = tmp_path / "test_archive.db"
    db = MetadataDatabase(db_file)

    # Upsert mit Fixity-Feldern
    record = db.upsert_metadata(
        file_path="/archive/scan_001.jpg",
        file_name="scan_001.jpg",
        title="Historisches Stadtarchiv Scan",
        sha256="abc123sha256hash",
        import_id="batch_01",
        last_fixity_check="2026-10-15T22:00:00",
        fixity_status="OK",
    )
    assert record["sha256"] == "abc123sha256hash"
    assert record["fixity_status"] == "OK"

    # Abrufen und Verifizieren
    fetched = db.get_metadata("/archive/scan_001.jpg")
    assert fetched is not None
    assert fetched["sha256"] == "abc123sha256hash"
    assert fetched["fixity_status"] == "OK"

    # Update Fixity
    db.update_fixity(
        "/archive/scan_001.jpg",
        sha256="updated_hash_456",
        fixity_status="CORRUPTED",
        last_fixity_check="2026-10-15T23:00:00",
    )
    updated = db.get_metadata("/archive/scan_001.jpg")
    assert updated["sha256"] == "updated_hash_456"
    assert updated["fixity_status"] == "CORRUPTED"
    assert updated["last_fixity_check"] == "2026-10-15T23:00:00"


def test_verify_fixity_workflow_and_bit_rot_detection(tmp_path: Path):
    db_file = tmp_path / "fixity_audit.db"
    db = MetadataDatabase(db_file)

    # 1. Erstelle zwei Test-Bilddateien
    img1 = tmp_path / "master1.tif"
    img2 = tmp_path / "master2.tif"
    missing_img = tmp_path / "deleted_master.tif"

    content1 = b"IMAGE_DATA_1_REVISIONS_SICHER" * 200
    content2 = b"IMAGE_DATA_2_BITSTREAM_STABLE" * 200

    img1.write_bytes(content1)
    img2.write_bytes(content2)

    hash1 = hashlib.sha256(content1).hexdigest()

    # In DB eintragen: img1 mit Hash, img2 ohne Hash (Altbestand), missing_img mit Hash
    db.upsert_metadata(str(img1), file_name="master1.tif", sha256=hash1)
    db.upsert_metadata(str(img2), file_name="master2.tif", sha256=None)
    db.upsert_metadata(str(missing_img), file_name="deleted_master.tif", sha256="some_old_hash")

    # 2. Erster Fixity-Check:
    # - img1 ist intakt
    # - img2 wird initialisiert (Baseline gesetzt)
    # - missing_img wird als MISSING erkannt
    res1 = db.verify_fixity(calculate_missing=True)
    assert res1["total_checked"] == 3
    assert res1["intact"] == 1
    assert res1["initialized"] == 1
    assert res1["missing"] == 1
    assert res1["corrupted"] == 0

    # Verifiziere, dass img2 nun in der DB einen Hash besitzt
    meta2 = db.get_metadata(str(img2))
    assert meta2["sha256"] == hashlib.sha256(content2).hexdigest()
    assert meta2["fixity_status"] == "OK"

    # 3. Zweiter Check: Beide existierende Dateien sollten nun intakt sein
    res2 = db.verify_fixity(calculate_missing=True)
    assert res2["intact"] == 2
    assert res2["missing"] == 1
    assert res2["corrupted"] == 0

    # 4. Simulation von Bit-Rot / unbefugter Modifikation: Ändere 1 Byte in master1.tif
    modified_content1 = b"X" + content1[1:]
    img1.write_bytes(modified_content1)

    # 5. Dritter Check: Erkennt Bit-Rot zuverlässig!
    res3 = db.verify_fixity(calculate_missing=True)
    assert res3["corrupted"] == 1
    assert res3["intact"] == 1
    assert res3["missing"] == 1
    assert len(res3["corrupted_items"]) == 1
    assert res3["corrupted_items"][0]["file_name"] == "master1.tif"
    assert res3["corrupted_items"][0]["expected_sha256"] == hash1

    # Verifiziere DB-Status
    meta1 = db.get_metadata(str(img1))
    assert meta1["fixity_status"] == "CORRUPTED"

    # Verifiziere, dass Audit-Log den Alarm protokolliert hat
    logs = db.get_audit_logs(target_type="IMAGE", target_id=str(img1))
    assert any(l["action"] == "FIXITY_BITROT_ALERT" for l in logs)

    # Verifiziere get_fixity_summary
    summary = db.get_fixity_summary()
    assert summary["corrupted"] == 1
    assert summary["intact"] == 1
    assert summary["missing"] == 1
    assert summary["alert_active"] is True

    # Verifiziere get_corrupted_metadata
    corrupted_list = db.get_corrupted_metadata()
    assert len(corrupted_list) >= 2  # 1 corrupted + 1 missing
    assert any(c["file_name"] == "master1.tif" and c["fixity_status"] == "CORRUPTED" for c in corrupted_list)


# =========================================================================
# PREMIS 3.0 & Fixity REST-API Tests
# =========================================================================

import base64
import xml.etree.ElementTree as ET
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.services.premis_service import premis_service
from app.services.fixity_service import fixity_service
from app.services.metadata_db import metadata_db


@pytest.fixture
def auth_headers():
    curator_cred = f"{settings.AUTH_DEFAULT_CURATOR_USER}:{settings.AUTH_DEFAULT_CURATOR_PASSWORD}".encode("utf-8")
    viewer_cred = f"{settings.AUTH_DEFAULT_VIEWER_USER}:{settings.AUTH_DEFAULT_VIEWER_PASSWORD}".encode("utf-8")
    return {
        "curator": {"Authorization": "Basic " + base64.b64encode(curator_cred).decode("ascii")},
        "viewer": {"Authorization": "Basic " + base64.b64encode(viewer_cred).decode("ascii")},
    }


def test_premis_service_xml_generation(tmp_path: Path):
    """Testet die Erzeugung valider PREMIS 3.0 XML-Metadatenpakete nach ISO 14721."""
    test_img = tmp_path / "altar_bild.jpg"
    test_content = b"PREMIS_TEST_BINARY_OCTET_STREAM_DATA" * 50
    test_img.write_bytes(test_content)
    test_sha = hashlib.sha256(test_content).hexdigest()

    xml_bytes = premis_service.generate_premis(
        items=[{
            "file_path": str(test_img),
            "file_name": "altar_bild.jpg",
            "title": "Hochaltar im Barockstil",
            "sha256": test_sha,
            "fixity_status": "OK",
            "last_fixity_check": "2026-10-28T10:00:00",
        }],
        archive_name="Bistumsarchiv Test",
    )

    assert xml_bytes.startswith(b"<?xml")
    root = ET.fromstring(xml_bytes)
    assert "premis" in root.tag.lower()
    assert root.attrib.get("version") == "3.0"

    # Prüfe Object-Knoten
    objects = [elem for elem in root if elem.tag.endswith("object")]
    assert len(objects) == 1
    chars = [elem for elem in objects[0] if elem.tag.endswith("objectCharacteristics")][0]
    fixity = [elem for elem in chars if elem.tag.endswith("fixity")][0]
    digest = [elem for elem in fixity if elem.tag.endswith("messageDigest")][0]
    assert digest.text == test_sha

    # Prüfe Event-Knoten
    events = [elem for elem in root if elem.tag.endswith("event")]
    assert len(events) == 1
    event_type = [elem for elem in events[0] if elem.tag.endswith("eventType")][0]
    assert event_type.text == "fixity check"

    # Prüfe Agent-Knoten
    agents = [elem for elem in root if elem.tag.endswith("agent")]
    assert len(agents) == 1


def test_fixity_api_endpoints_and_rbac(tmp_path: Path, auth_headers):
    """Testet die REST-API Endpunkte für Fixity-Status, Audit-Trigger und PREMIS-Download."""
    test_file = tmp_path / "archiv_scan_api.jpg"
    content = b"ARCHIV_MASTER_SCAN_BYTES_123456" * 40
    test_file.write_bytes(content)
    test_sha = hashlib.sha256(content).hexdigest()
    file_str = str(test_file.resolve())

    # In erlaubte Verzeichnisse eintragen
    orig_dirs = list(settings.ALLOWED_IMAGE_DIRS)
    settings.ALLOWED_IMAGE_DIRS.append(str(tmp_path))

    try:
        metadata_db.upsert_metadata(
            file_path=file_str,
            file_name="archiv_scan_api.jpg",
            sha256=test_sha,
            fixity_status="OK",
            last_fixity_check="2026-10-28T11:00:00",
        )

        client = TestClient(app)

        # 1. GET /api/fixity/status
        resp_status = client.get("/api/fixity/status")
        assert resp_status.status_code == 200
        data_status = resp_status.json()
        assert "is_running" in data_status
        assert "summary" in data_status

        # 2. GET /api/fixity/corrupted erfordert Kurator (Viewer -> 403)
        resp_corr_viewer = client.get("/api/fixity/corrupted", headers=auth_headers["viewer"])
        assert resp_corr_viewer.status_code == 403

        resp_corr_curator = client.get("/api/fixity/corrupted", headers=auth_headers["curator"])
        assert resp_corr_curator.status_code == 200
        assert "corrupted_items" in resp_corr_curator.json()

        # 3. POST /api/fixity/verify (Viewer -> 403, Curator -> 200)
        resp_verify_viewer = client.post("/api/fixity/verify", json={}, headers=auth_headers["viewer"])
        assert resp_verify_viewer.status_code == 403

        resp_verify_curator = client.post("/api/fixity/verify", json={"folder_path": str(tmp_path)}, headers=auth_headers["curator"])
        assert resp_verify_curator.status_code == 200
        assert resp_verify_curator.json()["success"] is True

        # 4. GET /api/fixity/premis (Download XML)
        resp_premis = client.get(f"/api/fixity/premis?path={file_str}")
        assert resp_premis.status_code == 200
        assert resp_premis.headers["content-type"].startswith("application/xml")
        assert b"SHA-256" in resp_premis.content
        assert test_sha.encode("utf-8") in resp_premis.content

        # 5. POST /api/fixity/premis/export (Batch Export)
        resp_batch = client.post(
            "/api/fixity/premis/export",
            json={"paths": [file_str], "archive_name": "Testarchiv"},
        )
        assert resp_batch.status_code == 200
        assert b"<premis:object" in resp_batch.content
    finally:
        settings.ALLOWED_IMAGE_DIRS = orig_dirs

