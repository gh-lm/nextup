"""Behaviour fixed after the 24 October review: lock, bad replies, mail, caches."""
import io
import json
import smtplib

import pytest

from app import auth

def _raises(exc):
    def fail(*args, **kwargs):
        raise exc
    return fail

def _account(client, **fields):
    data = {"username": "admin", "current": "nextup", "password": "", "confirm": ""}
    data.update(fields)
    return client.post("/settings/account", data=data)

def _upload(client, payload):
    return client.post(
        "/settings/import",
        data={"backup": (io.BytesIO(json.dumps(payload).encode()), "b.json"), "confirm": "replace"},
        content_type="multipart/form-data",
    )

def test_a_username_only_change_cannot_lift_the_starter_lock(app, client):
    client.post("/login", data={"username": "admin", "password": "nextup"})
    _account(client, username="sam")
    with app.app_context():
        from app import db

        assert db.query("SELECT username FROM admin_user WHERE id = 1", one=True)["username"] == "admin"
    assert client.get("/").headers["Location"].endswith("/settings#account")

def test_a_username_only_change_keeps_the_lock_off_once_a_password_is_chosen(app, signed_in):
    _account(signed_in, password="a-new-password", confirm="a-new-password")
    _account(signed_in, username="sam", current="a-new-password")
    assert signed_in.get("/").status_code == 200

def test_a_restore_of_the_default_password_puts_the_lock_back(app, signed_in):
    with app.app_context():
        from app import transfer

        payload = transfer.export_data()
    assert "session_epoch" not in payload["data"]["settings"]
    _upload(signed_in, payload)
    assert signed_in.get("/").headers["Location"].endswith("/settings#account")

def test_a_restore_ignores_a_session_epoch_in_the_file(app, signed_in):
    with app.app_context():
        from app import secretstore, transfer

        payload = transfer.export_data()
        payload["data"]["settings"]["session_epoch"] = "old"
        transfer.import_data(payload)
        assert secretstore.get("session_epoch") is None

def test_the_wait_grows_per_username_and_is_not_one_hard_stop(monkeypatch):
    auth._failures.clear()
    for _ in range(auth.FREE_TRIES):
        auth.record_failure("172.17.0.1", "Admin")
    assert auth.sign_in_wait("172.17.0.1", "admin") == 0
    auth.record_failure("172.17.0.1", "admin")
    first = auth.sign_in_wait("172.17.0.1", " ADMIN ")
    assert 0 < first <= 1
    for _ in range(20):
        auth.record_failure("172.17.0.1", "admin")
    assert auth.sign_in_wait("172.17.0.1", "admin") <= auth.MAX_DELAY
    assert auth.sign_in_wait("172.17.0.1", "other") == 0
    auth.forget_failures("172.17.0.1", "admin")
    assert auth.sign_in_wait("172.17.0.1", "admin") == 0
    auth._failures.clear()

def test_old_failures_are_dropped_and_the_table_is_capped(monkeypatch):
    auth._failures.clear()
    auth.record_failure("a", "x")
    later = auth.time.monotonic() + auth.FORGET_AFTER + 1
    monkeypatch.setattr(auth.time, "monotonic", lambda: later)
    auth.sign_in_wait("a", "y")
    assert auth._failures == {}
    monkeypatch.setattr(auth, "MAX_TRACKED", 3)
    for n in range(10):
        auth.record_failure("a", f"user{n}")
    assert len(auth._failures) == 3
    auth._failures.clear()

def test_a_flood_of_other_usernames_does_not_reset_the_real_one(monkeypatch):
    auth._failures.clear()
    monkeypatch.setattr(auth, "MAX_TRACKED", 5)
    for _ in range(auth.FREE_TRIES + 2):
        auth.record_failure("a", "admin")
    for n in range(50):
        auth.record_failure("a", f"flood{n}")
    assert auth.sign_in_wait("a", "admin") > 0
    auth._failures.clear()

