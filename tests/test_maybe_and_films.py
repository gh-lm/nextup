from datetime import date, timedelta

def _seed_show(app, shortlist=0):
    from app import db

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    db.execute("INSERT OR REPLACE INTO show (id, name) VALUES (700, 'Curious Thing')")
    db.execute(
        "INSERT OR REPLACE INTO tracked_show (show_id, added_at, shortlist)"
        " VALUES (700, '2026-01-01', ?)",
        (shortlist,),
    )
    db.execute(
        "INSERT OR REPLACE INTO episode (id, show_id, season_number, episode_number,"
        " name, air_date) VALUES (7001, 700, 1, 1, 'One', ?)",
        (yesterday,),
    )

def test_maybe_shows_stay_out_of_next_up(app):
    from app import queries

    with app.app_context():
        _seed_show(app, shortlist=1)
        assert queries.ready_to_watch()["rows"] == []
        assert [row["id"] for row in queries.tracked_shows(shortlist=True)] == [700]
        assert queries.tracked_shows() == []

def test_following_a_show_puts_it_back_in_next_up(app):
    from app import queries

    with app.app_context():
        _seed_show(app, shortlist=0)
        assert len(queries.ready_to_watch()["rows"]) == 1
        assert queries.tracked_shows(shortlist=True) == []

def test_maybe_shows_are_not_in_the_calendar(app):
    from app import queries

    with app.app_context():
        _seed_show(app, shortlist=1)
        start = (date.today() - timedelta(days=7)).isoformat()
        end = (date.today() + timedelta(days=7)).isoformat()
        assert queries.episodes_between(start, end) == []

def test_toggle_moves_a_show_between_the_two_lists(signed_in, app):
    from app import queries

    with app.app_context():
        _seed_show(app, shortlist=0)

    signed_in.post("/show/700/maybe", data={"maybe": "1"})
    with app.app_context():
        assert queries.show_list_state(700)["shortlist"] == 1

    signed_in.post("/show/700/maybe", data={"maybe": "0"})
    with app.app_context():
        assert queries.show_list_state(700)["shortlist"] == 0

def _seed_film(app, film_id, title, released=None):
    from app import db

    db.execute(
        "INSERT OR REPLACE INTO movie (id, title, release_date) VALUES (?, ?, ?)",
        (film_id, title, released),
    )
    db.execute(
        "INSERT OR REPLACE INTO tracked_movie (movie_id, added_at) VALUES (?, '2026-01-01')",
        (film_id,),
    )

def test_films_split_by_whether_you_can_watch_them(app):
    from app import queries

    future = (date.today() + timedelta(days=30)).isoformat()
    past = (date.today() - timedelta(days=30)).isoformat()
    with app.app_context():
        _seed_film(app, 802, "Already out", released=past)
        _seed_film(app, 803, "Not out yet", released=future)
        _seed_film(app, 804, "No date at all")

        films = queries.films_by_state()
        ready = {row["id"] for row in films["ready"]}
        waiting = {row["id"] for row in films["waiting"]}
        assert ready == {802}
        assert waiting == {803, 804}

def test_films_arriving_only_covers_the_window(app):
    from app import queries

    soon = (date.today() + timedelta(days=10)).isoformat()
    later = (date.today() + timedelta(days=200)).isoformat()
    with app.app_context():
        _seed_film(app, 811, "Soon", released=soon)
        _seed_film(app, 812, "Much later", released=later)
        assert [row["id"] for row in queries.films_arriving(days=60)] == [811]

def test_pages_still_load_with_the_new_sections(signed_in, app):
    with app.app_context():
        _seed_show(app, shortlist=1)
        _seed_film(app, 821, "Something")
    for path in ["/maybe", "/movies", "/upcoming", "/movie/821", "/show/700"]:
        assert signed_in.get(path).status_code == 200, path

def test_the_dashboard_coming_soon_panel_lists_films_with_the_episodes(signed_in, app):
    with app.app_context():
        _seed_show(app)
        _seed_film(app, 830, "Soon Film", released=(date.today() + timedelta(days=3)).isoformat())
    page = signed_in.get("/").get_data(as_text=True)
    assert "Soon Film" in page and "Movie · " in page

def test_the_coming_soon_page_puts_films_on_their_day_among_the_episodes(signed_in, app):
    soon = (date.today() + timedelta(days=3)).isoformat()
    with app.app_context():
        _seed_film(app, 831, "Same Day Film", released=soon)
    page = signed_in.get("/upcoming").get_data(as_text=True)
    assert "Same Day Film" in page
    assert "Movies landing" not in page
