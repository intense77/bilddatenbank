from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.services.thesaurus_service import thesaurus_service
from app.api.search import search_semantic


def test_thesaurus_service_lookup_and_expansion():
    # 1. Kasel / Messgewand
    res = thesaurus_service.expand_query("Messgewand")
    assert res is not None
    assert res["canonical"] == "Kasel"
    assert res["iconclass"] == "11Q71421"
    assert res["category"] == "Paramente"
    assert "Messgewand" in res["synonyms"]
    assert "Planeta" in res["synonyms"]
    assert "Kasel" in res["expansion_terms"]
    assert "Messgewand" in res["expansion_terms"]

    # 2. Synonym: Pluviale
    syn_res = thesaurus_service.expand_query("Pluviale")
    assert syn_res is not None
    assert syn_res["canonical"] == "Chormantel"
    assert syn_res["iconclass"] == "11Q71425"

    # 3. Monstranz / Ostensorium
    mon_res = thesaurus_service.expand_query("Ostensorium")
    assert mon_res is not None
    assert mon_res["canonical"] == "Monstranz"
    assert mon_res["iconclass"] == "11Q71441"

    # 4. Unknown query
    unk_res = thesaurus_service.expand_query("UnbekanntesWort999")
    assert unk_res is None


def test_autocomplete_and_categories():
    suggestions = thesaurus_service.autocomplete("Mess", limit=5)
    assert any(s["canonical"] == "Kasel" for s in suggestions)

    categories = thesaurus_service.get_all_categories()
    assert "Paramente" in categories
    assert "Vasa sacra" in categories
    assert "Sakrale Architektur" in categories
    assert "Liturgische Feiern" in categories
    assert "Klerus & Ordenswesen" in categories

    paramente_terms = thesaurus_service.get_terms("Paramente")
    assert len(paramente_terms) >= 3
    assert all(t["category"] == "Paramente" for t in paramente_terms)


def test_fastapi_thesaurus_endpoints():
    client = TestClient(app)

    # /thesaurus/categories
    r_cat = client.get("/thesaurus/categories")
    assert r_cat.status_code == 200
    cats = r_cat.json()
    assert isinstance(cats, list)
    assert "Paramente" in cats

    # /thesaurus/terms
    r_terms = client.get("/thesaurus/terms")
    assert r_terms.status_code == 200
    terms = r_terms.json()
    assert len(terms) >= 15
    assert any(t["canonical"] == "Monstranz" for t in terms)

    # /thesaurus/expand
    r_exp = client.get("/thesaurus/expand?q=Messgewand")
    assert r_exp.status_code == 200
    exp_data = r_exp.json()
    assert exp_data["has_expansion"] is True
    assert exp_data["canonical"] == "Kasel"
    assert exp_data["iconclass"] == "11Q71421"
    assert exp_data["gnd"] == "4163353-8"

    # /thesaurus/suggest
    r_sug = client.get("/thesaurus/suggest?prefix=Kelch")
    assert r_sug.status_code == 200
    sug_data = r_sug.json()
    assert len(sug_data) >= 1
    assert any("Kelch" in s["term"] or "Kelch" in s["canonical"] for s in sug_data)


def test_search_semantic_with_thesaurus_enrichment():
    mock_clip = MagicMock()
    mock_clip.embed_text.return_value = [0.05] * 512

    mock_qdrant = MagicMock()
    mock_qdrant.client.scroll.return_value = ([], None)

    mock_hit = MagicMock()
    mock_hit.id = "33333333-3333-3333-3333-333333333333"
    mock_hit.score = 0.72
    mock_hit.payload = {
        "file_path": "/data/test/kasel_foto.jpg",
        "file_name": "kasel_foto.jpg",
        "description": "Priester im feierlichen Messgewand",
    }
    mock_qdrant.search_images.return_value = [mock_hit]
    mock_qdrant.client.retrieve.return_value = []

    mock_variant = MagicMock()
    mock_variant.stack_search_results.side_effect = lambda hits, **kwargs: hits

    results = search_semantic(
        q="Messgewand",
        limit=5,
        offset=0,
        score_threshold=None,
        stack_variants=False,
        clip_service=mock_clip,
        qdrant=mock_qdrant,
        variant_service=mock_variant,
    )

    assert len(results) >= 1
    # Check that iconclass and thesaurus_category are attached to result
    assert results[0].iconclass == "11Q71421"
    assert results[0].thesaurus_category == "Paramente"
    print("✓ test_search_semantic_with_thesaurus_enrichment passed!")


