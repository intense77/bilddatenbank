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