class _Reply:
    status_code = 200
    ok = True
    headers = {}

    def json(self):
        raise requests_json_error()

def requests_json_error():
    import requests

    return requests.exceptions.JSONDecodeError("Expecting value", "<html>", 0)

def test_a_200_reply_that_is_not_json_is_a_tmdb_error(app, monkeypatch):
    from app import tmdb

    monkeypatch.setattr(tmdb, "api_key", lambda: "k")
    monkeypatch.setattr(tmdb.requests, "get", lambda *a, **k: _Reply())
    with app.app_context():
        with pytest.raises(tmdb.TmdbError):
            tmdb._get("/search/multi")

def test_a_bad_reply_for_one_show_does_not_stop_the_refresh(app, monkeypatch):
    from app import db, sync, tmdb

    with app.app_context():
        for show_id, name in ((801, "Broken"), (802, "Fine")):
            db.execute("INSERT INTO show (id, name) VALUES (?, ?)", (show_id, name))
            db.execute("INSERT INTO tracked_show (show_id, added_at) VALUES (?, '2026-01-01')", (show_id,))

        def show(show_id):
            if show_id == 801:
                raise ValueError("not json")
            return {"id": show_id, "name": "Fine", "seasons": []}

        monkeypatch.setattr(tmdb, "show", show)
        monkeypatch.setattr(sync, "sync_all_movies", lambda force=False: 0)
        done, _skipped, errors = sync.sync_all(force=True)
        run = sync.last_run()
        assert done == 1 and len(errors) == 1
        assert run["status"] == "error" and run["finished_at"]
        assert not sync.is_running()

def test_a_failed_first_write_does_not_leave_the_refresh_stuck(app, monkeypatch):
    from app import db, sync

    with app.app_context():
        monkeypatch.setattr(db, "execute", _raises(RuntimeError("disk")))
        with pytest.raises(RuntimeError):
            sync.sync_all()
        assert not sync.is_running()
        assert sync._sync_lock.acquire(blocking=False)
        sync._sync_lock.release()

def test_the_address_is_taken_from_the_page_not_typed(app, signed_in):
    from app import secretstore

    signed_in.post("/settings/mail", data={
        "smtp_host": "mail.example.com", "smtp_port": "587", "smtp_security": "starttls",
        "mail_from": "john@example.com", "mail_to": "john@example.com",
        "site_url": "ftp://nextup.example.com", "smtp_password": "pw",
    })
    with app.app_context():
        assert secretstore.get("site_url") != "ftp://nextup.example.com"
    body = signed_in.get(
        "/settings", headers={"X-Forwarded-Proto": "https", "X-Forwarded-Host": "nextup.example.ts.net:4090"}
    ).get_data(as_text=True)
    assert "https://nextup.example.ts.net:4090" in body
    with app.app_context():
        assert secretstore.get("site_url") == "https://nextup.example.ts.net:4090"

class _FakeSMTP:
    instances = []

    def __init__(self, *a, **k):
        self.closed = False
        _FakeSMTP.instances.append(self)

    def starttls(self, **k):
        raise smtplib.SMTPException("no tls")

    def ehlo(self):
        pass

    def login(self, *a):
        raise smtplib.SMTPAuthenticationError(535, b"no")

    def close(self):
        self.closed = True

def _configure_mail(app, **extra):
    from app import secretstore

    with app.app_context():
        for key, value in {"smtp_host": "mail.example.com", "smtp_port": "587",
                           "mail_from": "john@example.com", "mail_to": "john@example.com",
                           "smtp_username": "john", **extra}.items():
            secretstore.set(key, value)
        secretstore.set("smtp_password", "pw", encrypted=True)

