"""A lost or replaced secret.key must be said out loud, not look like nothing was saved."""

def test_a_replaced_key_is_reported(app, signed_in):
    from app import secretstore

    with app.app_context():
        secretstore.set("smtp_password", "abc", encrypted=True)
        assert secretstore.unreadable() == []

    import os

    from app import config

    os.remove(config.KEY_PATH)
    secretstore._fernet = None
    with app.app_context():
        assert secretstore.get("smtp_password") is None
        assert secretstore.unreadable() == ["mail password"]

    page = signed_in.get("/settings").data.decode()
    assert "cannot read the saved mail password" in page
    assert "cannot read the saved mail password" in signed_in.get("/").data.decode()

    with app.app_context():
        secretstore.set("smtp_password", "fresh", encrypted=True)
        assert secretstore.unreadable() == []
        assert secretstore.get("smtp_password") == "fresh"
