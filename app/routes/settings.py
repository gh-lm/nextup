import json

from flask import (Blueprint, Response, current_app, flash, redirect, render_template,
                   request, session, url_for)

from .. import clock, db, mailer, queries, secretstore, sync, timezones, tmdb, transfer
from ..auth import (change_account, check_current_password, keep_this_browser_signed_in,
                    login_required, uses_default_password)
from ..forms import confirmed, whole_number

bp = Blueprint("settings", __name__)

def notify(panel, message, kind="success"):
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

def _country_choices():
    if not secretstore.has("tmdb_api_key"):
        return []
    try:
        return tmdb.countries()
    except tmdb.TmdbError:
        return []

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
        unreadable=secretstore.unreadable(),
        backup=transfer.counts(),
        mail=mailer.config(),
        mail_ready=mailer.is_configured(),
        securities=mailer.SECURITIES,
        available_after=queries.available_after_days(),
        newest_first=queries.newest_first(),
        country=tmdb.country(),
        countries=_country_choices(),
        accents=ACCENTS,
        last_sync=sync.last_run(),
        syncing=sync.is_running(),
        stats=stats,
        default_password=bool(session.get("starter")),
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
    if not confirmed():
        return notify("tmdb", "Tick \"Yes, remove it\" to remove the key.", "error")
    secretstore.delete("tmdb_api_key")
    return notify("tmdb", "Key removed.", "success")

@bp.route("/settings/account", methods=["POST"])
@login_required
def save_account():
    username = (request.form.get("username") or "").strip()
    current = request.form.get("current") or ""
    password = request.form.get("password") or ""
    confirm = request.form.get("confirm") or ""

    if not check_current_password(current):
        return notify("account", "Your current password is not right.", "error")
    if not username:
        return notify("account", "The username cannot be empty.", "error")
    if session.get("starter") and not password:
        return notify("account", "Choose a new password. The starting one is public.", "error")
    if password or confirm:
        if password != confirm:
            return notify("account", "The two passwords did not match.", "error")
        if len(password) < 8:
            return notify("account", "Use at least 8 characters.", "error")

    change_account(username, password)
    if password:
        return notify("account", "Sign-in details updated. Other browsers were signed out.", "success")
    return notify("account", "Username updated.", "success")

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
    if not sync.start_now(current_app._get_current_object()):
        return notify("sync", "A refresh is already running.", "error")
    return notify("sync", "Refresh started. Reload this page in a minute to see how it went.", "success")

@bp.route("/settings/availability", methods=["POST"])
@login_required
def save_availability():
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

@bp.route("/settings/season-order", methods=["POST"])
@login_required
def save_season_order():
    choice = request.form.get("season_order")
    if choice not in ("newest", "oldest"):
        return notify("order", "Pick one of the two orders.", "error")
    secretstore.set("season_order", choice)
    return notify(
        "order",
        "Latest first, oldest at the bottom." if choice == "newest"
        else "Oldest first, latest at the bottom.",
        "success",
    )

@bp.route("/settings/country", methods=["POST"])
@login_required
def save_country():
    code = (request.form.get("country") or "").strip().upper()
    if not code and request.form.get("timezone"):
        code = timezones.country_for(request.form.get("timezone")) or ""
        if not code:
            return notify("country", "Your time zone does not belong to one country. Pick yours from the list.", "error")
    if code == tmdb.NO_COUNTRY:
        secretstore.set("country", tmdb.NO_COUNTRY)
        message = "No country chosen. Movies show their first home release anywhere."
    else:
        names = dict(_country_choices())
        if code not in names:
            return notify("country", "Pick a country from the list.", "error")
        secretstore.set("country", code)
        message = f"Country set to {names[code]}. Dates, services and age ratings now follow it."
    if secretstore.has("tmdb_api_key"):
        sync.start_now(current_app._get_current_object())
    return notify("country", message, "success")

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
    if port and whole_number(port, 1, 65535, None) is None:
        return notify("mail", "The port has to be a number between 1 and 65535.", "error")
    for label, value in (("from", from_address), ("to", to_address)):
        if value and "@" not in value:
            return notify("mail", f"That {label} address does not look like an email address.", "error")
    site = (request.form.get("site_url") or "").strip().rstrip("/")
    if site and not site.startswith(("http://", "https://")):
        return notify("mail", "The Nextup address needs to start with http or https.", "error")

    secretstore.set("smtp_host", host)
    secretstore.set("smtp_port", port or str(mailer.DEFAULT_PORT))
    secretstore.set("smtp_security", security)
    secretstore.set("smtp_username", username)
    secretstore.set("mail_from", from_address)
    secretstore.set("mail_from_name", from_name or "Nextup")
    secretstore.set("mail_to", to_address)

    secretstore.set("site_url", site)
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

    hour, minute = whole_number(hour, 0, 99, None), whole_number(minute, 0, 99, None)
    if hour is None or minute is None:
        return notify("mail", "Give the time as numbers.", "error")
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
    try:
        return notify("mail", mailer.send_daily(force=True), "success")
    except mailer.MailError as exc:
        return notify("mail", str(exc), "error")

@bp.route("/settings/mail/clear", methods=["POST"])
@login_required
def clear_mail():
    if not confirmed():
        return notify("mail", "Tick \"Yes, remove it\" to remove the mail settings.", "error")
    for key in ("smtp_host", "smtp_port", "smtp_security", "smtp_username",
                "smtp_password", "mail_from", "mail_from_name", "mail_to"):
        secretstore.delete(key)
    secretstore.set("daily_email_enabled", "0")
    return notify("mail", "Mail settings removed, including the password.", "success")

@bp.route("/settings/export")
@login_required
def export_data():
    include = request.args.get("secrets") == "1"
    payload = transfer.export_data(include_secrets=include)
    body = json.dumps(payload, indent=1, ensure_ascii=False)
    name = f"nextup-backup-{clock.today()}.json"
    return Response(
        body,
        mimetype="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "Content-Length": str(len(body.encode("utf-8"))),
            "Cache-Control": "no-store",
        },
    )

@bp.route("/settings/import", methods=["POST"])
@login_required
def import_data():
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
    except transfer.BackupError as exc:
        return notify("transfer", str(exc), "error")

    keep_this_browser_signed_in()
    session["starter"] = uses_default_password()
    message = f"Restored {transfer.summarise(restored)}."
    if not restored.get("secrets"):
        message += " The file had no keys in it, so type your TMDB key and mail password in again."
    return notify("transfer", message, "success")
