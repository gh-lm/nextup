from flask import Blueprint, current_app, redirect, render_template, request, session, url_for

from .. import catalog, config, secretstore, sync
from ..auth import check_login, forget_failures, record_failure, sign_in_wait, start_session
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
            if catalog.remember_country(request.form.get("timezone")) and secretstore.has("tmdb_api_key"):
                sync.start_now(current_app._get_current_object())
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
