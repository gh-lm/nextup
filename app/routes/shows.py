from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import clock, db, queries, sync, tmdb
from ..auth import login_required
from ..forms import confirmed, wanted_state
from ..redirects import back_to

bp = Blueprint("shows", __name__)

def _mark_watched(show_id, episode_ids):
    conn = db.get_db()
    stamp = clock.now_iso()
    conn.executemany(
        "INSERT OR IGNORE INTO watched_episode (episode_id, show_id, watched_at)"
        " VALUES (?, ?, ?)",
        [(episode_id, show_id, stamp) for episode_id in episode_ids],
    )
    conn.commit()

@bp.route("/shows")
@login_required
def index():
    view = request.args.get("view", "active")
    rows = queries.tracked_shows(include_archived=(view == "archived"))
    if view == "archived":
        rows = [row for row in rows if row["archived"]]
    shows = []
    progress = queries.all_progress()
    for row in rows:
        shows.append(
            {
                "show": row,
                "progress": progress.get(row["id"]) or queries.empty_progress(),
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
    kind = "movies" if request.args.get("kind") == "movies" else "tv"
    shows = []
    for row in queries.tracked_shows(shortlist=True):
        shows.append({"show": row, "next_air": queries.next_airing(row["id"])})
    shows = queries.dated(shows, lambda item: item["show"]["first_air_date"])
    films = queries.dated(queries.movies(shortlist=True), lambda row: row["release_date"])
    return render_template("pages/maybe.html", kind=kind, shows=shows, films=films)

@bp.route("/show/<int:show_id>")
@login_required
def detail(show_id):
    row = db.query("SELECT * FROM show WHERE id = ?", (show_id,), one=True)
    if row is None:
        try:
            sync.upsert_show(tmdb.show(show_id), stamp=False)
        except tmdb.TmdbError as exc:
            flash(str(exc), "error")
            return redirect(url_for("main.search"))
        row = db.query("SELECT * FROM show WHERE id = ?", (show_id,), one=True)
        if row is None:
            abort(404)

    extras = {"cast": [], "genres": [], "creators": [], "providers": [],
              "trailer": None, "imdb": None,
              "certification": None, "tagline": None, "homepage": None}
    try:
        payload = tmdb.show_detail(show_id)
        extras.update(
            cast=tmdb.cast_from(payload),
            genres=tmdb.genres_from(payload),
            creators=tmdb.creators_from(payload),
            providers=tmdb.providers_from(payload)[0],
            trailer=tmdb.trailer_from(payload),
            imdb=tmdb.imdb_from(payload),
            certification=tmdb.certification_from(payload),
            tagline=payload.get("tagline") or None,
            homepage=tmdb.safe_url(payload.get("homepage")),
        )
        if row["original_language"] is None and payload.get("original_language"):
            db.execute("UPDATE show SET original_language = ? WHERE id = ?",
                       (payload["original_language"], show_id))
            row = db.query("SELECT * FROM show WHERE id = ?", (show_id,), one=True)
    except tmdb.TmdbError:
        pass

    tracked_row = queries.show_list_state(show_id)
    return render_template(
        "pages/show.html",
        show=row,
        tracked=tracked_row is not None,
        archived=bool(tracked_row and tracked_row["archived"]),
        auto_unarchive=bool(tracked_row and tracked_row["auto_unarchive"]),
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
    wants_maybe = request.form.get("list") == "maybe"
    failed = []
    try:
        name = sync.sync_show(show_id, failed)
    except tmdb.TmdbError as exc:
        flash(str(exc), "error")
        return back_to("main.search", q="")
    db.execute(
        "INSERT INTO tracked_show (show_id, added_at, shortlist) VALUES (?, ?, ?)"
        " ON CONFLICT(show_id) DO UPDATE SET archived = 0,"
        " shortlist = excluded.shortlist",
        (show_id, clock.now_iso(), 1 if wants_maybe else 0),
    )
    if failed:
        flash(f"TMDB would not serve season {', '.join(str(n) for n in failed)}. It will be tried again.", "error")
    if wants_maybe:
        flash(f"Put {name} on your maybe list.", "success")
        return back_to("shows.maybe")
    flash(f"Added {name} to your shows.", "success")
    return back_to("shows.index")

@bp.route("/show/<int:show_id>/maybe", methods=["POST"])
@login_required
def toggle_maybe(show_id):
    row = queries.show_list_state(show_id)
    if row is None:
        abort(404)
    moving_to_maybe = wanted_state("maybe")
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
    if not confirmed():
        flash("Tick \"Yes, remove it\" to remove the show.", "error")
        return redirect(url_for("shows.detail", show_id=show_id))
    conn = db.get_db()
    conn.execute("DELETE FROM tracked_show WHERE show_id = ?", (show_id,))
    conn.execute("DELETE FROM watched_episode WHERE show_id = ?", (show_id,))
    conn.commit()
    flash("Removed from your shows, along with its watched history.", "success")
    return back_to("shows.index")

@bp.route("/show/<int:show_id>/archive", methods=["POST"])
@login_required
def archive(show_id):
    archiving = wanted_state()
    if queries.show_list_state(show_id) is None:
        abort(404)
    db.execute(
        "UPDATE tracked_show SET archived = ?, archived_season = ? WHERE show_id = ?",
        (1 if archiving else 0, queries.latest_season(show_id), show_id),
    )
    return back_to("shows.index")

@bp.route("/show/<int:show_id>/auto-unarchive", methods=["POST"])
@login_required
def auto_unarchive(show_id):
    if queries.show_list_state(show_id) is None:
        abort(404)
    db.execute(
        "UPDATE tracked_show SET auto_unarchive = ? WHERE show_id = ?",
        (1 if request.form.get("on") else 0, show_id),
    )
    return back_to("shows.detail", show_id=show_id)

@bp.route("/show/<int:show_id>/favourite", methods=["POST"])
@login_required
def favourite(show_id):
    favouring = wanted_state()
    if queries.show_list_state(show_id) is None:
        abort(404)
    db.execute(
        "UPDATE tracked_show SET favourite = ? WHERE show_id = ?",
        (1 if favouring else 0, show_id),
    )
    return back_to("shows.index")

@bp.route("/show/<int:show_id>/refresh", methods=["POST"])
@login_required
def refresh(show_id):
    try:
        failed = []
        sync.sync_show(show_id, failed)
        if failed:
            seasons = ", ".join(str(n) for n in failed)
            flash(f"Refreshed, but TMDB would not serve season {seasons}. It will be tried again.", "error")
        else:
            flash("Refreshed from TMDB.", "success")
    except tmdb.TmdbError as exc:
        flash(str(exc), "error")
    return back_to("shows.detail", show_id=show_id)

@bp.route("/episode/<int:episode_id>")
@login_required
def episode(episode_id):
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

    guests, crew, rating, providers = [], [], None, []
    try:
        providers = tmdb.watch_providers(tmdb.show_providers(row["show_id"]))[0]
    except tmdb.TmdbError:
        pass
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
        providers=providers,
        previous=previous,
        following=following,
    )

@bp.route("/episode/<int:episode_id>/watch", methods=["POST"])
@login_required
def watch_episode(episode_id):
    row = db.query("SELECT id, show_id FROM episode WHERE id = ?", (episode_id,), one=True)
    if row is None:
        abort(404)
    if wanted_state():
        _mark_watched(row["show_id"], [episode_id])
    else:
        db.execute("DELETE FROM watched_episode WHERE episode_id = ?", (episode_id,))
    return back_to("main.dashboard")

@bp.route("/show/<int:show_id>/watch-through/<int:episode_id>", methods=["POST"])
@login_required
def watch_through(show_id, episode_id):
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
          AND e.air_date IS NOT NULL AND e.air_date <= ?
          AND (e.season_number < ? OR (e.season_number = ? AND e.episode_number <= ?))
        """,
        (show_id, clock.today(), target["season_number"], target["season_number"], target["episode_number"]),
    )
    _mark_watched(show_id, [row["id"] for row in rows])
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
            " AND air_date IS NOT NULL AND air_date <= ?",
            (show_id, season_number, clock.today()),
        )
        _mark_watched(show_id, [row["id"] for row in rows])
    return back_to("shows.detail", show_id=show_id)