# =========================================================================
# Säule 3: Tests für GND-Normdaten, Trägererkennung & Zero-Shot API
# =========================================================================

import base64
import tempfile
import numpy as np
from PIL import Image
from pathlib import Path
import pytest
from app.core.config import settings
from app.services.metadata_db import metadata_db
from app.api.deps import get_clip_service, get_qdrant_service


@pytest.fixture
def auth_headers():
    curator_cred = f"{settings.AUTH_DEFAULT_CURATOR_USER}:{settings.AUTH_DEFAULT_CURATOR_PASSWORD}".encode("utf-8")
    viewer_cred = f"{settings.AUTH_DEFAULT_VIEWER_USER}:{settings.AUTH_DEFAULT_VIEWER_PASSWORD}".encode("utf-8")
    return {
        "curator": {"Authorization": "Basic " + base64.b64encode(curator_cred).decode("ascii")},
        "viewer": {"Authorization": "Basic " + base64.b64encode(viewer_cred).decode("ascii")},
    }


@pytest.fixture
def temp_thesaurus_image_dir():
    temp_dir = tempfile.mkdtemp(prefix="test_thesaurus_")
    orig_dirs = list(settings.ALLOWED_IMAGE_DIRS)
    settings.ALLOWED_IMAGE_DIRS.append(temp_dir)
    yield temp_dir
    settings.ALLOWED_IMAGE_DIRS = orig_dirs
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_sqlite_gnd_authorities_seeding_and_search():
    """Prüft die lokale SQLite-Normdatenbank für kirchliche GND- & Iconclass-Einträge."""
    # 1. Suche nach Vasa sacra (Kelch)
    results = metadata_db.search_gnd_authorities("Kelch")
    assert len(results) >= 1
    kelch = results[0]
    assert kelch["canonical"] == "Kelch"
    assert kelch["category"] == "Vasa sacra"
    assert kelch["gnd"] == "4163565-1"
    assert kelch["iconclass"] == "11Q71442"

    # 2. Alle Entitäten abrufen & Kategorien prüfen
    all_ents = metadata_db.get_all_gnd_authorities()
    assert len(all_ents) >= 30
    categories = {e["category"] for e in all_ents}
    assert "Vasa sacra" in categories
    assert "Paramente" in categories
    assert "Sakrale Architektur" in categories
    assert "Klerus & Ordenswesen" in categories

    # 3. Spezifischer Lookup
    auth = metadata_db.get_gnd_authority("Monstranz")
    assert auth is not None
    assert auth["canonical"] == "Monstranz"
    assert auth["gnd"] == "4040126-1"


def test_carrier_and_condition_detection(temp_thesaurus_image_dir):
    """Prüft die heuristische Träger- und Zustandserkennung für historische Verfahren."""
    dir_path = Path(temp_thesaurus_image_dir)

    # 1. Albuminpapier / Sepia im Carte de Visite Format (Ratio 1.6:1, B=600, H=960)
    cdv_path = dir_path / "cdv_portrait.jpg"
    cdv_img = Image.new("RGB", (600, 960), color=(185, 140, 95))
    cdv_img.save(cdv_path, quality=90)

    cdv_result = thesaurus_service.detect_carrier_and_condition(cdv_path)
    assert "Albumin" in cdv_result["carrier_type"]
    assert "Carte de Visite" in cdv_result["format_estimate"]
    assert "1860" in cdv_result["estimated_era"]

    # 2. Silbergelatine SW (Neutralgrau)
    bw_path = dir_path / "bw_church.jpg"
    bw_img = Image.new("RGB", (800, 600), color=(130, 130, 130))
    bw_img.save(bw_path, quality=90)

    bw_result = thesaurus_service.detect_carrier_and_condition(bw_path)
    assert "Silbergelatine" in bw_result["carrier_type"]
    assert "1890" in bw_result["estimated_era"]

    # 3. Cyanotypie (Preußischblau)
    cyano_path = dir_path / "cyanotype_chapel.jpg"
    cyano_img = Image.new("RGB", (800, 600), color=(30, 80, 170))
    cyano_img.save(cyano_path, quality=90)

    cyano_result = thesaurus_service.detect_carrier_and_condition(cyano_path)
    assert "Cyanotypie" in cyano_result["carrier_type"]
    assert "1880" in cyano_result["estimated_era"]


