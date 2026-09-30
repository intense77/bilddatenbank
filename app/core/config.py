from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Anwendungs- und Umgebungskonfiguration."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    PROJECT_NAME: str = "Historisches Bildarchiv Suchsystem"
    VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Qdrant Vektordatenbank
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_GRPC_PORT: int = 6334
    QDRANT_PREFER_GRPC: bool = False
    QDRANT_HTTPS: bool = False
    QDRANT_API_KEY: str | None = None

    # Collections (beide 512-dimensional, Cosine Distance)
    COLLECTION_IMAGES: str = "archive_images"
    COLLECTION_FACES: str = "archive_faces"

    # Vektordimensionen
    CLIP_VECTOR_SIZE: int = 512
    FACE_VECTOR_SIZE: int = 512

    # Hardware Beschleunigung
    DEVICE: str = Field(default="cuda", description="cuda oder cpu")

    # OpenCLIP Konfiguration
    CLIP_MODEL_NAME: str = "ViT-B-32"
    CLIP_PRETRAINED: str = "laion2b_s34b_b79k"

    # Biometrie & Gesichtserkennung (Opt-in nach Art. 9 DSGVO)
    ENABLE_FACE_RECOGNITION: bool = Field(
        default=False,
        description="Aktiviert die biometrische Gesichtserkennung (Opt-in, standardmäßig deaktiviert zur Datensparsamkeit)."
    )

    # InsightFace Konfiguration (wird nur geladen, wenn ENABLE_FACE_RECOGNITION=True)
    INSIGHTFACE_MODEL_NAME: str = "buffalo_l"
    INSIGHTFACE_DET_SIZE: int = 640

    # Datenverzeichnis für historische Bilder
    ARCHIVE_DATA_DIR: str = "./data"
    ALLOWED_IMAGE_DIRS: list[str] = ["./data", "."]
    THUMBNAIL_CACHE_DIR: str = "./.cache/thumbnails"

    # Sicherheit & CORS
    CORS_ORIGINS: list[str] = ["http://localhost:8000", "http://127.0.0.1:8000"]

    @property
    def effective_device(self) -> str:
        """Gibt das tatsächlich verfügbare Device zurück (Fallback auf CPU, falls CUDA nicht verfügbar)."""
        if self.DEVICE.lower().startswith("cuda"):
            try:
                import torch
                if torch.cuda.is_available():
                    return "cuda"
            except ImportError:
                pass
        return "cpu"


settings = Settings()
