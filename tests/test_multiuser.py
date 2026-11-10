import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Category, PaymentMethod, Transaction, User


def register(client, username="ali", password="secret123", first="علی", last="رضایی", confirm=None):
    return client.post(
        "/register",
        data={
            "first_name": first,
            "last_name": last,
            "username": username,
            "password": password,
            "confirm_password": password if confirm is None else confirm,
        },
        follow_redirects=False,
    )


def test_anonymous_visitors_are_sent_to_login(client):
    res = client.get("/", follow_redirects=False)
    assert res.status_code == 303 and res.headers["location"] == "/login"
    assert client.get("/ui/table", headers={"HX-Request": "true"}).status_code == 401
    assert client.post("/ui/transactions", data={}).status_code == 401
    assert client.get("/export.csv", follow_redirects=False).status_code == 303
    assert client.get("/login").status_code == 200
    assert client.get("/register").status_code == 200


def test_register_creates_account_seeds_defaults_and_logs_in(client, db_session):
    res = register(client)
    assert res.status_code == 303 and res.headers["location"] == "/"

    user = db_session.query(User).one()
    assert user.username == "ali"
    assert db_session.query(Category).filter_by(user_id=user.id).count() == 13
    assert db_session.query(PaymentMethod).filter_by(user_id=user.id).count() == 3
    assert "علی عزیز خوش آمدید" in client.get("/").text


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"username": "ab"}, "نام کاربری"),
        ({"username": "علی"}, "نام کاربری"),
        ({"password": "123"}, "حداقل"),
        ({"confirm": "other999"}, "یکسان نیستند"),
        ({"first": " "}, "لازم"),
    ],
)
def test_register_validation(client, db_session, kwargs, message):
    res = register(client, **kwargs)
    assert res.status_code == 400 and message in res.text
    assert db_session.query(User).count() == 0


def test_username_is_unique_ignoring_case(client, db_session):
    register(client)
    client.cookies.clear()
    res = register(client, username="ALI")
    assert res.status_code == 400 and "قبلاً" in res.text
    assert db_session.query(User).count() == 1


def test_login_and_logout(client):
    register(client)
    client.cookies.clear()

    wrong = client.post("/login", data={"username": "ali", "password": "nope"}, follow_redirects=False)
    assert wrong.status_code == 401

    ok = client.post("/login", data={"username": "ALI", "password": "secret123"}, follow_redirects=False)
    assert ok.status_code == 303 and ok.headers["location"] == "/"
    assert client.get("/").status_code == 200
    assert "/logout" in client.get("/").text

    client.get("/logout")
    assert client.get("/", follow_redirects=False).status_code == 303


def test_repeated_failures_lock_the_login(client):
    register(client)
    client.cookies.clear()
    for _ in range(5):
        res = client.post("/login", data={"username": "ali", "password": "bad"}, follow_redirects=False)
        assert res.status_code == 401
    blocked = client.post("/login", data={"username": "ali", "password": "secret123"}, follow_redirects=False)
    assert blocked.status_code == 429


def test_users_cannot_see_or_change_each_others_data(client, db_session):
    other = TestClient(app)
    register(client, username="ali")
    register(other, username="sara", first="سارا")

    ali = db_session.query(User).filter_by(username="ali").one()
    food = db_session.query(Category).filter_by(user_id=ali.id, name="خوراک").one()
    cash = db_session.query(PaymentMethod).filter_by(user_id=ali.id, name="نقد").one()
    data = {
        "amount": "123000",
        "date": "1405/08/05",
        "description": "private",
        "payment_method_id": cash.id,
        "category_id": food.id,
    }

    assert "۱۲۳،۰۰۰" in client.post("/ui/transactions", data=data).text
    # The other account sees none of it
    assert "۱۲۳،۰۰۰" not in other.get("/ui/table").text
    # ...cannot use Ali's category or payment method...
    assert other.post("/ui/transactions", data=data).status_code == 400

    # ...and cannot delete Ali's transaction
    db_session.expire_all()
    tx = db_session.query(Transaction).one()
    other.delete(f"/ui/transactions/{tx.id}")
    db_session.expire_all()
    assert db_session.query(Transaction).count() == 1

    # Both accounts have a category called "خوراک": names are unique per user, not globally
    assert db_session.query(Category).filter_by(name="خوراک").count() == 2


def test_settings_are_per_user(client):
    other = TestClient(app)
    register(client, username="ali")
    register(other, username="sara")
    client.post("/appearance", data={"theme": "dark", "currency": "rial"})
    assert 'data-theme="dark"' in client.get("/").text
    assert 'data-theme="light"' in other.get("/").text


def test_password_change_signs_out_other_devices(client):
    register(client)
    second = TestClient(app)
    second.post("/login", data={"username": "ali", "password": "secret123"})
    assert second.get("/", follow_redirects=False).status_code == 200

    bad = client.post(
        "/appearance/password",
        data={"current_password": "bad", "new_password": "newpass99", "confirm_password": "newpass99"},
    )
    assert "رمز فعلی اشتباه" in bad.text

    res = client.post(
        "/appearance/password",
        data={"current_password": "secret123", "new_password": "newpass99", "confirm_password": "newpass99"},
        follow_redirects=False,
    )
    assert res.status_code == 303
    assert client.get("/appearance").status_code == 200  # this browser stays signed in
    assert second.get("/", follow_redirects=False).status_code == 303  # the other one does not
