"""Single-user session login."""
import math
import secrets as pysecrets
import time
from functools import wraps

from flask import redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from . import config, db, secretstore

STARTER_ALLOWED = {"auth.setup", "settings.index", "settings.save_account", "auth.logout", "static"}

FREE_TRIES = 5
MAX_DELAY = 300
FORGET_AFTER = 15 * 60
MAX_TRACKED = 1000
_failures = {}

def _epoch():
    return secretstore.get("session_epoch", "0")

def end_all_sessions():
    secretstore.set("session_epoch", pysecrets.token_hex(8))

def keep_this_browser_signed_in():
    end_all_sessions()
    session["epoch"] = _epoch()

def start_session(starter):
    session.clear()
    session["logged_in"] = True
    session["epoch"] = _epoch()
    session["starter"] = bool(starter)
    session.permanent = True

def current_user():
    if not session.get("logged_in"):
        return None
    return db.query("SELECT id, username FROM admin_user WHERE id = 1", one=True)

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in") or session.get("epoch") != _epoch():
            session.clear()
            return redirect(url_for("auth.login", next=request.full_path))
        if session.get("starter") and request.endpoint not in STARTER_ALLOWED:
            return redirect(url_for("auth.setup"))
        return view(*args, **kwargs)

    return wrapped

def _who(address, username):
    return address, (username or "").strip().lower()[:64]

def sign_in_wait(address, username):
    now = time.monotonic()
    for stale in [k for k, (_, last) in _failures.items() if now - last > FORGET_AFTER]:
        del _failures[stale]
    count, last = _failures.get(_who(address, username), (0, 0))
    if count <= FREE_TRIES:
        return 0
    delay = min(2 ** (count - FREE_TRIES - 1), MAX_DELAY)
    return max(0, math.ceil(last + delay - now))

def record_failure(address, username):
    who = _who(address, username)
    if who not in _failures and len(_failures) >= MAX_TRACKED:
        del _failures[min(_failures, key=lambda k: _failures[k])]
    _failures[who] = (_failures.get(who, (0, 0))[0] + 1, time.monotonic())

def forget_failures(address, username):
    _failures.pop(_who(address, username), None)

def check_login(username, password):
    row = db.query("SELECT username, password_hash FROM admin_user WHERE id = 1", one=True)
    if row is None:
        return False
    if username.strip().lower() != row["username"].strip().lower():
        return False
    return check_password_hash(row["password_hash"], password)

def check_current_password(password):
    row = db.query("SELECT password_hash FROM admin_user WHERE id = 1", one=True)
    return bool(row) and check_password_hash(row["password_hash"], password)

def uses_default_password():
    row = db.query("SELECT password_hash FROM admin_user WHERE id = 1", one=True)
    return bool(row) and check_password_hash(row["password_hash"], config.DEFAULT_PASSWORD)

def change_account(username, new_password):
    if new_password:
        db.execute(
            "UPDATE admin_user SET username = ?, password_hash = ? WHERE id = 1",
            (username, generate_password_hash(new_password)),
        )
        end_all_sessions()
    else:
        db.execute("UPDATE admin_user SET username = ? WHERE id = 1", (username,))
    start_session(starter=uses_default_password())
