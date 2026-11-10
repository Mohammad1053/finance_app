import datetime as dt

from app.models import Frequency, RecurringTransaction, Transaction
from app.services.recurring import generate_due, next_occurrence


def test_monthly_anchored_on_31_clamps_and_recovers():
    current = dt.date(2026, 1, 31)
    seen = [current]
    for _ in range(4):
        current = next_occurrence(current, Frequency.MONTHLY, 31)
        seen.append(current)
    assert seen == [
        dt.date(2026, 1, 31),
        dt.date(2026, 2, 28),
        dt.date(2026, 3, 31),  # back to 31 after the short month
        dt.date(2026, 4, 30),
        dt.date(2026, 5, 31),
    ]


def test_february_in_leap_year():
    assert next_occurrence(dt.date(2028, 1, 31),
                           Frequency.MONTHLY, 31) == dt.date(2028, 2, 29)


def test_december_rolls_into_next_year():
    assert next_occurrence(dt.date(2026, 12, 15),
                           Frequency.MONTHLY, 15) == dt.date(2027, 1, 15)


def test_weekly_adds_seven_days():
    assert next_occurrence(dt.date(2026, 10, 25),
                           Frequency.WEEKLY, 25) == dt.date(2026, 11, 1)


def test_yearly_from_leap_day():
    assert next_occurrence(dt.date(2024, 2, 29),
                           Frequency.YEARLY, 29) == dt.date(2025, 2, 28)


def _make_template(db, seed, **overrides):
    values = dict(
        amount=15_000_000,
        description="اجاره",
        frequency=Frequency.MONTHLY,
        next_date=dt.date(2026, 8, 31),
        anchor_day=31,
        user_id=seed.user_id, payment_method_id=seed.cash_id,
        category_id=seed.food_id,
    )
    values.update(overrides)
    item = RecurringTransaction(**values)
    db.add(item)
    db.commit()
    return item


def test_generate_due_catches_up_and_is_idempotent(db_session, seed):
    item = _make_template(db_session, seed)
    today = dt.date(2026, 11, 1)

    assert generate_due(db_session, today) == 3
    dates = [t.date for t in db_session.query(
        Transaction).order_by(Transaction.date)]
    assert dates == [dt.date(2026, 8, 31), dt.date(
        2026, 9, 30), dt.date(2026, 10, 31)]

    db_session.refresh(item)
    assert item.next_date == dt.date(2026, 11, 30)

    # Running again the same day must not create duplicates
    assert generate_due(db_session, today) == 0
    assert db_session.query(Transaction).count() == 3


def test_paused_template_creates_nothing(db_session, seed):
    _make_template(db_session, seed, active=False)
    assert generate_due(db_session, dt.date(2026, 11, 1)) == 0
    assert db_session.query(Transaction).count() == 0


def test_future_template_creates_nothing(db_session, seed):
    _make_template(db_session, seed, next_date=dt.date(
        2026, 12, 5), anchor_day=5)
    assert generate_due(db_session, dt.date(2026, 11, 1)) == 0
