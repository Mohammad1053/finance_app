from app.models import AppSettings, Transaction
from app.units import to_base


def test_to_base_conversion():
    assert to_base(3_500_000, "rial") == 350_000
    assert to_base(3_500_000, "toman") == 3_500_000
    # a positive amount never rounds down to zero
    assert to_base(4, "rial") == 1
    assert to_base(None, "rial") is None


def test_first_visit_redirects_to_welcome(client):
    res = client.get("/", follow_redirects=False)
    assert res.status_code == 307
    assert res.headers["location"] == "/welcome"


def test_htmx_requests_are_not_redirected(client):
    assert client.get(
        "/ui/table", headers={"HX-Request": "true"}).status_code == 200


def test_welcome_saves_name_and_greets(client, db_session):
    res = client.post(
        "/welcome", data={"first_name": "علی", "last_name": "رضایی"}, follow_redirects=False
    )
    assert res.status_code == 303 and res.headers["location"] == "/"

    row = db_session.query(AppSettings).one()
    assert (row.first_name, row.last_name) == ("علی", "رضایی")
    assert "علی عزیز خوش آمدید" in client.get("/").text


def test_welcome_requires_both_names(client, db_session):
    res = client.post(
        "/welcome", data={"first_name": "علی", "last_name": "  "})
    assert "لازم" in res.text
    assert db_session.query(AppSettings).one().first_name == ""


def test_theme_defaults_to_light_and_can_change(client, seed):
    assert 'data-theme="light"' in client.get("/").text

    client.post("/appearance", data={"theme": "dark", "currency": "toman"})
    assert 'data-theme="dark"' in client.get("/").text

    client.post("/appearance", data={"theme": "system", "currency": "toman"})
    assert 'data-theme="system"' in client.get("/").text

    # Unknown values are ignored
    client.post("/appearance", data={"theme": "neon", "currency": "toman"})
    assert 'data-theme="system"' in client.get("/").text


def test_rial_mode_converts_input_output_and_reports(client, db_session, seed):
    client.post("/appearance", data={"theme": "light", "currency": "rial"})
    client.post(
        "/ui/transactions",
        data={
            "amount": "3500000",
            "date": "1405/08/05",
            "description": "",
            "payment_method_id": seed.cash_id,
            "category_id": seed.food_id,
        },
    )
    # Stored in Toman, shown in Rial
    assert db_session.query(Transaction).one().amount == 350_000
    assert "۳،۵۰۰،۰۰۰" in client.get("/ui/table").text

    data = client.get("/api/report-data",
                      params={"year": 1405, "month": 8}).json()
    assert data["totals"]["expense"] == 3_500_000
