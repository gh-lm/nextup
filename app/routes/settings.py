import json
from datetime import date

from flask import (Blueprint, Response, flash, make_response, redirect,
                   render_template, request, url_for)

from .. import db, mailer, queries, secretstore, sync, tmdb, transfer
from ..auth import login_required, set_password, set_username, using_default_password

bp = Blueprint("settings", __name__)

# "brand" means no data-accent attribute at all, which leaves the stylesheet
# on the brand yellow defined in :root.

def notify(panel, message, kind="success"):
    """Say what happened beside the control that did it.

    The message is tagged with its panel so the page can put it there, and the
    redirect carries an anchor so the browser returns to that panel rather than
    throwing you back to the top of the page to read a banner.
    """
    flash(message, f"{kind}:{panel}")
    return redirect(url_for("settings.index", _anchor=panel))


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
        backup=transfer.export_data()["counts"],
        mail=mailer.config(),
        mail_ready=mailer.is_configured(),
        securities=mailer.SECURITIES,
        available_after=queries.available_after_days(),
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
        return notify("tmdb", "Paste a key first.", "error")
    try:
        tmdb.verify_key(key)
    except tmdb.TmdbError as exc:
        return notify("tmdb", str(exc), "error")
    secretstore.set("tmdb_api_key", key, encrypted=True)
    return notify("tmdb", "Key checked against TMDB and saved, encrypted.", "success")


@bp.route("/settings/tmdb/clear", methods=["POST"])
@login_required
def clear_tmdb():
    secretstore.delete("tmdb_api_key")
    return notify("tmdb", "Key removed.", "success")


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
            return notify("account", "The two passwords did not match.", "error")
        if len(password) < 8:
            return notify("account", "Use at least 8 characters.", "error")
        set_password(password)
        return notify("account", "Sign-in details updated.", "success")
    if username:
        return notify("account", "Username updated.", "success")
    return redirect(url_for("settings.index", _anchor="account"))


@bp.route("/settings/accent", methods=["POST"])
@login_required
def save_accent():
    accent = request.form.get("accent", "brand")
    if accent in {row[0] for row in ACCENTS}:
        secretstore.set("accent", accent)
    return redirect(url_for("settings.index", _anchor="accent"))


@bp.route("/settings/sync", methods=["POST"])
@login_required
def run_sync():
    if not secretstore.has("tmdb_api_key"):
        return notify("sync", "Add a TMDB key first.", "error")
    done, skipped, errors = sync.sync_all(force=True)
    if errors:
        return notify("sync", f"Refreshed {done}, but hit problems: {errors[0]}", "error")
    return notify(
        "sync", f"Refreshed {done} show{'s' if done != 1 else ''}, skipped {skipped}.", "success"
    )


@bp.route("/settings/availability", methods=["POST"])
@login_required
def save_availability():
    """How long after something airs before Nextup calls it watchable."""
    raw = (request.form.get("available_after_days") or "").strip()
    try:
        days = int(raw)
    except ValueError:
        return notify("availability", "Give a whole number of days.", "error")
    if not 0 <= days <= 14:
        return notify("availability", "Pick something between 0 and 14 days.", "error")
    secretstore.set("available_after_days", str(days))
    if days == 0:
        return notify(
            "availability", "Programmes now count as watchable the day they air.", "success"
        )
    return notify(
        "availability",
        f"Programmes now count as watchable {days} day"
        f"{'s' if days != 1 else ''} after they air.",
        "success",
    )


@bp.route("/settings/mail", methods=["POST"])
@login_required
def save_mail():
    host = (request.form.get("smtp_host") or "").strip()
    port = (request.form.get("smtp_port") or "").strip()
    security = request.form.get("smtp_security", "starttls")
    username = (request.form.get("smtp_username") or "").strip()
    password = request.form.get("smtp_password") or ""
    from_address = (request.form.get("mail_from") or "").strip()
    from_name = (request.form.get("mail_from_name") or "Nextup").strip()
    to_address = (request.form.get("mail_to") or "").strip()

    if security not in mailer.SECURITIES:
        security = "starttls"
    if port and not port.isdigit():
        return notify("mail", "The port has to be a number.", "error")
    for label, value in (("from", from_address), ("to", to_address)):
        if value and "@" not in value:
            return notify("mail", f"That {label} address does not look like an email address.", "error")

    secretstore.set("smtp_host", host)
    secretstore.set("smtp_port", port or str(mailer.DEFAULT_PORT))
    secretstore.set("smtp_security", security)
    secretstore.set("smtp_username", username)
    secretstore.set("mail_from", from_address)
    secretstore.set("mail_from_name", from_name or "Nextup")
    secretstore.set("mail_to", to_address)

    site = (request.form.get("site_url") or "").strip().rstrip("/")
    if site and not site.startswith(("http://", "https://")):
        return notify("mail", "The Nextup address needs to start with http or https.", "error")
    secretstore.set("site_url", site)
    # An empty box leaves the stored password alone rather than wiping it.
    if password:
        secretstore.set("smtp_password", password, encrypted=True)
    return notify("mail", "Mail settings saved. The password is stored encrypted.", "success")


