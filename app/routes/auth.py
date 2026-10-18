from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from .. import config
from ..auth import check_login, forget_failures, record_failure, sign_in_blocked, start_session
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
        if sign_in_blocked(address):
            flash("Too many attempts. Wait a few minutes and try again.", "error")
            return render_template("pages/login.html"), 429
        if check_login(username, password):
            forget_failures(address)
            start_session(starter=password == config.DEFAULT_PASSWORD)
            target = request.args.get("next") or ""
            if not is_local_path(target):
                target = url_for("main.dashboard")
            return redirect(target)
        record_failure(address)
        flash("Those details did not match.", "error")
    return render_template("pages/login.html")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
