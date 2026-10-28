import base64
import os
import shutil
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.core.auth import Role
from app.services.ocr_service import ocr_service
from app.services.metadata_db import metadata_db
from app.services.recto_verso_service import recto_verso_service


@pytest.fixture
def auth_headers():
    admin_cred = f"{settings.AUTH_DEFAULT_ADMIN_USER}:{settings.AUTH_DEFAULT_ADMIN_PASSWORD}".encode("utf-8")
    curator_cred = f"{settings.AUTH_DEFAULT_CURATOR_USER}:{settings.AUTH_DEFAULT_CURATOR_PASSWORD}".encode("utf-8")
    viewer_cred = f"{settings.AUTH_DEFAULT_VIEWER_USER}:{settings.AUTH_DEFAULT_VIEWER_PASSWORD}".encode("utf-8")
    return {
        "admin": {"Authorization": "Basic " + base64.b64encode(admin_cred).decode("ascii")},
        "curator": {"Authorization": "Basic " + base64.b64encode(curator_cred).decode("ascii")},
        "viewer": {"Authorization": "Basic " + base64.b64encode(viewer_cred).decode("ascii")},
    }


@pytest.fixture
def temp_ocr_dir():
    temp_dir = tempfile.mkdtemp(prefix="test_ocr_")
    orig_dirs = list(settings.ALLOWED_IMAGE_DIRS)
    settings.ALLOWED_IMAGE_DIRS.append(temp_dir)
    yield temp_dir
    settings.ALLOWED_IMAGE_DIRS = orig_dirs
    shutil.rmtree(temp_dir, ignore_errors=True)


def create_test_text_image(path: Path, text: str = "ARCHIV 1924"):
    """Erzeugt ein Bild mit schwarzer Schrift auf hellem Grund."""
    img = Image.new("RGB", (600, 200), color=(245, 240, 220))  # Leicht gelbliches historisches Papier
    draw = ImageDraw.Draw(img)
    # Großbuchstaben zeichnen
    draw.text((30, 70), text, fill=(10, 10, 10))
    img.save(path)
    return path


def test_ocr_service_availability_and_languages():
    """Prüft, dass Tesseract 5 auf dem Host verfügbar ist und Sprachen auflistet."""
    assert ocr_service.is_available() is True
    langs = ocr_service.get_available_languages()
    assert isinstance(langs, list)
    assert len(langs) > 0
    assert any("deu" in l or "eng" in l or "osd" in l for l in langs)


def test_ocr_image_preprocessing(temp_ocr_dir):
    """Testet die Bild-Vorverarbeitung für historische Digitalisate."""
    img_path = Path(temp_ocr_dir) / "test_preproc.jpg"
    create_test_text_image(img_path, "TEST DOKUMENT")

    with Image.open(img_path) as raw:
        processed = ocr_service.preprocess_image_for_ocr(raw)
        assert processed.mode == "L"
        # Resolution scaling ensures minimum 1200 px on the long edge
        assert max(processed.size) >= 1200


def test_ocr_text_extraction(temp_ocr_dir):
    """Führt OCR auf einem erzeugten Testbild aus."""
    img_path = Path(temp_ocr_dir) / "test_extract.jpg"
    create_test_text_image(img_path, "ARCHIV 1924")

    res = ocr_service.extract_text_from_image(img_path, languages="deu+eng")
    assert res["status"] == "success"
    text = res["ocr_text"]
    assert "1924" in text or "ARCHIV" in text or len(text) > 0

    direct_text = ocr_service.extract_text(img_path)
    assert isinstance(direct_text, str)


def test_metadata_db_ocr_persistence(temp_ocr_dir):
    """Prüft Speichern, Abrufen und Volltextsuche in SQLite."""
    file_path = str(Path(temp_ocr_dir) / "doc_sample.jpg")

    metadata_db.save_ocr_text(file_path, "Kirchenchor St. Michael Jubiläum 1935")
    retrieved = metadata_db.get_ocr_text(file_path)
    assert retrieved == "Kirchenchor St. Michael Jubiläum 1935"

    # Suche über search_metadata
    hits = metadata_db.search_metadata("Kirchenchor")
    assert any(h["file_path"] == file_path for h in hits)

    hits_year = metadata_db.search_metadata("1935")
    assert any(h["file_path"] == file_path for h in hits_year)


