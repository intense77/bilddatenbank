from typing import Optional, List
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
    QDRANT_PREFER_GRPC: bool = True
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

    # Automatisches Clustering Schwellenwert (Dank GPU PyTorch FP16 Chunking bis 500.000 Gesichter sicher)
    AUTO_CLUSTER_MAX_FACES: int = Field(
        default=500000,
        description="Maximale Gesichtsanzahl in der Datenbank, bis zu der nach einem Import automatisch geclustert wird. Dank GPU-Beschleunigung auf 500.000 angehoben."
    )

    # Datenverzeichnis für historische Bilder
    ARCHIVE_DATA_DIR: str = "./data"
    ALLOWED_IMAGE_DIRS: list[str] = ["./data"]
    THUMBNAIL_CACHE_DIR: str = "./.cache/thumbnails"
    MAX_THUMBNAIL_CACHE_MB: int = Field(
        default=5000,
        description="Maximale Größe des Thumbnail-Caches in Megabyte (Standard: 5.000 MB = 5 GB). Bei Überschreitung greift automatische LRU-Bereinigung."
    )

    # Server-Binding & Netzwerksicherheit (127.0.0.1 schützt vor unberechtigtem LAN-Zugriff)
    SERVER_HOST: str = Field(default="127.0.0.1", description="Netzwerk-Binding (127.0.0.1 für lokale Datensicherheit, 0.0.0.0 für LAN)")
    SERVER_PORT: int = Field(default=8000, description="Server-Port")

    # Sicherheit & CORS
    CORS_ORIGINS: list[str] = ["http://localhost:8000", "http://127.0.0.1:8000"]

    # KDG-konforme Authentifizierung & Rollenverwaltung (RBAC)
    AUTH_ENABLED: bool = Field(default=True, description="Aktiviert die rollenbasierte Zugriffskontrolle (RBAC)")
    AUTH_SECRET_KEY: str = Field(default="historisches-archiv-geheimer-schluessel-2026", description="Geheimschlüssel für Sessions/Tokens")
    AUTH_SESSION_EXPIRE_HOURS: int = Field(default=24, description="Gültigkeitsdauer einer Session in Stunden")
    AUTH_LESESAAL_ANONYMOUS: bool = Field(
        default=True,
        description="Erlaubt unauthentifizierten Nutzern den Lesesaal-Modus (Viewer). Bei False ist vor der Recherche ein Login nötig."
    )
    AUTH_DEFAULT_ADMIN_USER: str = Field(default="admin", description="Standard-Admin-Benutzername")
    AUTH_DEFAULT_ADMIN_PASSWORD: str = Field(default="archivadmin2026", description="Standard-Admin-Passwort für Initial-Seeding")
    AUTH_DEFAULT_CURATOR_USER: str = Field(default="archivar", description="Standard-Kurator-Benutzername")
    AUTH_DEFAULT_CURATOR_PASSWORD: str = Field(default="kurator2026", description="Standard-Kurator-Passwort")
    AUTH_DEFAULT_VIEWER_USER: str = Field(default="lesesaal", description="Standard-Lesesaal-Benutzername")
    AUTH_DEFAULT_VIEWER_PASSWORD: str = Field(default="lesesaal2026", description="Standard-Lesesaal-Passwort")

    # Lokale Texterkennung & Handschriften-KI (OCR / HTR für Rückseiten, Stempel, Kurrent & Fraktur)
    OCR_ENABLED: bool = Field(default=True, description="Aktiviert die lokale OCR-Pipeline (Tesseract 5)")
    OCR_LANGUAGES: str = Field(default="deu+deu_latf+eng", description="Tesseract-Sprachmodelle (z. B. deu, deu+deu_latf+eng)")
    OCR_TESSERACT_CMD: str = Field(default="tesseract", description="Pfad zur Tesseract-Binärdatei")
    OCR_TESSDATA_DIR: Optional[str] = Field(
        default="./data/tessdata",
        description="Verzeichnis für historische Sprachmodelle (z. B. Fraktur, Kurrent). Fallback auf Systempfad."
    )
    OCR_DEFAULT_PROFILE: str = Field(
        default="auto",
        description="Standard-Erkennungsprofil ('auto', 'handwritten', 'printed', 'fraktur')"
    )
    OCR_AUTO_VERSO: bool = Field(
        default=True,
        description="Führt beim Indexieren von Rückseiten (_v, _verso) automatisch OCR durch und verknüpft das Ergebnis mit dem Vorderseiten-Foto"
    )

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
