from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from ..auth import check_login

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if check_login(username, password):
            session.clear()
            session["logged_in"] = True
            session.permanent = True
            # A leading double slash is a protocol-relative URL, so "//evil"
            # would send you off this site entirely. Only a plain path is kept.
            target = request.args.get("next") or ""
            if not target.startswith("/") or target.startswith("//"):
                target = url_for("main.dashboard")
            return redirect(target)
        flash("Those details did not match.", "error")
    return render_template("pages/login.html")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
