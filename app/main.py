import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.router import api_router
from app.api.deps import get_qdrant_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("archive_app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle-Management: Initialisiert Qdrant-Collections beim Start."""
    logger.info("Starte Anwendung '%s' (v%s)...", settings.PROJECT_NAME, settings.VERSION)
    qdrant = get_qdrant_service()
    if qdrant.check_health():
        logger.info("Verbindung zu Qdrant erfolgreich. Initialisiere Collections...")
        qdrant.init_collections()
    else:
        logger.warning(
            "Qdrant ist unter %s:%d noch nicht erreichbar. "
            "Stellen Sie sicher, dass 'docker compose up -d' ausgeführt wurde.",
            settings.QDRANT_HOST,
            settings.QDRANT_PORT,
        )
    yield
    logger.info("Fahre Anwendung herunter...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Datensparsames, lokales Bildarchiv-Suchsystem mit OpenCLIP und InsightFace/ArcFace.",
    lifespan=lifespan,
)

# CORS Middleware (konfigurierbar)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import os
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from app.api.search import router as search_router

app.include_router(api_router)
app.include_router(search_router)


@app.get("/api")
def api_info():
    """Gibt Metadaten und Status der API zurück."""
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs_url": "/docs",
        "health_url": "/api/system/health",
        "collections": [settings.COLLECTION_IMAGES, settings.COLLECTION_FACES],
    }


# Statisches Frontend unter / bereitstellen
static_path = Path(__file__).resolve().parent.parent / "static"
static_path.mkdir(exist_ok=True)
app.mount("/", StaticFiles(directory=str(static_path), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
