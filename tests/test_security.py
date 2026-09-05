"""Guards for the things a security review would look for first.

Each of these was a real gap once, so each has a test rather than a comment.
"""
import json


def test_login_will_not_send_you_off_the_site(client):
    """"//evil.example" starts with a slash but is a whole other website."""
    response = client.post(
        "/login?next=//evil.example/steal",
        data={"username": "admin", "password": "nextup"},
    )
    assert response.status_code == 302
    assert "evil.example" not in response.headers["Location"]
    assert response.headers["Location"].endswith("/")


def test_login_still_honours_an_ordinary_path(client):
    response = client.post(
        "/login?next=/settings", data={"username": "admin", "password": "nextup"}
    )
    assert response.headers["Location"] == "/settings"


def test_a_full_url_in_next_is_ignored(client):
    response = client.post(
        "/login?next=https://evil.example/", data={"username": "admin", "password": "nextup"}
    )
    assert "evil.example" not in response.headers["Location"]


def test_every_page_carries_the_security_headers(signed_in):
    response = signed_in.get("/")
    csp = response.headers["Content-Security-Policy"]
    assert "script-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "same-origin"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_the_login_page_carries_them_too(client):
    assert "Content-Security-Policy" in client.get("/login").headers


def test_the_session_cookie_is_locked_down(app):
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    # Off unless the whole way in is HTTPS, which is a deployment decision.
    assert app.config["SESSION_COOKIE_SECURE"] is False


def test_the_poster_proxy_only_fetches_tmdb_shaped_paths(app):
    from app import posters

    for bad in (
        "../../etc/passwd",
        "/../secret.key",
        "http://169.254.169.254/latest/meta-data",
        "a/b.jpg",
        "evil.jpg?x=1",
        "shell.sh",
        "",
    ):
        assert posters.normalise(bad) is None, bad
    assert posters.normalise("/abc123_-.jpg") == "/abc123_-.jpg"


def test_the_poster_proxy_refuses_a_made_up_size(signed_in):
    assert signed_in.get("/img/w9999/abc.jpg").status_code == 404


def test_a_restore_that_fails_part_way_changes_nothing(app):
    """Settings used to be written after the commit, so a failure there left
    you with no settings at all."""
    from app import db, secretstore, transfer

    with app.app_context():
        secretstore.set("accent", "brand")
        db.execute("INSERT INTO show (id, name) VALUES (55, 'Before')")
        before_shows = len(db.query("SELECT id FROM show"))

        payload = {
            "format": "nextup-backup",
            "version": 1,
            # A show row whose id is a dictionary cannot be written, so the
            # restore fails once it is already part way through.
            "data": {"show": [{"id": {"not": "an id"}, "name": "Broken"}]},
        }
        try:
            transfer.import_data(payload)
        except transfer.ImportError_:
            pass
        else:
            raise AssertionError("that restore should not have been accepted")

        assert len(db.query("SELECT id FROM show")) == before_shows
        assert secretstore.get("accent") == "brand"


def test_a_good_restore_puts_the_settings_back(app):
    from app import db, secretstore, transfer

    with app.app_context():
        secretstore.set("accent", "brand")
        secretstore.set("tmdb_api_key", "0123456789abcdef", encrypted=True)
        payload = transfer.export_data(include_secrets=True)

        db.execute("DELETE FROM settings")
        assert secretstore.get("accent") is None

        transfer.import_data(payload)
        assert secretstore.get("accent") == "brand"
        assert secretstore.get("tmdb_api_key") == "0123456789abcdef"
        row = db.query("SELECT encrypted FROM settings WHERE key = 'tmdb_api_key'", one=True)
        assert row["encrypted"] == 1


def test_a_file_that_is_not_a_backup_is_turned_away(app):
    from app import transfer

    with app.app_context():
        for rubbish in ({}, {"format": "something-else"}, [1, 2, 3], {"format": "nextup-backup", "version": 99}):
            try:
                transfer.import_data(rubbish)
            except transfer.ImportError_:
                continue
            raise AssertionError(f"accepted {rubbish!r}")


def test_signed_out_visitors_are_sent_to_the_login_page(client):
    for path in ("/", "/shows", "/movies", "/settings", "/calendar", "/discover/tv"):
        response = client.get(path)
        assert response.status_code == 302, path
        assert "/login" in response.headers["Location"], path
