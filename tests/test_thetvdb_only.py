"""TheTVDB is the only source: older numbers resolve to it, and nothing of TMDB is left to reach."""
import io
import json

import pytest

from app import catalog, db, sync, transfer, tvdb

def test_an_older_number_with_no_match_says_so(app, monkeypatch):
    monkeypatch.setattr(tvdb, "find_by_tmdb", lambda number, kind: None)
    catalog._legacy.clear()
    with app.app_context():
        with pytest.raises(tvdb.TvdbError):
            catalog.show(1234)

def test_a_new_id_goes_straight_to_thetvdb(app, monkeypatch):
    seen = []
    monkeypatch.setattr(tvdb, "show", lambda show_id: seen.append(show_id) or {"id": show_id, "name": "X"})
    monkeypatch.setattr(tvdb, "find_by_tmdb", lambda *a: pytest.fail("looked up a number that needed no lookup"))
    with app.app_context():
        assert catalog.show(tvdb.internal(5))["id"] == tvdb.internal(5)
    assert seen == [tvdb.internal(5)]

def test_an_older_number_keeps_its_own_id_and_its_episode_ids(app, monkeypatch):
    catalog._legacy.clear()
    monkeypatch.setattr(tvdb, "find_by_tmdb", lambda number, kind: tvdb.internal(77))
    monkeypatch.setattr(tvdb, "season", lambda show_id, n: {"season_number": n, "episodes": [
        {"id": tvdb.internal(900), "season_number": 1, "episode_number": 1}]})
    with app.app_context():
        db.execute("INSERT INTO show (id, name) VALUES (42, 'Old')")
        db.execute("INSERT INTO episode (id, show_id, season_number, episode_number) VALUES (5, 42, 1, 1)")
        assert catalog.season(42, 1)["episodes"][0]["id"] == 5

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

def test_an_old_backup_with_a_tmdb_key_restores_without_it(app, monkeypatch):
    monkeypatch.setattr(sync, "start_now", lambda *a, **k: True)
    old = {
        "format": "nextup-backup", "version": 1,
        "data": {
            "show": [{"id": 3, "name": "A", "overview": "long text", "poster_path": "/old.jpg"}],
            "tracked_show": [{"show_id": 3, "added_at": "2026-01-01"}],
            "settings": {"accent": "teal", "source_first": "tmdb", "country": "GB"},
            "secrets": {"tmdb_api_key": "old-key", "smtp_password": "mail-pass"},
        },
    }
    with app.app_context():
        transfer.import_data(json.loads(json.dumps(old)))
        row = db.query("SELECT overview, poster_path FROM show WHERE id = 3", one=True)
        assert row["overview"] is None and row["poster_path"] is None
        keys = {r["key"] for r in db.query("SELECT key FROM settings")}
        assert keys == {"accent", "smtp_password"}

def test_restoring_starts_a_refresh_so_details_come_back(signed_in, monkeypatch):
    started = []
    monkeypatch.setattr(sync, "start_now", lambda *a, **k: started.append(1) or True)
    plain = signed_in.get("/settings/export").data
    signed_in.post("/settings/import", data={
        "backup": (io.BytesIO(plain), "b.json"), "confirm": "replace",
    }, content_type="multipart/form-data")
    assert started

def test_an_older_number_only_matches_a_record_listed_under_it(monkeypatch):
    def fake(path, params=None, tries=3):
        if path.startswith("/search/remoteid/"):
            return [{"series": {"id": 10}}, {"series": {"id": 11}}]
        return {"remoteIds": [{"sourceName": "TheMovieDB.com", "id": "1396" if "/11/" in path else "5"}]}

    monkeypatch.undo()
    monkeypatch.setattr(tvdb, "_get", fake)
    assert tvdb.find_by_tmdb(1396, "tv") == tvdb.internal(11)
    assert tvdb.find_by_tmdb(77, "tv") is None

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

def test_an_older_show_with_no_number_match_is_found_by_its_exact_title(app, monkeypatch):
    catalog._legacy.clear()
    monkeypatch.setattr(tvdb, "find_by_tmdb", lambda number, kind: None)
    monkeypatch.setattr(tvdb, "_get", lambda path, params=None, tries=3: [
        {"type": "series", "tvdb_id": "480102", "name": "Benidorm Is Murder"},
        {"type": "series", "tvdb_id": "9", "name": "Benidorm Is Murder Too"}])
    with app.app_context():
        db.execute("INSERT INTO show (id, name) VALUES (328804, 'Benidorm Is Murder')")
        assert catalog._twin(328804, "tv") == tvdb.internal(480102)

def test_two_exact_title_matches_are_not_guessed_between(monkeypatch):
    monkeypatch.setattr(tvdb, "_get", lambda path, params=None, tries=3: [
        {"type": "series", "tvdb_id": "1", "name": "Betrayal"},
        {"type": "series", "tvdb_id": "2", "name": "Betrayal"}])
    assert tvdb.find_by_name("Betrayal", "tv") is None

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
