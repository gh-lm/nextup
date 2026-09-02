def test_key_is_stored_encrypted(app):
    from app import db, secretstore

    with app.app_context():
        secretstore.set("tmdb_api_key", "abc123secret", encrypted=True)
        assert secretstore.get("tmdb_api_key") == "abc123secret"

        row = db.query("SELECT value, encrypted FROM settings WHERE key = ?",
                       ("tmdb_api_key",), one=True)
        assert row["encrypted"] == 1
        assert "abc123secret" not in row["value"]


def test_plain_settings_round_trip(app):
    from app import secretstore

    with app.app_context():
        secretstore.set("accent", "teal")
        assert secretstore.get("accent") == "teal"
        secretstore.delete("accent")
        assert secretstore.get("accent", "brand") == "brand"
