import pytest
from sqlalchemy import create_engine, inspect, text

from app.models import AppSettings
from app.services.migrate import add_missing_columns


def make_old_database(tmp_path):
    """Create an app_settings table that lacks the newer columns, with one real row."""
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE app_settings (id INTEGER PRIMARY KEY, first_name VARCHAR(100) NOT NULL, "
            "last_name VARCHAR(100) NOT NULL, theme VARCHAR(10) NOT NULL)"
        ))
        conn.execute(text("INSERT INTO app_settings VALUES (1, 'علی', 'رضایی', 'dark')"))
    return engine


def test_missing_columns_are_added_and_data_is_kept(tmp_path):
    engine = make_old_database(tmp_path)

    added = add_missing_columns(engine)

    assert "app_settings.currency" in added
    assert "app_settings.defaults_seeded" in added
    columns = {c["name"] for c in inspect(engine).get_columns("app_settings")}
    assert {"currency", "defaults_seeded"} <= columns

    with engine.connect() as conn:
        row = conn.execute(text("SELECT first_name, theme, currency, defaults_seeded FROM app_settings")).one()
    assert row == ("علی", "dark", "toman", 0)  # old data untouched, defaults applied


def test_orm_can_read_the_migrated_table(tmp_path):
    from sqlalchemy.orm import sessionmaker

    engine = make_old_database(tmp_path)
    add_missing_columns(engine)

    with sessionmaker(bind=engine)() as db:
        settings = db.get(AppSettings, 1)
        assert (settings.first_name, settings.currency, settings.defaults_seeded) == ("علی", "toman", False)


def test_second_run_changes_nothing(tmp_path):
    engine = make_old_database(tmp_path)
    assert add_missing_columns(engine)
    assert add_missing_columns(engine) == []


def test_fresh_database_needs_no_migration(session_factory):
    engine = session_factory.kw["bind"]
    assert add_missing_columns(engine) == []
