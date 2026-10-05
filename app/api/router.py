from fastapi import APIRouter
from app.api.routes import system, archive, iiif
from app.api.search import router as search_router
from app.api.network import router as network_router

api_router = APIRouter(prefix="/api")
api_router.include_router(system.router)
api_router.include_router(archive.router)
api_router.include_router(iiif.router)
api_router.include_router(search_router)
api_router.include_router(network_router)

