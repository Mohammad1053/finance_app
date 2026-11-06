from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import Base, SessionLocal, engine
from app import models  # noqa: F401
from app.routers import (
    appearance,
    categories,
    data_io,
    goals,
    pages,
    payment_methods,
    pwa,
    recurring,
    reports,
    settings,
    transactions,
)
from app.services.recurring import generate_due

from app.deps import require_login


Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create due recurring transactions every time the app starts."""
    with SessionLocal() as db:
        generate_due(db)
    yield


app = FastAPI(
    title="Personal Finance Manager",
    lifespan=lifespan,
    dependencies=[Depends(require_login)],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(pages.router)
app.include_router(settings.router)
app.include_router(reports.router)
app.include_router(goals.router)
app.include_router(recurring.router)
app.include_router(categories.router)
app.include_router(payment_methods.router)
app.include_router(transactions.router)
app.include_router(data_io.router)
app.include_router(appearance.router)
app.include_router(pwa.router)
