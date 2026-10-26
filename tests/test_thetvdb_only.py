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
