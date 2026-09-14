from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.catalog import router as catalog_router
from app.api.digitizer import router as digitizer_router
from app.api.health import router as health_router
from app.api.review import router as review_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(digitizer_router, prefix="/api/digitizer")
app.include_router(review_router, prefix="/api/digitizer")
app.include_router(catalog_router, prefix="/api/catalog")
