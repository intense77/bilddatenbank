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


if __name__ == "__main__":
    test_search_pagination_and_person_separation()
    test_batch_browsing_empty_query()
    test_batch_search_leakage_prevention()
    test_metadata_db_batch_filtering()
    print("All search tests passed successfully!")
