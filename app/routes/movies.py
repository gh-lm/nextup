import re
from datetime import timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import catalog, clock, db, queries, streaming, sync, tvdb
from ..auth import login_required
from ..forms import confirmed, wanted_state
from ..redirects import back_to

bp = Blueprint("movies", __name__)

@bp.route("/movies")
@login_required
def index():
    films = queries.films_by_state()
    return render_template(
        "pages/movies.html",
        ready=films["ready"],
        waiting=films["waiting"],
        seen=films["seen"],
    )

@bp.route("/movie/<int:movie_id>")
@login_required
def detail(movie_id):
    row = db.query("SELECT * FROM movie WHERE id = ?", (movie_id,), one=True)
    if row is None:
        try:
            sync.upsert_movie(catalog.movie(movie_id))
        except catalog.TvdbError as exc:
            flash(str(exc), "error")
            return redirect(url_for("main.search"))
        row = db.query("SELECT * FROM movie WHERE id = ?", (movie_id,), one=True)
        if row is None:
            abort(404)
    extras = {"cast": [], "genres": [], "trailer": None, "imdb": None, "watch": None}
    try:
        payload = catalog.movie_detail(movie_id)
        extras.update(
            cast=tvdb.cast_from(payload),
            genres=tvdb.genres_from(payload),
            trailer=tvdb.trailer_from(payload),
            imdb=tvdb.imdb_from(payload),
            watch=streaming.lookup(tvdb.imdb_id_from(payload)) if queries.is_released(row) else None,
        )
        if row["original_language"] is None and payload.get("original_language"):
            db.execute("UPDATE movie SET original_language = ? WHERE id = ?",
                       (payload["original_language"], movie_id))
            row = db.query("SELECT * FROM movie WHERE id = ?", (movie_id,), one=True)
    except catalog.TvdbError:
        pass

    tracked = queries.movie_list_state(movie_id)
    return render_template(
        "pages/movie.html",
        extras=extras,
        watch_country_name=streaming.COUNTRIES.get(streaming.country(), ""),
        movie=row,
        tracked=tracked,
        shortlisted=bool(tracked and tracked["shortlist"]),
        released=queries.is_released(row),
    )

@bp.route("/movie/<int:movie_id>/track", methods=["POST"])
@login_required
def track(movie_id):
    try:
        payload = catalog.movie(movie_id)
        sync.upsert_movie(payload)
    except catalog.TvdbError as exc:
        flash(str(exc), "error")
        return back_to("movies.index")
    db.execute(
        "INSERT OR IGNORE INTO tracked_movie (movie_id, added_at) VALUES (?, ?)",
        (movie_id, clock.now_iso()),
    )
    flash(f"Added {payload.get('title') or 'this movie'}.", "success")
    return back_to("movies.index")

@bp.route("/movie/<int:movie_id>/refresh", methods=["POST"])
@login_required
def refresh(movie_id):
    try:
        sync.sync_movie(movie_id)
        flash("Checked TheTVDB for a new release date.", "success")
    except catalog.TvdbError as exc:
        flash(str(exc), "error")
    return back_to("movies.index")

@bp.route("/movie/<int:movie_id>/untrack", methods=["POST"])
@login_required
def untrack(movie_id):
    if not confirmed():
        flash("Tick \"Yes, remove it\" to remove the movie.", "error")
        return redirect(url_for("movies.detail", movie_id=movie_id))
    db.execute("DELETE FROM tracked_movie WHERE movie_id = ?", (movie_id,))
    return back_to("movies.index")

@bp.route("/movie/<int:movie_id>/maybe", methods=["POST"])
@login_required
def toggle_maybe(movie_id):
    row = queries.movie_list_state(movie_id)
    if row is None:
        abort(404)
    moving = wanted_state("maybe")
    db.execute(
        "UPDATE tracked_movie SET shortlist = ? WHERE movie_id = ?",
        (1 if moving else 0, movie_id),
    )
    flash("Moved to your maybe list." if moving else "Moved to your movies.", "success")
    return back_to("shows.maybe" if moving else "movies.index")