@bp.route("/settings/mail/schedule", methods=["POST"])
@login_required
def save_mail_schedule():
    enabled = "1" if request.form.get("daily_email_enabled") else "0"
    hour = (request.form.get("send_hour") or "").strip()
    minute = (request.form.get("send_minute") or "0").strip()
    meridiem = (request.form.get("send_meridiem") or "").strip().lower()

    if not hour.isdigit() or not minute.isdigit():
        return notify("mail", "Give the time as numbers.", "error")
    hour, minute = int(hour), int(minute)
    if not 0 <= minute <= 59:
        return notify("mail", "Minutes have to be between 0 and 59.", "error")

    if meridiem in {"am", "pm"}:
        if not 1 <= hour <= 12:
            return notify("mail", "On a 12 hour clock the hour has to be between 1 and 12.", "error")
        hour = hour % 12 + (12 if meridiem == "pm" else 0)
    elif not 0 <= hour <= 23:
        return notify("mail", "The hour has to be between 0 and 23.", "error")

    if enabled == "1" and not mailer.is_configured():
        return notify("mail", "Fill in the mail server details before switching the email on.", "error")

    when = f"{hour:02d}:{minute:02d}"
    secretstore.set("daily_email_enabled", enabled)
    secretstore.set("daily_email_time", when)
    secretstore.delete("daily_email_hour")

    shown = mailer.format_time(mailer.parse_time(when))
    if enabled == "1":
        return notify("mail", f"The morning email will go out at {shown}.", "success")
    return notify("mail", f"Time saved as {shown}. The morning email is off.", "success")


@bp.route("/settings/clock", methods=["POST"])
@login_required
def save_clock():
    """Switch between the 24 hour clock and am and pm."""
    choice = request.form.get("clock_format", "24")
    secretstore.set("clock_format", "12" if choice == "12" else "24")
    return redirect(url_for("settings.index", _anchor="mail"))


@bp.route("/settings/mail/test", methods=["POST"])
@login_required
def test_mail():
    try:
        mailer.send_test()
        return notify("mail", "Test message sent. Have a look in your inbox.", "success")
    except mailer.MailError as exc:
        return notify("mail", str(exc), "error")


@bp.route("/settings/mail/preview", methods=["POST"])
@login_required
def preview_mail():
    """Send this morning's email now, whatever the clock says."""
    try:
        return notify("mail", mailer.send_daily(force=True), "success")
    except mailer.MailError as exc:
        return notify("mail", str(exc), "error")


@bp.route("/settings/mail/clear", methods=["POST"])
@login_required
def clear_mail():
    for key in ("smtp_host", "smtp_port", "smtp_security", "smtp_username",
                "smtp_password", "mail_from", "mail_from_name", "mail_to"):
        secretstore.delete(key)
    secretstore.set("daily_email_enabled", "0")
    return notify("mail", "Mail settings removed, including the password.", "success")


@bp.route("/settings/export")
@login_required
def export_data():
    """Everything you have, as one file you can keep."""
    include = request.args.get("secrets") == "1"
    payload = transfer.export_data(include_secrets=include)
    body = json.dumps(payload, indent=1, ensure_ascii=False)
    name = f"nextup-backup-{date.today().isoformat()}.json"
    return Response(
        body,
        mimetype="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "Content-Length": str(len(body.encode("utf-8"))),
        },
    )


@bp.route("/settings/import", methods=["POST"])
@login_required
def import_data():
    """Put a backup back. All of it or none of it."""
    upload = request.files.get("backup")
    if upload is None or not upload.filename:
        return notify("transfer", "Choose a backup file first.", "error")
    if request.form.get("confirm") != "replace":
        return notify(
            "transfer",
            "Tick the box to say you understand this replaces everything you have now.",
            "error",
        )

    try:
        payload = json.loads(upload.read().decode("utf-8"))
    except UnicodeDecodeError:
        return notify("transfer", "That file is not text, so it is not a backup.", "error")
    except json.JSONDecodeError as exc:
        return notify("transfer", f"That file is not readable JSON: {exc}", "error")

    try:
        restored = transfer.import_data(payload)
    except transfer.ImportError_ as exc:
        return notify("transfer", str(exc), "error")

    return notify("transfer", f"Restored {transfer.summarise(restored)}.", "success")


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
