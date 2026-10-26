from datetime import date, timedelta

def test_label_names_the_language_and_hides_english():
    from app import languages

    assert languages.label("ko") == "Korean"
    assert languages.label("fr") == "French"
    assert languages.label("en") == ""
    assert languages.label("xx") == ""
    assert languages.label(None) == ""
    assert languages.label("zz") == "ZZ"

def _seed(app, language):
    from app import db

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    db.execute(
        "INSERT OR REPLACE INTO show (id, name, original_language) VALUES (810, 'Seoul Nights', ?)",
        (language,),
    )
    db.execute("INSERT OR REPLACE INTO tracked_show (show_id, added_at) VALUES (810, '2026-01-01')")
    db.execute(
        "INSERT OR REPLACE INTO episode (id, show_id, season_number, episode_number,"
        " name, air_date) VALUES (8101, 810, 1, 1, 'One', ?)",
        (yesterday,),
    )
    db.execute(
        "INSERT OR REPLACE INTO movie (id, title, original_language, release_date)"
        " VALUES (811, 'Paris Rain', ?, ?)",
        (language and "fr", yesterday),
    )
    db.execute("INSERT OR REPLACE INTO tracked_movie (movie_id, added_at) VALUES (811, '2026-01-01')")

def test_cards_name_a_foreign_original_language(signed_in, app):
    with app.app_context():
        _seed(app, "ko")
    assert "Korean" in signed_in.get("/shows").get_data(as_text=True)
    assert "French" in signed_in.get("/movies").get_data(as_text=True)

def test_english_titles_carry_no_language_label(signed_in, app):
    with app.app_context():
        _seed(app, "en")
    body = signed_in.get("/shows").get_data(as_text=True)
    assert "English" not in body and ">EN<" not in body
