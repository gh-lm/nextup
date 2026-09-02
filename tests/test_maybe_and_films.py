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
        assert queries.to_watch() == []
        assert [row["id"] for row in queries.tracked_shows(shortlist=True)] == [700]
        assert queries.tracked_shows() == []


def test_following_a_show_puts_it_back_in_next_up(app):
    from app import queries

    with app.app_context():
        _seed_show(app, shortlist=0)
        assert len(queries.to_watch()) == 1
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

    signed_in.post("/show/700/maybe")
    with app.app_context():
        assert queries.show_list_state(700)["shortlist"] == 1

    signed_in.post("/show/700/maybe")
    with app.app_context():
        assert queries.show_list_state(700)["shortlist"] == 0


def _seed_film(app, film_id, title, digital=None, providers=None):
    from app import db

    db.execute(
        "INSERT OR REPLACE INTO movie (id, title, release_date, digital_release, providers)"
        " VALUES (?, ?, '2026-01-01', ?, ?)",
        (film_id, title, digital, providers),
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
        _seed_film(app, 801, "On a service now", providers="Netflix")
        _seed_film(app, 802, "Out for home viewing", digital=past)
        _seed_film(app, 803, "Still in cinemas", digital=future)
        _seed_film(app, 804, "No date at all")

        films = queries.films_by_state()
        ready = {row["id"] for row in films["ready"]}
        waiting = {row["id"] for row in films["waiting"]}
        assert ready == {801, 802}
        assert waiting == {803, 804}


def test_films_arriving_only_covers_the_window(app):
    from app import queries

    soon = (date.today() + timedelta(days=10)).isoformat()
    later = (date.today() + timedelta(days=200)).isoformat()
    with app.app_context():
        _seed_film(app, 811, "Soon", digital=soon)
        _seed_film(app, 812, "Much later", digital=later)
        assert [row["id"] for row in queries.films_arriving(days=60)] == [811]


def test_digital_release_prefers_a_uk_date():
    from app import tmdb

    payload = {
        "results": [
            {"iso_3166_1": "US", "release_dates": [
                {"type": 3, "release_date": "2026-01-01T00:00:00.000Z"},
                {"type": 4, "release_date": "2026-02-01T00:00:00.000Z"},
            ]},
            {"iso_3166_1": "GB", "release_dates": [
                {"type": 4, "release_date": "2026-03-15T00:00:00.000Z"},
            ]},
        ]
    }
    assert tmdb.digital_release_date(payload) == "2026-03-15"


def test_digital_release_ignores_cinema_dates():
    from app import tmdb

    payload = {"results": [
        {"iso_3166_1": "GB", "release_dates": [
            {"type": 3, "release_date": "2026-01-01T00:00:00.000Z"},
        ]},
    ]}
    assert tmdb.digital_release_date(payload) is None


def test_providers_read_the_uk_list_and_skip_rentals():
    from app import tmdb

    payload = {"results": {"GB": {
        "link": "https://www.themoviedb.org/movie/1/watch",
        "flatrate": [{"provider_name": "Netflix"}],
        "free": [{"provider_name": "ITVX"}],
        "rent": [{"provider_name": "Apple TV"}],
        "buy": [{"provider_name": "Amazon Video"}],
    }}}
    names, link = tmdb.uk_providers(payload)
    assert names == ["Netflix", "ITVX"]
    assert "themoviedb.org" in link


def test_pages_still_load_with_the_new_sections(signed_in, app):
    with app.app_context():
        _seed_show(app, shortlist=1)
        _seed_film(app, 821, "Something", providers="Netflix")
    for path in ["/maybe", "/movies", "/upcoming", "/movie/821", "/show/700"]:
        assert signed_in.get(path).status_code == 200, path
