import calendar as pycalendar
from datetime import date, timedelta

from flask import Blueprint, render_template, request

from .. import queries, secretstore, sync, tmdb
from ..auth import login_required, using_default_password

bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def dashboard():
    return render_template(
        "pages/dashboard.html",
        to_watch=queries.to_watch(),
        upcoming=queries.upcoming(days=21, limit=12),
        recent=queries.recently_watched(6),
        counts=queries.dashboard_counts(),
        has_key=secretstore.has("tmdb_api_key"),
        default_password=using_default_password(),
        last_sync=sync.last_run(),
    )


@bp.route("/calendar")
@login_required
def calendar_view():
    today = date.today()
    try:
        year = int(request.args.get("y", today.year))
        month = int(request.args.get("m", today.month))
        if not 1 <= month <= 12:
            raise ValueError
        first = date(year, month, 1)
    except (TypeError, ValueError):
        first = date(today.year, today.month, 1)
        year, month = first.year, first.month

    last_day = pycalendar.monthrange(year, month)[1]
    last = date(year, month, last_day)

    # Pad out to whole weeks, Monday first.
    grid_start = first - timedelta(days=first.weekday())
    grid_end = last + timedelta(days=(6 - last.weekday()))

    episodes = queries.episodes_between(grid_start.isoformat(), grid_end.isoformat())
    by_day = {}
    for episode in episodes:
        by_day.setdefault(episode["air_date"][:10], []).append(episode)

    films = queries.films_between(grid_start.isoformat(), grid_end.isoformat())
    films_by_day = {}
    for film in films:
        films_by_day.setdefault(film["digital_release"][:10], []).append(film)

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
    days = request.args.get("days", "60")
    days = int(days) if days.isdigit() and 1 <= int(days) <= 365 else 60
    episodes = queries.upcoming(days=days)
    grouped = {}
    for episode in episodes:
        grouped.setdefault(episode["air_date"][:10], []).append(episode)
    return render_template(
        "pages/upcoming.html",
        grouped=sorted(grouped.items()),
        films=queries.films_arriving(days=days),
        days=days,
    )


@bp.route("/search")
@login_required
def search():
    term = (request.args.get("q") or "").strip()
    page = request.args.get("page", "1")
    page = int(page) if page.isdigit() and 1 <= int(page) <= 500 else 1

    results, error, total_pages = [], None, 1
    if term:
        try:
            payload = tmdb.search_multi(term, page=page)
            results = payload["results"]
            total_pages = min(payload["total_pages"], 500)
        except tmdb.MissingKey as exc:
            error = str(exc)
        except tmdb.TmdbError as exc:
            error = str(exc)

    tracked_tv = {row["id"] for row in queries.tracked_shows(everything=True)}
    tracked_film = {row["id"] for row in queries.movies()}
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
