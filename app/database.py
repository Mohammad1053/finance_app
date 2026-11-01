import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# The database location can be overridden with the DATABASE_URL environment variable
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./finance.db")

engine = create_engine(
    DATABASE_URL,
    # needed for SQLite with FastAPI
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    """Base class for all models."""


def get_db():
    """Yield a session and always close it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
