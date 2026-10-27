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
