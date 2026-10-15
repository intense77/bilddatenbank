import pytest
from unittest.mock import MagicMock
from app.services.metadata_db import MetadataDatabase
from app.services.clustering_service import ClusteringService
from app.api.search import label_single_face, FaceLabelRequest
import tempfile
from pathlib import Path


def test_metadata_db_persons_support():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_meta.db"
        db = MetadataDatabase(db_path=db_path)

        # Upsert with persons list
        res = db.upsert_metadata(
            file_path="/data/photo1.jpg",
            title="Bischofsweihe",
            persons=["Bischof Müller", "Pfarrer Schmidt"],
        )
        assert res["persons"] == ["Bischof Müller", "Pfarrer Schmidt"]

        # Read back
        loaded = db.get_metadata("/data/photo1.jpg")
        assert loaded is not None
        assert loaded["title"] == "Bischofsweihe"
        assert loaded["persons"] == ["Bischof Müller", "Pfarrer Schmidt"]


def test_label_face_with_existing_cluster():
    mock_qdrant = MagicMock()
    mock_record = MagicMock()
    mock_record.payload = {"cluster_id": "cluster_42", "parent_image_id": "img-123"}
    mock_qdrant.client.scroll.return_value = ([mock_record], None)

    service = ClusteringService(qdrant_service=mock_qdrant)
    service.label_cluster = MagicMock(return_value=3)

    res = service.label_face("face-abc-123", "Bischof Ulrich")
    assert res["status"] == "success"
    assert res["cluster_id"] == "cluster_42"
    assert res["label"] == "Bischof Ulrich"
    assert res["updated_faces"] == 3
    service.label_cluster.assert_called_once_with(cluster_id="cluster_42", label="Bischof Ulrich")


def test_label_single_face_endpoint():
    mock_clustering = MagicMock()
    mock_clustering.label_face.return_value = {
        "status": "success",
        "face_id": "face-999",
        "cluster_id": "cluster_999",
        "label": "Kardinal Döpfner",
        "updated_faces": 1,
    }

    req = FaceLabelRequest(label="Kardinal Döpfner")
    res = label_single_face(face_id="face-999", request=req, clustering_service=mock_clustering)

    assert res["status"] == "success"
    assert res["label"] == "Kardinal Döpfner"
    mock_clustering.label_face.assert_called_once_with(face_id="face-999", label="Kardinal Döpfner")
