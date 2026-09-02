from datetime import date, timedelta


def _seed(app):
    from app import db

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    db.execute("INSERT OR REPLACE INTO show (id, name) VALUES (900, 'Test Show')")
    db.execute("INSERT OR REPLACE INTO tracked_show (show_id, added_at) VALUES (900, '2026-01-01')")
    rows = [
        (9001, 900, 1, 1, "One", None, yesterday, 45, None),
        (9002, 900, 1, 2, "Two", None, yesterday, 45, None),
        (9003, 900, 1, 3, "Three", None, tomorrow, 45, None),
        (9000, 900, 0, 1, "A special", None, yesterday, 20, None),
    ]
    conn = db.get_db()
    conn.executemany(
        "INSERT OR REPLACE INTO episode (id, show_id, season_number, episode_number,"
        " name, overview, air_date, runtime, still_path) VALUES (?,?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()


def test_progress_ignores_specials_and_unaired(app):
    from app import queries

    with app.app_context():
        _seed(app)
        progress = queries.show_progress(900)
        assert progress["aired"] == 2
        assert progress["total"] == 3
        assert progress["watched"] == 0
        assert progress["remaining"] == 2


def test_next_unwatched_is_the_earliest_aired(app):
    from app import queries

    with app.app_context():
        _seed(app)
        episode = queries.next_unwatched(900)
        assert episode["episode_number"] == 1
        assert episode["season_number"] == 1


def test_watch_through_ticks_everything_before_it(signed_in, app):
    from app import queries

    with app.app_context():
        _seed(app)

    signed_in.post("/show/900/watch-through/9002")

    with app.app_context():
        progress = queries.show_progress(900)
        assert progress["watched"] == 2
        assert progress["complete"] is True
        # The unaired episode must not have been ticked.
        assert queries.next_unwatched(900) is None


def test_next_airing_looks_forward_only(app):
    from app import queries

    with app.app_context():
        _seed(app)
        episode = queries.next_airing(900)
        assert episode["episode_number"] == 3
