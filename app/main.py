from fastapi import FastAPI

from app.database import Base, engine
from app import models  # noqa: F401  (لازمه تا مدل‌ها شناخته بشن)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Personal Finance Manager")


@app.get("/")
def home():
    return {"message": "سلام! برنامه‌ی مدیریت مالی در حال اجراست"}
