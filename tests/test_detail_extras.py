"""The helpers that turn a TMDB payload into what a detail page shows."""


def test_cast_reads_a_film_credit():
    from app import tmdb

    payload = {"credits": {"cast": [
        {"name": "A Performer", "character": "The Lead", "profile_path": "/abc.jpg"},
        {"name": "Another", "character": "The Friend", "profile_path": None},
    ]}}
    cast = tmdb.cast_from(payload)
    assert [p["name"] for p in cast] == ["A Performer", "Another"]
    assert cast[0]["role"] == "The Lead"
    assert cast[1]["profile_path"] is None


def test_cast_reads_a_shows_roles_across_seasons():
    from app import tmdb

    payload = {"aggregate_credits": {"cast": [
        {"name": "A Performer", "roles": [{"character": "The Lead"}], "profile_path": None},
    ]}}
    assert tmdb.cast_from(payload)[0]["role"] == "The Lead"


def test_cast_is_capped():
    from app import tmdb

    payload = {"credits": {"cast": [
        {"name": f"Person {i}", "character": "Someone"} for i in range(40)
    ]}}
    assert len(tmdb.cast_from(payload, limit=14)) == 14


def test_crew_keeps_only_the_jobs_worth_naming():
    from app import tmdb

    payload = {"credits": {"crew": [
        {"name": "A Director", "job": "Director"},
        {"name": "A Writer", "job": "Screenplay"},
        {"name": "Someone", "job": "Best Boy"},
        {"name": "A Director", "job": "Director"},
    ]}}
    crew = tmdb.crew_from(payload)
    assert [p["name"] for p in crew] == ["A Director", "A Writer"]


def test_trailer_prefers_youtube_and_never_embeds():
    from app import tmdb

    payload = {"videos": {"results": [
        {"site": "Vimeo", "type": "Trailer", "key": "nope"},
        {"site": "YouTube", "type": "Trailer", "key": "abc123", "name": "Official Trailer"},
    ]}}
    trailer = tmdb.trailer_from(payload)
    assert trailer["url"] == "https://www.youtube.com/watch?v=abc123"


def test_no_trailer_is_not_an_error():
    from app import tmdb

    assert tmdb.trailer_from({}) is None
    assert tmdb.trailer_from({"videos": {"results": []}}) is None


def test_certification_prefers_the_uk_rating():
    from app import tmdb

    show = {"content_ratings": {"results": [
        {"iso_3166_1": "US", "rating": "TV-MA"},
        {"iso_3166_1": "GB", "rating": "15"},
    ]}}
    assert tmdb.certification_from(show) == "15"

    film = {"release_dates": {"results": [
        {"iso_3166_1": "US", "release_dates": [{"certification": "R"}]},
        {"iso_3166_1": "GB", "release_dates": [{"certification": "12A"}]},
    ]}}
    assert tmdb.certification_from(film) == "12A"


def test_certification_falls_back_when_there_is_no_uk_one():
    from app import tmdb

    payload = {"content_ratings": {"results": [{"iso_3166_1": "US", "rating": "TV-14"}]}}
    assert tmdb.certification_from(payload) == "TV-14"


def test_imdb_link_from_either_shape():
    from app import tmdb

    assert tmdb.imdb_from({"imdb_id": "tt1234567"}).endswith("tt1234567/")
    assert tmdb.imdb_from({"external_ids": {"imdb_id": "tt7654321"}}).endswith("tt7654321/")
    assert tmdb.imdb_from({}) is None


def test_genres_and_creators():
    from app import tmdb

    payload = {
        "genres": [{"name": "Drama"}, {"name": "Crime"}],
        "created_by": [{"name": "Someone"}, {"id": 2}],
    }
    assert tmdb.genres_from(payload) == ["Drama", "Crime"]
    assert tmdb.creators_from(payload) == ["Someone"]


def test_providers_read_from_an_appended_block():
    from app import tmdb

    payload = {"watch/providers": {"results": {"GB": {
        "link": "https://example.invalid/watch",
        "flatrate": [{"provider_name": "Some Service"}],
    }}}}
    names, link = tmdb.providers_from(payload)
    assert names == ["Some Service"]
    assert link.endswith("/watch")


def test_a_detail_page_still_renders_when_tmdb_is_down(signed_in, app, monkeypatch):
    from app import db, tmdb

    def boom(*a, **k):
        raise tmdb.TmdbError("TMDB is unreachable")

    monkeypatch.setattr(tmdb, "show_detail", boom)
    monkeypatch.setattr(tmdb, "movie_detail", boom)
    with app.app_context():
        db.execute("INSERT OR REPLACE INTO show (id, name) VALUES (500, 'A Show')")
        db.execute("INSERT OR REPLACE INTO tracked_show (show_id, added_at) VALUES (500, '2026-01-01')")
        db.execute("INSERT OR REPLACE INTO movie (id, title) VALUES (501, 'A Film')")
        db.execute("INSERT OR REPLACE INTO tracked_movie (movie_id, added_at) VALUES (501, '2026-01-01')")

    assert signed_in.get("/show/500").status_code == 200
    assert signed_in.get("/movie/501").status_code == 200


def test_the_image_proxy_accepts_a_profile_path(signed_in):
    """Profile filenames can carry dashes and underscores, unlike posters."""
    from app.posters import PATH_RE

    assert PATH_RE.match("/8Ac2mfkQiCJj5nDNMMBQZLwEEEG.jpg")
    assert PATH_RE.match("/a-b_c.png")
    assert not PATH_RE.match("/../secret.jpg")
    assert not PATH_RE.match("/thing.txt")
