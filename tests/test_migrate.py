import datetime as dt

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.models import Category, Transaction, User
from app.services.auth import verify_password
from app.services.migrate import add_missing_columns, migrate_legacy_single_user


# ---------- add_missing_columns ----------
def make_old_users_table(tmp_path):
    """A users table that lacks the newer columns, with one real row."""
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(50) NOT NULL, "
            "first_name VARCHAR(100) NOT NULL, last_name VARCHAR(100) NOT NULL, "
            "password_hash VARCHAR(300) NOT NULL, session_secret VARCHAR(100) NOT NULL, "
            "theme VARCHAR(10) NOT NULL)"
        ))
        conn.execute(text("INSERT INTO users VALUES (1, 'ali', 'علی', 'رضایی', 'h', 's', 'dark')"))
    return engine


def test_missing_columns_are_added_and_data_is_kept(tmp_path):
    engine = make_old_users_table(tmp_path)
    added = add_missing_columns(engine)

    assert "users.currency" in added and "users.defaults_seeded" in added
    columns = {c["name"] for c in inspect(engine).get_columns("users")}
    assert {"currency", "defaults_seeded"} <= columns

    with engine.connect() as conn:
        row = conn.execute(text("SELECT first_name, theme, currency, defaults_seeded FROM users")).one()
    assert row == ("علی", "dark", "toman", 0)


def test_second_run_changes_nothing(tmp_path):
    engine = make_old_users_table(tmp_path)
    assert add_missing_columns(engine)
    assert add_missing_columns(engine) == []


def test_fresh_database_needs_no_column_migration(session_factory):
    assert add_missing_columns(session_factory.kw["bind"]) == []


# ---------- single-user -> multi-user ----------
def make_legacy_database(tmp_path):
    """The old single-user schema with a little data, as the first version of the app made it."""
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    statements = [
        "CREATE TABLE payment_methods (id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL UNIQUE)",
        "CREATE TABLE categories (id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL UNIQUE, type VARCHAR(7) NOT NULL)",
        "CREATE TABLE transactions (id INTEGER PRIMARY KEY, amount INTEGER NOT NULL, date DATE NOT NULL, "
        "description VARCHAR(255) NOT NULL, payment_method_id INTEGER NOT NULL, category_id INTEGER NOT NULL)",
        "CREATE TABLE app_settings (id INTEGER PRIMARY KEY, first_name VARCHAR(100), last_name VARCHAR(100), "
        "theme VARCHAR(10), currency VARCHAR(10), defaults_seeded BOOLEAN)",
        "CREATE TABLE auth_settings (id INTEGER PRIMARY KEY, password_hash VARCHAR(300), secret VARCHAR(100))",
        "INSERT INTO payment_methods VALUES (1, 'نقد')",
        "INSERT INTO categories VALUES (1, 'خوراک', 'EXPENSE')",
        "INSERT INTO transactions VALUES (1, 350000, '2026-10-25', 'خرید', 1, 1)",
        "INSERT INTO app_settings VALUES (1, 'علی', 'رضایی', 'dark', 'toman', 1)",
    ]
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
    return engine


def test_legacy_data_moves_to_the_owner_account(tmp_path, monkeypatch):
    monkeypatch.setenv("LEGACY_OWNER_PASSWORD", "owner-pass-1")
    engine = make_legacy_database(tmp_path)

    assert migrate_legacy_single_user(engine) is True

    with sessionmaker(bind=engine)() as db:
        owner = db.query(User).one()
        assert (owner.username, owner.first_name, owner.theme) == ("owner", "علی", "dark")
        assert verify_password("owner-pass-1", owner.password_hash)

        tx = db.query(Transaction).one()
        assert (tx.user_id, tx.amount, tx.category.name) == (owner.id, 350000, "خوراک")
        assert tx.date == dt.date(2026, 10, 25)
    assert (tmp_path / "legacy.db.pre-multiuser.bak").exists()  # backup was made first


def test_migration_runs_only_once(tmp_path, monkeypatch):
    monkeypatch.setenv("LEGACY_OWNER_PASSWORD", "owner-pass-1")
    engine = make_legacy_database(tmp_path)
    assert migrate_legacy_single_user(engine) is True
    assert migrate_legacy_single_user(engine) is False


def test_fresh_database_is_not_migrated(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'empty.db'}")
    assert migrate_legacy_single_user(engine) is False


def test_names_are_unique_per_user_only(db_session):
    first, second = User(username="a"), User(username="b")
    db_session.add_all([first, second])
    db_session.commit()

    db_session.add_all([Category(user_id=first.id, name="x", type="INCOME"), Category(user_id=second.id, name="x", type="INCOME")])
    db_session.commit()  # same name for two different users is fine

    db_session.add(Category(user_id=first.id, name="x", type="INCOME"))
    with pytest.raises(IntegrityError):
        db_session.commit()