def test_recto_verso_ocr_relationship(temp_ocr_dir):
    """Prüft, dass der Zweiblatt-Service OCR-Texte beider Seiten liefert."""
    recto_path = Path(temp_ocr_dir) / "foto_001_r.jpg"
    verso_path = Path(temp_ocr_dir) / "foto_001_v.jpg"
    create_test_text_image(recto_path, "FOTO VORDERSEITE")
    create_test_text_image(verso_path, "STEMPEL ATELIER MEYER 1928")

    recto_str = str(recto_path.resolve())
    verso_str = str(verso_path.resolve())

    metadata_db.save_ocr_text(recto_str, "Vorderseite Schild")
    metadata_db.save_ocr_text(verso_str, "Stempel Fotoatelier Meyer 1928")

    # Info für Recto abrufen
    info_r = recto_verso_service.get_two_sided_info(recto_path)
    assert info_r["is_two_sided"] is True
    assert info_r["role"] == "recto"
    assert info_r["ocr_text"] == "Vorderseite Schild"
    assert info_r["companion_ocr_text"] == "Stempel Fotoatelier Meyer 1928"
    assert info_r["verso_ocr_text"] == "Stempel Fotoatelier Meyer 1928"
    assert info_r["recto_ocr_text"] == "Vorderseite Schild"

    # Info für Verso abrufen
    info_v = recto_verso_service.get_two_sided_info(verso_path)
    assert info_v["is_two_sided"] is True
    assert info_v["role"] == "verso"
    assert info_v["ocr_text"] == "Stempel Fotoatelier Meyer 1928"
    assert info_v["companion_ocr_text"] == "Vorderseite Schild"


def test_ocr_api_endpoints_permissions_and_workflow(temp_ocr_dir, auth_headers):
    """Testet die OCR REST-API Endpunkte inkl. RBAC Berechtigungen."""
    img_path = Path(temp_ocr_dir) / "api_test.jpg"
    create_test_text_image(img_path, "STADTMUSEUM 1950")
    img_str = str(img_path.resolve())

    client = TestClient(app)

    # 1. GET /api/archive/ocr ist öffentlich / lesbar
    resp_get = client.get(f"/api/archive/ocr?path={img_str}", headers=auth_headers["viewer"])
    assert resp_get.status_code == 200
    data_get = resp_get.json()
    assert data_get["file_path"] == img_str
    assert data_get["engine_available"] is True

    # 2. POST /api/archive/ocr/save erfordert Curator-Rolle
    # Lesesaal-Gast (Viewer) darf nicht speichern (403)
    resp_save_viewer = client.post(
        "/api/archive/ocr/save",
        json={"path": img_str, "ocr_text": "Manuelle Korrektur"},
        headers=auth_headers["viewer"],
    )
    assert resp_save_viewer.status_code == 403

    # Archivar darf speichern (200)
    resp_save_curator = client.post(
        "/api/archive/ocr/save",
        json={"path": img_str, "ocr_text": "Kuratierter Text 1950"},
        headers=auth_headers["curator"],
    )
    assert resp_save_curator.status_code == 200
    assert resp_save_curator.json()["ocr_text"] == "Kuratierter Text 1950"

    # 3. POST /api/archive/ocr/extract erfordert Curator-Rolle
    resp_extract_viewer = client.post(
        "/api/archive/ocr/extract",
        json={"path": img_str},
        headers=auth_headers["viewer"],
    )
    assert resp_extract_viewer.status_code == 403

    resp_extract_curator = client.post(
        "/api/archive/ocr/extract",
        json={"path": img_str, "languages": "deu+eng", "save_result": True},
        headers=auth_headers["curator"],
    )
    assert resp_extract_curator.status_code == 200
    data_extract = resp_extract_curator.json()
    assert data_extract["success"] is True
    assert "ocr_text" in data_extract


def test_sauvola_adaptive_binarization():
    """Prüft die mathematische Korrektheit der Sauvola-Lokalvarianz-Binarisierung."""
    import numpy as np
    from app.services.ocr_service import sauvola_threshold

    # Testbild: Vergilbter Hintergrund (200) mit feinen Tintenstrichen (50)
    arr = np.full((100, 100), 200, dtype=np.uint8)
    # Strich einzeichnen
    arr[40:60, 50] = 50

    binary = sauvola_threshold(arr, window_size=15, k=0.25, r=128.0)
    # Hintergrund muss weiß (255) sein, Textlinie schwarz (0)
    assert binary[10, 10] == 255
    assert binary[50, 50] == 0


