from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = "sqlite:///./finance.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # لازم برای SQLite در FastAPI
)

SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    """پایه‌ی همه‌ی مدل‌ها"""
    pass


def get_db():
    """یک session می‌سازه و بعد از تموم شدن کار می‌بنده"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
