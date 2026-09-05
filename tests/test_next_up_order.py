"""Next up is a run of everything that has come out and is still waiting.

One line per episode, not one per show, newest first, with films dropped in
at the date they reached home viewing.
"""
from datetime import date, timedelta


def _days_ago(n):
    return (date.today() - timedelta(days=n)).isoformat()


def _seed(app):
    from app import db

    # A show never started, whose only episode went out years ago.
    db.execute("INSERT OR REPLACE INTO show (id, name) VALUES (801, 'Old Thing')")
    db.execute(
        "INSERT OR REPLACE INTO tracked_show (show_id, added_at, shortlist)"
        " VALUES (801, '2026-01-01', 0)"
    )
    db.execute(
        "INSERT OR REPLACE INTO episode (id, show_id, season_number, episode_number,"
        " name, air_date) VALUES (8011, 801, 1, 1, 'Pilot', '2013-04-02')"
    )

    # A show three episodes deep, all of them still waiting.
    db.execute("INSERT OR REPLACE INTO show (id, name) VALUES (803, 'Behind Thing')")
    db.execute(
        "INSERT OR REPLACE INTO tracked_show (show_id, added_at, shortlist)"
        " VALUES (803, '2026-01-01', 0)"
    )
    for number, (title, when) in enumerate(
        [("Old One", _days_ago(60)), ("Old Two", _days_ago(40)), ("Just Aired", _days_ago(2))],
        start=1,
    ):
        db.execute(
            "INSERT OR REPLACE INTO episode (id, show_id, season_number, episode_number,"
            " name, air_date) VALUES (?, 803, 2, ?, ?, ?)",
            (8030 + number, number, title, when),
        )

    # A film that reached home viewing yesterday, and one still weeks away.
    db.execute(
        "INSERT OR REPLACE INTO movie (id, title, digital_release) VALUES (901, 'A Film', ?)",
        (_days_ago(1),),
    )
    db.execute(
        "INSERT OR REPLACE INTO tracked_movie (movie_id, added_at, shortlist)"
        " VALUES (901, '2026-01-01', 0)"
    )
    db.execute(
        "INSERT OR REPLACE INTO movie (id, title, digital_release) VALUES (902, 'Later Film', ?)",
        ((date.today() + timedelta(days=30)).isoformat(),),
    )
    db.execute(
        "INSERT OR REPLACE INTO tracked_movie (movie_id, added_at, shortlist)"
        " VALUES (902, '2026-01-01', 0)"
    )


def test_every_waiting_episode_gets_its_own_line(app):
    from app import queries

    with app.app_context():
        _seed(app)
        result = queries.ready_to_watch()
        names = [
            item["episode"]["name"]
            for item in result["rows"]
            if item["kind"] == "episode" and item["show_name"] == "Behind Thing"
        ]
        assert names == ["Just Aired", "Old Two", "Old One"]


def test_newest_first_puts_what_just_landed_at_the_top(app):
    from app import queries

    with app.app_context():
        _seed(app)
        items = queries.ready_to_watch("newest")["rows"]
        dates = [item["date"] for item in items]
        assert dates == sorted(dates, reverse=True)
        assert items[0]["kind"] == "film"
        assert items[0]["film"]["title"] == "A Film"
        assert items[-1]["kind"] == "episode"
        assert items[-1]["episode"]["name"] == "Pilot"


def test_oldest_first_reverses_it(app):
    from app import queries

    with app.app_context():
        _seed(app)
        items = queries.ready_to_watch("oldest")["rows"]
        assert items[0]["episode"]["name"] == "Pilot"


def test_films_still_to_come_are_left_out(app):
    from app import queries

    with app.app_context():
        _seed(app)
        titles = [
            item["film"]["title"]
            for item in queries.ready_to_watch()["rows"]
            if item["kind"] == "film"
        ]
        assert titles == ["A Film"]


def test_watched_episodes_drop_off_the_list(app):
    from app import db, queries

    with app.app_context():
        _seed(app)
        db.execute(
            "INSERT INTO watched_episode (episode_id, show_id, watched_at)"
            " VALUES (8033, 803, '2026-01-02')"
        )
        names = [
            item["episode"]["name"]
            for item in queries.ready_to_watch()["rows"]
            if item["kind"] == "episode"
        ]
        assert "Just Aired" not in names
        assert "Old Two" in names


def test_how_far_behind_is_carried_once_per_show(app):
    from app import queries

    with app.app_context():
        _seed(app)
        leads = [
            item["episode"]["name"]
            for item in queries.ready_to_watch()["rows"]
            if item["kind"] == "episode" and item["lead"]
        ]
        # The newest line for each show, and no repeats below it.
        assert leads == ["Just Aired", "Pilot"]


def test_long_lists_are_paged(app):
    from app import queries

    with app.app_context():
        _seed(app)
        first = queries.ready_to_watch(per_page=2)
        assert first["total"] == 5
        assert first["pages"] == 3
        assert len(first["rows"]) == 2
        assert (first["first"], first["last"]) == (1, 2)

        second = queries.ready_to_watch(per_page=2, page=2)
        assert (second["first"], second["last"]) == (3, 4)
        assert second["rows"][0]["date"] <= first["rows"][-1]["date"]

        # Asking beyond the end lands on the last page rather than an empty one.
        assert queries.ready_to_watch(per_page=2, page=99)["page"] == 3


def test_the_dashboard_lists_films_and_episodes_together(signed_in, app):
    with app.app_context():
        _seed(app)
    page = signed_in.get("/").get_data(as_text=True)
    assert "A Film" in page
    assert "Just Aired" in page
    assert "Old Two" in page
    assert "Later Film" not in page


def test_the_dashboard_offers_a_catch_up_button(signed_in, app):
    with app.app_context():
        _seed(app)
    page = signed_in.get("/").get_data(as_text=True)
    assert "Up to here" in page
    assert "/show/803/watch-through/8033" in page
