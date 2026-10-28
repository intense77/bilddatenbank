import os
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.system_profile import check_image_memory_guard, HardwareProfile
from app.services.thumbnail_service import ThumbnailService
from app.main import app


def test_thumbnail_cache_lru_pruning(tmp_path):
    """Testet, dass der ThumbnailService bei Überschreiten des Limits älteste WebP-Dateien sauber bereinigt."""
    cache_dir = tmp_path / "thumb_cache_test"
    cache_dir.mkdir()

    # Erzeuge 5 Test-Cache-Dateien mit jeweils 1 MB (Gesamt: ~5 MB)
    one_mb = b"X" * (1024 * 1024)
    file_paths = []
    for i in range(5):
        f = cache_dir / f"thumb_test_{i}.webp"
        f.write_bytes(one_mb)
        # Künstliche Zeitabstände für deterministisches LRU
        mtime = time.time() - (500 - i * 100)
        os.utime(f, (mtime, mtime))
        file_paths.append(f)

    # Initialisiere Service mit Limit 3 MB
    service = ThumbnailService(cache_dir=cache_dir, max_cache_mb=3)
    stats = service.get_cache_stats()

    assert stats["total_files"] == 5
    assert stats["total_mb"] >= 5.0
    assert stats["limit_exceeded"] is True

    # 1. LRU-Bereinigung durchführen (Ziel: 80% von 3 MB = 2.4 MB -> sollte 3 älteste Dateien löschen)
    prune_res = service.prune_lru()
    assert prune_res["status"] == "pruned"
    assert prune_res["pruned_count"] >= 3
    assert prune_res["freed_mb"] >= 3.0

    # Die ältesten Dateien (0, 1, 2) müssen weg sein, die neuesten (3, 4) bleiben
    assert not file_paths[0].exists()
    assert not file_paths[1].exists()
    assert file_paths[4].exists()

    # Cache-Status nach Bereinigung
    new_stats = service.get_cache_stats()
    assert new_stats["limit_exceeded"] is False
    assert new_stats["total_mb"] <= 3.0


def test_thumbnail_touch_file_preserves_active_files(tmp_path):
    """Testet, dass _touch_file die Zugriffszeit aktualisiert und so das Löschen aktiver Dateien verhindert."""
    cache_dir = tmp_path / "thumb_cache_touch"
    cache_dir.mkdir()

    one_mb = b"Y" * (1024 * 1024)
    old_file = cache_dir / "thumb_old.webp"
    active_file = cache_dir / "thumb_active.webp"

    old_file.write_bytes(one_mb)
    active_file.write_bytes(one_mb)

    past = time.time() - 1000
    os.utime(old_file, (past, past))
    os.utime(active_file, (past, past))

    service = ThumbnailService(cache_dir=cache_dir, max_cache_mb=1)

    # Nun active_file berühren (Cache-Hit simuliert)
    service._touch_file(active_file)

    # Bereinigung auf 1 MB -> nur old_file darf gelöscht werden
    res = service.prune_lru(target_mb=1, force=True)
    assert res["status"] == "pruned"
    assert not old_file.exists()
    assert active_file.exists()


def test_memory_guard_rejection():
    """Testet, dass check_image_memory_guard Scans abweist, die das Hardware-Limit überschreiten."""
    # Test-Hardware-Profil mit 50 MP Limit
    dummy_profile = HardwareProfile(
        tier="LOW",
        cpu_cores=2,
        ram_gb=4.0,
        gpu_available=False,
        gpu_name="None",
        vram_gb=0.0,
        batch_size=10,
        prefetch_queue_size=1,
        max_downsample_dim=1000,
        max_image_pixels=50_000_000,  # 50 MP
        clustering_leaf_size=20,
        clustering_chunk_size=5000,
        hnsw_indexing_threshold=5000,
    )

    # 40 MP Bild: Erlaubt
    assert check_image_memory_guard(width=8000, height=5000, profile=dummy_profile) is True

    # 100 MP Bild (z. B. 10.000 x 10.000): Abgewiesen zum Schutz vor RAM-OOM
    assert check_image_memory_guard(width=10000, height=10000, profile=dummy_profile) is False


def test_thumbnail_cache_api_endpoints():
    """Testet die REST-Endpunkte für Thumbnail-Cache Stats und Pruning."""
    client = TestClient(app)
    client.headers["Authorization"] = "Basic YWRtaW46YXJjaGl2YWRtaW4yMDI2"

    # 1. Stats
    res_stats = client.get("/api/system/thumbnail-cache/stats")
    assert res_stats.status_code == 200
    stats_data = res_stats.json()
    assert "total_files" in stats_data
    assert "total_mb" in stats_data
    assert "max_cache_mb" in stats_data

    # 2. Prune (ohne force, wenn unter Limit sollte status ok sein)
    res_prune = client.post("/api/system/thumbnail-cache/prune")
    assert res_prune.status_code == 200
    prune_data = res_prune.json()
    assert "status" in prune_data
