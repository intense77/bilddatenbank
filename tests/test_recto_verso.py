import shutil
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient

from app.main import app
from app.services.recto_verso_service import recto_verso_service
from app.services.metadata_db import metadata_db

client = TestClient(app)


def test_recto_verso_pattern_detection():
    # 1. Reine Namenserkennung prüfen (ohne physische Dateien)
    # _r / _v
    rel_r = recto_verso_service.detect_relationship("archive/foto_1928_r.jpg")
    assert rel_r is not None
    assert rel_r["role"] == "recto"
    assert rel_r["companion_role"] == "verso"
    assert rel_r["companion_name"] == "foto_1928_v.jpg"

    rel_v = recto_verso_service.detect_relationship("archive/foto_1928_v.jpg")
    assert rel_v is not None
    assert rel_v["role"] == "verso"
    assert rel_v["companion_role"] == "recto"

    # _recto / _verso
    rel_recto = recto_verso_service.detect_relationship("archive/dom_altar_recto.png")
    assert rel_recto is not None
    assert rel_recto["role"] == "recto"
    assert rel_recto["companion_role"] == "verso"

    # _vorderseite / _rueckseite
    rel_vs = recto_verso_service.detect_relationship("archive/gottesdienst_vorderseite.tif")
    assert rel_vs is not None
    assert rel_vs["role"] == "recto"
    assert rel_vs["companion_role"] == "verso"

    # _a / _b
    rel_a = recto_verso_service.detect_relationship("archive/postkarte_042_a.webp")
    assert rel_a is not None
    assert rel_a["role"] == "recto"
    assert rel_a["companion_role"] == "verso"
    assert rel_a["companion_name"] == "postkarte_042_b.webp"

    # _01 / _02
    rel_01 = recto_verso_service.detect_relationship("archive/urkunde_01.jpg")
    assert rel_01 is not None
    assert rel_01["role"] == "recto"
    assert rel_01["companion_role"] == "verso"
    assert rel_01["companion_name"] == "urkunde_02.jpg"

    # Kein Zweiblatt-Muster
    assert recto_verso_service.detect_relationship("archive/landschaft.jpg") is None


def test_recto_verso_physical_files_and_api():
    test_dir = Path("data/test_recto_verso")
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True, exist_ok=True)

    recto_path = test_dir / "archiv_fronleichnam_r.jpg"
    verso_path = test_dir / "archiv_fronleichnam_v.jpg"

    # Erzeuge zwei Testbilder
    img_recto = Image.new("RGB", (300, 200), color=(200, 100, 80))
    img_recto.save(recto_path, format="JPEG")
    img_verso = Image.new("RGB", (300, 200), color=(240, 240, 230))
    img_verso.save(verso_path, format="JPEG")

    try:
        # 1. Partnererkennung auf Dateisystem-Ebene
        info_recto = recto_verso_service.get_two_sided_info(recto_path)
        assert info_recto["is_two_sided"] is True
        assert info_recto["role"] == "recto"
        assert info_recto["companion_exists"] is True
        assert Path(info_recto["companion_path"]).resolve() == verso_path.resolve()
        assert "companion_serve_url" in info_recto

        # Umgekehrt: Test auf der Rückseite gestartet
        info_verso = recto_verso_service.get_two_sided_info(verso_path)
        assert info_verso["is_two_sided"] is True
        assert info_verso["role"] == "verso"
        assert info_verso["companion_exists"] is True
        assert Path(info_verso["companion_path"]).resolve() == recto_path.resolve()

        # 2. Speichern handschriftlicher Notizen der Rückseite
        test_note = "Fronleichnam 1928, Pfarrer Huber mit Kirchenchor St. Viktor vor dem Rathaus"
        success = recto_verso_service.save_verso_notes(recto_path, test_note)
        assert success is True

        # Notizen müssen für beide Seiten abrufbar sein
        saved_note_r = metadata_db.get_verso_notes(str(recto_path.resolve()))
        saved_note_v = metadata_db.get_verso_notes(str(verso_path.resolve()))
        assert saved_note_r == test_note
        assert saved_note_v == test_note

        # 3. Metadaten-Freitextsuche nach Rückseiten-Inhalt ("Pfarrer Huber")
        search_results = metadata_db.search_metadata("Pfarrer Huber")
        matched_paths = [r["file_path"] for r in search_results]
        assert str(recto_path.resolve()) in matched_paths or str(verso_path.resolve()) in matched_paths

        # 4. HTTP API Endpunkte testen
        # GET /api/archive/two-sided
        resp_get = client.get(f"/api/archive/two-sided?path={str(recto_path.resolve())}")
        assert resp_get.status_code == 200
        data_get = resp_get.json()
        assert data_get["is_two_sided"] is True
        assert data_get["role"] == "recto"
        assert data_get["companion_exists"] is True
        assert "Pfarrer Huber" in data_get["verso_notes"]

        # POST /api/archive/two-sided/notes
        updated_note = "Ergänzung: Fotograf Franz Mayer, Archiv Signatur Pfarrei-1928-09"
        resp_post = client.post(
            "/api/archive/two-sided/notes",
            json={"path": str(recto_path.resolve()), "notes": updated_note},
        )
        assert resp_post.status_code == 200
        assert resp_post.json()["success"] is True

        # Neuer Notizstand prüfen
        refreshed_info = recto_verso_service.get_two_sided_info(recto_path)
        assert refreshed_info["verso_notes"] == updated_note

    finally:
        if test_dir.exists():
            shutil.rmtree(test_dir)
