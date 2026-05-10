from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from scalar_fastapi import get_scalar_api_reference
from starlette.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings
from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
from app.modules.users.model import models
from app.modules.users.service.user_service import ensure_service_manager_exists


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        await ensure_service_manager_exists(session)

    yield


MEDIA_DIR = Path('media')
AVATARS_DIR = MEDIA_DIR / 'avatars'

MEDIA_DIR.mkdir(exist_ok=True)
AVATARS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title=settings.app_title,
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")
app.include_router(api_router, prefix="/api")


@app.get("/docs", include_in_schema=False)
async def scalar_docs():
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title=settings.app_title,
    )


@app.get("/health")
async def health_check():
    return {"status": "ok"}