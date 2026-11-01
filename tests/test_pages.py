import datetime as dt

import pytest

from app.models import Goal, GoalContribution, Transaction


@pytest.mark.parametrize(
    "path",
    ["/", "/reports", "/goals", "/recurring", "/settings", "/data",
     "/ui/table", "/ui/goals", "/ui/recurring", "/ui/settings"],
)
def test_every_page_renders(client, seed, path):
    assert client.get(path).status_code == 200


def test_add_transaction_from_form_shows_persian_output(client, db_session, seed):
    res = client.post(
        "/ui/transactions",
        data={
            "amount": "350000",
            "date": "1405/08/05",
            "description": "خرید",
            "payment_method_id": seed.cash_id,
            "category_id": seed.food_id,
        },
    )
    assert res.status_code == 200
    assert "۳۵۰،۰۰۰" in res.text      # amount with Persian digits and separator
    assert "۱۴۰۵/۰۸/۰۵" in res.text   # Jalali date in the table
    # Stored as a Gregorian date
    assert db_session.query(Transaction).one().date == dt.date(2026, 10, 27)


def test_jalali_filter_on_table(client, seed):
    for date in ("1405/08/05", "1405/09/05"):
        client.post(
            "/ui/transactions",
            data={"amount": "1000", "date": date, "description": "",
                  "payment_method_id": seed.cash_id, "category_id": seed.food_id},
        )
    res = client.get("/ui/table", params={"date_from": "1405/09/01"})
    assert "۱۴۰۵/۰۹/۰۵" in res.text
    assert "۱۴۰۵/۰۸/۰۵" not in res.text


def test_delete_transaction_from_ui(client, db_session, seed):
    client.post(
        "/ui/transactions",
        data={"amount": "1000", "date": "1405/08/05", "description": "",
              "payment_method_id": seed.cash_id, "category_id": seed.food_id},
    )
    tx_id = db_session.query(Transaction).one().id
    assert client.delete(f"/ui/transactions/{tx_id}").status_code == 200
    assert db_session.query(Transaction).count() == 0


def test_settings_duplicate_category_shows_error(client):
    data = {"name": "اجاره", "type": "expense"}
    client.post("/ui/categories", data=data)
    res = client.post("/ui/categories", data=data)
    assert "قبلاً ثبت شده" in res.text


def test_goal_percent_and_cap(db_session):
    goal = Goal(name="لپ‌تاپ", target_amount=1000)
    db_session.add(goal)
    db_session.commit()

    db_session.add(GoalContribution(goal_id=goal.id, amount=250))
    db_session.commit()
    db_session.refresh(goal)
    assert (goal.saved, goal.percent) == (250, 25)

    db_session.add(GoalContribution(goal_id=goal.id, amount=2000))
    db_session.commit()
    db_session.refresh(goal)
    assert goal.percent == 100  # capped even when saved exceeds the target


def test_goal_duplicate_name_shows_error(client):
    data = {"name": "سفر", "target_amount": "5000"}
    client.post("/ui/goals", data=data)
    assert "قبلاً ثبت شده" in client.post("/ui/goals", data=data).text


def test_exports_are_valid_files(client, db_session, seed):
    db_session.add(
        Transaction(amount=1000, date=dt.date(2026, 10, 25), description="",
                    payment_method_id=seed.cash_id, category_id=seed.food_id)
    )
    db_session.commit()

    csv_res = client.get("/export.csv")
    assert csv_res.status_code == 200
    assert csv_res.content.startswith(b"\xef\xbb\xbf")

    xlsx_res = client.get("/export.xlsx")
    assert xlsx_res.status_code == 200
    assert xlsx_res.content.startswith(b"PK")  # .xlsx files are zip archives


def test_upload_through_the_page(client, db_session, seed):
    content = (
        "date,type,category,payment_method,amount,description\n"
        "1405/08/03,هزینه,خوراک,نقد,350000,خرید\n"
    ).encode("utf-8-sig")
    res = client.post(
        "/data/import", files={"file": ("t.csv", content, "text/csv")})
    assert res.status_code == 200
    assert "با موفقیت وارد شد" in res.text
    assert db_session.query(Transaction).count() == 1
