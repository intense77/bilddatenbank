from unittest.mock import MagicMock
from app.api.search import search_semantic, SemanticSearchResult
from app.services.metadata_db import MetadataDatabase
from pathlib import Path
import tempfile
import uuid


def test_search_pagination_and_person_separation():
    # Setup mocks
    mock_clip = MagicMock()
    mock_clip.embed_text.return_value = [0.1] * 512

    mock_qdrant = MagicMock()
    # Mock scroll on archive_faces for labeled faces
    mock_face_point = MagicMock()
    mock_face_point.payload = {
        "label": "TestPerson",
        "file_path": "/data/test/person_image.jpg",
        "parent_image_id": "11111111-1111-1111-1111-111111111111"
    }
    # Return 1 labeled face on first scroll, then None for next_offset
    mock_qdrant.client.scroll.side_effect = [
        ([mock_face_point], None),  # archive_faces
    ]

    mock_img_hit = MagicMock()
    mock_img_hit.id = "22222222-2222-2222-2222-222222222222"
    mock_img_hit.score = 0.25
    mock_img_hit.payload = {
        "file_path": "/data/test/scene_image.jpg",
        "file_name": "scene_image.jpg"
    }
    mock_qdrant.search_images.return_value = [mock_img_hit]
    mock_qdrant.client.retrieve.return_value = []

    mock_variant = MagicMock()
    mock_variant.stack_search_results.side_effect = lambda hits, **kwargs: hits

    # 1. Search for TestPerson with limit=1, offset=0
    results_p1 = search_semantic(
        q="TestPerson",
        limit=1,
        offset=0,
        score_threshold=None,
        stack_variants=False,
        clip_service=mock_clip,
        qdrant=mock_qdrant,
        variant_service=mock_variant,
    )

    assert len(results_p1) == 1
    assert results_p1[0].match_type == "person"
    assert results_p1[0].matched_query == "TestPerson"
    assert results_p1[0].score == 1.0

    print("✓ Search pagination and person match test passed successfully!")


def test_batch_browsing_empty_query():
    """Prüft, dass bei q='' und batch_id alle Bilder des Bestands ohne Suchwort geliefert werden."""
    mock_clip = MagicMock()
    mock_qdrant = MagicMock()
    mock_variant = MagicMock()
    mock_variant.stack_search_results.side_effect = lambda hits, **kwargs: hits

    batch_rec1 = MagicMock()
    batch_rec1.id = "rec-1"
    batch_rec1.payload = {
        "file_path": "/data/test/batch1/img_01.jpg",
        "file_name": "img_01.jpg",
        "import_id": "batch_import_42",
        "title": "Erstes Bild im Batch"
    }
    batch_rec2 = MagicMock()
    batch_rec2.id = "rec-2"
    batch_rec2.payload = {
        "file_path": "/data/test/batch1/img_02.jpg",
        "file_name": "img_02.jpg",
        "import_id": "batch_import_42",
        "title": "Zweites Bild im Batch"
    }

    mock_qdrant.client.scroll.return_value = ([batch_rec1, batch_rec2], None)

    results = search_semantic(
        q="",
        limit=24,
        offset=0,
        batch_id="batch_import_42",
        clip_service=mock_clip,
        qdrant=mock_qdrant,
        variant_service=mock_variant,
    )

    assert len(results) == 2
    assert results[0].file_name == "img_01.jpg"
    assert results[0].matched_query == "Bestand: batch_import_42"
    assert results[0].score == 1.0


def test_batch_search_leakage_prevention():
    """Prüft, dass bei Angabe von batch_id keinesfalls Bilder aus fremden Batches lecken."""
    mock_clip = MagicMock()
    mock_clip.embed_text.return_value = [0.1] * 512

    mock_qdrant = MagicMock()

    # Face aus fremdem Batch (batch_other)
    face_foreign = MagicMock()
    face_foreign.payload = {
        "label": "Pfarrer Mueller",
        "file_path": "/data/test/other/foreign_face.jpg",
        "import_id": "batch_other",
        "parent_image_id": "foreign-img-id"
    }

    # Face aus Ziel-Batch (batch_target)
    face_target = MagicMock()
    face_target.payload = {
        "label": "Pfarrer Mueller",
        "file_path": "/data/test/target/target_face.jpg",
        "import_id": "batch_target",
        "parent_image_id": "target-img-id"
    }

    mock_qdrant.client.scroll.return_value = ([face_foreign, face_target], None)

    # CLIP Hit aus Ziel-Batch
    clip_hit = MagicMock()
    clip_hit.id = "target-img-id"
    clip_hit.score = 0.85
    clip_hit.payload = {
        "file_path": "/data/test/target/target_face.jpg",
        "file_name": "target_face.jpg",
        "import_id": "batch_target"
    }
    mock_qdrant.search_images.return_value = [clip_hit]
    mock_qdrant.client.retrieve.return_value = []

    mock_variant = MagicMock()
    mock_variant.stack_search_results.side_effect = lambda hits, **kwargs: hits

    results = search_semantic(
        q="Pfarrer Mueller",
        limit=24,
        offset=0,
        batch_id="batch_target",
        clip_service=mock_clip,
        qdrant=mock_qdrant,
        variant_service=mock_variant,
    )

    # Es darf NUR das Bild aus batch_target vorkommen!
    assert len(results) == 1
    assert results[0].file_path == "/data/test/target/target_face.jpg"
    assert all("foreign" not in r.file_path for r in results)


