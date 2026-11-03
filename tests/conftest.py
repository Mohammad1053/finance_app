from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import AppSettings, Category, PaymentMethod, TransactionType


@pytest.fixture()
def session_factory():
    """Create a fresh in-memory SQLite database for every test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # keep one shared connection so the memory DB survives
    )
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(bind=engine, autoflush=False)
    engine.dispose()


@pytest.fixture()
def db_session(session_factory):
    """A session the test itself can use to seed or inspect data."""
    session = session_factory()
    yield session
    session.close()


@pytest.fixture()
def client(session_factory):
    """A test client whose requests use the in-memory database."""

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # Not used as a context manager on purpose: the startup hook must not run
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def seed(db_session):
    """Create two payment methods and two categories; return their ids."""
    cash = PaymentMethod(name="نقد")
    card = PaymentMethod(name="کارت بانکی")
    food = Category(name="خوراک", type=TransactionType.EXPENSE)
    salary = Category(name="حقوق", type=TransactionType.INCOME)
    db_session.add_all([cash, card, food, salary])
    db_session.add(AppSettings(id=1, first_name="تست", last_name="کاربر"))
    db_session.commit()
    return SimpleNamespace(
        cash_id=cash.id,
        card_id=card.id,
        food_id=food.id,
        salary_id=salary.id,
    )
