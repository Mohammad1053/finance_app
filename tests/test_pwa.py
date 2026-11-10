import json


def test_manifest_is_valid_and_public(client):
    res = client.get("/static/manifest.webmanifest")
    assert res.status_code == 200
    data = json.loads(res.text)
    assert data["display"] == "standalone"
    assert {i["sizes"] for i in data["icons"]} >= {"192x192", "512x512"}
    assert "حسابدار من" in res.text


def test_service_worker_served_from_root(client):
    res = client.get("/service-worker.js")
    assert res.status_code == 200
    assert "javascript" in res.headers["content-type"]


def test_public_pages_have_install_banner_and_manifest(client):
    for path in ("/register", "/login"):
        html = client.get(path).text
        assert 'id="install-banner"' in html
        assert 'rel="manifest"' in html


def test_pwa_files_are_public_without_login(client):
    for path in ("/service-worker.js", "/static/manifest.webmanifest", "/static/offline.html"):
        assert client.get(path, follow_redirects=False).status_code == 200


def test_offline_page_is_self_contained(client):
    res = client.get("/static/offline.html")
    assert "آفلاین هستید" in res.text
    assert "{{" not in res.text  # no template placeholders, no server data


def test_service_worker_caches_only_the_offline_shell(client):
    js = client.get("/service-worker.js").text
    assert "/static/offline.html" in js
    assert 'request.mode !== "navigate"' in js
    for path in ("/reports", "/ui/table", "/transactions", "/export"):
        assert path not in js


def test_responsive_stylesheet_is_linked_after_theme(client):
    html = client.get("/register").text
    assert "/static/responsive.css" in html
    assert html.index("/static/theme.css") < html.index("/static/responsive.css")
    assert 'name="viewport"' in html


def test_brand_name_links_to_home_and_menu_toggle_exists(client, seed):
    html = client.get("/").text
    assert 'href="/" class="brand">حسابدار من</a>' in html
    assert 'class="nav-toggle"' in html and 'id="main-nav"' in html
