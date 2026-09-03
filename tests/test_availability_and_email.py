from datetime import date, timedelta


def _seed(app, air_offset_days=0, digital_offset_days=0):
    """One tracked show and one tracked film, dated relative to today."""
    from app import db

    aired = (date.today() - timedelta(days=air_offset_days)).isoformat()
    digital = (date.today() - timedelta(days=digital_offset_days)).isoformat()
    db.execute("INSERT OR REPLACE INTO show (id, name) VALUES (300, 'Late Night Show')")
    db.execute("INSERT OR REPLACE INTO tracked_show (show_id, added_at) VALUES (300, '2026-01-01')")
    db.execute(
        "INSERT OR REPLACE INTO episode (id, show_id, season_number, episode_number, name, air_date)"
        " VALUES (3001, 300, 1, 1, 'The Late One', ?)",
        (aired,),
    )
    db.execute(
        "INSERT OR REPLACE INTO movie (id, title, digital_release) VALUES (301, 'A Late Film', ?)",
        (digital,),
    )
    db.execute(
        "INSERT OR REPLACE INTO tracked_movie (movie_id, added_at) VALUES (301, '2026-01-01')"
    )


def test_the_default_is_the_day_after(app):
    from app import queries

    with app.app_context():
        assert queries.available_after_days() == 1
        assert queries.available_cutoff() == date.today() - timedelta(days=1)


def test_nonsense_falls_back_and_silly_numbers_are_clamped(app):
    """The form rejects bad input, so this only guards a hand-edited database."""
    from app import queries, secretstore

    with app.app_context():
        for bad in ["", "banana", None]:
            secretstore.set("available_after_days", bad)
            assert queries.available_after_days() == queries.DEFAULT_AVAILABLE_AFTER, bad

        secretstore.set("available_after_days", "-3")
        assert queries.available_after_days() == 0

        secretstore.set("available_after_days", "900")
        assert queries.available_after_days() == 14


def test_something_that_aired_today_waits_until_tomorrow(app):
    from app import queries, secretstore

    with app.app_context():
        secretstore.set("available_after_days", "1")
        _seed(app, air_offset_days=0, digital_offset_days=0)
        assert queries.next_unwatched(300) is None
        film = queries.movies(watched=False)[0]
        assert queries.is_streamable(film) is False


def test_the_same_thing_a_day_later_is_ready(app):
    from app import queries, secretstore

    with app.app_context():
        secretstore.set("available_after_days", "1")
        _seed(app, air_offset_days=1, digital_offset_days=1)
        assert queries.next_unwatched(300)["id"] == 3001
        film = queries.movies(watched=False)[0]
        assert queries.is_streamable(film) is True


def test_setting_it_to_zero_makes_it_available_the_same_day(app):
    from app import queries, secretstore

    with app.app_context():
        secretstore.set("available_after_days", "0")
        _seed(app, air_offset_days=0, digital_offset_days=0)
        assert queries.next_unwatched(300)["id"] == 3001
        assert queries.is_streamable(queries.movies(watched=False)[0]) is True


def test_the_email_uses_the_same_rule_as_the_app(app):
    """A Tuesday broadcast belongs in Wednesday's email, not Tuesday's."""
    from app import queries, secretstore

    with app.app_context():
        secretstore.set("available_after_days", "1")

        # Aired today: nothing to send this morning.
        _seed(app, air_offset_days=0, digital_offset_days=0)
        assert queries.available_today()["episodes"] == []
        assert queries.available_today()["films"] == []

        # Aired yesterday: it is this morning's news.
        _seed(app, air_offset_days=1, digital_offset_days=1)
        today = queries.available_today()
        assert [row["id"] for row in today["episodes"]] == [3001]
        assert [row["id"] for row in today["films"]] == [301]


def test_nothing_to_report_means_no_email(app):
    from app import mailer

    with app.app_context():
        assert mailer.build_digest() is None


def test_the_digest_names_what_is_ready(app):
    from app import mailer, secretstore

    with app.app_context():
        secretstore.set("available_after_days", "1")
        _seed(app, air_offset_days=1, digital_offset_days=1)
        subject, text, html, _images = mailer.build_digest()
        assert "1 episode" in subject and "1 film" in subject
        assert "Late Night Show S01E01" in text
        assert "A Late Film" in text
        # The email is built from tables, which is what mail clients render.
        assert "Late Night Show" in html
        assert "A Late Film" in html
        assert "<table" in html


def test_the_password_is_stored_encrypted_and_never_handed_back(app):
    from app import db, mailer, secretstore

    with app.app_context():
        secretstore.set("smtp_password", "hunter2-secret", encrypted=True)
        row = db.query("SELECT value, encrypted FROM settings WHERE key = 'smtp_password'", one=True)
        assert row["encrypted"] == 1
        assert "hunter2-secret" not in row["value"]
        # The config the page renders from carries a flag, not the password.
        settings = mailer.config()
        assert settings["has_password"] is True
        assert "hunter2-secret" not in repr(settings)


def test_sending_refuses_until_it_is_configured(app):
    from app import mailer

    with app.app_context():
        assert mailer.is_configured() is False
        try:
            mailer.send("Subject", "Body")
        except mailer.MailError as exc:
            assert "from address" in str(exc)
        else:
            raise AssertionError("it should have refused")


def test_it_does_not_send_twice_in_one_day(app, monkeypatch):
    from app import mailer, secretstore

    sent = []
    with app.app_context():
        secretstore.set("available_after_days", "1")
        _seed(app, air_offset_days=1, digital_offset_days=1)
        for key, value in [("smtp_host", "mail.invalid"), ("mail_from", "a@example.com"),
                           ("mail_to", "b@example.com"), ("daily_email_enabled", "1")]:
            secretstore.set(key, value)
        monkeypatch.setattr(mailer, "send", lambda *a, **k: sent.append(a[0]))

        first = mailer.send_daily()
        assert "Sent:" in first
        assert len(sent) == 1

        second = mailer.send_daily()
        assert second == "Already sent today."
        assert len(sent) == 1


def test_an_empty_day_is_recorded_so_it_does_not_retry(app):
    from app import mailer, secretstore

    with app.app_context():
        for key, value in [("smtp_host", "mail.invalid"), ("mail_from", "a@example.com"),
                           ("mail_to", "b@example.com"), ("daily_email_enabled", "1")]:
            secretstore.set(key, value)
        result = mailer.send_daily()
        assert "Nothing became available" in result
        assert secretstore.get("daily_email_last_sent") == date.today().isoformat()


def test_the_settings_page_shows_both_new_panels(signed_in):
    body = signed_in.get("/settings").data.decode()
    assert "When something counts as watchable" in body
    assert "Morning email" in body
    assert "Mail server" in body
