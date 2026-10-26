from flask import Blueprint, redirect, render_template, request, session, url_for

from .. import config, db
from ..auth import (change_account, check_login, forget_failures, login_required, record_failure,
                    sign_in_wait, start_session)
from ..redirects import is_local_path

bp = Blueprint("auth", __name__)

@bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        address = request.remote_addr or "unknown"
        wait = sign_in_wait(address, username)
        if wait:
            error = f"Too many attempts. Wait {wait} seconds and try again."
            return render_template("pages/login.html", error=error), 429
        if check_login(username, password):
            forget_failures(address, username)
            start_session(starter=password == config.DEFAULT_PASSWORD)
            target = request.args.get("next") or ""
            if not is_local_path(target):
                target = url_for("main.dashboard")
            return redirect(target)
        record_failure(address, username)
        return render_template("pages/login.html", error="Those details did not match.")
    return render_template("pages/login.html")

@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))

@bp.route("/setup", methods=["GET", "POST"])
@login_required
def setup():
    if not session.get("starter"):
        return redirect(url_for("main.dashboard"))
    current = db.query("SELECT username FROM admin_user WHERE id = 1", one=True)
    username = current["username"] if current else "admin"
    error = None
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""
        if not username:
            error = "The username cannot be empty."
        elif len(password) < 8:
            error = "Use at least 8 characters for the password."
        elif password != confirm:
            error = "The two passwords did not match."
        elif password == config.DEFAULT_PASSWORD:
            error = "Choose a password of your own. The starting one is public."
        else:
            change_account(username, password)
            return redirect(url_for("main.dashboard"))
    return render_template("pages/setup.html", username=username, error=error)
