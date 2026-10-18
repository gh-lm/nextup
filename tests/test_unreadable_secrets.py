"""A lost or replaced secret.key must be said out loud, not look like nothing was saved."""


def test_a_replaced_key_is_reported(app, signed_in):
    from app import secretstore

    with app.app_context():
        secretstore.set("tmdb_api_key", "abc", encrypted=True)
        assert secretstore.unreadable() == []

    # Same data, new key: what restoring only the database looks like.
    import os

    from app import config

    os.remove(config.KEY_PATH)
    secretstore._fernet = None
    with app.app_context():
        assert secretstore.get("tmdb_api_key") is None
        assert secretstore.unreadable() == ["TMDB key"]

    page = signed_in.get("/settings").data.decode()
    assert "cannot read the saved TMDB key" in page
    assert "cannot read the saved TMDB key" in signed_in.get("/").data.decode()

    with app.app_context():
        secretstore.set("tmdb_api_key", "fresh", encrypted=True)
        assert secretstore.unreadable() == []
        assert secretstore.get("tmdb_api_key") == "fresh"
