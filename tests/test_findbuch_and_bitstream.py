import hashlib
import io
from pathlib import Path
from PIL import Image
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from app.main import app
from app.services.image_rotation_service import ImageRotationService
from app.services.thumbnail_service import ThumbnailService
from app.services.metadata_db import metadata_db


class MockIndexingService:
    def reindex_single_image(self, file_path):
        return True, 0


def test_virtual_rotation_bitstream_preservation():
    """Testet, dass die Originaldatei auf dem Datenträger bei virtuellen Drehungen zu 100% unverändert bleibt."""
    thumb_svc = ThumbnailService(cache_dir=Path("/tmp/test_thumb_cache_preservation"))
    indexing_svc = MockIndexingService()
    rot_svc = ImageRotationService(indexing_service=indexing_svc, thumbnail_service_instance=thumb_svc)

    test_file = Path("/tmp/test_bitstream_original.jpg")
    try:
        # Bestehende Einstellungen in DB zurücksetzen
        metadata_db.save_edit_settings(str(test_file.resolve()), {})

        # Erstelle ein 100x200 Bild
        img = Image.new("RGB", (100, 200), color=(80, 140, 200))
        img.save(test_file, quality=95)

        # Ursprüngliche Prüfsumme und Dateigröße erfassen
        initial_bytes = test_file.read_bytes()
        initial_hash = hashlib.sha256(initial_bytes).hexdigest()
        initial_mtime = test_file.stat().st_mtime

        # 1. Virtuelle Drehung um 90° im Uhrzeigersinn
        res90 = rot_svc.rotate_image(test_file, angle=90, virtual=True)
        assert res90["success"] is True
        assert res90["bitstream_preserved"] is True
        assert res90["rotation_method"] == "virtual_non_destructive"
        assert res90["width"] == 200
        assert res90["height"] == 100

        # Prüfe, dass die Datei auf der Festplatte absolut identisch geblieben ist!
        after_rot_bytes = test_file.read_bytes()
        after_rot_hash = hashlib.sha256(after_rot_bytes).hexdigest()
        assert after_rot_hash == initial_hash, "Originaldatei wurde modifiziert! Bitstream-Verletzung."
        assert test_file.stat().st_mtime == initial_mtime

        # Prüfe, dass edit_settings in SQLite persistiert wurde
        es = metadata_db.get_edit_settings(str(test_file.resolve()))
        assert es is not None
        assert es.get("rotation") == 90

        # 2. Thumbnail-Erzeugung liefert die gedrehten Maße (200x100)
        thumb_bytes = thumb_svc.get_or_create_thumbnail(test_file, max_dim=400, rotation=90)
        with Image.open(io.BytesIO(thumb_bytes)) as t_img:
            assert t_img.width >= t_img.height, "Thumbnail sollte Querformat sein"

        # 3. Weiterdrehen um 90° (gesamt 180°)
        res180 = rot_svc.rotate_image(test_file, angle=90, virtual=True)
        assert res180["normalized_angle"] == 180
        es180 = metadata_db.get_edit_settings(str(test_file.resolve()))
        assert es180.get("rotation") == 180

        # Master ist weiterhin bitgenau unverändert
        assert hashlib.sha256(test_file.read_bytes()).hexdigest() == initial_hash

    finally:
        test_file.unlink(missing_ok=True)


def test_export_findbuch_csv_endpoint():
    """Testet den Endpunkt /export/findbuch-csv für archivische Findbücher."""
    client = TestClient(app)

    payload = {
        "items": [
            {
                "file_path": "/data/archive/img_001.jpg",
                "file_name": "img_001.jpg",
                "title": "Bischofsweihe im Dom",
                "date": "1954-06-12",
                "creator": "Fotoatelier Schmidt",
                "signature": "A-1954-042",
                "persons": ["Bischof Johann", "Weihbischof Karl"],
                "notes": "Originalabzug Vintage Print"
            },
            {
                "file_path": "/data/archive/img_002.jpg",
                "file_name": "img_002.jpg",
                "title": "Domportal Restaurierung",
                "date": "1960",
                "creator": "Unbekannt",
                "signature": "A-1960-105",
                "persons": [],
                "notes": "Glasnegativ 9x12"
            }
        ],
        "archive_name": "Diözesanarchiv St. Peter",
        "collection_title": "Bestand Domfotografien"
    }

    res = client.post("/export/findbuch-csv", json=payload)
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert 'attachment; filename="Findbuch_' in res.headers["content-disposition"]

    content = res.content
    # Prüfe UTF-8 mit BOM (\xef\xbb\xbf) für Microsoft Excel Kompatibilität
    assert content.startswith(b"\xef\xbb\xbf"), "BOM fehlt für Excel-Kompatibilität"

    decoded_csv = content.decode("utf-8-sig")
    assert "# FINDBUCH / BESTANDSÜBERSICHT: Bestand Domfotografien" in decoded_csv
    assert "Diözesanarchiv St. Peter" in decoded_csv
    assert "Archivsignatur;Titel / Enthält-Vermerk;Datierung" in decoded_csv
    assert "A-1954-042;Bischofsweihe im Dom;1954-06-12;Fotoatelier Schmidt;Bischof Johann, Weihbischof Karl" in decoded_csv
    assert "A-1960-105;Domportal Restaurierung;1960;Unbekannt" in decoded_csv
