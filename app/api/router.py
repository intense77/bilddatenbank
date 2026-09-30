from fastapi import APIRouter
from app.api.routes import system
from app.api.search import router as search_router

api_router = APIRouter(prefix="/api")
api_router.include_router(system.router)
api_router.include_router(search_router)
