import json


def test_manifest_is_valid_and_public(client):
    res = client.get("/static/manifest.webmanifest")
    assert res.status_code == 200
    data = json.loads(res.text)
    assert data["display"] == "standalone"
    assert {i["sizes"] for i in data["icons"]} >= {"192x192", "512x512"}


def test_service_worker_served_from_root(client):
    res = client.get("/service-worker.js")
    assert res.status_code == 200
    assert "javascript" in res.headers["content-type"]


def test_welcome_page_has_install_banner(client):
    html = client.get("/welcome").text
    assert 'id="install-banner"' in html
    assert 'rel="manifest"' in html


def test_pwa_files_stay_public_when_password_is_set(client, seed):
    client.post(
        "/appearance/password",
        data={"current_password": "", "new_password": "secret123", "confirm_password": "secret123"},
    )
    client.cookies.clear()
    assert client.get("/service-worker.js", follow_redirects=False).status_code == 200
    assert client.get("/static/manifest.webmanifest", follow_redirects=False).status_code == 200


def test_offline_page_is_public_and_self_contained(client, seed):
    client.post(
        "/appearance/password",
        data={"current_password": "", "new_password": "secret123", "confirm_password": "secret123"},
    )
    client.cookies.clear()
    res = client.get("/static/offline.html", follow_redirects=False)
    assert res.status_code == 200
    assert "آفلاین هستید" in res.text
    # No server data and no template placeholders
    assert "{{" not in res.text


def test_service_worker_caches_only_the_offline_shell(client):
    js = client.get("/service-worker.js").text
    assert "/static/offline.html" in js
    assert 'request.mode !== "navigate"' in js
    # Pages with financial data must never be precached
    for path in ("/reports", "/ui/table", "/transactions", "/export"):
        assert path not in js
