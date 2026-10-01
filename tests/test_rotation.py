import shutil
from pathlib import Path
from PIL import Image
from app.services.image_rotation_service import ImageRotationService
from app.services.thumbnail_service import ThumbnailService


class MockIndexingService:
    def reindex_single_image(self, file_path):
        return True, 0


def test_jpeg_rotation():
    thumb_svc = ThumbnailService(cache_dir=Path("/tmp/test_thumb_cache"))
    indexing_svc = MockIndexingService()
    rot_svc = ImageRotationService(indexing_service=indexing_svc, thumbnail_service_instance=thumb_svc)

    test_file = Path("/tmp/test_rot_unit.jpg")
    try:
        # Create 100x200 portrait image
        img = Image.new("RGB", (100, 200), color=(120, 180, 240))
        img.save(test_file, quality=95)

        # 1. Rotate 90 deg clockwise
        res90 = rot_svc.rotate_image(test_file, angle=90)
        assert res90["success"] is True
        assert res90["width"] == 200
        assert res90["height"] == 100
        assert "lossless" in res90["rotation_method"]

        with Image.open(test_file) as r90:
            assert r90.size == (200, 100)

        # 2. Rotate -90 deg (270 deg CW) -> back to 100x200
        res_back = rot_svc.rotate_image(test_file, angle=-90)
        assert res_back["success"] is True
        assert res_back["width"] == 100
        assert res_back["height"] == 200

        with Image.open(test_file) as r_back:
            assert r_back.size == (100, 200)

        print("✓ JPEG lossless rotation test passed successfully!")

    finally:
        test_file.unlink(missing_ok=True)


def test_png_rotation():
    thumb_svc = ThumbnailService(cache_dir=Path("/tmp/test_thumb_cache"))
    indexing_svc = MockIndexingService()
    rot_svc = ImageRotationService(indexing_service=indexing_svc, thumbnail_service_instance=thumb_svc)

    test_file = Path("/tmp/test_rot_unit.png")
    try:
        img = Image.new("RGB", (150, 300), color=(200, 100, 50))
        img.save(test_file, format="PNG")

        res90 = rot_svc.rotate_image(test_file, angle=90)
        assert res90["success"] is True
        assert res90["width"] == 300
        assert res90["height"] == 150
        assert res90["rotation_method"] == "lossless_png"

        print("✓ PNG lossless rotation test passed successfully!")
    finally:
        test_file.unlink(missing_ok=True)


if __name__ == "__main__":
    test_jpeg_rotation()
    test_png_rotation()
    print("All unit tests passed!")
