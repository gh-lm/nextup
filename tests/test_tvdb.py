import pytest

from app import catalog, db, secretstore, sync, tmdb, tvdb

@pytest.fixture()
def keyed(app):
    with app.app_context():
        secretstore.set("tvdb_api_key", "tv-key", encrypted=True)
        yield

SERIES = {
    "id": 252800, "name": "Death in Paradise", "overview": "Murders and mojitos.",
    "image": "https://artworks.thetvdb.com/banners/posters/252800-14.jpg",
    "firstAired": "2011-10-25", "lastAired": "2026-03-27", "status": {"name": "Continuing"},
    "averageRuntime": 58, "originalLanguage": "eng", "defaultSeasonType": 1,
    "latestNetwork": {"name": "BBC One"},
    "seasons": [{"number": 1, "type": {"id": 1}}, {"number": 2, "type": {"id": 1}}, {"number": 1, "type": {"id": 2}}],
    "genres": [{"name": "Drama"}], "trailers": [{"name": "Trailer", "url": "https://www.youtube.com/watch?v=abc123XYZ_-"}],
    "remoteIds": [{"id": "tt1888075", "sourceName": "IMDB"}, {"id": "41956", "sourceName": "TheMovieDB.com"}],
}
EPISODES = [
    {"id": 11, "seasonNumber": 1, "number": 1, "name": "One", "aired": "2011-10-25", "runtime": 58, "overview": None, "image": None},
    {"id": 12, "seasonNumber": 2, "number": 1, "name": "Two", "aired": "2012-01-01", "runtime": 58, "overview": "Second", "image": None},
]

def fake_get(responses):
    def get(path, params=None, tries=3):
        for prefix, value in responses.items():
            if path.startswith(prefix):
                return value
        raise tvdb.TvdbError("TheTVDB has no record of that.")
    return get

def test_ids_say_where_a_record_came_from():
    assert tvdb.is_tvdb(tvdb.internal(5)) and tvdb.raw(tvdb.internal(5)) == 5
    assert not tvdb.is_tvdb(5)

def test_picture_paths_round_trip_and_foreign_hosts_are_refused():
    stored = tvdb.image("https://artworks.thetvdb.com/banners/v4/series/1/posters/ab12.jpg")
    assert stored == "/tvdb__banners__v4__series__1__posters__ab12.jpg"
    assert tvdb.image_url(stored) == "https://artworks.thetvdb.com/banners/v4/series/1/posters/ab12.jpg"
    assert tvdb.image("https://evil.example/banners/x.jpg") is None
    assert tvdb.image_url("/abc.jpg") is None

def test_a_series_comes_back_in_tmdb_shape(keyed, monkeypatch):
    monkeypatch.setattr(tvdb, "_get", fake_get({"/series/252800/extended": SERIES}))
    show = tvdb.show(tvdb.internal(252800))
    assert show["id"] == tvdb.internal(252800)
    assert show["status"] == "Returning Series" and show["original_language"] == "en"
    assert show["networks"] == [{"name": "BBC One"}] and show["episode_run_time"] == [58]
    assert [s["season_number"] for s in show["seasons"]] == [1, 2]
    assert show["tmdb_id"] == 41956
    assert tmdb.imdb_from(show) == "https://www.imdb.com/title/tt1888075/"
    assert tmdb.trailer_from(show)["url"].endswith("abc123XYZ_-")

def test_tracking_a_tvdb_show_saves_its_episodes(keyed, monkeypatch):
    monkeypatch.setattr(tvdb, "_get", fake_get({
        "/series/252800/extended": SERIES,
        "/series/252800/episodes": {"episodes": EPISODES, "links": {"next": None}},
    }))
    tvdb._episodes.clear()
    sid = tvdb.internal(252800)
    assert sync.sync_show(sid) == "Death in Paradise"
    rows = db.query("SELECT id, season_number, episode_number, name FROM episode WHERE show_id = ? ORDER BY id", (sid,))
    assert [(r["season_number"], r["name"]) for r in rows] == [(1, "One"), (2, "Two")]
    assert rows[0]["id"] == tvdb.internal(11)

