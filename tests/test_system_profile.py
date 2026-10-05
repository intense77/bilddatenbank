import numpy as np
from PIL import Image
from fastapi.testclient import TestClient

from app.main import app
from app.core.system_profile import (
    detect_system_hardware,
    apply_system_profile,
    safe_normalize_image_to_rgb,
    HardwareProfile,
)

client = TestClient(app)


def test_hardware_profile_detection():
    profile = detect_system_hardware()
    assert isinstance(profile, HardwareProfile)
    assert profile.cpu_cores >= 1
    assert profile.ram_gb > 0
    assert profile.tier in ["LOW", "MEDIUM", "HIGH"]
    assert profile.batch_size in [20, 50, 100]
    assert profile.prefetch_queue_size in [2, 4, 8]
    assert profile.max_image_pixels >= 200_000_000

    # Test apply_system_profile
    active = apply_system_profile(profile)
    assert Image.MAX_IMAGE_PIXELS == profile.max_image_pixels


def test_safe_normalize_image_to_rgb():
    # 1. RGB Bild unverändert
    rgb_img = Image.new("RGB", (100, 100), color=(10, 20, 30))
    res_rgb = safe_normalize_image_to_rgb(rgb_img)
    assert res_rgb.mode == "RGB"
    assert res_rgb.size == (100, 100)

    # 2. CMYK Bild sauber konvertiert
    cmyk_img = Image.new("CMYK", (80, 80), color=(50, 100, 150, 20))
    res_cmyk = safe_normalize_image_to_rgb(cmyk_img)
    assert res_cmyk.mode == "RGB"
    assert res_cmyk.size == (80, 80)

    # 3. 16-Bit Graustufen Bild (Modus 'I')
    raw_16 = np.random.randint(0, 65535, (50, 50), dtype=np.uint32)
    i_img = Image.fromarray(raw_16, mode="I")
    res_16 = safe_normalize_image_to_rgb(i_img)
    assert res_16.mode == "RGB"
    assert res_16.size == (50, 50)


def test_health_endpoint_hardware_profile():
    resp = client.get("/api/system/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "hardware_profile" in data
    hw = data["hardware_profile"]
    assert "tier" in hw
    assert "batch_size" in hw
    assert "prefetch_queue_size" in hw
    assert "cpu_cores" in hw
    assert "ram_gb" in hw
