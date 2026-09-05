"""Nextup - a personal TV and film tracker."""
import os
import secrets as pysecrets
from datetime import date, datetime

from flask import Flask

from . import config, db

def _read_version():
    """VERSION at the repo root is the single source of truth."""
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "VERSION")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read().strip() or "0.0.0"
    except OSError:
        return "0.0.0"


__version__ = _read_version()


def _session_secret():
    """A stable session key kept beside the database, not in the environment."""
    path = os.path.join(config.DATA_DIR, "session.key")
    os.makedirs(config.DATA_DIR, exist_ok=True)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            value = fh.read().strip()
            if value:
                return value
    value = pysecrets.token_hex(32)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(value)
    return value


def create_app(start_sync=True):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=_session_secret(),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        # Off by default: the container speaks plain HTTP and something in
        # front of it (Tailscale Serve, a reverse proxy) does the TLS. Turn it
        # on with NEXTUP_HTTPS_ONLY=1 when every route in really is HTTPS.
        SESSION_COOKIE_SECURE=config.HTTPS_ONLY,
        # Big enough for a backup of a large library to be uploaded back.
        MAX_CONTENT_LENGTH=64 * 1024 * 1024,
        JSON_SORT_KEYS=False,
        TEMPLATES_AUTO_RELOAD=False,
    )

    db.init_db()
    app.teardown_appcontext(db.close_db)

    from .routes import auth as auth_routes
    from .routes import discover as discover_routes
    from .routes import images as image_routes
    from .routes import main as main_routes
    from .routes import movies as movie_routes
    from .routes import settings as settings_routes
    from .routes import shows as show_routes

    app.register_blueprint(auth_routes.bp)
    app.register_blueprint(discover_routes.bp)
    app.register_blueprint(main_routes.bp)
    app.register_blueprint(show_routes.bp)
    app.register_blueprint(movie_routes.bp)
    app.register_blueprint(settings_routes.bp)
    app.register_blueprint(image_routes.bp)

    _register_filters(app)
    _register_context(app)
    _register_headers(app)

    if start_sync:
        from . import mailer, sync

        sync.start_background(app)
        mailer.start_background(app)

    return app


# Nothing here loads from anywhere else, so the page is allowed to load only
# from this app. Inline styles are permitted because progress bars and a few
# widths are set on the element; scripts are not, which is the part that
# matters for cross-site scripting.
CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self'; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'none'; "
    "object-src 'none'"
)


def _register_headers(app):
    @app.after_request
    def security_headers(response):
        response.headers.setdefault("Content-Security-Policy", CSP)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response


def _register_filters(app):
    @app.template_filter("pretty_date")
    def pretty_date(value):
        if not value:
            return "TBA"
        try:
            parsed = datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
        except ValueError:
            return str(value)
        return parsed.strftime("%-d %b %Y")

    @app.template_filter("short_date")
    def short_date(value):
        if not value:
            return "TBA"
        try:
            parsed = datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
        except ValueError:
            return str(value)
        return parsed.strftime("%-d %b")

    @app.template_filter("year")
    def year(value):
        return str(value)[:4] if value else ""

    @app.template_filter("relative_day")
    def relative_day(value):
        if not value:
            return "TBA"
        try:
            parsed = datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
        except ValueError:
            return str(value)
        delta = (parsed - date.today()).days
        if delta == 0:
            return "Today"
        if delta == 1:
            return "Tomorrow"
        if delta == -1:
            return "Yesterday"
        if 0 < delta < 7:
            return parsed.strftime("%A")
        if -7 < delta < 0:
            return f"{-delta} days ago"
        return parsed.strftime("%-d %b %Y")

    @app.template_filter("episode_code")
    def episode_code(episode):
        return f"S{episode['season_number']:02d}E{episode['episode_number']:02d}"

    @app.template_filter("runtime_hours")
    def runtime_hours(minutes):
        minutes = int(minutes or 0)
        if minutes < 60:
            return f"{minutes} min"
        hours, rest = divmod(minutes, 60)
        if hours < 48:
            return f"{hours}h {rest}m"
        days, hours = divmod(hours, 24)
        return f"{days}d {hours}h"


def _register_context(app):
    from flask import get_flashed_messages, request, session

    from . import secretstore
    from .auth import current_user

    @app.context_processor
    def inject():
        theme = request.cookies.get("theme", "")
        accent = "brand"
        try:
            accent = secretstore.get("accent", "brand") or "brand"
        except Exception:
            pass
        # Read once here, because reading clears them. Both the layout and the
        # page itself need them: a message tagged with a panel is shown beside
        # that panel, and anything untagged falls back to the top of the page.
        notes = []
        for category, message in get_flashed_messages(with_categories=True):
            kind, _, panel = (category or "info").partition(":")
            notes.append({"kind": kind or "info", "panel": panel, "message": message})

        return {
            "app_version": __version__,
            "notes": notes,
            "user": current_user() if session.get("logged_in") else None,
            "theme": theme,
            "accent": accent,
            "today": date.today(),
        }
