"""Where to watch: asked of the relay, grouped, kept briefly, and never fatal."""
import pytest

OPTIONS = [
    {"service": "Apple TV", "type": "subscription", "link": "https://tv.apple.com/x"},
    {"service": "Apple TV", "type": "subscription", "link": "https://tv.apple.com/x"},
    {"service": "Prime Video", "type": "addon", "addon": "Apple TV", "link": "https://p.example/x"},
    {"service": "Prime Video", "type": "buy", "link": "http://insecure.example/x"},
    {"service": "Odd", "type": "mystery", "link": "https://o.example"},
]

class Reply:
    ok = True

    def __init__(self, body):
        self.body = body

    def json(self):
        return self.body

@pytest.fixture()
def relay(monkeypatch, data_dir):
    from app import streaming, tvdb

    streaming._kept.clear()
    monkeypatch.setattr(tvdb, "RELAY_URL", "https://relay.example")
    calls = []

    def fake_get(url, **kw):
        calls.append((url, kw["params"]))
        return Reply({"title": "T", "options": OPTIONS})

    monkeypatch.setattr(streaming.requests, "get", fake_get)
    return calls

def test_options_are_grouped_and_unsafe_links_dropped(relay):
    from app import streaming

    groups = streaming.lookup("tt11280740", "gb")
    assert [g["label"] for g in groups] == ["Stream", "Buy"]
    assert [s["name"] for s in groups[0]["services"]] == ["Apple TV", "Prime Video (Apple TV)"]
    assert groups[1]["services"][0]["link"] is None

def test_a_repeat_is_not_asked_again(relay):
    from app import streaming

    streaming.lookup("tt1", "gb")
    streaming.lookup("tt1", "gb")
    assert len(relay) == 1
    assert relay[0] == ("https://relay.example/motn/shows/tt1", {"country": "gb"})

def test_bad_input_or_a_failure_gives_nothing(relay, monkeypatch, app):
    from app import secretstore, streaming

    assert streaming.lookup("not-an-id", "gb") is None
    with app.app_context():
        secretstore.set("watch_country", "")
        assert streaming.lookup("tt1") is None
    monkeypatch.setattr(streaming.requests, "get", lambda *a, **k: (_ for _ in ()).throw(streaming.requests.ConnectionError()))
    assert streaming.lookup("tt2", "gb") is None

def test_country_setting(signed_in, app):
    from app import streaming

    def now():
        with app.app_context():
            return streaming.country()

    assert now() == "gb"
    signed_in.post("/settings/watch-country", data={"watch_country": "us"})
    assert now() == "us"
    signed_in.post("/settings/watch-country", data={"watch_country": "zz"})
    assert now() == "us"
    signed_in.post("/settings/watch-country", data={"watch_country": ""})
    assert now() == ""
    assert "Where to watch" in signed_in.get("/settings").get_data(as_text=True)

def test_imdb_id_alone():
    from app import tvdb

    assert tvdb.imdb_id_from({"imdb_id": "tt12"}) == "tt12"
    assert tvdb.imdb_id_from({"imdb_id": "x"}) is None

def test_nothing_is_asked_before_release(signed_in, app, monkeypatch):
    from datetime import date, timedelta

    from app import catalog, db, streaming, tvdb

    asked = []
    monkeypatch.setattr(streaming, "lookup", lambda imdb, code=None: asked.append(imdb) or [])
    payload = {"imdb_id": "tt99"}
    monkeypatch.setattr(catalog, "show_detail", lambda _id: payload)
    monkeypatch.setattr(catalog, "movie_detail", lambda _id: payload)
    soon = (date.today() + timedelta(days=30)).isoformat()
    past = (date.today() - timedelta(days=30)).isoformat()
    with app.app_context():
        db.execute("INSERT OR REPLACE INTO show (id, name, first_air_date) VALUES (840, 'Later', ?)", (soon,))
        db.execute("INSERT OR REPLACE INTO movie (id, title, release_date) VALUES (841, 'Later', ?)", (soon,))
        db.execute("INSERT OR REPLACE INTO show (id, name, first_air_date) VALUES (842, 'Out', ?)", (past,))
        db.execute("INSERT OR REPLACE INTO movie (id, title, release_date) VALUES (843, 'Out', ?)", (past,))
    for path in ("/show/840", "/movie/841"):
        signed_in.get(path)
    assert asked == []
    for path in ("/show/842", "/movie/843"):
        signed_in.get(path)
    assert asked == ["tt99", "tt99"]

