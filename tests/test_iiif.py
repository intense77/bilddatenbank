import io
import shutil
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient

from app.main import app
from app.services.iiif_service import IIIFService

client = TestClient(app)


def test_iiif_service_and_endpoints(tmp_path: Path):
    test_cache_dir = tmp_path / "iiif_cache"
    iiif_svc = IIIFService(cache_dir=test_cache_dir)

    # 1. Testbild anlegen (1200 x 800) in einem erlaubten Testverzeichnis
    test_img_path = Path("data/test_iiif_sample.jpg")
    test_img_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (1200, 800), color=(180, 140, 100))
    img.save(test_img_path, format="JPEG")

    try:
        # 2. Identifier kodieren und auflösen
        identifier = iiif_svc.encode_identifier(test_img_path)
        resolved = iiif_svc.resolve_identifier(identifier)
        assert resolved.resolve() == test_img_path.resolve()

        # 3. info.json testen
        info = iiif_svc.get_image_info(identifier, base_url="http://testserver")
        assert info["width"] == 1200
        assert info["height"] == 800
        assert info["type"] == "ImageService3"
        assert len(info["tiles"]) > 0
        assert info["tiles"][0]["width"] == 512
        assert 1 in info["tiles"][0]["scaleFactors"]
        assert len(info["sizes"]) > 0

        # 4. Kacheln rendern (verschiedene Regionen, Größen, Formate)
        # a) Full, Max, WebP
        tile_bytes, mtype = iiif_svc.render_tile(
            identifier=identifier,
            region="full",
            size="max",
            rotation="0",
            quality="default",
            fmt="webp",
        )
        assert mtype == "image/webp"
        with Image.open(io.BytesIO(tile_bytes)) as r_img:
            assert r_img.size == (1200, 800)

        # b) Bounding Box Kachel 0,0,512,512 skaliert auf 256,256
        tile_bytes_crop, _ = iiif_svc.render_tile(
            identifier=identifier,
            region="0,0,512,512",
            size="256,256",
            rotation="0",
            quality="default",
            fmt="jpg",
        )
        with Image.open(io.BytesIO(tile_bytes_crop)) as r_crop:
            assert r_crop.size == (256, 256)

        # c) Square Region & Rotation 90 & Gray
        tile_rot, _ = iiif_svc.render_tile(
            identifier=identifier,
            region="square",
            size="200,200",
            rotation="90",
            quality="gray",
            fmt="png",
        )
        with Image.open(io.BytesIO(tile_rot)) as r_rot:
            assert r_rot.size == (200, 200)
            assert r_rot.mode == "L"

        # 5. HTTP Endpoints testen via TestClient
        resp_info = client.get(f"/api/iiif/{identifier}/info.json")
        assert resp_info.status_code == 200
        data = resp_info.json()
        assert data["width"] == 1200
        assert data["height"] == 800

        # Tile endpoint
        resp_tile = client.get(f"/api/iiif/{identifier}/0,0,512,512/512,/0/default.webp")
        assert resp_tile.status_code == 200
        assert resp_tile.headers["content-type"] == "image/webp"
        assert len(resp_tile.content) > 0

        # Redirect endpoint
        resp_red = client.get(f"/api/iiif/{identifier}", follow_redirects=False)
        assert resp_red.status_code == 303

    finally:
        test_img_path.unlink(missing_ok=True)
