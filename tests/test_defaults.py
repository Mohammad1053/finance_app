from app.models import Category, PaymentMethod, User
from app.services.defaults import seed_defaults


def test_new_user_gets_defaults_once(db_session):
    user = User(username="u1")
    db_session.add(user)
    db_session.commit()

    assert seed_defaults(db_session, user) is True
    assert db_session.query(Category).filter_by(user_id=user.id).count() == 13
    assert db_session.query(PaymentMethod).filter_by(user_id=user.id).count() == 3

    # A second run must not add anything, even after the user deletes everything
    db_session.query(Category).delete()
    db_session.query(PaymentMethod).delete()
    db_session.commit()
    assert seed_defaults(db_session, user) is False
    assert db_session.query(Category).count() == 0


def test_existing_user_data_is_never_touched(db_session, seed):
    user = db_session.get(User, seed.user_id)
    user.defaults_seeded = False
    db_session.commit()
    before = db_session.query(Category).count()

    assert seed_defaults(db_session, user) is False
    assert db_session.query(Category).count() == before
    assert user.defaults_seeded is True