def test_thesaurus_zero_shot_suggestions_with_mock_clip():
    """Testet die Zero-Shot Ähnlichkeitsberechnung gegen vorberechnete GND-Embeddings."""
    mock_clip = MagicMock()
    # Simuliere normalisierten 512-dim Vektor
    vec = [0.0] * 512
    vec[0] = 1.0
    mock_clip.embed_text.return_value = vec

    # Vokabular-Matrix aufbauen lassen
    thesaurus_service._thesaurus_embeddings = None
    suggestions = thesaurus_service.suggest_thesaurus_tags(
        image_embedding=vec,
        clip_service=mock_clip,
        top_k=5,
        min_confidence=0.1,
    )
    assert len(suggestions) > 0
    assert "canonical" in suggestions[0]
    assert "confidence" in suggestions[0]
    assert suggestions[0]["confidence"] > 0.0


def test_thesaurus_api_säule3_endpoints(temp_thesaurus_image_dir, auth_headers):
    """Testet die neuen REST-API Endpunkte für GND-Suche, Trägererkennung und Tag-Übernahme."""
    dir_path = Path(temp_thesaurus_image_dir)
    test_img = dir_path / "altar_photo.jpg"
    img = Image.new("RGB", (800, 600), color=(140, 140, 140))
    img.save(test_img, quality=90)
    img_str = str(test_img.resolve())

    # Initialen Metadatensatz in SQLite anlegen
    metadata_db.upsert_metadata(
        file_path=img_str,
        file_name="altar_photo.jpg",
        title="Historischer Hochaltar",
        keywords=["Archiv2026"],
    )

    client = TestClient(app)

    # 1. GET /thesaurus/authorities
    resp_auth = client.get("/thesaurus/authorities?q=Altar")
    assert resp_auth.status_code == 200
    auth_list = resp_auth.json()
    assert isinstance(auth_list, list)
    assert any("altar" in a["canonical"].lower() for a in auth_list)

    # 2. GET /thesaurus/carrier
    resp_carrier = client.get(f"/thesaurus/carrier?path={img_str}")
    assert resp_carrier.status_code == 200
    carrier_data = resp_carrier.json()
    assert carrier_data["success"] is True
    assert "carrier_analysis" in carrier_data
    assert "Silbergelatine" in carrier_data["carrier_analysis"]["carrier_type"]

    # 3. GET /thesaurus/suggest-for-image (mit Dependency Mock)
    mock_clip = MagicMock()
    mock_clip.embed_image.return_value = [0.05] * 512
    mock_clip.embed_text.return_value = [0.05] * 512
    app.dependency_overrides[get_clip_service] = lambda: mock_clip

    try:
        resp_sug = client.get(f"/thesaurus/suggest-for-image?path={img_str}&top_k=5")
        assert resp_sug.status_code == 200
        sug_data = resp_sug.json()
        assert sug_data["success"] is True
        assert "suggestions" in sug_data
        assert "carrier_analysis" in sug_data
    finally:
        app.dependency_overrides.pop(get_clip_service, None)

    # 4. POST /thesaurus/apply-tags mit RBAC
    mock_qdrant = MagicMock()
    mock_qdrant.client.scroll.return_value = ([], None)
    app.dependency_overrides[get_qdrant_service] = lambda: mock_qdrant

    try:
        # Viewer darf nicht speichern (403)
        resp_apply_viewer = client.post(
            "/thesaurus/apply-tags",
            json={"path": img_str, "tags": ["Hochaltar", "Tabernakel"]},
            headers=auth_headers["viewer"],
        )
        assert resp_apply_viewer.status_code == 403

        # Curator darf speichern (200)
        resp_apply_curator = client.post(
            "/thesaurus/apply-tags",
            json={
                "path": img_str,
                "tags": ["Hochaltar", "Tabernakel"],
                "carrier_type": "Silbergelatine-Abzug (Schwarz-Weiß)",
            },
            headers=auth_headers["curator"],
        )
        assert resp_apply_curator.status_code == 200
        apply_data = resp_apply_curator.json()
        assert apply_data["success"] is True
        assert "Hochaltar" in apply_data["merged_keywords"]
        assert "Silbergelatine-Abzug (Schwarz-Weiß)" in apply_data["merged_keywords"]
        assert "Archiv2026" in apply_data["merged_keywords"]

        # Prüfe Persistenz in SQLite
        db_record = metadata_db.get_metadata(img_str)
        assert "Hochaltar" in db_record["keywords"]
        assert "Tabernakel" in db_record["keywords"]
    finally:
        app.dependency_overrides.pop(get_qdrant_service, None)


if __name__ == "__main__":
    test_thesaurus_service_lookup_and_expansion()
    test_autocomplete_and_categories()
    test_fastapi_thesaurus_endpoints()
    test_search_semantic_with_thesaurus_enrichment()
    print("All thesaurus tests passed successfully!")