@bp.route("/movie/<int:movie_id>/watched", methods=["POST"])
@login_required
def watched(movie_id):
    watching = wanted_state()
    row = db.query(
        "SELECT watched_at FROM tracked_movie WHERE movie_id = ?", (movie_id,), one=True
    )
    if row is None:
        abort(404)
    db.execute(
        "UPDATE tracked_movie SET watched_at = ? WHERE movie_id = ?",
        (clock.now_iso() if watching else None, movie_id),
    )
    return back_to("movies.index")

@bp.route("/discover")
@login_required
def discover():
    service = request.args.get("service", "")
    if service not in dict(streaming.SERVICES):
        service = ""
    kind = "series" if request.args.get("kind") == "series" else "movie"
    when = "out" if request.args.get("when") == "out" else "upcoming"
    try:
        days = int(request.args.get("days", ""))
    except ValueError:
        days = streaming.DEFAULT_DISCOVER_DAYS
    if days not in streaming.DISCOVER_DAYS:
        days = streaming.DEFAULT_DISCOVER_DAYS
    code = streaming.country()
    items = streaming.discover(kind, when) if code else None
    if items is not None:
        today = clock.today_date()
        names = dict(streaming.SERVICES)
        edge = (today + timedelta(days=days) if when == "upcoming" else today - timedelta(days=days)).isoformat()
        now = today.isoformat()
        items = [
            i for i in items
            if (now <= i["date"] <= edge if when == "upcoming" else edge <= i["date"] <= now)
            and (not service or names[service] in i.get("services", []))
        ]
    held = {row["imdb_id"] for row in db.query(
        "SELECT m.imdb_id FROM movie m JOIN tracked_movie t ON t.movie_id = m.id WHERE m.imdb_id IS NOT NULL"
        " UNION SELECT s.imdb_id FROM show s JOIN tracked_show t ON t.show_id = s.id WHERE s.imdb_id IS NOT NULL")}
    return render_template(
        "pages/discover.html",
        items=items,
        kind=kind,
        when=when,
        days=days,
        held=held,
        service=service,
        services=streaming.SERVICES,
        day_choices=streaming.DISCOVER_DAYS,
        country_name=streaming.COUNTRIES.get(code, ""),
    )

@bp.route("/discover/add", methods=["POST"])
@login_required
def discover_add():
    imdb = request.form.get("imdb", "")
    day = request.form.get("date", "")
    if not re.fullmatch(r"tt\d{1,10}", imdb) or not re.fullmatch(r"\d{4}-\d\d-\d\d", day):
        abort(400)
    if request.form.get("kind") == "series":
        return _discover_add_show(imdb)
    movie_id = tvdb.movie_id_by_imdb(imdb)
    if movie_id is None:
        flash("TheTVDB does not list that movie yet, so it cannot be added.", "error")
        return back_to("movies.discover")
    try:
        payload = catalog.movie(movie_id)
        sync.upsert_movie(payload)
    except catalog.TvdbError as exc:
        flash(str(exc), "error")
        return back_to("movies.discover")
    db.execute("UPDATE movie SET digital_release = ?, release_date = ?, imdb_id = ? WHERE id = ?",
               (day, day, imdb, movie_id))
    db.execute("INSERT OR IGNORE INTO tracked_movie (movie_id, added_at) VALUES (?, ?)",
               (movie_id, clock.now_iso()))
    flash(f"Added {payload.get('title') or 'this movie'}. It shows on the calendar on {day}.", "success")
    return back_to("movies.discover")

def _discover_add_show(imdb):
    show_id = tvdb.series_id_by_imdb(imdb)
    if show_id is None:
        flash("TheTVDB does not list that show yet, so it cannot be added.", "error")
        return back_to("movies.discover")
    failed = []
    try:
        name = sync.sync_show(show_id, failed)
    except catalog.TvdbError as exc:
        flash(str(exc), "error")
        return back_to("movies.discover")
    db.execute("UPDATE show SET imdb_id = ? WHERE id = ?", (imdb, show_id))
    db.execute(
        "INSERT INTO tracked_show (show_id, added_at, shortlist) VALUES (?, ?, 0)"
        " ON CONFLICT(show_id) DO UPDATE SET archived = 0",
        (show_id, clock.now_iso()),
    )
    flash(f"Added {name} to your shows.", "success")
    return back_to("movies.discover")