def test_the_first_source_is_asked_and_the_second_fills_gaps(keyed, monkeypatch):
    secretstore.set("tmdb_api_key", "tm-key", encrypted=True)
    thin = dict(SERIES, overview=None, image=None)
    monkeypatch.setattr(tvdb, "_get", fake_get({"/series/252800/extended": thin, "/series/252800/translations": {}}))
    monkeypatch.setattr(tmdb, "show", lambda i: {"id": i, "name": "Other", "overview": "From TMDB", "poster_path": "/p.jpg", "seasons": []})
    catalog._counterparts.clear()
    merged = catalog.show(tvdb.internal(252800))
    assert merged["name"] == "Death in Paradise" and merged["overview"] == "From TMDB"
    assert merged["poster_path"] == "/p.jpg"

def test_a_tmdb_show_is_filled_from_tvdb_when_chosen_first(keyed, monkeypatch):
    secretstore.set("tmdb_api_key", "tm-key", encrypted=True)
    secretstore.set("source_first", "tmdb")
    assert catalog.order() == ["tmdb", "tvdb"]
    monkeypatch.setattr(tmdb, "show", lambda i: {"id": i, "name": "X", "overview": "", "poster_path": "/p.jpg", "first_air_date": "2020-01-01",
                                                   "last_air_date": "2020-02-01", "backdrop_path": "/b.jpg", "status": "Ended", "original_language": "en"})
    monkeypatch.setattr(tvdb, "find_by_tmdb", lambda i, kind: tvdb.internal(9))
    monkeypatch.setattr(tvdb, "show", lambda i: {"id": i, "name": "Y", "overview": "From TVDB"})
    catalog._counterparts.clear()
    assert catalog.show(41956)["overview"] == "From TVDB"

def test_only_one_key_means_only_that_source(keyed):
    assert catalog.order() == ["tvdb"]
    with pytest.raises(tvdb.TvdbError):
        catalog.show_providers(tvdb.internal(1))

def test_a_bad_tvdb_key_is_explained_and_not_saved(signed_in, app, monkeypatch):
    def refuse(key):
        raise tvdb.TvdbError("TheTVDB rejected that key.")

    monkeypatch.setattr(tvdb, "verify_key", refuse)
    response = signed_in.post("/settings/tvdb", data={"tvdb_api_key": "bad"}, follow_redirects=True)
    assert b"TheTVDB rejected that key." in response.data
    with app.app_context():
        assert not secretstore.has("tvdb_api_key")

def test_a_good_tvdb_key_is_saved_and_the_source_choice_sticks(signed_in, app, monkeypatch):
    monkeypatch.setattr(tvdb, "verify_key", lambda key: None)
    signed_in.post("/settings/tvdb", data={"tvdb_api_key": "good"})
    signed_in.post("/settings/source", data={"source_first": "tmdb"})
    with app.app_context():
        assert secretstore.has("tvdb_api_key")
        assert catalog.first_name() == "tmdb"
    assert signed_in.post("/settings/source", data={"source_first": "x"}).status_code == 302

def test_the_welcome_page_takes_a_tvdb_key(signed_in, app, monkeypatch):
    with signed_in.session_transaction() as sess:
        sess.pop("skip_welcome")
    body = signed_in.get("/").get_data(as_text=True)
    assert "thetvdb.com/api-information/signup" in body
    monkeypatch.setattr(tvdb, "verify_key", lambda key: None)
    monkeypatch.setattr(sync, "start_now", lambda app: None)
    assert signed_in.post("/welcome", data={"tvdb_api_key": "abc"}).status_code == 302
    with app.app_context():
        assert secretstore.has("tvdb_api_key") and catalog.first_name() == "tvdb"

def test_the_footer_credits_thetvdb_once_a_key_is_saved(signed_in, keyed):
    assert "Metadata provided by" in signed_in.get("/settings").get_data(as_text=True)
