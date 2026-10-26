import pytest

from app import catalog, db, sync, tvdb

@pytest.fixture()
def keyed(app):
    with app.app_context():
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

def test_a_series_comes_back_in_the_shape_the_app_reads(keyed, monkeypatch):
    monkeypatch.setattr(tvdb, "_get", fake_get({"/series/252800/extended": SERIES}))
    show = tvdb.show(tvdb.internal(252800))
    assert show["id"] == tvdb.internal(252800)
    assert show["status"] == "Returning Series" and show["original_language"] == "en"
    assert show["networks"] == [{"name": "BBC One"}] and show["episode_run_time"] == [58]
    assert [s["season_number"] for s in show["seasons"]] == [1, 2]
    assert tvdb.imdb_from(show) == "https://www.imdb.com/title/tt1888075/"
    assert tvdb.trailer_from(show)["url"].endswith("abc123XYZ_-")

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

def test_the_footer_credits_thetvdb(signed_in):
    assert "Metadata provided by" in signed_in.get("/settings").get_data(as_text=True)

RELAY = "https://relay.example"

class Reply:
    ok = True
    status_code = 200

    def json(self):
        return {"data": {"ok": True}}

def test_lookups_go_through_the_relay_and_carry_no_credentials(app, monkeypatch):
    monkeypatch.setattr(tvdb, "RELAY_URL", RELAY)
    seen = {}

    def fake(url, params=None, timeout=None, headers=None):
        seen.update(url=url, headers=headers)
        return Reply()

    monkeypatch.setattr(tvdb.requests, "get", fake)
    with app.app_context():
        assert tvdb._get("/series/1/extended") == {"ok": True}
    assert seen["url"] == f"{RELAY}/v4/series/1/extended"
    assert "Authorization" not in seen["headers"]

def test_a_watched_mark_follows_an_episode_whose_id_changes_source(app):
    with app.app_context():
        db.execute("INSERT INTO show (id, name) VALUES (7, 'S')")
        db.execute("INSERT INTO episode (id, show_id, season_number, episode_number) VALUES (1, 7, 1, 1)")
        db.execute("INSERT INTO watched_episode (episode_id, show_id, watched_at) VALUES (1, 7, '2026-01-01')")
        sync.upsert_episodes(7, {"season_number": 1, "episodes": [{"id": 99, "season_number": 1, "episode_number": 1, "name": "x"}]})
        assert db.query("SELECT 1 FROM watched_episode WHERE episode_id = 99", one=True)

def test_cast_comes_from_the_characters_in_order_with_photos():
    record = {"characters": [
        {"peopleType": "Actor", "personName": "B Person", "name": "Role B", "sort": 2,
         "personImgURL": "https://artworks.thetvdb.com/banners/v4/actor/2/photo/b.jpg"},
        {"peopleType": "Director", "personName": "Not Cast", "sort": 0},
        {"peopleType": "Actor", "personName": "A Person", "name": "Role A", "sort": 1, "personImgURL": None},
    ]}
    cast = tvdb._credits(record)["cast"]
    assert [c["name"] for c in cast] == ["A Person", "B Person"]
    assert cast[0]["profile_path"] is None
    assert cast[1]["profile_path"] == "/tvdb__banners__v4__actor__2__photo__b.jpg"
    assert tvdb.cast_from({"credits": tvdb._credits(record)})[1]["role"] == "Role B"

def test_a_background_refresh_waits_out_a_refusal_but_a_page_does_not(app, monkeypatch):
    class Reply:
        def __init__(self, status):
            self.status_code, self.ok, self.headers = status, status == 200, {"Retry-After": "7"}

        def json(self):
            return {"data": {"ok": True}}

    def run(patient):
        replies = [Reply(429), Reply(200)]
        sleeps = []
        monkeypatch.setattr(tvdb.requests, "get", lambda *a, **k: replies.pop(0))
        monkeypatch.setattr(tvdb.time, "sleep", sleeps.append)
        tvdb._mode.patient = patient
        try:
            assert tvdb._get("/x") == {"ok": True}
        finally:
            tvdb._mode.patient = False
        return sleeps

    assert 7 in run(True)
    assert 7 not in run(False)
