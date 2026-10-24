"""The country setting: guessed from the browser once, then the person's choice."""
def test_time_zone_gives_its_country():
    from app import timezones

    assert timezones.country_for("Africa/Johannesburg") == "ZA"
    assert timezones.country_for("Asia/Kolkata") == "IN"
    assert timezones.country_for("Asia/Calcutta") == "IN"
    assert timezones.country_for("Europe/London") == "GB"
    assert timezones.country_for("America/Toronto") == "CA"

def test_time_zones_without_one_country_give_none():
    from app import timezones

    for zone in ["UTC", "Etc/GMT+3", "", None, "../../etc/passwd", "x" * 500]:
        assert timezones.country_for(zone) is None

def test_no_country_is_set_until_one_is_guessed_or_chosen(app):
    from app import tmdb

    with app.test_request_context():
        assert tmdb.country() is None

def test_signing_in_takes_the_country_from_the_browser(client, app):
    from app import tmdb

    client.post(
        "/login",
        data={"username": "admin", "password": "nextup", "timezone": "America/Toronto"},
    )
    with app.app_context():
        assert tmdb.country() == "CA"
        assert tmdb.remember_country("Europe/Berlin") is False
        assert tmdb.country() == "CA"

def test_choosing_no_country_stops_the_guess(signed_in, app, monkeypatch):
    from app import secretstore, tmdb

    with app.app_context():
        secretstore.set("tmdb_api_key", "made-up", encrypted=True)
    monkeypatch.setattr(tmdb, "countries", lambda: [("DE", "Germany"), ("JP", "Japan")])
    from app import sync
    monkeypatch.setattr(sync, "start_now", lambda app: True)

    resp = signed_in.post("/settings/country", data={"country": "-"})
    assert resp.headers["Location"].endswith("#country")
    with app.app_context():
        assert tmdb.country() is None
        assert tmdb.remember_country("Pacific/Auckland") is False

def test_saving_a_country_from_the_list(signed_in, app, monkeypatch):
    from app import secretstore, sync, tmdb

    with app.app_context():
        secretstore.set("tmdb_api_key", "made-up", encrypted=True)
    monkeypatch.setattr(tmdb, "countries", lambda: [("DE", "Germany"), ("JP", "Japan")])
    started = []
    monkeypatch.setattr(sync, "start_now", lambda app: started.append(1) or True)

    signed_in.post("/settings/country", data={"country": "jp"})
    with app.app_context():
        assert tmdb.country() == "JP"
    assert started

    body = signed_in.get("/settings").get_data(as_text=True)
    assert '<option value="JP" selected>Japan</option>' in body

def test_the_time_zone_button_picks_the_country(signed_in, app, monkeypatch):
    from app import secretstore, sync, tmdb

    with app.app_context():
        secretstore.set("tmdb_api_key", "made-up", encrypted=True)
    monkeypatch.setattr(tmdb, "countries", lambda: [("IN", "India"), ("ZA", "South Africa")])
    monkeypatch.setattr(sync, "start_now", lambda app: True)

    signed_in.post("/settings/country", data={"timezone": "Africa/Johannesburg"})
    with app.app_context():
        assert tmdb.country() == "ZA"
    signed_in.post("/settings/country", data={"timezone": "UTC"})
    with app.app_context():
        assert tmdb.country() == "ZA"

def test_a_country_not_on_the_list_is_refused(signed_in, app, monkeypatch):
    from app import secretstore, tmdb

    with app.app_context():
        secretstore.set("tmdb_api_key", "made-up", encrypted=True)
        secretstore.set("country", "DE")
    monkeypatch.setattr(tmdb, "countries", lambda: [("DE", "Germany")])

    for bad in ["XX", "<script>", "GBR", ""]:
        signed_in.post("/settings/country", data={"country": bad})
        with app.app_context():
            assert tmdb.country() == "DE"

def test_services_from_another_country_are_never_shown(monkeypatch):
    from app import tmdb

    payload = {"results": {"US": {"flatrate": [{"provider_name": "Some Service"}]}}}
    monkeypatch.setattr(tmdb, "country", lambda: "DE")
    assert tmdb.watch_providers(payload) == ([], None)
    monkeypatch.setattr(tmdb, "country", lambda: None)
    assert tmdb.watch_providers(payload) == ([], None)

def test_discover_only_names_a_region_once_one_is_chosen(monkeypatch):
    from app import tmdb

    seen = []
    monkeypatch.setattr(tmdb, "_get", lambda path, params=None, **kw: seen.append(params) or {})
    monkeypatch.setattr(tmdb, "country", lambda: None)
    tmdb.discover_films_reaching_streaming("2026-01-01", "2026-02-01")
    monkeypatch.setattr(tmdb, "country", lambda: "JP")
    tmdb.discover_films_reaching_streaming("2026-01-01", "2026-02-01")
    assert "region" not in seen[0]
    assert seen[1]["region"] == "JP"

def test_country_list_keeps_only_real_codes(app, monkeypatch):
    from app import tmdb

    monkeypatch.setattr(tmdb, "_get", lambda path, params=None, **kw: [
        {"iso_3166_1": "JP", "english_name": "Japan"},
        {"iso_3166_1": "de", "english_name": "Germany"},
        {"iso_3166_1": "<b>", "english_name": "Bad"},
        "not a row",
    ])
    with app.app_context():
        assert tmdb.countries() == [("DE", "Germany"), ("JP", "Japan")]
