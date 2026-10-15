import pytest
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch
from pathlib import Path
from app.services.xmp_service import XmpService


def test_mwg_regions_xml_generation():
    service = XmpService()
    test_regions = [
        {
            "name": "Bischof Johann",
            "type": "Face",
            "bbox_percent": {"left": 20.0, "top": 30.0, "width": 10.0, "height": 20.0},
            "orig_width": 2000,
            "orig_height": 1000,
            "curation_status": "VERIFIED",
        },
        {
            "name": "",
            "type": "Face",
            "bbox": [100, 200, 300, 400],
            "orig_width": 2000,
            "orig_height": 1000,
            "curation_status": "KI_AUTO",
        }
    ]

    xml_str = service.generate_xmp_content(
        file_path="/data/photos/test_bild.jpg",
        title="Feierlicher Einzug",
        regions=test_regions,
        image_width=2000,
        image_height=1000,
    )

    assert "mwg-rs:Regions" in xml_str
    assert "mwg-rs:AppliedToDimensions" in xml_str
    assert "stDim:w" in xml_str
    assert "2000" in xml_str
    assert "1000" in xml_str
    assert "Bischof Johann" in xml_str
    assert "VERIFIED" in xml_str
    assert "KI_AUTO" in xml_str
    assert "stArea:unit" in xml_str
    assert "normalized" in xml_str

    # Parse XML and inspect structure
    root = ET.fromstring(xml_str)
    # Check namespaces
    namespaces = {
        "x": "adobe:ns:meta/",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "mwg-rs": "http://www.metadataworkinggroup.com/schemas/regions/",
        "stDim": "http://ns.adobe.com/xap/1.0/sType/Dimensions#",
        "stArea": "http://ns.adobe.com/xmp/sType/Area#",
        "Iptc4xmpExt": "http://iptc.org/std/Iptc4xmpExt/2008-02-29/",
    }

    region_nodes = root.findall(".//mwg-rs:RegionList/rdf:Bag/rdf:li", namespaces)
    assert len(region_nodes) == 2

    # First region (Bischof Johann): left=20%, width=10% -> center x = 0.25; top=30%, height=20% -> center y = 0.40
    r1 = region_nodes[0]
    r1_name = r1.find("mwg-rs:Name", namespaces)
    assert r1_name is not None and r1_name.text == "Bischof Johann"
    r1_status = r1.find("mwg-rs:Description", namespaces)
    assert r1_status is not None and r1_status.text == "VERIFIED"
    r1_x = r1.find(".//stArea:x", namespaces)
    r1_y = r1.find(".//stArea:y", namespaces)
    r1_w = r1.find(".//stArea:w", namespaces)
    r1_h = r1.find(".//stArea:h", namespaces)
    assert float(r1_x.text) == pytest.approx(0.25, 0.001)
    assert float(r1_y.text) == pytest.approx(0.40, 0.001)
    assert float(r1_w.text) == pytest.approx(0.10, 0.001)
    assert float(r1_h.text) == pytest.approx(0.20, 0.001)

    # Bischof Johann should also be present in PersonInImage
    person_in_img = root.findall(".//Iptc4xmpExt:PersonInImage/rdf:Bag/rdf:li", namespaces)
    person_names = [p.text for p in person_in_img]
    assert "Bischof Johann" in person_names


def test_update_face_curation_status_endpoint():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.api.deps import get_qdrant_service

    mock_qdrant = MagicMock()
    mock_point = MagicMock()
    mock_point.id = "face-uuid-test"
    mock_point.payload = {
        "file_path": "/data/photos/test.jpg",
        "label": "Bischof Johann",
        "curation_status": "KI_AUTO",
    }
    mock_qdrant.client.scroll.return_value = ([mock_point], None)

    app.dependency_overrides[get_qdrant_service] = lambda: mock_qdrant
    client = TestClient(app)

    try:
        # 1. Successful update to VERIFIED
        resp = client.post(
            "/faces/face-uuid-test/curation-status",
            json={"status": "VERIFIED"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["curation_status"] == "VERIFIED"
        mock_qdrant.client.set_payload.assert_called_with(
            collection_name="archive_faces",
            payload={"curation_status": "VERIFIED"},
            points=["face-uuid-test"],
        )

        # 2. Reject invalid status
        resp_bad = client.post(
            "/faces/face-uuid-test/curation-status",
            json={"status": "UNKNOWN_STATUS"}
        )
        assert resp_bad.status_code == 400
    finally:
        app.dependency_overrides.clear()
