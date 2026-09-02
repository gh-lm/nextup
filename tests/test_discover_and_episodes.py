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


def test_episode_page_shows_what_is_stored(signed_in, app, monkeypatch):
    from app import tmdb

    monkeypatch.setattr(tmdb, "episode", lambda *a, **k: (_ for _ in ()).throw(tmdb.MissingKey("no key")))
    with app.app_context():
        _seed_show_with_episodes(app)

    resp = signed_in.get("/episode/6002")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "Second" in body
    assert "It continues." in body
    assert "S01E02" in body


def test_episode_page_links_to_its_neighbours(signed_in, app, monkeypatch):
    from app import queries, tmdb

    monkeypatch.setattr(tmdb, "episode", lambda *a, **k: (_ for _ in ()).throw(tmdb.MissingKey("no key")))
    with app.app_context():
        _seed_show_with_episodes(app)
        previous, following = queries.episode_neighbours(600, 1, 2)
        assert previous["id"] == 6001
        assert following["id"] == 6003

    body = signed_in.get("/episode/6002").data.decode()
    assert "/episode/6001" in body
    assert "/episode/6003" in body


def test_episode_page_survives_tmdb_being_down(signed_in, app, monkeypatch):
    from app import tmdb

    def boom(*a, **k):
        raise tmdb.TmdbError("TMDB is unreachable")

    monkeypatch.setattr(tmdb, "episode", boom)
    with app.app_context():
        _seed_show_with_episodes(app)
    assert signed_in.get("/episode/6001").status_code == 200


def test_unknown_episode_is_a_404(signed_in):
    assert signed_in.get("/episode/999999").status_code == 404


def test_saying_no_hides_a_show_from_discover(signed_in, app):
    from app import queries

    signed_in.post("/discover/show/1234/no")
    with app.app_context():
        assert queries.is_dismissed("tv", 1234)
        assert 1234 in queries.dismissed_ids("tv")
        # Films are a separate list.
        assert queries.dismissed_ids("movie") == set()


def test_restore_brings_dismissed_items_back(signed_in, app):
    from app import queries

    signed_in.post("/discover/show/11/no")
    signed_in.post("/discover/film/22/no")
    signed_in.post("/discover/restore", data={"kind": "tv"})
    with app.app_context():
        assert queries.dismissed_ids("tv") == set()
        assert queries.dismissed_ids("movie") == {22}

    signed_in.post("/discover/restore")
    with app.app_context():
        assert queries.dismissed_ids("movie") == set()


def _fake_sync_show(monkeypatch):
    """Stand in for the TMDB fetch, writing the show row the real one writes."""
    from app import db, sync

    def fake(show_id):
        db.execute(
            "INSERT OR REPLACE INTO show (id, name) VALUES (?, ?)",
            (show_id, f"Show {show_id}"),
        )
        return f"Show {show_id}"

    monkeypatch.setattr(sync, "sync_show", fake)


def test_yes_and_maybe_put_a_show_on_the_right_list(signed_in, app, monkeypatch):
    from app import queries

    _fake_sync_show(monkeypatch)

    signed_in.post("/discover/show/600/yes")
    with app.app_context():
        assert queries.show_list_state(600)["shortlist"] == 0

    signed_in.post("/discover/show/601/maybe")
    with app.app_context():
        assert queries.show_list_state(601)["shortlist"] == 1


def test_adding_something_clears_its_dismissal(signed_in, app, monkeypatch):
    from app import queries

    _fake_sync_show(monkeypatch)
    signed_in.post("/discover/show/700/no")
    with app.app_context():
        assert queries.is_dismissed("tv", 700)

    signed_in.post("/discover/show/700/yes")
    with app.app_context():
        assert not queries.is_dismissed("tv", 700)


def test_maybe_films_stay_out_of_the_films_page(app):
    from app import db, queries

    with app.app_context():
        db.execute("INSERT OR REPLACE INTO movie (id, title, providers) VALUES (901, 'A Film', 'Netflix')")
        db.execute(
            "INSERT OR REPLACE INTO tracked_movie (movie_id, added_at, shortlist)"
            " VALUES (901, '2026-01-01', 1)"
        )
        films = queries.films_by_state()
        assert films["ready"] == []
        assert films["waiting"] == []
        assert [row["id"] for row in films["maybe"]] == [901]


def test_discover_pages_explain_a_missing_key(signed_in):
    for path in ["/discover/films", "/discover/tv"]:
        resp = signed_in.get(path)
        assert resp.status_code == 200, path
        assert b"No TMDB API key saved" in resp.data, path


def test_an_unknown_decision_is_rejected(signed_in):
    assert signed_in.post("/discover/show/1/sideways").status_code == 404
    assert signed_in.post("/discover/film/1/sideways").status_code == 404
