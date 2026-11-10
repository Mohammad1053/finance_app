import datetime as dt

from app.models import Transaction


def _add(db, seed, date, amount, income=False):
    db.add(
        Transaction(
            amount=amount,
            date=date,
            description="",
            user_id=seed.user_id, payment_method_id=seed.cash_id,
            category_id=seed.salary_id if income else seed.food_id,
        )
    )


def test_report_uses_jalali_month_boundaries(client, db_session, seed):
    # Aban 1405 = 2026-10-23 .. 2026-11-21 (inclusive)
    _add(db_session, seed, dt.date(2026, 10, 25), 20_000_000, income=True)
    _add(db_session, seed, dt.date(2026, 10, 24), 350_000)
    _add(db_session, seed, dt.date(2026, 11, 1), 120_000)
    # Outside Aban: last day of Mehr and first day of Azar
    _add(db_session, seed, dt.date(2026, 10, 22), 999)
    _add(db_session, seed, dt.date(2026, 11, 22), 777)
    db_session.commit()

    data = client.get("/api/report-data",
                      params={"year": 1405, "month": 8}).json()

    assert data["totals"] == {
        "income": 20_000_000,
        "expense": 470_000,
        "balance": 19_530_000,
    }
    assert data["by_category"] == [{"name": "خوراک", "total": 470_000}]


def test_trend_has_twelve_months_ending_at_selected_month(client, db_session, seed):
    _add(db_session, seed, dt.date(2026, 10, 25), 1000)  # Aban 1405
    _add(db_session, seed, dt.date(2026, 10, 22), 500)   # Mehr 1405
    db_session.commit()

    trend = client.get("/api/report-data",
                       params={"year": 1405, "month": 8}).json()["trend"]

    assert len(trend) == 12
    assert trend[-1] == {"month": "آبان 1405", "income": 0, "expense": 1000}
    assert trend[-2] == {"month": "مهر 1405", "income": 0, "expense": 500}
    assert trend[0]["month"] == "آذر 1404"


def test_empty_month_returns_zeros(client, seed):
    data = client.get("/api/report-data",
                      params={"year": 1405, "month": 1}).json()
    assert data["totals"] == {"income": 0, "expense": 0, "balance": 0}
    assert data["by_category"] == []


def test_invalid_month_falls_back_to_current(client, seed):
    res = client.get("/api/report-data", params={"year": 1405, "month": 13})
    assert res.status_code == 200
    assert 1 <= res.json()["month"] <= 12
