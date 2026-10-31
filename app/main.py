from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app import models  # noqa: F401
from app.routers import categories, pages, payment_methods, reports, settings, transactions
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Personal Finance Manager")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(pages.router)
app.include_router(settings.router)
app.include_router(reports.router)
app.include_router(categories.router)
app.include_router(payment_methods.router)
app.include_router(transactions.router)
