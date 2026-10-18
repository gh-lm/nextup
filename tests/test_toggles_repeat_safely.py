"""Buttons send the state they want, so pressing one twice changes nothing more."""

def _seed(app):
    from app import db

    db.execute("INSERT INTO show (id, name) VALUES (710, 'Twice')")
    db.execute("INSERT INTO tracked_show (show_id, added_at) VALUES (710, '2026-01-01')")
    db.execute(
        "INSERT INTO episode (id, show_id, season_number, episode_number, name, air_date)"
        " VALUES (7101, 710, 1, 1, 'One', '2020-01-01')"
    )
    db.execute("INSERT INTO movie (id, title) VALUES (711, 'Twice Film')")
    db.execute("INSERT INTO tracked_movie (movie_id, added_at) VALUES (711, '2026-01-01')")

def _watched(app):
    from app import db

    return db.query("SELECT COUNT(*) AS n FROM watched_episode WHERE episode_id = 7101", one=True)["n"]

def test_marking_an_episode_watched_twice_leaves_it_watched(signed_in, app):
    with app.app_context():
        _seed(app)
    signed_in.post("/episode/7101/watch", data={"to": "1"})
    signed_in.post("/episode/7101/watch", data={"to": "1"})
    with app.app_context():
        assert _watched(app) == 1
    signed_in.post("/episode/7101/watch", data={"to": "0"})
    signed_in.post("/episode/7101/watch", data={"to": "0"})
    with app.app_context():
        assert _watched(app) == 0

def test_a_film_marked_watched_twice_stays_watched(signed_in, app):
    from app import db

    with app.app_context():
        _seed(app)
    signed_in.post("/movie/711/watched", data={"to": "1"})
    signed_in.post("/movie/711/watched", data={"to": "1"})
    with app.app_context():
        assert db.query("SELECT watched_at FROM tracked_movie WHERE movie_id = 711", one=True)["watched_at"]

def test_favourite_and_archive_repeat_safely(signed_in, app):
    from app import queries

    with app.app_context():
        _seed(app)
    for _ in range(2):
        signed_in.post("/show/710/favourite", data={"to": "1"})
        signed_in.post("/show/710/archive", data={"to": "1"})
    with app.app_context():
        state = queries.show_list_state(710)
        assert state["favourite"] == 1 and state["archived"] == 1

def test_a_toggle_without_a_wanted_state_is_refused(signed_in, app):
    with app.app_context():
        _seed(app)
    assert signed_in.post("/episode/7101/watch").status_code == 400
    assert signed_in.post("/movie/711/watched", data={"to": "maybe"}).status_code == 400