def test_the_connection_is_closed_after_a_failed_starttls(app, monkeypatch):
    from app import mailer

    _FakeSMTP.instances.clear()
    monkeypatch.setattr(mailer.smtplib, "SMTP", _FakeSMTP)
    _configure_mail(app, smtp_security="starttls")
    with app.app_context():
        with pytest.raises(mailer.MailError):
            mailer.send_test()
    assert _FakeSMTP.instances and all(s.closed for s in _FakeSMTP.instances)

def test_the_connection_is_closed_after_a_failed_login(app, monkeypatch):
    from app import mailer

    _FakeSMTP.instances.clear()
    monkeypatch.setattr(mailer.smtplib, "SMTP", _FakeSMTP)
    monkeypatch.setattr(_FakeSMTP, "starttls", lambda self, **k: None)
    _configure_mail(app, smtp_security="none")
    with app.app_context():
        with pytest.raises(mailer.MailError, match="rejected"):
            mailer.send_test()
    assert all(s.closed for s in _FakeSMTP.instances)

def test_a_bad_header_is_a_mail_error_not_a_crash(app, monkeypatch):
    from app import mailer

    monkeypatch.setattr(mailer.smtplib, "SMTP", _FakeSMTP)
    _configure_mail(app, mail_from_name="John\nBcc: x@example.com")
    with app.app_context():
        with pytest.raises(mailer.MailError):
            mailer.send_test()

def test_a_time_with_odd_digits_is_not_a_time():
    from app import mailer

    assert mailer.parse_time("²:00") is None
    assert mailer.parse_time("07:30").hour == 7

def test_the_country_list_is_kept_and_reused_for_a_week(app, monkeypatch):
    from app import tmdb

    calls = []

    def fetch(path, params=None, **kw):
        calls.append(kw)
        return [{"iso_3166_1": "DE", "english_name": "Germany"}]

    monkeypatch.setattr(tmdb, "_get", fetch)
    with app.app_context():
        assert tmdb.countries() == [("DE", "Germany")]
        assert tmdb.countries() == [("DE", "Germany")]
    assert len(calls) == 1
    assert calls[0]["tries"] == 1 and calls[0]["timeout"] <= 10

def test_an_old_country_list_is_used_when_tmdb_is_down(app, monkeypatch):
    from app import secretstore, tmdb

    def down(*a, **k):
        raise tmdb.TmdbError("down")

    monkeypatch.setattr(tmdb, "_get", down)
    with app.app_context():
        secretstore.set("countries_cache", json.dumps([["DE", "Germany"]]))
        secretstore.set("countries_fetched_at", "2020-01-01T00:00:00+00:00")
        assert tmdb.countries() == [("DE", "Germany")]
        secretstore.delete("countries_cache")
        with pytest.raises(tmdb.TmdbError):
            tmdb.countries()

def test_the_country_cache_is_not_part_of_a_backup(app):
    from app import secretstore, transfer

    with app.app_context():
        secretstore.set("countries_cache", "[]")
        secretstore.set("countries_fetched_at", "2026-01-01T00:00:00+00:00")
        assert "countries_cache" not in transfer.export_data()["data"]["settings"]

def test_unsafe_links_and_keyless_trailers_are_dropped():
    from app import tmdb

    assert tmdb.safe_url("javascript:alert(1)") is None
    assert tmdb.safe_url("https://example.com/a") == "https://example.com/a"
    assert tmdb.safe_url(None) is None
    assert tmdb.trailer_from({"videos": {"results": [
        {"site": "YouTube", "type": "Trailer", "key": None}]}}) is None
    assert tmdb.trailer_from({"videos": {"results": [
        {"site": "YouTube", "type": "Trailer", "key": "abc_123"}]}})["url"].endswith("abc_123")
    assert tmdb.imdb_from({"imdb_id": "x/../y"}) is None

def test_a_webp_picture_is_labelled_webp_and_svg_is_not_accepted(data_dir):
    import os

    from app import config, posters

    assert posters.normalise("/poster.svg") is None
    os.makedirs(config.CACHE_DIR)
    name = posters.cache_name("w185", "/poster.webp")
    with open(os.path.join(config.CACHE_DIR, name), "wb") as fh:
        fh.write(b"x")
    data, subtype = posters.read_bytes("w185", "/poster.webp")
    assert data == b"x" and subtype == "webp"

