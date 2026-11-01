from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import Base, SessionLocal, engine
from app import models  # noqa: F401
from app.routers import (
    categories,
    goals,
    pages,
    payment_methods,
    recurring,
    reports,
    settings,
    transactions,
)
from app.services.recurring import generate_due

Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create due recurring transactions every time the app starts."""
    with SessionLocal() as db:
        generate_due(db)
    yield


app = FastAPI(title="Personal Finance Manager", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(pages.router)
app.include_router(settings.router)
app.include_router(reports.router)
app.include_router(goals.router)
app.include_router(recurring.router)
app.include_router(categories.router)
app.include_router(payment_methods.router)
app.include_router(transactions.router)