def test_discover_lists_and_adds_by_streaming_date(signed_in, app, monkeypatch):
    from app import catalog, db, streaming, sync, tvdb

    from datetime import date, timedelta

    monkeypatch.setattr(streaming, "discover", lambda kind, when, code=None: [
        {"imdb": "tt55", "title": "Soon", "year": "2026", "date": (date.today() + timedelta(days=9)).isoformat(), "services": ["Netflix"], "overview": "A film."}])
    body = signed_in.get("/discover").get_data(as_text=True)
    assert "Soon" in body and "tt55" in body
    monkeypatch.setattr(tvdb, "movie_id_by_imdb", lambda imdb: 5000)
    monkeypatch.setattr(catalog, "movie", lambda _id: {"id": 5000, "title": "Soon", "release_date": "2026-11-20"})
    signed_in.post("/discover/add", data={"imdb": "tt55", "date": "2026-12-01"})
    with app.app_context():
        row = db.query("SELECT release_date, imdb_id FROM movie WHERE id = 5000", one=True)
        assert (row["release_date"], row["imdb_id"]) == ("2026-12-01", "tt55")
        assert db.query("SELECT 1 FROM tracked_movie WHERE movie_id = 5000", one=True)
        sync.upsert_movie({"id": 5000, "title": "Soon", "release_date": "2026-11-20"})
        assert db.query("SELECT release_date FROM movie WHERE id = 5000", one=True)["release_date"] == "2026-12-01"
    assert "On your list" in signed_in.get("/discover").get_data(as_text=True)
    assert signed_in.post("/discover/add", data={"imdb": "x", "date": "2026-12-01"}).status_code == 400

def test_discover_filters_by_time_direction_and_service(signed_in, app, monkeypatch):
    from datetime import date, timedelta

    from app import db, streaming, sync, tvdb

    def day(n):
        return (date.today() + timedelta(days=n)).isoformat()

    asked = []

    def fake(kind, when, code=None):
        asked.append((kind, when))
        return [
            {"imdb": "tt71", "title": "Near Show", "year": "2026", "date": day(5), "services": ["Netflix"], "overview": ""},
            {"imdb": "tt72", "title": "Far Show", "year": "2026", "date": day(50), "services": ["Now"], "overview": ""},
            {"imdb": "tt73", "title": "Fresh Show", "year": "2026", "date": day(-3), "services": ["Netflix", "Now"], "overview": ""},
            {"imdb": "tt74", "title": "Old Show", "year": "2026", "date": day(-40), "services": ["Netflix"], "overview": ""},
        ]

    monkeypatch.setattr(streaming, "discover", fake)
    page = lambda q: signed_in.get("/discover?" + q).get_data(as_text=True)
    body = page("kind=series")
    assert asked[-1] == ("series", "upcoming") and "Near Show" in body and "Far Show" not in body and "Fresh Show" not in body
    assert "Far Show" in page("days=60")
    body = page("when=out")
    assert asked[-1] == ("movie", "out") and "Fresh Show" in body and "Old Show" not in body and "Near Show" not in body
    assert "Old Show" in page("when=out&days=60")
    body = page("days=60&service=now")
    assert "Far Show" in body and "Near Show" not in body
    assert "Near Show" in page("days=999&service=nonsense")
    monkeypatch.setattr(tvdb, "series_id_by_imdb", lambda imdb: 6000)
    monkeypatch.setattr(sync, "sync_show", lambda show_id, failed: db.execute(
        "INSERT OR REPLACE INTO show (id, name) VALUES (?, 'Near Show')", (show_id,)) and "Near Show")
    signed_in.post("/discover/add", data={"imdb": "tt71", "date": day(5), "kind": "series"})
    with app.app_context():
        assert db.query("SELECT 1 FROM tracked_show WHERE show_id = 6000", one=True)
        assert db.query("SELECT imdb_id FROM show WHERE id = 6000", one=True)["imdb_id"] == "tt71"
    assert "On your list" in page("kind=series")

def test_discover_upcoming_drops_old_titles(app, monkeypatch):
    from datetime import date

    import requests

    from app import streaming, tvdb

    this = date.today().year
    items = [
        {"imdb": "tt1", "title": "New", "year": str(this), "date": "2026-11-01"},
        {"imdb": "tt2", "title": "Last year", "year": str(this - 1), "date": "2026-11-01"},
        {"imdb": "tt3", "title": "Old", "year": "1987", "date": "2026-11-01"},
    ]

    class Resp:
        ok = True

        def json(self):
            return {"items": items}

    monkeypatch.setattr(tvdb, "RELAY_URL", "https://relay.example.com")
    monkeypatch.setattr(requests, "get", lambda *a, **k: Resp())
    streaming._kept.clear()
    got = streaming.discover("movie", "upcoming", "gb")
    assert [i["title"] for i in got] == ["New", "Last year"]

def test_discover_poster_is_fetched_once_and_only_from_movie_of_the_night(signed_in, app, monkeypatch):
    from app import posters, streaming

    streaming._kept.clear()
    streaming._kept[("discover", "movie", "upcoming", "gb")] = (0, [
        {"imdb": "tt8", "poster": "https://cdn.movieofthenight.com/a/240.jpg?x=1"},
        {"imdb": "tt9", "poster": "https://evil.example.com/a.jpg"},
    ])
    calls = []
    monkeypatch.setattr(posters, "_download", lambda url: calls.append(url) or b"\xff\xd8jpeg")
    assert signed_in.get("/discover/poster/tt8").data == b"\xff\xd8jpeg"
    signed_in.get("/discover/poster/tt8")
    assert len(calls) == 1
    assert signed_in.get("/discover/poster/tt9").status_code == 302
    assert len(calls) == 1
