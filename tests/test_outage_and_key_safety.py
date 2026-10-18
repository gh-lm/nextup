"""A TMDB outage must not cost the user data, and the API key must stay private."""
import pytest
import requests

def test_a_network_error_never_carries_the_api_key(app, monkeypatch):
    from app import tmdb

    secret = "k3y-that-must-not-leak"
    monkeypatch.setattr(tmdb, "api_key", lambda: secret)
    monkeypatch.setattr(tmdb.time, "sleep", lambda *_: None)

    def fail(url, params=None, timeout=None):
        raise requests.ConnectionError(f"HTTPSConnectionPool: {url}?api_key={secret}")

    monkeypatch.setattr(tmdb.requests, "get", fail)
    with app.app_context():
        with pytest.raises(tmdb.TmdbError) as caught:
            tmdb._get("/movie/1")
        with pytest.raises(tmdb.TmdbError) as checked:
            tmdb.verify_key(secret)
    for exc in (caught.value, checked.value):
        assert secret not in str(exc)
        assert secret not in repr(exc.__cause__)
        assert exc.__suppress_context__

def test_an_outage_leaves_the_saved_streaming_services_alone(app, monkeypatch):
    from app import db, sync, tmdb

    with app.app_context():
        db.execute(
            "INSERT INTO movie (id, title, digital_release, providers) VALUES (401, 'Kept', '2026-01-01', 'Netflix')"
        )

        def down(movie_id):
            raise tmdb.TmdbError("Could not reach TMDB (ConnectionError).")

        monkeypatch.setattr(tmdb, "movie_release_dates", down)
        monkeypatch.setattr(tmdb, "movie_providers", down)
        with pytest.raises(tmdb.TmdbError):
            sync.sync_movie_availability(401)
        row = db.query("SELECT digital_release, providers FROM movie WHERE id = 401")[0]
    assert row["providers"] == "Netflix"
    assert row["digital_release"] == "2026-01-01"

def _season(number):
    return {"season_number": number, "episodes": [
        {"id": 9000 + number, "season_number": number, "episode_number": 1, "name": "x", "air_date": "2026-01-01"}
    ]}

def test_a_show_is_not_marked_fresh_while_a_season_is_missing(app, monkeypatch):
    from app import db, sync, tmdb

    payload = {"id": 500, "name": "Patchy", "seasons": [{"season_number": 1}, {"season_number": 2}]}
    monkeypatch.setattr(tmdb, "show", lambda show_id: payload)

    def season(show_id, number):
        if number == 2:
            raise tmdb.TmdbError("TMDB returned 500.")
        return _season(number)

    monkeypatch.setattr(tmdb, "season", season)
    with app.app_context():
        failed = []
        sync.sync_show(500, failed)
        assert failed == [2]
        assert db.query("SELECT synced_at FROM show WHERE id = 500", one=True)["synced_at"] is None

        monkeypatch.setattr(tmdb, "season", lambda show_id, number: _season(number))
        failed = []
        sync.sync_show(500, failed)
        assert failed == []
        assert db.query("SELECT synced_at FROM show WHERE id = 500", one=True)["synced_at"]

def test_old_sync_history_holding_a_key_is_scrubbed_on_start(data_dir):
    from app import db

    db.init_db()
    conn = db.connect()
    conn.execute(
        "INSERT INTO sync_run (started_at, status, message) VALUES ('2026-01-01', 'error',"
        " 'Show: https://api.themoviedb.org/3/tv/1?api_key=abc123')"
    )
    conn.commit()
    conn.close()
    db.init_db()
    conn = db.connect()
    message = conn.execute("SELECT message FROM sync_run").fetchone()[0]
    conn.close()
    assert "abc123" not in message
