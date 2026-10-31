from fastapi import FastAPI

app = FastAPI(title="Personal Finance Manager")


@app.get("/")
def home():
    return {"message": "سلام! برنامه‌ی مدیریت مالی در حال اجراست"}