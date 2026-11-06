from app.models import AppSettings, Category, PaymentMethod
from app.services.defaults import seed_defaults


def test_empty_database_gets_defaults_once(db_session):
    assert seed_defaults(db_session) is True
    assert db_session.query(Category).count() == 13
    assert db_session.query(PaymentMethod).count() == 3

    # A second run must not add anything, even after the user deletes everything
    db_session.query(Category).delete()
    db_session.query(PaymentMethod).delete()
    db_session.commit()
    assert seed_defaults(db_session) is False
    assert db_session.query(Category).count() == 0


def test_existing_user_data_is_never_touched(db_session, seed):
    before = (db_session.query(Category).count(), db_session.query(PaymentMethod).count())
    assert seed_defaults(db_session) is False
    after = (db_session.query(Category).count(), db_session.query(PaymentMethod).count())
    assert before == after
    assert db_session.query(AppSettings).one().defaults_seeded is True
