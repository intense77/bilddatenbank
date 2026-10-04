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


if __name__ == "__main__":
    test_thesaurus_service_lookup_and_expansion()
    test_autocomplete_and_categories()
    test_fastapi_thesaurus_endpoints()
    test_search_semantic_with_thesaurus_enrichment()
    print("All thesaurus tests passed successfully!")
