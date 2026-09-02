def test_login_page_renders(client):
    resp = client.get("/login")
    assert resp.status_code == 200
    assert b"Sign in" in resp.data


def test_dashboard_needs_login(client):
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_bad_password_is_rejected(client):
    resp = client.post("/login", data={"username": "admin", "password": "wrong"})
    assert b"did not match" in resp.data


def test_dashboard_after_login(signed_in):
    resp = signed_in.get("/")
    assert resp.status_code == 200
    assert b"Next up" in resp.data
    # No key saved yet, so the app should say so rather than fail.
    assert b"No TMDB key yet" in resp.data


def test_every_page_loads(signed_in):
    for path in ["/", "/shows", "/calendar", "/upcoming", "/movies", "/settings", "/search"]:
        assert signed_in.get(path).status_code == 200, path


def test_search_without_key_explains_itself(signed_in):
    resp = signed_in.get("/search?q=anything")
    assert resp.status_code == 200
    assert b"No TMDB API key saved" in resp.data


def test_no_external_hosts_in_markup(signed_in):
    """Every asset must come from this app, not a third-party host."""
    body = signed_in.get("/").data.decode()
    for host in ["image.tmdb.org", "fonts.googleapis.com", "cdn.", "unpkg", "jsdelivr"]:
        assert host not in body
