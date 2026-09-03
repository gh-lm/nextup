from datetime import date, time, timedelta


def test_the_default_send_time_is_eight_in_the_morning(app):
    from app import mailer

    with app.app_context():
        assert mailer.send_time() == time(8, 0)
        assert mailer.clock_format() == "24"


def test_any_minute_of_the_day_can_be_set(app):
    from app import mailer, secretstore

    with app.app_context():
        secretstore.set("daily_email_time", "07:12")
        assert mailer.send_time() == time(7, 12)
        assert mailer.config()["time_display"] == "07:12"

        secretstore.set("clock_format", "12")
        assert mailer.config()["time_display"] == "7:12 am"


def test_the_twelve_hour_clock_reads_correctly(app):
    from app import mailer, secretstore

    with app.app_context():
        secretstore.set("clock_format", "12")
        cases = {
            "00:00": "12:00 am",
            "00:30": "12:30 am",
            "07:12": "7:12 am",
            "12:00": "12:00 pm",
            "12:45": "12:45 pm",
            "13:05": "1:05 pm",
            "23:59": "11:59 pm",
        }
        for stored, shown in cases.items():
            secretstore.set("daily_email_time", stored)
            assert mailer.config()["time_display"] == shown, stored


def test_a_bad_time_falls_back_rather_than_breaking(app):
    from app import mailer, secretstore

    with app.app_context():
        for bad in ["", "half seven", "25:00", "07:99", "7", None]:
            secretstore.set("daily_email_time", bad)
            assert mailer.send_time() == time(8, 0), bad


def test_an_old_install_that_only_stored_an_hour_still_works(app):
    from app import mailer, secretstore

    with app.app_context():
        secretstore.delete("daily_email_time")
        secretstore.set("daily_email_hour", "6")
        assert mailer.send_time() == time(6, 0)


def test_saving_a_twelve_hour_time_stores_it_as_twenty_four(signed_in, app):
    from app import secretstore

    signed_in.post("/settings/mail/schedule", data={
        "send_hour": "7", "send_minute": "12", "send_meridiem": "pm",
    })
    with app.app_context():
        assert secretstore.get("daily_email_time") == "19:12"

    signed_in.post("/settings/mail/schedule", data={
        "send_hour": "12", "send_minute": "05", "send_meridiem": "am",
    })
    with app.app_context():
        assert secretstore.get("daily_email_time") == "00:05"


def test_impossible_times_are_refused(signed_in, app):
    from app import secretstore

    with app.app_context():
        secretstore.set("daily_email_time", "08:00")
    for bad in [
        {"send_hour": "25", "send_minute": "0"},
        {"send_hour": "7", "send_minute": "77"},
        {"send_hour": "13", "send_minute": "0", "send_meridiem": "pm"},
        {"send_hour": "abc", "send_minute": "0"},
    ]:
        signed_in.post("/settings/mail/schedule", data=bad)
        with app.app_context():
            assert secretstore.get("daily_email_time") == "08:00", bad


def test_the_clock_switch_flips_and_sticks(signed_in, app):
    from app import mailer

    signed_in.post("/settings/clock", data={"clock_format": "12"})
    with app.app_context():
        assert mailer.clock_format() == "12"
    signed_in.post("/settings/clock", data={"clock_format": "24"})
    with app.app_context():
        assert mailer.clock_format() == "24"


def _seed_ready(app):
    from app import db

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    db.execute("INSERT OR REPLACE INTO show (id, name, network) VALUES (200, 'A Series', 'BBC One')")
    db.execute("INSERT OR REPLACE INTO tracked_show (show_id, added_at) VALUES (200, '2026-01-01')")
    db.execute(
        "INSERT OR REPLACE INTO episode (id, show_id, season_number, episode_number, name, air_date)"
        " VALUES (2001, 200, 2, 4, 'The One With The Thing', ?)",
        (yesterday,),
    )
    db.execute(
        "INSERT OR REPLACE INTO movie (id, title, digital_release, runtime, providers)"
        " VALUES (201, 'A Good Film', ?, 118, 'Netflix')",
        (yesterday,),
    )
    db.execute("INSERT OR REPLACE INTO tracked_movie (movie_id, added_at) VALUES (201, '2026-01-01')")


def test_the_email_carries_the_name_and_the_credit(app):
    from app import mailer

    with app.app_context():
        _seed_ready(app)
        subject, text, html, _images = mailer.build_digest()
        assert ">Nextup<" in html
        assert "Made by" in html
        assert 'href="https://lightmorphic.com"' in html
        assert "lightmorphic.com" in text


def test_the_email_names_what_is_ready_and_where(app):
    from app import mailer

    with app.app_context():
        _seed_ready(app)
        _subject, text, html, _images = mailer.build_digest()
        assert "A Series" in html and "S02E04" in html
        assert "BBC One" in html
        assert "A Good Film" in html and "Netflix" in html
        assert "A Series S02E04" in text


def test_the_email_loads_nothing_from_anywhere_else(app):
    """His server is not on the public internet, so no remote images."""
    from app import mailer

    with app.app_context():
        _seed_ready(app)
        _subject, _text, html, _images = mailer.build_digest()
        assert "<img" not in html
        assert "url(" not in html
        assert html.count("http") == html.count("https://lightmorphic.com")


def test_the_test_message_uses_the_same_frame(app, monkeypatch):
    from app import mailer

    captured = {}
    with app.app_context():
        monkeypatch.setattr(mailer, "send", lambda s, t, h=None: captured.update(s=s, t=t, h=h))
        mailer.send_test()
        assert ">Nextup<" in captured["h"]
        assert 'href="https://lightmorphic.com"' in captured["h"]
