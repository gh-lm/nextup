from datetime import datetime, timezone

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import db, queries, sync, tmdb
from ..auth import login_required
from ..redirects import back_to

bp = Blueprint("shows", __name__)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@bp.route("/shows")
@login_required
def index():
    view = request.args.get("view", "active")
    rows = queries.tracked_shows(include_archived=(view == "archived"))
    if view == "archived":
        rows = [row for row in rows if row["archived"]]
    shows = []
    for row in rows:
        shows.append(
            {
                "show": row,
                "progress": queries.show_progress(row["id"]),
                "next_up": queries.next_unwatched(row["id"]),
                "next_air": queries.next_airing(row["id"]),
            }
        )
    if view == "behind":
        shows = [item for item in shows if item["progress"]["remaining"] > 0]
    shows.sort(key=lambda item: (not item["show"]["favourite"], item["show"]["name"].lower()))
    return render_template("pages/shows.html", shows=shows, view=view)


@bp.route("/maybe")
@login_required
def maybe():
    """Shows you are curious about but are not following yet."""
    shows = []
    for row in queries.tracked_shows(shortlist=True):
        shows.append({"show": row, "next_air": queries.next_airing(row["id"])})
    return render_template(
        "pages/maybe.html", shows=shows, films=queries.movies(shortlist=True)
    )


@bp.route("/show/<int:show_id>")
@login_required
def detail(show_id):
    row = db.query("SELECT * FROM show WHERE id = ?", (show_id,), one=True)
    if row is None:
        # Not seen before - pull it straight from TMDB so the page still works.
        try:
            sync.upsert_show(tmdb.show(show_id))
        except tmdb.TmdbError as exc:
            flash(str(exc), "error")
            return redirect(url_for("main.search"))
        row = db.query("SELECT * FROM show WHERE id = ?", (show_id,), one=True)
        if row is None:
            abort(404)

    # The extras are fetched live rather than stored: they change rarely, and a
    # page that still works when TMDB is unreachable is worth more than a cache.
    extras = {"cast": [], "genres": [], "creators": [], "providers": [],
              "provider_link": None, "trailer": None, "imdb": None,
              "certification": None, "tagline": None, "homepage": None}
    try:
        payload = tmdb.show_detail(show_id)
        names, link = tmdb.providers_from(payload)
        extras.update(
            cast=tmdb.cast_from(payload),
            genres=tmdb.genres_from(payload),
            creators=tmdb.creators_from(payload),
            providers=names,
            provider_link=link,
            trailer=tmdb.trailer_from(payload),
            imdb=tmdb.imdb_from(payload),
            certification=tmdb.certification_from(payload),
            tagline=payload.get("tagline") or None,
            homepage=payload.get("homepage") or None,
        )
    except tmdb.TmdbError:
        pass

    tracked_row = queries.show_list_state(show_id)
    return render_template(
        "pages/show.html",
        show=row,
        tracked=tracked_row is not None,
        archived=bool(tracked_row and tracked_row["archived"]),
        show_favourite=bool(tracked_row and tracked_row["favourite"]),
        shortlisted=bool(tracked_row and tracked_row["shortlist"]),
        seasons=queries.show_seasons(show_id),
        progress=queries.show_progress(show_id),
        next_up=queries.next_unwatched(show_id),
        next_air=queries.next_airing(show_id),
        extras=extras,
    )


@bp.route("/show/<int:show_id>/track", methods=["POST"])
@login_required
def track(show_id):
    """Add a show, either to the shows you follow or to the maybe list."""
    wants_maybe = request.form.get("list") == "maybe"
    try:
        name = sync.sync_show(show_id)
    except tmdb.TmdbError as exc:
        flash(str(exc), "error")
        return back_to("main.search", q="")
    db.execute(
        "INSERT INTO tracked_show (show_id, added_at, shortlist) VALUES (?, ?, ?)"
        " ON CONFLICT(show_id) DO UPDATE SET archived = 0,"
        " shortlist = excluded.shortlist",
        (show_id, _now(), 1 if wants_maybe else 0),
    )
    if wants_maybe:
        flash(f"Put {name} on your maybe list.", "success")
        return back_to("shows.maybe")
    flash(f"Added {name} to your shows.", "success")
    return back_to("shows.index")


@bp.route("/show/<int:show_id>/maybe", methods=["POST"])
@login_required
def toggle_maybe(show_id):
    """Move a show between the list you follow and the maybe list."""
    row = queries.show_list_state(show_id)
    if row is None:
        abort(404)
    moving_to_maybe = not row["shortlist"]
    db.execute(
        "UPDATE tracked_show SET shortlist = ?, archived = 0 WHERE show_id = ?",
        (1 if moving_to_maybe else 0, show_id),
    )
    if moving_to_maybe:
        flash("Moved to your maybe list. It will stay out of Next up.", "success")
    else:
        flash("Now following this show.", "success")
    return back_to("shows.maybe" if moving_to_maybe else "shows.index")


@bp.route("/show/<int:show_id>/untrack", methods=["POST"])
@login_required
def untrack(show_id):
    db.execute("DELETE FROM tracked_show WHERE show_id = ?", (show_id,))
    db.execute("DELETE FROM watched_episode WHERE show_id = ?", (show_id,))
    flash("Removed from your shows, along with its watched history.", "success")
    return back_to("shows.index")


@bp.route("/show/<int:show_id>/archive", methods=["POST"])
@login_required
def archive(show_id):
    row = db.query("SELECT archived FROM tracked_show WHERE show_id = ?", (show_id,), one=True)
    if row is None:
        abort(404)
    db.execute(
        "UPDATE tracked_show SET archived = ? WHERE show_id = ?",
        (0 if row["archived"] else 1, show_id),
    )
    return back_to("shows.index")