class _Picture:
    ok = True

    def __init__(self, chunks, length=None):
        self.chunks, self.read, self.closed = chunks, 0, False
        self.headers = {"Content-Type": "image/jpeg"}
        if length is not None:
            self.headers["Content-Length"] = str(length)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.closed = True

    def iter_content(self, size):
        for chunk in self.chunks:
            self.read += 1
            yield chunk

def test_an_oversize_picture_is_not_cached(data_dir, monkeypatch):
    from app import posters

    big = _Picture([b"x"], length=posters.MAX_BYTES + 1)
    monkeypatch.setattr(posters.requests, "get", lambda *a, **k: big)
    assert posters.cached_file("w185", "/big.jpg") is None
    assert big.closed and big.read == 0

def test_a_picture_with_no_length_stops_being_read_once_too_big(data_dir, monkeypatch):
    from app import posters

    endless = _Picture(iter(lambda: b"x" * 65536, None))
    monkeypatch.setattr(posters.requests, "get", lambda *a, **k: endless)
    assert posters.cached_file("w185", "/endless.jpg") is None
    assert endless.closed and endless.read == posters.MAX_BYTES // 65536 + 1

def test_opening_an_unknown_show_does_not_mark_it_fresh(app, signed_in, monkeypatch):
    from app import db, tmdb

    monkeypatch.setattr(tmdb, "show", lambda show_id: {"id": show_id, "name": "New"})
    monkeypatch.setattr(tmdb, "show_detail", _raises(tmdb.TmdbError("x")))
    assert signed_in.get("/show/777").status_code == 200
    with app.app_context():
        assert db.query("SELECT synced_at FROM show WHERE id = 777", one=True)["synced_at"] is None

def test_adding_a_show_with_a_missing_season_says_so(app, signed_in, monkeypatch):
    from app import tmdb

    monkeypatch.setattr(tmdb, "show", lambda show_id: {"id": show_id, "name": "Patchy", "seasons": [{"season_number": 1}]})
    monkeypatch.setattr(tmdb, "season", _raises(tmdb.TmdbError("x")))
    page = signed_in.post("/show/778/track", follow_redirects=True).get_data(as_text=True)
    assert "would not serve season 1" in page

def test_a_film_without_a_title_is_not_announced_as_none(app, signed_in, monkeypatch):
    from app import sync, tmdb

    monkeypatch.setattr(tmdb, "movie", lambda movie_id: {"id": movie_id})
    monkeypatch.setattr(sync, "sync_movie_availability", lambda movie_id: (None, []))
    page = signed_in.post("/movie/779/track", follow_redirects=True).get_data(as_text=True)
    assert "None" not in page

def test_remove_buttons_do_nothing_without_the_second_click(app, signed_in):
    from app import db, secretstore

    with app.app_context():
        secretstore.set("tmdb_api_key", "made-up-key")
        db.execute("INSERT INTO show (id, name) VALUES (780, 'Kept')")
        db.execute("INSERT INTO tracked_show (show_id, added_at) VALUES (780, '2026-10-24')")
    signed_in.post("/settings/tmdb/clear")
    signed_in.post("/show/780/untrack")
    with app.app_context():
        assert secretstore.get("tmdb_api_key") == "made-up-key"
        assert db.query("SELECT 1 FROM tracked_show WHERE show_id = 780", one=True)
    signed_in.post("/settings/tmdb/clear", data={"sure": "1"})
    signed_in.post("/show/780/untrack", data={"sure": "1"})
    with app.app_context():
        assert not secretstore.get("tmdb_api_key")
        assert db.query("SELECT 1 FROM tracked_show WHERE show_id = 780", one=True) is None
