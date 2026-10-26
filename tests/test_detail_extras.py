"""The helpers that turn a TheTVDB payload into what a detail page shows."""

def test_cast_reads_a_film_credit():
    from app import tvdb

    payload = {"credits": {"cast": [
        {"name": "A Performer", "character": "The Lead", "profile_path": "/abc.jpg"},
        {"name": "Another", "character": "The Friend", "profile_path": None},
    ]}}
    cast = tvdb.cast_from(payload)
    assert [p["name"] for p in cast] == ["A Performer", "Another"]
    assert cast[0]["role"] == "The Lead"
    assert cast[1]["profile_path"] is None

def test_cast_is_capped():
    from app import tvdb

    payload = {"credits": {"cast": [
        {"name": f"Person {i}", "character": "Someone"} for i in range(40)
    ]}}
    assert len(tvdb.cast_from(payload, limit=14)) == 14

def test_trailer_is_a_youtube_link_and_never_embeds():
    from app import tvdb

    payload = {"videos": {"results": [
        {"site": "YouTube", "type": "Trailer", "key": "not a key!", "name": "Broken"},
        {"site": "YouTube", "type": "Trailer", "key": "abc123", "name": "Official Trailer"},
    ]}}
    trailer = tvdb.trailer_from(payload)
    assert trailer["url"] == "https://www.youtube.com/watch?v=abc123"

def test_no_trailer_is_not_an_error():
    from app import tvdb

    assert tvdb.trailer_from({}) is None
    assert tvdb.trailer_from({"videos": {"results": []}}) is None

def test_imdb_link_from_either_shape():
    from app import tvdb

    assert tvdb.imdb_from({"imdb_id": "tt1234567"}).endswith("tt1234567/")
    assert tvdb.imdb_from({"external_ids": {"imdb_id": "tt7654321"}}).endswith("tt7654321/")
    assert tvdb.imdb_from({}) is None

def test_genres():
    from app import tvdb

    payload = {
        "genres": [{"name": "Drama"}, {"name": "Crime"}],
    }
    assert tvdb.genres_from(payload) == ["Drama", "Crime"]

def test_a_detail_page_still_renders_when_thetvdb_is_down(signed_in, app, monkeypatch):
    from app import db, tvdb

    def boom(*a, **k):
        raise tvdb.TvdbError("TheTVDB is unreachable")

    monkeypatch.setattr(tvdb, "show_detail", boom)
    monkeypatch.setattr(tvdb, "movie_detail", boom)
    with app.app_context():
        db.execute("INSERT OR REPLACE INTO show (id, name) VALUES (500, 'A Show')")
        db.execute("INSERT OR REPLACE INTO tracked_show (show_id, added_at) VALUES (500, '2026-01-01')")
        db.execute("INSERT OR REPLACE INTO movie (id, title) VALUES (501, 'A Film')")
        db.execute("INSERT OR REPLACE INTO tracked_movie (movie_id, added_at) VALUES (501, '2026-01-01')")

    assert signed_in.get("/show/500").status_code == 200
    assert signed_in.get("/movie/501").status_code == 200

def test_the_image_proxy_accepts_a_profile_path():
    from app.posters import PATH_RE

    assert PATH_RE.fullmatch("/8Ac2mfkQiCJj5nDNMMBQZLwEEEG.jpg")
    assert PATH_RE.fullmatch("/a-b_c.png")
    assert not PATH_RE.fullmatch("/../secret.jpg")
    assert not PATH_RE.fullmatch("/thing.txt")
