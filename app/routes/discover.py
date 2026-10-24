"""Discover: what is arriving, and a quick yes, no or maybe on each."""
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for

from .. import clock, db, languages, queries, sync, tmdb
from ..auth import login_required
from ..forms import whole_number
from ..redirects import back_to

bp = Blueprint("discover", __name__, url_prefix="/discover")

WINDOWS = [7, 14, 30, 60]
DEFAULT_DAYS = 14
MAX_PAGES = 3
RECENT_DAYS = 14
HOME_DATE_TTL = 12 * 3600
HOME_DATE_LIMIT = 2000
MAX_WORKERS = 8
_HOME_DATES = {}

def _window(default=DEFAULT_DAYS):
    days = whole_number(request.args.get("days"), 1, 180, default)
    today = clock.today_date()
    return days, today.isoformat(), (today + timedelta(days=days)).isoformat()

def _collect(fetch, start, end, wanted=40):
    app = current_app._get_current_object()
    codes = [None] if languages.show_all() else languages.watched()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        lists = pool.map(lambda code: _collect_language(app, fetch, start, end, code, wanted), codes)
        return [row for items in lists for row in items]

def _collect_language(app, fetch, start, end, code, wanted):
    items, page = [], 1
    while len(items) < wanted and page <= MAX_PAGES:
        with app.app_context():
            payload = fetch(start, end, page=page, language=code)
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

def _release_payloads(ids):
    app = current_app._get_current_object()
    code = tmdb.country()
    if len(_HOME_DATES) > HOME_DATE_LIMIT:
        now = time.time()
        for key in [k for k, (_, at) in _HOME_DATES.items() if now - at >= HOME_DATE_TTL]:
            _HOME_DATES.pop(key, None)
        if len(_HOME_DATES) > HOME_DATE_LIMIT:
            _HOME_DATES.clear()

    def look(movie_id):
        hit = _HOME_DATES.get((movie_id, code))
        if hit and time.time() - hit[1] < HOME_DATE_TTL:
            return movie_id, hit[0]
        try:
            with app.app_context():
                payload = tmdb.movie_release_dates(movie_id)
        except tmdb.TmdbError:
            return movie_id, None
        _HOME_DATES[(movie_id, code)] = (payload, time.time())
        return movie_id, payload

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        return dict(pool.map(look, ids))

def _cards(raw, skip, seen, title_key, date_key, home=None):
    cards = []
    for row in raw:
        if row["id"] in skip or row["id"] in seen:
            continue
        if home is not None and row["id"] not in home:
            continue
        seen.add(row["id"])
        date = ((home or {}).get(row["id"]) or row.get(date_key) or "")[:10]
        cards.append(
            {
                "id": row["id"],
                "title": row.get(title_key) or "Untitled",
                "date": date,
                "overview": row.get("overview") or "",
                "poster_path": row.get("poster_path"),
                "vote_average": row.get("vote_average") or 0,
                "language": row.get("original_language"),
            }
        )
    return queries.dated(cards, lambda i: i["date"])

def _recent_window():
    today = clock.today_date()
    return (today - timedelta(days=RECENT_DAYS)).isoformat(), (today - timedelta(days=1)).isoformat()

def _both_windows(fetch, start, end):
    recent_start, recent_end = _recent_window()
    error = None
    try:
        ahead = _collect(fetch, start, end)
        recent = _collect(fetch, recent_start, recent_end)
    except tmdb.TmdbError as exc:
        ahead, recent, error = [], [], str(exc)
    return ahead, recent, error

@bp.route("/films")
@login_required
def films():
    days, start, end = _window()
    ahead, recent, error = _both_windows(tmdb.discover_films_reaching_streaming, start, end)

    _, tracked = queries.known_ids()
    skip = tracked | queries.dismissed_ids("movie")
    seen = set()
    recent_start, recent_end = _recent_window()
    wanted = {row["id"] for row in ahead + recent if row["id"] not in skip}
    payloads = _release_payloads(wanted) if wanted else {}
    missed = sum(1 for payload in payloads.values() if payload is None)
    if missed and not error:
        error = f"TMDB would not give the release dates for {missed} movies, so some may be missing. Try again shortly."

    def home_in(rows, first, last):
        found = {}
        for row in rows:
            payload = payloads.get(row["id"])
            date = tmdb.home_release_in(payload, first, last) if payload else None
            if date:
                found[row["id"]] = date
        return found

    return render_template(
        "pages/discover_films.html",
        items=_cards(ahead, skip, seen, "title", "release_date", home_in(ahead, start, end)),
        recent=_cards(recent, skip, seen, "title", "release_date", home_in(recent, recent_start, recent_end)),
        days=days,
        recent_days=RECENT_DAYS,
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
    ahead, recent, error = _both_windows(fetch, start, end)

    tracked, _ = queries.known_ids()
    skip = tracked | queries.dismissed_ids("tv")
    seen = set()

    return render_template(
        "pages/discover_tv.html",
        items=_cards(ahead, skip, seen, "name", "first_air_date"),
        recent=_cards(recent, skip, seen, "name", "first_air_date"),
        days=days,
        recent_days=RECENT_DAYS,
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
            (show_id, clock.now_iso()),
        )
        return back_to("discover.tv")

    failed = []
    try:
        name = sync.sync_show(show_id, failed)
    except tmdb.TmdbError as exc:
        flash(str(exc), "error")
        return back_to("discover.tv")

    db.execute(
        "INSERT INTO tracked_show (show_id, added_at, shortlist) VALUES (?, ?, ?)"
        " ON CONFLICT(show_id) DO UPDATE SET archived = 0, shortlist = excluded.shortlist",
        (show_id, clock.now_iso(), 1 if action == "maybe" else 0),
    )
    _undismiss("tv", show_id)
    if failed:
        flash(f"TMDB would not serve season {', '.join(str(n) for n in failed)}. It will be tried again.", "error")
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
            (movie_id, clock.now_iso()),
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
        (movie_id, clock.now_iso(), 1 if action == "maybe" else 0),
    )
    _undismiss("movie", movie_id)
    try:
        sync.sync_movie_availability(movie_id)
    except tmdb.TmdbError:
        pass
    flash(
        f"{payload.get('title') or 'The movie'} added to your "
        f"{'maybe list' if action == 'maybe' else 'movies'}.",
        "success",
    )
    return back_to("discover.films")

@bp.route("/restore", methods=["POST"])
@login_required
def restore():
    kind = request.form.get("kind")
    if kind in {"tv", "movie"}:
        db.execute("DELETE FROM dismissed WHERE kind = ?", (kind,))
    else:
        db.execute("DELETE FROM dismissed")
    flash("Everything you said no to is back in Discover.", "success")
    return back_to("discover.films")
