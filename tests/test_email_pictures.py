"""The morning email carries its own artwork and links back here."""
from datetime import date, timedelta


def _seed(app, poster=True):
    from app import db

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    db.execute(
        "INSERT OR REPLACE INTO show (id, name, network, poster_path)"
        " VALUES (500, 'A Series', 'BBC One', ?)",
        ("/showposter.jpg" if poster else None,),
    )
    db.execute("INSERT OR REPLACE INTO tracked_show (show_id, added_at) VALUES (500, '2026-01-01')")
    db.execute(
        "INSERT OR REPLACE INTO episode (id, show_id, season_number, episode_number,"
        " name, overview, air_date) VALUES (5001, 500, 2, 4, 'The One', ?, ?)",
        ("A thing happens. Then another thing happens to somebody else entirely.", yesterday),
    )
    db.execute(
        "INSERT OR REPLACE INTO movie (id, title, overview, digital_release, runtime,"
        " poster_path, providers) VALUES (501, 'A Film', 'A film about something.', ?, 101, ?, 'Netflix')",
        (yesterday, "/filmposter.jpg" if poster else None),
    )
    db.execute("INSERT OR REPLACE INTO tracked_movie (movie_id, added_at) VALUES (501, '2026-01-01')")


def _fake_posters(monkeypatch):
    from app import posters

    monkeypatch.setattr(posters, "read_bytes", lambda size, path: (b"\x89PNG-pretend", "png"))


def test_the_pictures_travel_with_the_message(app, monkeypatch):
    from app import mailer

    _fake_posters(monkeypatch)
    with app.app_context():
        _seed(app)
        _subject, _text, html, images = mailer.build_digest()
        assert len(images) == 2
        for cid, data, subtype in images:
            assert data == b"\x89PNG-pretend"
            assert subtype == "png"
            assert f'src="cid:{cid}"' in html


def test_nothing_is_fetched_from_another_server(app, monkeypatch):
    from app import mailer

    _fake_posters(monkeypatch)
    with app.app_context():
        _seed(app)
        _s, _t, html, _i = mailer.build_digest()
        assert "image.tmdb.org" not in html
        assert "<img" in html
        # The only address in the message is the credit at the foot.
        assert html.count("http") == html.count("https://lightmorphic.com")


def test_each_item_links_to_its_page_here(app, monkeypatch):
    from app import mailer, secretstore

    _fake_posters(monkeypatch)
    with app.app_context():
        secretstore.set("site_url", "https://home.example.ts.net:4090/")
        _seed(app)
        _s, _t, html, _i = mailer.build_digest()
        assert 'href="https://home.example.ts.net:4090/episode/5001"' in html
        assert 'href="https://home.example.ts.net:4090/movie/501"' in html


def test_without_an_address_there_is_simply_nothing_to_click(app, monkeypatch):
    from app import mailer

    _fake_posters(monkeypatch)
    with app.app_context():
        _seed(app)
        _s, _t, html, _i = mailer.build_digest()
        assert "/episode/5001" not in html
        assert "A Series" in html


def test_a_nonsense_address_is_ignored_rather_than_linked(app):
    from app import mailer, secretstore

    with app.app_context():
        for bad in ["homelab", "javascript:alert(1)", "ftp://x", ""]:
            secretstore.set("site_url", bad)
            assert mailer.base_url() == "", bad
            assert mailer.item_url("episode", 1) == ""


def test_the_description_is_included_and_kept_short(app, monkeypatch):
    from app import mailer

    _fake_posters(monkeypatch)
    with app.app_context():
        _seed(app)
        _s, _t, html, _i = mailer.build_digest()
        assert "A thing happens." in html
        assert "A film about something." in html


def test_a_long_description_is_cut_on_a_boundary():
    from app import mailer

    long = ("First sentence here. " * 30).strip()
    cut = mailer.shorten(long)
    assert len(cut) <= mailer.SYNOPSIS_LIMIT + 1
    assert cut.endswith(".")
    assert not cut.endswith(" .")


def test_a_missing_poster_does_not_stop_the_email(app, monkeypatch):
    from app import mailer, posters

    monkeypatch.setattr(posters, "read_bytes", lambda size, path: (None, None))
    with app.app_context():
        _seed(app, poster=False)
        subject, _t, html, images = mailer.build_digest()
        assert images == []
        assert "cid:" not in html
        assert "A Series" in subject or "episode" in subject


def test_the_plain_text_version_still_stands_on_its_own(app, monkeypatch):
    from app import mailer

    _fake_posters(monkeypatch)
    with app.app_context():
        _seed(app)
        _s, text, _h, _i = mailer.build_digest()
        assert "A Series S02E04" in text
        assert "A Film" in text


def test_the_plain_text_carries_the_description_and_the_link(app, monkeypatch):
    """Whoever reads the text version should not get less than the other one."""
    from app import mailer, secretstore

    _fake_posters(monkeypatch)
    with app.app_context():
        secretstore.set("site_url", "https://home.example.ts.net:4090")
        _seed(app)
        _s, text, _h, _i = mailer.build_digest()
        assert "A thing happens." in text
        assert "A film about something." in text
        assert "https://home.example.ts.net:4090/episode/5001" in text
        assert "https://home.example.ts.net:4090/movie/501" in text


def test_both_the_cover_and_the_title_are_clickable(app, monkeypatch):
    """One click from either, straight to the page here."""
    import re

    from app import mailer, secretstore

    _fake_posters(monkeypatch)
    with app.app_context():
        secretstore.set("site_url", "https://home.example.ts.net:4090")
        _seed(app)
        _s, _t, html, _i = mailer.build_digest()

        for kind, item in (("episode", 5001), ("movie", 501)):
            url = f"https://home.example.ts.net:4090/{kind}/{item}"
            # The cover: an anchor wrapping the attached image.
            assert re.search(
                rf'<a href="{re.escape(url)}"[^>]*>\s*<img src="cid:', html
            ), f"cover not linked for {kind}"
            # The title: an anchor wrapping words, not an image.
            assert re.search(
                rf'<a href="{re.escape(url)}"[^>]*>[A-Za-z]', html
            ), f"title not linked for {kind}"


def test_a_linked_cover_carries_no_border(app, monkeypatch):
    """Otherwise some mail clients ring it in blue."""
    from app import mailer, secretstore

    _fake_posters(monkeypatch)
    with app.app_context():
        secretstore.set("site_url", "https://home.example.ts.net:4090")
        _seed(app)
        _s, _t, html, _i = mailer.build_digest()
        anchor = html[html.index('<a href="https://home.example.ts.net:4090/episode/5001"'):]
        anchor = anchor[: anchor.index(">") + 1]
        assert "border:0" in anchor
