from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import models  # noqa: F401
from app.database import Base, SessionLocal, engine
from app.routers import (
    appearance,
    data_io,
    goals,
    pages,
    pwa,
    recurring,
    reports,
    settings,
)
from app.services.migrate import add_missing_columns, migrate_legacy_single_user
from app.services.recurring import generate_due

# Order matters: convert an old single-user database first, then create and extend tables
migrate_legacy_single_user(engine)
Base.metadata.create_all(bind=engine)
add_missing_columns(engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create due recurring transactions for every user at startup."""
    with SessionLocal() as db:
        generate_due(db)
    yield


# The interactive API docs are disabled: the UI is the only public interface
app = FastAPI(
    title="Hesabdar-e Man",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(appearance.router)
app.include_router(pages.router)
app.include_router(settings.router)
app.include_router(reports.router)
app.include_router(goals.router)
app.include_router(recurring.router)
app.include_router(data_io.router)
app.include_router(pwa.router)
