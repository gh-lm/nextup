def test_season_order_setting_flips_the_show_page(signed_in, app):
    from app import db

    with app.app_context():
        db.execute("INSERT OR REPLACE INTO show (id, name) VALUES (820, 'Ordered')")
        for season in (1, 2):
            db.execute(
                "INSERT OR REPLACE INTO episode (id, show_id, season_number, episode_number, name)"
                " VALUES (?, 820, ?, 1, 'E')",
                (8200 + season, season),
            )

    def newest_first():
        body = signed_in.get("/show/820").get_data(as_text=True)
        return body.index('id="season-2"') < body.index('id="season-1"')

    assert newest_first() is True
    assert signed_in.post("/settings/season-order", data={"season_order": "oldest"}).status_code == 302
    assert newest_first() is False
    assert signed_in.post("/settings/season-order", data={"season_order": "sideways"}).status_code == 302
    assert newest_first() is False

def test_movies_and_dashboard_follow_the_same_setting(signed_in, app):
    from datetime import date, timedelta

    from app import db

    old = (date.today() - timedelta(days=20)).isoformat()
    new = (date.today() - timedelta(days=2)).isoformat()
    with app.app_context():
        for movie_id, title, day in ((830, "Older One", old), (831, "Newer One", new)):
            db.execute(
                "INSERT OR REPLACE INTO movie (id, title, digital_release) VALUES (?, ?, ?)",
                (movie_id, title, day),
            )
            db.execute(
                "INSERT OR REPLACE INTO tracked_movie (movie_id, added_at) VALUES (?, '2026-01-01')",
                (movie_id,),
            )

    def newer_first(path):
        body = signed_in.get(path).get_data(as_text=True)
        return body.index("Newer One") < body.index("Older One")

    assert newer_first("/movies") and newer_first("/")
    signed_in.post("/settings/season-order", data={"season_order": "oldest"})
    assert not newer_first("/movies") and not newer_first("/")

def test_discover_languages_default_to_english_and_can_be_added(signed_in, app):
    from app import languages

    with app.app_context():
        assert languages.show_all() is True
        assert languages.watched() == ["en"]
    signed_in.post("/settings/languages", data={"toggle": "1"})
    with app.app_context():
        assert languages.show_all() is False
    signed_in.post("/settings/languages", data={"add": "nl"})
    signed_in.post("/settings/languages", data={"add": "en"})
    with app.app_context():
        assert languages.watched() == ["en", "nl"]
    signed_in.post("/settings/languages", data={"remove": "nl"})
    with app.app_context():
        assert languages.watched() == ["en"]
