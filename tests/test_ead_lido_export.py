import pytest
import xml.etree.ElementTree as ET
from fastapi.testclient import TestClient
from app.main import app
from app.services.ead_lido_service import ead_lido_service


@pytest.fixture
def sample_items():
    return [
        {
            "file_path": "/data/scans/bischof_mueller_1932.jpg",
            "file_name": "bischof_mueller_1932.jpg",
            "title": "Bischof Müller bei der Grundsteinlegung",
            "date": "1932-06-15",
            "creator": "Atelier Hoffmann, Augsburg",
            "signature": "DAA-FOTO-1932-042",
            "persons": ["Bischof Müller", "Domkapitular Weber"],
            "notes": "Rückseitige Bleistiftnotiz: 'Feierliche Einweihung bei strahlendem Sonnenschein.'",
        },
        {
            "file_path": "/data/scans/altar_monstranz.jpg",
            "file_name": "altar_monstranz.jpg",
            "title": "Barocke Sonnenmonstranz auf Hochaltar",
            "date": "ca. 1910",
            "creator": "Unbekannt",
            "signature": "DAA-KUNST-089",
            "persons": [],
            "notes": "Silber vergoldet mit Edelsteinbesatz.",
        },
    ]


def test_ead3_generation(sample_items):
    """Prüft, dass valides EAD3-XML nach ISAD(G) erzeugt wird."""
    xml_bytes = ead_lido_service.generate_ead3(
        items=sample_items,
        archive_name="Bistumsarchiv Augsburg",
        collection_title="Ausstellung 2026",
    )
    assert xml_bytes.startswith(b"<?xml")
    assert b"<ead" in xml_bytes
    assert b"xmlns=\"http://ead3.archivists.org/schema/\"" in xml_bytes

    # XML-Parsing zur Validierung
    root = ET.fromstring(xml_bytes)
    assert "ead" in root.tag

    # Prüfe did und Verzeichnungseinheiten
    xml_str = xml_bytes.decode("utf-8")
    assert "Bischof Müller bei der Grundsteinlegung" in xml_str
    assert "DAA-FOTO-1932-042" in xml_str
    assert "Bistumsarchiv Augsburg" in xml_str
    assert "Bischof Müller" in xml_str
    assert "Feierliche Einweihung" in xml_str


def test_lido_generation(sample_items):
    """Prüft, dass valides LIDO 1.1 XML für DDB & Europeana erzeugt wird."""
    xml_bytes = ead_lido_service.generate_lido(
        items=sample_items,
        archive_name="Diözesanmuseum St. Afra",
        collection_title="Sakrale Schätze",
    )
    assert xml_bytes.startswith(b"<?xml")
    assert b"lidoWrap" in xml_bytes
    assert b"xmlns:lido=\"http://www.lido-schema.org\"" in xml_bytes

    # XML-Parsing zur Validierung
    root = ET.fromstring(xml_bytes)
    assert "lidoWrap" in root.tag

    xml_str = xml_bytes.decode("utf-8")
    assert "Barocke Sonnenmonstranz auf Hochaltar" in xml_str
    assert "DAA-KUNST-089" in xml_str
    assert "Diözesanmuseum St. Afra" in xml_str
    assert "Atelier Hoffmann, Augsburg" in xml_str


def test_ead_and_lido_api_endpoints(sample_items):
    """Testet die HTTP-Endpunkte /export/ead-xml und /export/lido-xml."""
    client = TestClient(app)

    payload = {
        "items": sample_items,
        "archive_name": "Archiv der Diözese",
        "collection_title": "Historischer Leuchttisch",
    }

    # 1. EAD3
    res_ead = client.post("/export/ead-xml", json=payload)
    assert res_ead.status_code == 200
    assert "application/xml" in res_ead.headers["content-type"]
    assert "attachment; filename=\"EAD3_" in res_ead.headers["content-disposition"]
    assert b"http://ead3.archivists.org/schema/" in res_ead.content

    # 2. LIDO
    res_lido = client.post("/export/lido-xml", json=payload)
    assert res_lido.status_code == 200
    assert "application/xml" in res_lido.headers["content-type"]
    assert "attachment; filename=\"LIDO_" in res_lido.headers["content-disposition"]
    assert b"http://www.lido-schema.org" in res_lido.content
