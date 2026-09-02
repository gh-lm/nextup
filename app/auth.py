"""Single-user session login."""
from functools import wraps

from flask import redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from . import db


def current_user():
    if not session.get("logged_in"):
        return None
    return db.query("SELECT id, username FROM admin_user WHERE id = 1", one=True)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("auth.login", next=request.full_path))
        return view(*args, **kwargs)

    return wrapped


def check_login(username, password):
    row = db.query("SELECT username, password_hash FROM admin_user WHERE id = 1", one=True)
    if row is None:
        return False
    if username.strip().lower() != row["username"].strip().lower():
        return False
    return check_password_hash(row["password_hash"], password)


def set_password(new_password):
    db.execute(
        "UPDATE admin_user SET password_hash = ? WHERE id = 1",
        (generate_password_hash(new_password),),
    )


def set_username(new_username):
    db.execute("UPDATE admin_user SET username = ? WHERE id = 1", (new_username.strip(),))


def using_default_password():
    from . import config

    row = db.query("SELECT password_hash FROM admin_user WHERE id = 1", one=True)
    return bool(row) and check_password_hash(row["password_hash"], config.DEFAULT_PASSWORD)
