from flask import Blueprint, flash, make_response, redirect, render_template, request, url_for

from .. import db, secretstore, sync, tmdb
from ..auth import login_required, set_password, set_username, using_default_password

bp = Blueprint("settings", __name__)

# "brand" means no data-accent attribute at all, which leaves the stylesheet
# on the brand yellow defined in :root.
ACCENTS = [
    ("brand", "Brand yellow", "#fbc711"),
    ("red", "Red", "#f34236"), ("pink", "Pink", "#e8207e"),
    ("purple", "Purple", "#9b26ae"), ("deep_purple", "Deep purple", "#6639ab"),
    ("indigo", "Indigo", "#3d51b4"), ("blue", "Blue", "#2295f1"),
    ("light_blue", "Light blue", "#03a8f3"), ("cyan", "Cyan", "#00bcd3"),
    ("teal", "Teal", "#019587"), ("green", "Green", "#4bae4f"),
    ("light_green", "Light green", "#8ac248"), ("lime", "Lime", "#cbdc38"),
    ("yellow", "Yellow", "#ffea3a"), ("amber", "Amber", "#ffc006"),
    ("orange", "Orange", "#fe9700"), ("deep_orange", "Deep orange", "#ff5721"),
    ("brown", "Brown", "#795649"), ("grey", "Grey", "#9e9d9e"),
    ("blue_grey", "Blue grey", "#607c8b"),
]


@bp.route("/settings")
@login_required
def index():
    stats = db.query(
        "SELECT (SELECT COUNT(*) FROM show) AS shows,"
        " (SELECT COUNT(*) FROM episode) AS episodes,"
        " (SELECT COUNT(*) FROM movie) AS movies",
        one=True,
    )
    return render_template(
        "pages/settings.html",
        has_key=secretstore.has("tmdb_api_key"),
        accents=ACCENTS,
        last_sync=sync.last_run(),
        syncing=sync.is_running(),
        stats=stats,
        default_password=using_default_password(),
    )


@bp.route("/settings/tmdb", methods=["POST"])
@login_required
def save_tmdb():
    key = (request.form.get("tmdb_api_key") or "").strip()
    if not key:
        flash("Paste a key first.", "error")
        return redirect(url_for("settings.index"))
    try:
        tmdb.verify_key(key)
    except tmdb.TmdbError as exc:
        flash(str(exc), "error")
        return redirect(url_for("settings.index"))
    secretstore.set("tmdb_api_key", key, encrypted=True)
    flash("Key checked against TMDB and saved, encrypted.", "success")
    return redirect(url_for("settings.index"))


@bp.route("/settings/tmdb/clear", methods=["POST"])
@login_required
def clear_tmdb():
    secretstore.delete("tmdb_api_key")
    flash("Key removed.", "success")
    return redirect(url_for("settings.index"))


@bp.route("/settings/account", methods=["POST"])
@login_required
def save_account():
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    confirm = request.form.get("confirm") or ""

    if username:
        set_username(username)
    if password or confirm:
        if password != confirm:
            flash("The two passwords did not match.", "error")
            return redirect(url_for("settings.index"))
        if len(password) < 8:
            flash("Use at least 8 characters.", "error")
            return redirect(url_for("settings.index"))
        set_password(password)
        flash("Sign-in details updated.", "success")
    elif username:
        flash("Username updated.", "success")
    return redirect(url_for("settings.index"))


@bp.route("/settings/accent", methods=["POST"])
@login_required
def save_accent():
    accent = request.form.get("accent", "brand")
    if accent in {row[0] for row in ACCENTS}:
        secretstore.set("accent", accent)
    return redirect(url_for("settings.index"))


@bp.route("/settings/sync", methods=["POST"])
@login_required
def run_sync():
    if not secretstore.has("tmdb_api_key"):
        flash("Add a TMDB key first.", "error")
        return redirect(url_for("settings.index"))
    done, skipped, errors = sync.sync_all(force=True)
    if errors:
        flash(f"Refreshed {done}, but hit problems: {errors[0]}", "error")
    else:
        flash(f"Refreshed {done} show{'s' if done != 1 else ''}, skipped {skipped}.", "success")
    return redirect(url_for("settings.index"))


@bp.route("/theme", methods=["POST"])
def theme():
    choice = request.form.get("theme", "")
    target = request.form.get("next") or url_for("main.dashboard")
    if not target.startswith("/"):
        target = url_for("main.dashboard")
    resp = make_response(redirect(target))
    if choice in {"light", "dark"}:
        resp.set_cookie("theme", choice, max_age=60 * 60 * 24 * 365, samesite="Lax")
    else:
        resp.delete_cookie("theme")
    return resp
