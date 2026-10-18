"""Changing the account, the starter-password lock and the sign-in limit."""
from app import auth


def _username(app):
    from app import db

    with app.app_context():
        return db.query("SELECT username FROM admin_user WHERE id = 1", one=True)["username"]


def _save(client, **fields):
    data = {"username": "admin", "current": "nextup", "password": "", "confirm": ""}
    data.update(fields)
    return client.post("/settings/account", data=data)


def test_changing_the_account_needs_the_current_password(app, signed_in):
    _save(signed_in, username="intruder", current="wrong", password="a-new-password", confirm="a-new-password")
    assert _username(app) == "admin"


def test_a_refused_password_change_does_not_rename_the_user(app, signed_in):
    _save(signed_in, username="renamed", password="a-new-password", confirm="different")
    assert _username(app) == "admin"
    _save(signed_in, username="renamed", password="short", confirm="short")
    assert _username(app) == "admin"


def test_an_empty_username_is_refused(app, signed_in):
    _save(signed_in, username="  ")
    assert _username(app) == "admin"


def test_a_good_change_signs_out_every_other_browser(app, signed_in):
    other = app.test_client()
    other.post("/login", data={"username": "admin", "password": "nextup"})
    with other.session_transaction() as sess:
        sess["starter"] = False
    assert other.get("/").status_code == 200

    _save(signed_in, username="sam", password="a-new-password", confirm="a-new-password")

    assert other.get("/").status_code == 302  # sent back to sign in
    assert signed_in.get("/").status_code == 200  # this browser stays signed in
    fresh = app.test_client()
    response = fresh.post("/login", data={"username": "sam", "password": "a-new-password"})
    assert response.status_code == 302


def test_the_starter_password_locks_everything_but_the_account_form(client):
    client.post("/login", data={"username": "admin", "password": "nextup"})
    assert client.get("/").headers["Location"].endswith("/settings#account")
    assert client.get("/settings").status_code == 200

    response = _save(client, password="my-own-password", confirm="my-own-password")
    assert response.status_code == 302
    assert client.get("/").status_code == 200


def test_too_many_wrong_passwords_lock_the_door_for_a_while(client):
    auth._failures.clear()
    for _ in range(auth.MAX_FAILURES):
        assert client.post("/login", data={"username": "admin", "password": "nope"}).status_code == 200
    response = client.post("/login", data={"username": "admin", "password": "nextup"})
    assert response.status_code == 429
    auth._failures.clear()
