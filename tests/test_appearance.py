from app.models import Transaction, User
from app.units import to_base


def test_to_base_conversion():
    assert to_base(3_500_000, "rial") == 350_000
    assert to_base(3_500_000, "toman") == 3_500_000
    assert to_base(4, "rial") == 1  # a positive amount never rounds down to zero
    assert to_base(None, "rial") is None


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

    data = client.get("/api/report-data", params={"year": 1405, "month": 8}).json()
    assert data["totals"]["expense"] == 3_500_000


def test_change_name(client, db_session, seed):
    client.post("/appearance/name", data={"first_name": "سارا", "last_name": "احمدی"})
    db_session.expire_all()
    user = db_session.query(User).one()
    assert (user.first_name, user.last_name) == ("سارا", "احمدی")
    assert "سارا عزیز خوش آمدید" in client.get("/").text

    res = client.post("/appearance/name", data={"first_name": "", "last_name": "x"})
    assert "لازم" in res.text


def test_footer_links_to_designer_site(client, seed):
    html = client.get("/").text
    assert "طراحی شده توسط" in html
    assert 'href="https://mksafarzadeh.ir"' in html and "محمد صفرزاده" in html