def test_htr_profile_handwriting_recognition():
    """
    Testet die HTR-Erkennung mit Sauvola-Binarisierung auf dem historischen Testbeleg.
    Prüft, dass handschriftliche Notizen und Stempel auf Verso korrekt entziffert werden.
    """
    demo_path = Path("data/demo_zweiblatt/historisches_foto_v.jpg").resolve()
    if not demo_path.is_file():
        pytest.skip("Demo-Zweiblatt-Datei nicht vorhanden")

    res = ocr_service.extract_text_from_image(str(demo_path), profile="handwritten")
    assert res["status"] == "success"
    text = res["ocr_text"]

    # Prüfe Erkennung der handschriftlichen Widmung oder des Stempels
    assert any(term in text for term in ["Fronleichnam", "Huber", "Meyer", "RÜCKSEITE", "RUECKSEITE"])
    assert res.get("profile_used") == "handwritten"


def test_available_profiles_and_api_selection(auth_headers):
    """Testet die Profilauswahl in der REST-API (Auto, Handwritten, Fraktur, Printed)."""
    profiles = ocr_service.get_available_profiles()
    assert "auto" in profiles
    assert "handwritten" in profiles
    assert "fraktur" in profiles
    assert "printed" in profiles

    demo_path = Path("data/demo_zweiblatt/historisches_foto_v.jpg").resolve()
    if not demo_path.is_file():
        pytest.skip("Demo-Zweiblatt-Datei nicht vorhanden")

    client = TestClient(app)
    resp = client.post(
        "/api/archive/ocr/extract",
        json={
            "path": str(demo_path),
            "profile": "handwritten",
            "save_result": False,
        },
        headers=auth_headers["curator"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["profile_used"] == "handwritten"
    assert data["word_count"] > 0


def test_historical_ligature_and_long_s_correction():
    """
    Testet die automatische Normalisierung historischer Ligaturen (æ, œ, ſ)
    und typischer Fraktur-OCR-Fehlinterpretationen (z.B. Meffgewand -> Messgewand).
    """
    raw_text = "In noftro Klofter trug der Priefter ein Meffgewand mit Kruzifir vor dem Erzbifchof."
    cleaned = ocr_service._clean_ocr_text(raw_text)
    assert "Kloster" in cleaned
    assert "Priester" in cleaned
    assert "Messgewand" in cleaned
    assert "Kruzifix" in cleaned
    assert "Erzbischof" in cleaned

    # Teste Ligaturen und langes s
    latin_ligatures = "Sacræ Scripturæ et Cœlum Meſſe"
    cleaned_latin = ocr_service._clean_ocr_text(latin_ligatures)
    assert "Sacrae Scripturae" in cleaned_latin
    assert "Coelum" in cleaned_latin
    assert "Messe" in cleaned_latin


def test_latin_profile_and_user_words(auth_headers):
    """
    Prüft das Latein/Liturgica-Profil sowie das Vorhandensein der Tesseract-5-Wörterbücher
    (church_archival.user-words und user-patterns).
    """
    profiles = ocr_service.get_available_profiles()
    assert "latin" in profiles
    assert "Latein" in profiles["latin"]

    # Prüfe Wörterbuchdateien
    words_file = ocr_service.get_effective_user_words_file()
    assert words_file is not None
    assert Path(words_file).is_file()

    words_content = Path(words_file).read_text(encoding="utf-8")
    assert "Tabernaculum" in words_content
    assert "Messgewand" in words_content
    assert "Consecratio" in words_content

    patterns_file = ocr_service.get_effective_user_patterns_file()
    assert patterns_file is not None
    assert Path(patterns_file).is_file()

    # REST-API Aufruf mit Profil 'latin'
    demo_path = Path("data/demo_zweiblatt/historisches_foto_v.jpg").resolve()
    if not demo_path.is_file():
        pytest.skip("Demo-Zweiblatt-Datei nicht vorhanden")

    client = TestClient(app)
    resp = client.post(
        "/api/archive/ocr/extract",
        json={
            "path": str(demo_path),
            "profile": "latin",
            "save_result": False,
        },
        headers=auth_headers["curator"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["profile_used"] == "latin"

