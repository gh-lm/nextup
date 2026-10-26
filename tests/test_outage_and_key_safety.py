"""A TheTVDB outage must not cost the user data, and error messages must stay plain."""
import pytest
import requests

def test_a_network_error_never_carries_the_address_it_failed_on(app, monkeypatch):
    from app import tvdb

    monkeypatch.setattr(tvdb, "RELAY_URL", "https://relay.example.com")
    monkeypatch.setattr(tvdb.time, "sleep", lambda *_: None)

    def fail(url, params=None, timeout=None, headers=None):
        raise requests.ConnectionError(f"HTTPSConnectionPool: {url}?token=abc123")

    monkeypatch.setattr(tvdb.requests, "get", fail)
    with app.app_context():
        with pytest.raises(tvdb.TvdbError) as caught:
            tvdb._get("/movies/1")
    assert "abc123" not in str(caught.value)
    assert "abc123" not in repr(caught.value.__cause__)
    assert caught.value.__suppress_context__

def _season(number):
    return {"season_number": number, "episodes": [
        {"id": 9000 + number, "season_number": number, "episode_number": 1, "name": "x", "air_date": "2026-01-01"}
    ]}

def test_a_show_is_not_marked_fresh_while_a_season_is_missing(app, monkeypatch):
    from app import db, sync, tvdb

    payload = {"id": 500, "name": "Patchy", "seasons": [{"season_number": 1}, {"season_number": 2}]}
    monkeypatch.setattr(tvdb, "show", lambda show_id: payload)

    def season(show_id, number):
        if number == 2:
            raise tvdb.TvdbError("TheTVDB returned 500.")
        return _season(number)

    monkeypatch.setattr(tvdb, "season", season)
    with app.app_context():
        failed = []
        sync.sync_show(500, failed)
        assert failed == [2]
        assert db.query("SELECT synced_at FROM show WHERE id = 500", one=True)["synced_at"] is None

        monkeypatch.setattr(tvdb, "season", lambda show_id, number: _season(number))
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