def test_metadata_db_batch_filtering():
    """Prüft die batch_id Filterung in MetadataDatabase.search_metadata."""
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        db = MetadataDatabase(db_path=Path(tmp.name))
        db.upsert_metadata("/img1.jpg", file_name="img1.jpg", title="Foto Altar")
        db.update_metadata_import_id("/img1.jpg", "batch_A")

        db.upsert_metadata("/img2.jpg", file_name="img2.jpg", title="Foto Orgel")
        db.update_metadata_import_id("/img2.jpg", "batch_B")

        # Suche nach 'Foto' ohne Batch-Filter -> beide
        all_res = db.search_metadata("Foto")
        assert len(all_res) == 2

        # Suche nach 'Foto' mit Batch-Filter 'batch_A' -> nur img1
        batch_a_res = db.search_metadata("Foto", import_id="batch_A")
        assert len(batch_a_res) == 1
        assert batch_a_res[0]["file_path"] == "/img1.jpg"

        # Suche nach 'Foto' mit Batch-Filter 'batch_B' -> nur img2
        batch_b_res = db.search_metadata("Foto", import_id="batch_B")
        assert len(batch_b_res) == 1
        assert batch_b_res[0]["file_path"] == "/img2.jpg"


def test_timeline_and_facet_filtering():
    """Prüft historische Zeitleiste (Jahresfilter / Epochen), Signaturen- und Urheberfilter."""
    from app.api.search import extract_year_from_item, item_matches_facets

    # 1. Jahres-Extraktion testen
    assert extract_year_from_item("1928:05:14 12:00:00") == 1928
    assert extract_year_from_item("2010-10-31") == 2010
    assert extract_year_from_item("ca. 1895") == 1895
    assert extract_year_from_item(None, "/archive/1914_Kaiserreich/foto1.jpg") == 1914
    assert extract_year_from_item(None, "/archive/unbekannt/foto.jpg") is None

    # 2. item_matches_facets mit Zeitraum
    item_payload = {"date": "1925-06-01", "signature": "Sig-1925-A", "creator": "Atelier Müller"}
    assert item_matches_facets(item_payload, "/img.jpg", year_from=1914, year_to=1939) is True
    assert item_matches_facets(item_payload, "/img.jpg", year_from=1930, year_to=1945) is False
    assert item_matches_facets(item_payload, "/img.jpg", year_from=1880, year_to=1920) is False

    # 3. Signature & Creator Filter
    assert item_matches_facets(item_payload, "/img.jpg", signature_filter="Sig-1925") is True
    assert item_matches_facets(item_payload, "/img.jpg", signature_filter="Sig-9999") is False
    assert item_matches_facets(item_payload, "/img.jpg", creator_filter="müller") is True
    assert item_matches_facets(item_payload, "/img.jpg", creator_filter="schmidt") is False

    # 4. search_semantic mit Epoche 'weimar' (1914-1939)
    mock_clip = MagicMock()
    mock_clip.embed_text.return_value = [0.1] * 512
    mock_qdrant = MagicMock()
    mock_variant = MagicMock()
    mock_variant.stack_search_results.side_effect = lambda hits, **kwargs: hits

    hit1 = MagicMock()
    hit1.id = "1"
    hit1.score = 0.8
    hit1.payload = {"file_path": "/img_weimar.jpg", "file_name": "weimar.jpg", "date": "1928"}

    hit2 = MagicMock()
    hit2.id = "2"
    hit2.score = 0.75
    hit2.payload = {"file_path": "/img_modern.jpg", "file_name": "modern.jpg", "date": "2005"}

    mock_qdrant.search_images.return_value = [hit1, hit2]
    mock_qdrant.client.scroll.return_value = ([], None)

    results = search_semantic(
        q="feier",
        epoch="weimar",
        clip_service=mock_clip,
        qdrant=mock_qdrant,
        variant_service=mock_variant,
    )
    assert len(results) == 1
    assert results[0].file_path == "/img_weimar.jpg"


def test_facets_summary_endpoint():
    """Prüft die Aggregierung der Metadaten-Facetten in MetadataDatabase."""
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        db = MetadataDatabase(db_path=Path(tmp.name))
        db.upsert_metadata("/img1.jpg", file_name="img1.jpg", date="1910", creator="Fotoatelier Karl", signature="Sig-001")
        db.upsert_metadata("/img2.jpg", file_name="img2.jpg", date="1968", creator="Presseamt", signature="Sig-002")

        facets = db.get_facets_summary()
        assert "years" in facets
        assert "epochs" in facets
        assert "creators" in facets
        assert "signatures" in facets
        assert "Fotoatelier Karl" in facets["creators"]
        assert "Presseamt" in facets["creators"]
        assert "Sig-001" in facets["signatures"]
        assert facets["years"]["min"] <= 1910


if __name__ == "__main__":
    test_search_pagination_and_person_separation()
    test_batch_browsing_empty_query()
    test_batch_search_leakage_prevention()
    test_metadata_db_batch_filtering()
    test_timeline_and_facet_filtering()
    test_facets_summary_endpoint()
    print("All search tests passed successfully!")
