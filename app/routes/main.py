import calendar as pycalendar
from datetime import date, timedelta

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for

from .. import catalog, clock, queries, secretstore, sync
from ..auth import login_required
from ..forms import page_number, whole_number
from ..redirects import back

bp = Blueprint("main", __name__)

MIN_YEAR, MAX_YEAR = 1970, 2100

@bp.route("/")
@login_required
def dashboard():
    order = queries.date_order()
    page = page_number(10000)
    return render_template(
        "pages/dashboard.html",
        ready=queries.ready_to_watch(order, page=page),
        order=order,
        soon=queries.coming_soon(days=21, limit=12),
        recent=queries.recently_watched(6),
        counts=queries.dashboard_counts(),
        unreadable=secretstore.unreadable(),
        last_sync=sync.last_run(),
    )

@bp.route("/calendar")
@login_required
def calendar_view():
    today = clock.today_date()
    year = whole_number(request.args.get("y"), MIN_YEAR, MAX_YEAR, today.year)
    month = whole_number(request.args.get("m"), 1, 12, today.month)
    first = date(year, month, 1)

    last_day = pycalendar.monthrange(year, month)[1]
    last = date(year, month, last_day)

    grid_start = first - timedelta(days=first.weekday())
    grid_end = last + timedelta(days=(6 - last.weekday()))

    episodes = queries.episodes_between(grid_start.isoformat(), grid_end.isoformat())
    by_day = {}
    for episode in episodes:
        by_day.setdefault(episode["air_date"][:10], []).append(episode)

    films = queries.films_between(grid_start.isoformat(), grid_end.isoformat())
    films_by_day = {}
    for film in films:
        films_by_day.setdefault(film["release_date"][:10], []).append(film)

    weeks, cursor = [], grid_start
    while cursor <= grid_end:
        week = []
        for _ in range(7):
            week.append(
                {
                    "date": cursor,
                    "in_month": cursor.month == month,
                    "is_today": cursor == today,
                    "episodes": by_day.get(cursor.isoformat(), []),
                    "films": films_by_day.get(cursor.isoformat(), []),
                }
            )
            cursor += timedelta(days=1)
        weeks.append(week)

    prev_month = (first - timedelta(days=1)).replace(day=1)
    next_month = (last + timedelta(days=1))

    return render_template(
        "pages/calendar.html",
        weeks=weeks,
        month_label=first.strftime("%B %Y"),
        film_count=len(films),
        prev_month=prev_month,
        next_month=next_month,
        today=today,
        day_names=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    )

@bp.route("/upcoming")
@login_required
def upcoming_view():
    days = whole_number(request.args.get("days"), 1, 365, 60)
    grouped = {}
    for episode in queries.upcoming(days=days):
        grouped.setdefault(episode["air_date"][:10], []).append(("episode", episode))
    for film in queries.films_arriving(days=days):
        grouped.setdefault(film["release_date"][:10], []).append(("film", film))
    return render_template(
        "pages/upcoming.html",
        grouped=sorted(grouped.items()),
        days=days,
    )

@bp.route("/search")
@login_required
def search():
    term = (request.args.get("q") or "").strip()
    page = page_number(500)

    results, error, total_pages = [], None, 1
    if term:
        try:
            payload = catalog.search_multi(term, page=page)
            results = payload["results"]
            total_pages = min(payload["total_pages"], 500)
        except catalog.TvdbError as exc:
            error = str(exc)

    tracked_tv, tracked_film = queries.known_ids()
    for item in results:
        item["tracked"] = (
            item["id"] in tracked_tv if item["kind"] == "tv" else item["id"] in tracked_film
        )

    return render_template(
        "pages/search.html",
        term=term,
        results=results,
        error=error,
        page=page,
        total_pages=total_pages,
    )

@bp.route("/sync/status")
@login_required
def sync_status():
    found = sync.progress()
    return jsonify(running=bool(found), **(found or {"done": 0, "total": 0}))

@bp.route("/intro/ok", methods=["POST"])
@login_required
def intro_ok():
    secretstore.set("intro_seen", "1")
    return back(url_for("main.dashboard"))
