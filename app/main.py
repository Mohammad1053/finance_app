from fastapi import FastAPI

from app.database import Base, engine
from app import models  # noqa: F401
from app.routers import categories, payment_methods, transactions

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Personal Finance Manager")

app.include_router(categories.router)
app.include_router(payment_methods.router)
app.include_router(transactions.router)


@app.get("/")
def home():
    return {"message": "سلام! برنامه‌ی مدیریت مالی در حال اجراست"}
