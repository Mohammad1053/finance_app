import os
import tempfile
from types import SimpleNamespace

# The app creates tables at import time; point it at a throw-away file, never at finance.db
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "import-time.db")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Category, PaymentMethod, TransactionType, User  # noqa: E402
from app.services import auth  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_login_throttle():
    """Failed-login counters must not leak between tests."""
    auth.throttle.clear()
    yield


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
    """An anonymous test client whose requests use the in-memory database."""

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
def seed(db_session, client):
    """Create a user with two payment methods and two categories, and sign the client in."""
    user = User(
        username="tester",
        first_name="تست",
        last_name="کاربر",
        password_hash=auth.hash_password("secret123"),
        session_secret=auth.new_secret(),
        defaults_seeded=True,
    )
    db_session.add(user)
    db_session.flush()

    cash = PaymentMethod(user_id=user.id, name="نقد")
    card = PaymentMethod(user_id=user.id, name="کارت بانکی")
    food = Category(user_id=user.id, name="خوراک", type=TransactionType.EXPENSE)
    salary = Category(user_id=user.id, name="حقوق", type=TransactionType.INCOME)
    db_session.add_all([cash, card, food, salary])
    db_session.commit()

    client.cookies.set(auth.COOKIE_NAME, auth.session_token(user), domain="testserver")
    return SimpleNamespace(
        user_id=user.id,
        cash_id=cash.id,
        card_id=card.id,
        food_id=food.id,
        salary_id=salary.id,
    )
