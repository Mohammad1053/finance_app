from app.models import AppSettings


def set_password(client, password="secret123"):
    return client.post(
        "/appearance/password",
        data={"current_password": "", "new_password": password, "confirm_password": password},
        follow_redirects=False,
    )


def test_app_is_open_without_password(client, seed):
    assert client.get("/").status_code == 200


def test_footer_links_to_designer_site(client, seed):
    html = client.get("/").text
    assert "طراحی شده توسط" in html
    assert 'href="https://mksafarzadeh.ir"' in html and "محمد صفرزاده" in html


def test_short_or_mismatched_password_is_rejected(client, seed):
    short = client.post(
        "/appearance/password",
        data={"current_password": "", "new_password": "123", "confirm_password": "123"},
    )
    assert "حداقل" in short.text

    mismatch = client.post(
        "/appearance/password",
        data={"current_password": "", "new_password": "secret123", "confirm_password": "other123"},
    )
    assert "یکسان نیستند" in mismatch.text
    assert client.get("/", follow_redirects=False).status_code == 200  # still unlocked


def test_password_locks_everything_until_login(client, seed):
    assert set_password(client).status_code == 303
    assert client.get("/appearance").status_code == 200  # this browser stays logged in

    client.cookies.clear()
    res = client.get("/", follow_redirects=False)
    assert res.status_code == 303 and res.headers["location"] == "/login"

    assert client.get("/transactions/", follow_redirects=False).status_code == 303
    assert client.post("/ui/transactions", data={}).status_code == 401
    assert client.get("/ui/table", headers={"HX-Request": "true"}).status_code == 401


def test_login_logout_flow(client, seed):
    set_password(client)
    client.cookies.clear()

    wrong = client.post("/login", data={"password": "nope"}, follow_redirects=False)
    assert wrong.status_code == 401 and "اشتباه" in wrong.text

    ok = client.post("/login", data={"password": "secret123"}, follow_redirects=False)
    assert ok.status_code == 303 and ok.headers["location"] == "/"
    assert client.get("/").status_code == 200
    assert "/logout" in client.get("/").text

    client.get("/logout")
    assert client.get("/", follow_redirects=False).status_code == 303


def test_changing_password_requires_current_one(client, seed):
    set_password(client)
    res = client.post(
        "/appearance/password",
        data={"current_password": "wrong", "new_password": "newpass99", "confirm_password": "newpass99"},
    )
    assert "رمز فعلی اشتباه" in res.text

    res = client.post(
        "/appearance/password",
        data={"current_password": "secret123", "new_password": "newpass99", "confirm_password": "newpass99"},
        follow_redirects=False,
    )
    assert res.status_code == 303

    # The old password no longer works
    client.cookies.clear()
    assert client.post("/login", data={"password": "secret123"}).status_code == 401
    assert client.post("/login", data={"password": "newpass99"}, follow_redirects=False).status_code == 303


def test_remove_password_unlocks_app(client, seed):
    set_password(client)
    res = client.post(
        "/appearance/password/remove", data={"current_password": "secret123"}, follow_redirects=False
    )
    assert res.status_code == 303
    client.cookies.clear()
    assert client.get("/", follow_redirects=False).status_code == 200


def test_change_name(client, db_session, seed):
    client.post("/appearance/name", data={"first_name": "سارا", "last_name": "احمدی"})
    db_session.expire_all()
    row = db_session.query(AppSettings).one()
    assert (row.first_name, row.last_name) == ("سارا", "احمدی")
    assert "سارا عزیز خوش آمدید" in client.get("/").text

    res = client.post("/appearance/name", data={"first_name": "", "last_name": "x"})
    assert "لازم" in res.text


def test_invite_button_is_disabled_without_link(client, seed):
    assert "دعوت از دوستان" in client.get("/appearance").text
