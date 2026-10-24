from flask import Blueprint, abort, flash, redirect, render_template, url_for

from .. import clock, db, queries, sync, tmdb
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
        provider_names=queries.provider_names,
    )

@bp.route("/movie/<int:movie_id>")
@login_required
def detail(movie_id):
    row = db.query("SELECT * FROM movie WHERE id = ?", (movie_id,), one=True)
    if row is None:
        try:
            sync.upsert_movie(tmdb.movie(movie_id))
        except tmdb.TmdbError as exc:
            flash(str(exc), "error")
            return redirect(url_for("main.search"))
        row = db.query("SELECT * FROM movie WHERE id = ?", (movie_id,), one=True)
        if row is None:
            abort(404)
    extras = {"cast": [], "crew": [], "genres": [], "trailer": None,
              "imdb": None, "certification": None, "tagline": None}
    try:
        payload = tmdb.movie_detail(movie_id)
        extras.update(
            cast=tmdb.cast_from(payload),
            crew=tmdb.crew_from(payload),
            genres=tmdb.genres_from(payload),
            trailer=tmdb.trailer_from(payload),
            imdb=tmdb.imdb_from(payload),
            certification=tmdb.certification_from(payload),
            tagline=payload.get("tagline") or None,
        )
    except tmdb.TmdbError:
        pass

    tracked = queries.movie_list_state(movie_id)
    return render_template(
        "pages/movie.html",
        extras=extras,
        movie=row,
        tracked=tracked,
        shortlisted=bool(tracked and tracked["shortlist"]),
        providers=queries.provider_names(row),
        streamable=queries.is_streamable(row),
    )

@bp.route("/movie/<int:movie_id>/track", methods=["POST"])
@login_required
def track(movie_id):
    try:
        payload = tmdb.movie(movie_id)
        sync.upsert_movie(payload)
    except tmdb.TmdbError as exc:
        flash(str(exc), "error")
        return back_to("movies.index")
    db.execute(
        "INSERT OR IGNORE INTO tracked_movie (movie_id, added_at) VALUES (?, ?)",
        (movie_id, clock.now_iso()),
    )
    try:
        digital, names = sync.sync_movie_availability(movie_id)
    except tmdb.TmdbError:
        digital, names = None, []
    title = payload.get("title") or "this film"
    if names:
        flash(f"Added {title}. It is on {', '.join(names)} now.", "success")
    elif digital:
        flash(f"Added {title}. Streaming from {digital}.", "success")
    else:
        flash(f"Added {title}. No streaming date announced yet.", "success")
    return back_to("movies.index")

@bp.route("/movie/<int:movie_id>/refresh", methods=["POST"])
@login_required
def refresh(movie_id):
    try:
        sync.sync_movie_availability(movie_id)
        flash("Checked TMDB for a streaming date.", "success")
    except tmdb.TmdbError as exc:
        flash(str(exc), "error")
    return back_to("movies.index")

@bp.route("/movie/<int:movie_id>/untrack", methods=["POST"])
@login_required
def untrack(movie_id):
    if not confirmed():
        flash("Tick \"Yes, remove it\" to remove the film.", "error")
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
    flash("Moved to your maybe list." if moving else "Moved to your films.", "success")
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
