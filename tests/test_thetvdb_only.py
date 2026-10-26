"""TheTVDB is the only source: nothing of TMDB is left to reach."""
import io
import json

import pytest

from app import catalog, db, sync, transfer, tvdb

def test_a_new_id_goes_straight_to_thetvdb(app, monkeypatch):
    seen = []
    monkeypatch.setattr(tvdb, "show", lambda show_id: seen.append(show_id) or {"id": show_id, "name": "X"})
    with app.app_context():
        assert catalog.show(tvdb.internal(5))["id"] == tvdb.internal(5)
    assert seen == [tvdb.internal(5)]

def test_a_film_is_ready_once_its_release_date_has_passed(app):
    from app import queries

    with app.app_context():
        for film_id, day in ((1, "2000-01-01"), (2, "2999-01-01"), (3, None)):
            db.execute("INSERT INTO movie (id, title, release_date) VALUES (?, 'F', ?)", (film_id, day))
            db.execute("INSERT INTO tracked_movie (movie_id, added_at) VALUES (?, '2026-01-01')", (film_id,))
        states = queries.films_by_state()
        assert [r["id"] for r in states["ready"]] == [1]
        assert {r["id"] for r in states["waiting"]} == {2, 3}

def test_refreshing_a_film_fetches_it_again(app, monkeypatch):
    monkeypatch.setattr(tvdb, "movie", lambda movie_id: {"id": movie_id, "title": "Moved", "release_date": "2030-05-05"})
    with app.app_context():
        db.execute("INSERT INTO movie (id, title) VALUES (?, 'Old')", (tvdb.internal(8),))
        sync.sync_movie(tvdb.internal(8))
        row = db.query("SELECT title, release_date FROM movie WHERE id = ?", (tvdb.internal(8),), one=True)
        assert (row["title"], row["release_date"]) == ("Moved", "2030-05-05")

def test_the_pages_that_used_to_need_a_tmdb_key_are_gone(signed_in):
    for path in ("/discover/films", "/discover/tv", "/welcome", "/settings/tmdb", "/settings/source",
                 "/settings/country", "/settings/languages"):
        assert signed_in.get(path).status_code in (404, 405), path

def test_the_settings_page_asks_for_no_key_but_the_mail_password(signed_in):
    page = signed_in.get("/settings").get_data(as_text=True)
    assert "TMDB" not in page and "TheTVDB key" not in page

def test_restoring_starts_a_refresh_so_details_come_back(signed_in, monkeypatch):
    started = []
    monkeypatch.setattr(sync, "start_now", lambda *a, **k: started.append(1) or True)
    plain = signed_in.get("/settings/export").data
    signed_in.post("/settings/import", data={
        "backup": (io.BytesIO(plain), "b.json"), "confirm": "replace",
    }, content_type="multipart/form-data")
    assert started

def test_a_running_refresh_shows_a_loading_card_and_a_status(signed_in, monkeypatch):
    from app import sync

    monkeypatch.setattr(sync, "_running", True)
    monkeypatch.setitem(sync._progress, "done", 12)
    monkeypatch.setitem(sync._progress, "total", 94)
    page = signed_in.get("/").get_data(as_text=True)
    assert "12 of 94 done." in page
    assert signed_in.get("/sync/status").get_json() == {"running": True, "done": 12, "total": 94}

def test_no_loading_card_when_nothing_is_running(signed_in):
    assert "loading-count" not in signed_in.get("/").get_data(as_text=True)
    assert signed_in.get("/sync/status").get_json()["running"] is False

def test_the_slow_first_load_card_shows_until_ok_is_pressed_and_comes_back_after_a_restore(signed_in):
    from app import secretstore, transfer

    assert "The first load can take a while" in signed_in.get("/").get_data(as_text=True)
    signed_in.post("/intro/ok")
    assert "The first load can take a while" not in signed_in.get("/").get_data(as_text=True)
    assert "intro_seen" in transfer.NOT_BACKED_UP

def test_first_sign_in_goes_to_a_page_that_picks_the_username_and_password(client):
    page = client.post("/login", data={"username": "admin", "password": "nextup"}, follow_redirects=True)
    assert page.request.path == "/setup"
    assert client.get("/").headers["Location"].endswith("/setup")
    bad = client.post("/setup", data={"username": "Charlie", "password": "short", "confirm": "short"})
    assert "at least 8" in bad.get_data(as_text=True)
    ok = client.post("/setup", data={"username": "Charlie", "password": "a-long-own-password", "confirm": "a-long-own-password"})
    assert ok.headers["Location"] == "/"
    assert client.get("/").status_code == 200
    client.post("/logout")
    again = client.post("/login", data={"username": "Charlie", "password": "a-long-own-password"})
    assert again.headers["Location"] == "/"

def test_watched_films_and_maybe_shows_never_synced_still_get_their_pictures(app, monkeypatch):
    seen = []
    monkeypatch.setattr(sync, "sync_movie", lambda movie_id: seen.append(("movie", movie_id)))
    monkeypatch.setattr(sync, "sync_show", lambda show_id, failed=None: seen.append(("show", show_id)))
    with app.app_context():
        db.execute("INSERT INTO movie (id, title) VALUES (1, 'Seen')")
        db.execute("INSERT INTO tracked_movie (movie_id, added_at, watched_at) VALUES (1, '2026-01-01', '2026-02-01')")
        db.execute("INSERT INTO show (id, name) VALUES (2, 'Maybe')")
        db.execute("INSERT INTO tracked_show (show_id, added_at, shortlist) VALUES (2, '2026-01-01', 1)")
        sync.sync_all(force=True)
    assert ("movie", 1) in seen and ("show", 2) in seen
