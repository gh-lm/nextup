"""Discover: what is arriving, and a quick yes, no or maybe on each.

Films are filtered to home releases rather than cinema ones, because a
cinema date is no help if you wait for things to reach a service you
already pay for.
"""
from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import db, queries, sync, tmdb
from ..auth import login_required
from ..redirects import back_to

bp = Blueprint("discover", __name__, url_prefix="/discover")

WINDOWS = [7, 14, 30, 60]
DEFAULT_DAYS = 14
MAX_PAGES = 3


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _window(default=DEFAULT_DAYS):
    raw = request.args.get("days", str(default))
    days = int(raw) if raw.isdigit() and 1 <= int(raw) <= 180 else default
    today = date.today()
    return days, today.isoformat(), (today + timedelta(days=days)).isoformat()


def _collect(fetch, start, end, wanted=40):
    """Walk a few pages of a Discover endpoint until we have enough."""
    items, page = [], 1
    while len(items) < wanted and page <= MAX_PAGES:
        payload = fetch(start, end, page=page)
        results = payload.get("results", [])
        if not results:
            break
        items.extend(results)
        if page >= payload.get("total_pages", 1):
            break
        page += 1
    return items


@bp.route("/")
@login_required
def index():
    return redirect(url_for("discover.films"))


@bp.route("/films")
@login_required
def films():
    days, start, end = _window()
    error, items = None, []
    try:
        raw = _collect(tmdb.discover_films_reaching_streaming, start, end)
    except tmdb.TmdbError as exc:
        raw, error = [], str(exc)

    _, tracked = queries.known_ids()
    skip = tracked | queries.dismissed_ids("movie")
    seen = set()
    for row in raw:
        if row["id"] in skip or row["id"] in seen:
            continue
        seen.add(row["id"])
        items.append(
            {
                "id": row["id"],
                "title": row.get("title") or "Untitled",
                "date": (row.get("release_date") or "")[:10],
                "overview": row.get("overview") or "",
                "poster_path": row.get("poster_path"),
                "vote_average": row.get("vote_average") or 0,
            }
        )

    return render_template(
        "pages/discover_films.html",
        items=items,
        days=days,
        windows=WINDOWS,
        error=error,
        dismissed_count=len(queries.dismissed_ids("movie")),
    )


@bp.route("/tv")
@login_required
def tv():
    mode = request.args.get("mode", "new")
    days, start, end = _window(30 if mode == "new" else DEFAULT_DAYS)
    fetch = tmdb.discover_new_series if mode == "new" else tmdb.discover_returning_series

    error, items = None, []
    try:
        raw = _collect(fetch, start, end)
    except tmdb.TmdbError as exc:
        raw, error = [], str(exc)

    tracked, _ = queries.known_ids()
    skip = tracked | queries.dismissed_ids("tv")
    seen = set()
    for row in raw:
        if row["id"] in skip or row["id"] in seen:
            continue
        seen.add(row["id"])
        items.append(
            {
                "id": row["id"],
                "title": row.get("name") or "Untitled",
                "date": (row.get("first_air_date") or "")[:10],
                "overview": row.get("overview") or "",
                "poster_path": row.get("poster_path"),
                "vote_average": row.get("vote_average") or 0,
            }
        )

    return render_template(
        "pages/discover_tv.html",
        items=items,
        days=days,
        mode=mode,
        windows=WINDOWS,
        error=error,
        dismissed_count=len(queries.dismissed_ids("tv")),
    )


def _undismiss(kind, item_id):
    db.execute("DELETE FROM dismissed WHERE kind = ? AND item_id = ?", (kind, item_id))


@bp.route("/show/<int:show_id>/<action>", methods=["POST"])
@login_required
def decide_show(show_id, action):
    if action not in {"yes", "no", "maybe"}:
        abort(404)

    if action == "no":
        db.execute(
            "INSERT OR REPLACE INTO dismissed (kind, item_id, dismissed_at)"
            " VALUES ('tv', ?, ?)",
            (show_id, _now()),
        )
        return back_to("discover.tv")

    try:
        name = sync.sync_show(show_id)
    except tmdb.TmdbError as exc:
        flash(str(exc), "error")
        return back_to("discover.tv")

    db.execute(
        "INSERT INTO tracked_show (show_id, added_at, shortlist) VALUES (?, ?, ?)"
        " ON CONFLICT(show_id) DO UPDATE SET archived = 0, shortlist = excluded.shortlist",
        (show_id, _now(), 1 if action == "maybe" else 0),
    )
    _undismiss("tv", show_id)
    flash(
        f"{name} added to your {'maybe list' if action == 'maybe' else 'shows'}.",
        "success",
    )
    return back_to("discover.tv")


@bp.route("/film/<int:movie_id>/<action>", methods=["POST"])
@login_required
def decide_film(movie_id, action):
    if action not in {"yes", "no", "maybe"}:
        abort(404)

    if action == "no":
        db.execute(
            "INSERT OR REPLACE INTO dismissed (kind, item_id, dismissed_at)"
            " VALUES ('movie', ?, ?)",
            (movie_id, _now()),
        )
        return back_to("discover.films")

    try:
        payload = tmdb.movie(movie_id)
        sync.upsert_movie(payload)
    except tmdb.TmdbError as exc:
        flash(str(exc), "error")
        return back_to("discover.films")

    db.execute(
        "INSERT INTO tracked_movie (movie_id, added_at, shortlist) VALUES (?, ?, ?)"
        " ON CONFLICT(movie_id) DO UPDATE SET shortlist = excluded.shortlist",
        (movie_id, _now(), 1 if action == "maybe" else 0),
    )
    _undismiss("movie", movie_id)
    try:
        sync.sync_movie_availability(movie_id)
    except tmdb.TmdbError:
        pass
    flash(
        f"{payload.get('title')} added to your "
        f"{'maybe list' if action == 'maybe' else 'films'}.",
        "success",
    )
    return back_to("discover.films")


@bp.route("/restore", methods=["POST"])
@login_required
def restore():
    """Bring back everything you said no to, for one kind or both."""
    kind = request.form.get("kind")
    if kind in {"tv", "movie"}:
        db.execute("DELETE FROM dismissed WHERE kind = ?", (kind,))
    else:
        db.execute("DELETE FROM dismissed")
    flash("Everything you said no to is back in Discover.", "success")
    return back_to("discover.films")
