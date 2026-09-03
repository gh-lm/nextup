from datetime import date, timedelta


def _seed(app):
    from app import db

    today = date.today()
    db.execute("INSERT OR REPLACE INTO show (id, name) VALUES (400, 'A Show')")
    db.execute("INSERT OR REPLACE INTO tracked_show (show_id, added_at) VALUES (400, '2026-01-01')")
    db.execute(
        "INSERT OR REPLACE INTO episode (id, show_id, season_number, episode_number, name, air_date)"
        " VALUES (4001, 400, 1, 1, 'One', ?)",
        (today.isoformat(),),
    )
    films = [
        (410, "In the window", today.isoformat(), 0, None),
        (411, "Outside the window", (today + timedelta(days=90)).isoformat(), 0, None),
        (412, "No date at all", None, 0, None),
        (413, "On the maybe list", today.isoformat(), 1, None),
        (414, "Already seen", today.isoformat(), 0, "2026-01-01"),
    ]
    for film_id, title, digital, shortlist, watched in films:
        db.execute(
            "INSERT OR REPLACE INTO movie (id, title, digital_release) VALUES (?, ?, ?)",
            (film_id, title, digital),
        )
        db.execute(
            "INSERT OR REPLACE INTO tracked_movie (movie_id, added_at, shortlist, watched_at)"
            " VALUES (?, '2026-01-01', ?, ?)",
            (film_id, shortlist, watched),
        )


def test_films_between_covers_the_window_only(app):
    from app import queries

    with app.app_context():
        _seed(app)
        start = (date.today() - timedelta(days=3)).isoformat()
        end = (date.today() + timedelta(days=3)).isoformat()
        found = {row["id"] for row in queries.films_between(start, end)}
        # In the window and on the main list, watched or not.
        assert found == {410, 414}


def test_maybe_films_stay_off_the_calendar(app):
    from app import queries

    with app.app_context():
        _seed(app)
        start = (date.today() - timedelta(days=3)).isoformat()
        end = (date.today() + timedelta(days=3)).isoformat()
        assert 413 not in {row["id"] for row in queries.films_between(start, end)}


def test_a_film_with_no_streaming_date_is_not_placed(app):
    from app import queries

    with app.app_context():
        _seed(app)
        start = "2000-01-01"
        end = "2099-01-01"
        assert 412 not in {row["id"] for row in queries.films_between(start, end)}


def test_the_calendar_page_shows_both_kinds(signed_in, app):
    with app.app_context():
        _seed(app)
    body = signed_in.get("/calendar").data.decode()
    assert "A Show" in body
    assert "In the window" in body
    assert "cal-film" in body
    # The difference must not rest on colour alone.
    assert "<small>Film" in body


def test_a_watched_film_is_faded_not_hidden(signed_in, app):
    with app.app_context():
        _seed(app)
    body = signed_in.get("/calendar").data.decode()
    assert "Already seen" in body
    assert "cal-ep cal-film done" in body
