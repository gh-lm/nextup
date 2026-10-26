from datetime import date, timedelta

import pytest

def _seed_show_with_episodes(app):
    from app import db

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    db.execute("INSERT OR REPLACE INTO show (id, name) VALUES (600, 'A Series')")
    conn = db.get_db()
    conn.executemany(
        "INSERT OR REPLACE INTO episode (id, show_id, season_number, episode_number,"
        " name, overview, air_date, runtime) VALUES (?,?,?,?,?,?,?,?)",
        [
            (6001, 600, 1, 1, "First", "It begins.", yesterday, 50),
            (6002, 600, 1, 2, "Second", "It continues.", yesterday, 50),
            (6003, 600, 2, 1, "Third", None, yesterday, 50),
        ],
    )
    conn.commit()
    db.execute("INSERT OR REPLACE INTO tracked_show (show_id, added_at) VALUES (600, '2026-01-01')")

def _no_key(*a, **k):
    from app import tvdb

    raise tvdb.TvdbError("no key")

def test_episode_page_shows_what_is_stored(signed_in, app, monkeypatch):
    from app import tvdb

    monkeypatch.setattr(tvdb, "episode", _no_key)
    with app.app_context():
        _seed_show_with_episodes(app)

    resp = signed_in.get("/episode/6002")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "Second" in body
    assert "It continues." in body
    assert "S01E02" in body

def test_episode_page_links_to_its_neighbours(signed_in, app, monkeypatch):
    from app import queries, tvdb

    monkeypatch.setattr(tvdb, "episode", _no_key)
    with app.app_context():
        _seed_show_with_episodes(app)
        previous, following = queries.episode_neighbours(600, 1, 2)
        assert previous["id"] == 6001
        assert following["id"] == 6003

    body = signed_in.get("/episode/6002").data.decode()
    assert "/episode/6001" in body
    assert "/episode/6003" in body

def test_episode_page_survives_thetvdb_being_down(signed_in, app, monkeypatch):
    from app import tvdb

    def boom(*a, **k):
        raise tvdb.TvdbError("TheTVDB is unreachable")

    monkeypatch.setattr(tvdb, "episode", boom)
    with app.app_context():
        _seed_show_with_episodes(app)
    assert signed_in.get("/episode/6001").status_code == 200

def test_unknown_episode_is_a_404(signed_in):
    assert signed_in.get("/episode/999999").status_code == 404

def test_maybe_films_stay_out_of_the_films_page(app):
    from app import db, queries

    with app.app_context():
        db.execute("INSERT OR REPLACE INTO movie (id, title, release_date) VALUES (901, 'A Film', '2020-01-01')")
        db.execute(
            "INSERT OR REPLACE INTO tracked_movie (movie_id, added_at, shortlist)"
            " VALUES (901, '2026-01-01', 1)"
        )
        films = queries.films_by_state()
        assert films["ready"] == []
        assert films["waiting"] == []
        assert [row["id"] for row in films["maybe"]] == [901]
