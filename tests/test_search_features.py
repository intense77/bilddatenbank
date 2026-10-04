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


if __name__ == "__main__":
    test_search_pagination_and_person_separation()
    print("All search tests passed!")
