"""
Hardware- und Ressourcen-Profiler für das Historische Bildarchiv.
Erkennt dynamisch CPU-Kerne, Arbeitsspeicher und GPU/VRAM und passt
Batch-Größen, Pipelining-Puffer und Schwellenwerte adaptiv an das Einsatzsystem an.
"""

import os
import io
import logging
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional
from PIL import Image

logger = logging.getLogger("archive_app.system_profile")


@dataclass
class HardwareProfile:
    tier: str  # "LOW", "MEDIUM", "HIGH"
    cpu_cores: int
    ram_gb: float
    gpu_available: bool
    gpu_name: str
    vram_gb: float
    # Adaptive Parameter:
    batch_size: int
    prefetch_queue_size: int
    max_downsample_dim: int
    max_image_pixels: int
    clustering_leaf_size: int
    clustering_chunk_size: int
    hnsw_indexing_threshold: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def detect_system_hardware() -> HardwareProfile:
    """
    Analysiert die Systemhardware und wählt das optimale Leistungsprofil.
    """
    # 1. CPU-Kerne ermitteln
    cpu_cores = os.cpu_count() or 2

    # 2. RAM ermitteln (zero-dependency über sysconf)
    try:
        ram_bytes = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        ram_gb = round(ram_bytes / (1024**3), 2)
    except Exception:
        ram_gb = 8.0

    # 3. GPU / VRAM ermitteln via PyTorch
    gpu_available = False
    gpu_name = "Keine dedizierte GPU (CPU-Modus)"
    vram_gb = 0.0

    try:
        import torch
        if torch.cuda.is_available():
            gpu_available = True
            gpu_name = torch.cuda.get_device_name(0)
            total_vram = torch.cuda.get_device_properties(0).total_memory
            vram_gb = round(total_vram / (1024**3), 2)
    except Exception as e:
        logger.debug("GPU-Erkennung nicht möglich: %s", e)

    # 4. Einstufung in Leistungsklassen (Tiers)
    if gpu_available and vram_gb >= 10.0 and ram_gb >= 24.0:
        # HIGH-END WORKSTATION / GPU-SERVER
        tier = "HIGH"
        batch_size = 100
        prefetch_queue_size = 8
        max_downsample_dim = 2000
        max_image_pixels = 500_000_000  # bis zu 500 Megapixel Großscans
        clustering_leaf_size = 50
        clustering_chunk_size = 60_000
        hnsw_indexing_threshold = 25000

    elif (gpu_available and vram_gb >= 3.5) or (cpu_cores >= 8 and ram_gb >= 15.0):
        # MID-RANGE / STANDARD-GPU ODER STARKER MULTICORE-SERVER
        tier = "MEDIUM"
        batch_size = 50
        prefetch_queue_size = 4
        max_downsample_dim = 1600
        max_image_pixels = 350_000_000  # bis zu 350 Megapixel
        clustering_leaf_size = 40
        clustering_chunk_size = 30_000
        hnsw_indexing_threshold = 20000

    else:
        # LOW-END / BÜRORECHNER OHNE GPU / ENGE SPEICHERGRENZEN
        tier = "LOW"
        batch_size = 20
        prefetch_queue_size = 2
        max_downsample_dim = 1400
        max_image_pixels = 250_000_000  # bis zu 250 Megapixel
        clustering_leaf_size = 30
        clustering_chunk_size = 15_000
        hnsw_indexing_threshold = 10000

    profile = HardwareProfile(
        tier=tier,
        cpu_cores=cpu_cores,
        ram_gb=ram_gb,
        gpu_available=gpu_available,
        gpu_name=gpu_name,
        vram_gb=vram_gb,
        batch_size=batch_size,
        prefetch_queue_size=prefetch_queue_size,
        max_downsample_dim=max_downsample_dim,
        max_image_pixels=max_image_pixels,
        clustering_leaf_size=clustering_leaf_size,
        clustering_chunk_size=clustering_chunk_size,
        hnsw_indexing_threshold=hnsw_indexing_threshold,
    )

    return profile


def apply_system_profile(profile: Optional[HardwareProfile] = None) -> HardwareProfile:
    """
    Aktiviert systemspezifische Schutzgrenzen (z. B. DecompressionBombError-Schutz in Pillow).
    """
    active = profile or detect_system_hardware()

    # Pillow DecompressionBomb-Schutz auf das hardwareangepasste Limit anheben
    Image.MAX_IMAGE_PIXELS = active.max_image_pixels

    logger.info(
        "Hardware-Profil aktiviert: Tier=%s | CPU=%d Kerne | RAM=%.1f GB | GPU=%s (%.1f GB VRAM) "
        "-> Batch=%d, Prefetch=%d, MaxPx=%d MP",
        active.tier,
        active.cpu_cores,
        active.ram_gb,
        active.gpu_name,
        active.vram_gb,
        active.batch_size,
        active.prefetch_queue_size,
        active.max_image_pixels // 1_000_000,
    )
    return active


def safe_normalize_image_to_rgb(img: Image.Image) -> Image.Image:
    """
    Normalisiert beliebige historische Bildformate (CMYK, 16-Bit Grayscale, Palette, LAB)
    farbgetreu und ohne Helligkeitsverfälschungen zu 8-Bit-RGB.
    Berücksichtigt eingebettete ICC-Profile bei CMYK-TIFFs.
    """
    if img.mode == "RGB":
        return img

    if img.mode == "CMYK":
        try:
            from PIL import ImageCms
            icc = img.info.get("icc_profile")
            if icc:
                input_profile = ImageCms.ImageCmsProfile(io.BytesIO(icc))
                srgb_profile = ImageCms.createProfile("sRGB")
                return ImageCms.profileToProfile(img, input_profile, srgb_profile, outputMode="RGB")
        except Exception:
            pass
        return img.convert("RGB")

    # 16-Bit Graustufen (I, I;16, I;16L, I;16B)
    if "16" in img.mode or img.mode == "I":
        try:
            import numpy as np
            arr = np.asarray(img)
            max_val = arr.max()
            if max_val > 255:
                scaled = (arr / (max_val / 255.0)).astype(np.uint8)
            else:
                scaled = arr.astype(np.uint8)
            return Image.fromarray(scaled).convert("RGB")
        except Exception:
            return img.convert("RGB")

    return img.convert("RGB")


# Initialer Erkennungslauf beim Modulstart
current_hardware_profile = apply_system_profile()