@bp.route("/show/<int:show_id>/favourite", methods=["POST"])
@login_required
def favourite(show_id):
    row = db.query("SELECT favourite FROM tracked_show WHERE show_id = ?", (show_id,), one=True)
    if row is None:
        abort(404)
    db.execute(
        "UPDATE tracked_show SET favourite = ? WHERE show_id = ?",
        (0 if row["favourite"] else 1, show_id),
    )
    return back_to("shows.index")


@bp.route("/show/<int:show_id>/refresh", methods=["POST"])
@login_required
def refresh(show_id):
    try:
        sync.sync_show(show_id)
        flash("Refreshed from TMDB.", "success")
    except tmdb.TmdbError as exc:
        flash(str(exc), "error")
    return back_to("shows.detail", show_id=show_id)


@bp.route("/episode/<int:episode_id>")
@login_required
def episode(episode_id):
    """Everything known about one episode.

    Nearly all of it is already in the database. The guest cast and the
    director are the exception, so those are fetched live and simply left out
    if TMDB cannot be reached.
    """
    row = db.query(
        "SELECT e.*, (w.episode_id IS NOT NULL) AS watched FROM episode e"
        " LEFT JOIN watched_episode w ON w.episode_id = e.id WHERE e.id = ?",
        (episode_id,),
        one=True,
    )
    if row is None:
        abort(404)
    show = db.query("SELECT * FROM show WHERE id = ?", (row["show_id"],), one=True)
    if show is None:
        abort(404)

    guests, crew, rating = [], [], None
    try:
        payload = tmdb.episode(row["show_id"], row["season_number"], row["episode_number"])
        guests = [
            {"name": person.get("name"), "role": person.get("character")}
            for person in (payload.get("guest_stars") or [])[:12]
            if person.get("name")
        ]
        crew = [
            {"name": person.get("name"), "role": person.get("job")}
            for person in (payload.get("crew") or [])
            if person.get("job") in {"Director", "Writer"}
        ][:6]
        rating = payload.get("vote_average") or None
    except tmdb.TmdbError:
        pass

    previous, following = queries.episode_neighbours(
        row["show_id"], row["season_number"], row["episode_number"]
    )
    return render_template(
        "pages/episode.html",
        show=show,
        episode=row,
        tracked=queries.is_tracked(row["show_id"]),
        guests=guests,
        crew=crew,
        rating=rating,
        previous=previous,
        following=following,
    )


@bp.route("/episode/<int:episode_id>/watch", methods=["POST"])
@login_required
def watch_episode(episode_id):
    row = db.query("SELECT id, show_id FROM episode WHERE id = ?", (episode_id,), one=True)
    if row is None:
        abort(404)
    watched = db.query(
        "SELECT 1 FROM watched_episode WHERE episode_id = ?", (episode_id,), one=True
    )
    if watched:
        db.execute("DELETE FROM watched_episode WHERE episode_id = ?", (episode_id,))
    else:
        db.execute(
            "INSERT INTO watched_episode (episode_id, show_id, watched_at) VALUES (?, ?, ?)",
            (episode_id, row["show_id"], _now()),
        )
    return back_to("main.dashboard")


@bp.route("/show/<int:show_id>/watch-through/<int:episode_id>", methods=["POST"])
@login_required
def watch_through(show_id, episode_id):
    """Tick this episode and everything before it - the common catch-up case."""
    target = db.query(
        "SELECT season_number, episode_number FROM episode WHERE id = ? AND show_id = ?",
        (episode_id, show_id),
        one=True,
    )
    if target is None:
        abort(404)
    rows = db.query(
        """
        SELECT e.id FROM episode e
        LEFT JOIN watched_episode w ON w.episode_id = e.id
        WHERE e.show_id = ? AND w.episode_id IS NULL AND e.season_number > 0
          AND e.air_date IS NOT NULL AND e.air_date <= date('now')
          AND (e.season_number < ? OR (e.season_number = ? AND e.episode_number <= ?))
        """,
        (show_id, target["season_number"], target["season_number"], target["episode_number"]),
    )
    conn = db.get_db()
    conn.executemany(
        "INSERT OR IGNORE INTO watched_episode (episode_id, show_id, watched_at)"
        " VALUES (?, ?, ?)",
        [(row["id"], show_id, _now()) for row in rows],
    )
    conn.commit()
    flash(f"Marked {len(rows)} episode{'s' if len(rows) != 1 else ''} as watched.", "success")
    return back_to("shows.detail", show_id=show_id)


@bp.route("/show/<int:show_id>/season/<int:season_number>/watch", methods=["POST"])
@login_required
def watch_season(show_id, season_number):
    mode = request.form.get("mode", "watch")
    if mode == "unwatch":
        db.execute(
            "DELETE FROM watched_episode WHERE episode_id IN"
            " (SELECT id FROM episode WHERE show_id = ? AND season_number = ?)",
            (show_id, season_number),
        )
    else:
        rows = db.query(
            "SELECT id FROM episode WHERE show_id = ? AND season_number = ?"
            " AND air_date IS NOT NULL AND air_date <= date('now')",
            (show_id, season_number),
        )
        conn = db.get_db()
        conn.executemany(
            "INSERT OR IGNORE INTO watched_episode (episode_id, show_id, watched_at)"
            " VALUES (?, ?, ?)",
            [(row["id"], show_id, _now()) for row in rows],
        )
        conn.commit()
    return back_to("shows.detail", show_id=show_id)
