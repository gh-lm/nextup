"""The read-side of the app: what to watch, what is coming, how far in."""
from datetime import timedelta

from . import clock, db, secretstore

DEFAULT_AVAILABLE_AFTER = 1

FALLBACK_RUNTIME = 45

def newest_first():
    return secretstore.get("season_order", "newest") != "oldest"

def date_order():
    return "newest" if newest_first() else "oldest"

def dated(rows, key):
    have = [r for r in rows if key(r)]
    have.sort(key=key, reverse=newest_first())
    return have + [r for r in rows if not key(r)]

def available_after_days():
    raw = secretstore.get("available_after_days", str(DEFAULT_AVAILABLE_AFTER))
    try:
        return max(0, min(14, int(raw)))
    except (TypeError, ValueError):
        return DEFAULT_AVAILABLE_AFTER

def available_cutoff():
    return clock.today_date() - timedelta(days=available_after_days())

def available_cutoff_iso():
    return available_cutoff().isoformat()

def tracked_shows(include_archived=False, shortlist=False, everything=False):
    clauses = []
    if not everything:
        clauses.append("t.shortlist = 1" if shortlist else "t.shortlist = 0")
        if not include_archived:
            clauses.append("t.archived = 0")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return db.query(
        f"""
        SELECT s.*, t.added_at, t.archived, t.favourite, t.shortlist
        FROM show s JOIN tracked_show t ON t.show_id = s.id
        {where}
        ORDER BY s.name COLLATE NOCASE
        """
    )

def show_list_state(show_id):
    return db.query(
        "SELECT archived, favourite, shortlist, auto_unarchive FROM tracked_show WHERE show_id = ?",
        (show_id,),
        one=True,
    )

def latest_season(show_id):
    row = db.query(
        "SELECT MAX(season_number) AS n FROM episode WHERE show_id = ? AND season_number > 0",
        (show_id,),
        one=True,
    )
    return (row["n"] or 0) if row else 0

def is_tracked(show_id):
    return db.query("SELECT 1 FROM tracked_show WHERE show_id = ?", (show_id,), one=True) is not None

def show_progress(show_id):
    row = db.query(
        """
        SELECT
            (SELECT COUNT(*) FROM episode e
              WHERE e.show_id = ? AND e.season_number > 0
                AND e.air_date IS NOT NULL AND e.air_date <= ?) AS aired,
            (SELECT COUNT(*) FROM episode e
              JOIN watched_episode w ON w.episode_id = e.id
              WHERE e.show_id = ? AND e.season_number > 0) AS watched,
            (SELECT COUNT(*) FROM episode e
              WHERE e.show_id = ? AND e.season_number > 0) AS total
        """,
        (show_id, clock.today(), show_id, show_id),
        one=True,
    )
    return _progress(row["aired"], row["watched"], row["total"])

def _progress(aired, watched, total):
    aired, watched, total = aired or 0, watched or 0, total or 0
    return {
        "aired": aired,
        "watched": watched,
        "total": total,
        "remaining": max(0, aired - watched),
        "percent": round(100 * watched / aired) if aired else 0,
        "complete": aired > 0 and watched >= aired,
    }

def all_progress():
    today = clock.today()
    totals = {
        row["show_id"]: (row["aired"], row["total"])
        for row in db.query(
            "SELECT show_id, COUNT(*) AS total,"
            " SUM(air_date IS NOT NULL AND air_date <= ?) AS aired"
            " FROM episode WHERE season_number > 0 GROUP BY show_id",
            (today,),
        )
    }
    watched = {
        row["show_id"]: row["n"]
        for row in db.query(
            "SELECT e.show_id, COUNT(*) AS n FROM episode e"
            " JOIN watched_episode w ON w.episode_id = e.id"
            " WHERE e.season_number > 0 GROUP BY e.show_id"
        )
    }
    return {
        show_id: _progress(aired, watched.get(show_id), total)
        for show_id, (aired, total) in totals.items()
    }

def empty_progress():
    return _progress(0, 0, 0)

def next_unwatched(show_id):
    return db.query(
        """
        SELECT e.* FROM episode e
        LEFT JOIN watched_episode w ON w.episode_id = e.id
        WHERE e.show_id = ? AND e.season_number > 0 AND w.episode_id IS NULL
          AND e.air_date IS NOT NULL AND e.air_date <= ?
        ORDER BY e.season_number, e.episode_number
        LIMIT 1
        """,
        (show_id, available_cutoff_iso()),
        one=True,
    )

def next_airing(show_id):
    return db.query(
        """
        SELECT e.* FROM episode e
        WHERE e.show_id = ? AND e.air_date IS NOT NULL AND e.air_date > ?
        ORDER BY e.air_date, e.season_number, e.episode_number
        LIMIT 1
        """,
        (show_id, clock.today()),
        one=True,
    )

def ready_to_watch(order=None, page=1, per_page=60):
    cutoff = available_cutoff_iso()
    episodes = db.query(
        """
        SELECT e.*, s.name AS show_name, s.poster_path AS show_poster
        FROM episode e
        JOIN show s ON s.id = e.show_id
        JOIN tracked_show t ON t.show_id = e.show_id
             AND t.archived = 0 AND t.shortlist = 0
        LEFT JOIN watched_episode w ON w.episode_id = e.id
        WHERE w.episode_id IS NULL AND e.season_number > 0
          AND e.air_date IS NOT NULL AND e.air_date <= ?
        ORDER BY e.air_date DESC
        """,
        (cutoff,),
    )

    items = [
        {
            "kind": "episode",
            "date": row["air_date"],
            "show_id": row["show_id"],
            "show_name": row["show_name"],
            "poster_path": row["show_poster"],
            "episode": row,
        }
        for row in episodes
    ]
    for film in movies(watched=False, shortlist=False):
        if is_streamable(film, cutoff):
            items.append({"kind": "film", "date": film["digital_release"], "film": film})

    order = order or date_order()
    missing = "0000-00-00" if order == "newest" else "9999-99-99"
    items.sort(key=lambda item: (item["date"] or missing), reverse=(order == "newest"))

    total = len(items)
    pages = max(1, -(-total // per_page))
    page = max(1, min(page, pages))
    start = (page - 1) * per_page
    window = items[start : start + per_page]

    progress_cache, seen = {}, set()
    for item in window:
        if item["kind"] != "episode":
            continue
        show_id = item["show_id"]
        if show_id not in progress_cache:
            progress_cache[show_id] = show_progress(show_id)
        item["progress"] = progress_cache[show_id]
        item["lead"] = show_id not in seen
        seen.add(show_id)

    return {
        "rows": window,
        "total": total,
        "page": page,
        "pages": pages,
        "first": start + 1 if window else 0,
        "last": start + len(window),
    }

def available_today():
    cutoff = available_cutoff_iso()
    episodes = db.query(
        """
        SELECT e.*, s.name AS show_name, s.network, s.poster_path AS show_poster,
               (w.episode_id IS NOT NULL) AS watched
        FROM episode e
        JOIN show s ON s.id = e.show_id
        JOIN tracked_show t ON t.show_id = e.show_id
             AND t.archived = 0 AND t.shortlist = 0
        LEFT JOIN watched_episode w ON w.episode_id = e.id
        WHERE e.air_date = ?
        ORDER BY s.name COLLATE NOCASE, e.season_number, e.episode_number
        """,
        (cutoff,),
    )
    films = db.query(
        """
        SELECT m.* FROM movie m
        JOIN tracked_movie t ON t.movie_id = m.id
        WHERE t.watched_at IS NULL AND t.shortlist = 0 AND m.digital_release = ?
        ORDER BY m.title COLLATE NOCASE
        """,
        (cutoff,),
    )
    return {"date": cutoff, "episodes": episodes, "films": films}

def upcoming(days=30, limit=None):
    end = (clock.today_date() + timedelta(days=days)).isoformat()
    sql = """
        SELECT e.*, s.name AS show_name, s.poster_path, s.network
        FROM episode e
        JOIN show s ON s.id = e.show_id
        JOIN tracked_show t ON t.show_id = e.show_id
             AND t.archived = 0 AND t.shortlist = 0
        WHERE e.air_date IS NOT NULL AND e.air_date >= ? AND e.air_date <= ?
        ORDER BY e.air_date, s.name COLLATE NOCASE, e.season_number, e.episode_number
    """
    if limit:
        sql += f" LIMIT {int(limit)}"
    return db.query(sql, (clock.today(), end))

def episodes_between(start_iso, end_iso):
    return db.query(
        """
        SELECT e.*, s.name AS show_name, s.poster_path,
               (w.episode_id IS NOT NULL) AS watched
        FROM episode e
        JOIN show s ON s.id = e.show_id
        JOIN tracked_show t ON t.show_id = e.show_id
             AND t.archived = 0 AND t.shortlist = 0
        LEFT JOIN watched_episode w ON w.episode_id = e.id
        WHERE e.air_date IS NOT NULL AND e.air_date >= ? AND e.air_date <= ?
        ORDER BY e.air_date, s.name COLLATE NOCASE, e.season_number, e.episode_number
        """,
        (start_iso, end_iso),
    )

def films_between(start_iso, end_iso):
    return db.query(
        """
        SELECT m.*, t.watched_at FROM movie m
        JOIN tracked_movie t ON t.movie_id = m.id
        WHERE t.shortlist = 0
          AND m.digital_release IS NOT NULL
          AND m.digital_release >= ? AND m.digital_release <= ?
        ORDER BY m.digital_release, m.title COLLATE NOCASE
        """,
        (start_iso, end_iso),
    )

def show_seasons(show_id):
    rows = db.query(
        """
        SELECT e.*, (w.episode_id IS NOT NULL) AS watched
        FROM episode e
        LEFT JOIN watched_episode w ON w.episode_id = e.id
        WHERE e.show_id = ?
        ORDER BY e.season_number, e.episode_number
        """,
        (show_id,),
    )
    seasons = {}
    for row in rows:
        seasons.setdefault(row["season_number"], []).append(row)
    ordered = []
    for number in sorted(seasons):
        episodes = seasons[number]
        aired = [e for e in episodes if e["air_date"] and e["air_date"] <= clock.today()]
        watched = [e for e in episodes if e["watched"]]
        ordered.append(
            {
                "number": number,
                "episodes": episodes,
                "aired_count": len(aired),
                "watched_count": len(watched),
                "complete": bool(aired) and len(watched) >= len(aired),
            }
        )
    if newest_first():
        ordered.reverse()
        for season in ordered:
            season["episodes"] = list(reversed(season["episodes"]))
    return ordered

def episode_neighbours(show_id, season_number, episode_number):
    previous = db.query(
        """
        SELECT * FROM episode WHERE show_id = ?
          AND (season_number < ? OR (season_number = ? AND episode_number < ?))
        ORDER BY season_number DESC, episode_number DESC LIMIT 1
        """,
        (show_id, season_number, season_number, episode_number),
        one=True,
    )
    following = db.query(
        """
        SELECT * FROM episode WHERE show_id = ?
          AND (season_number > ? OR (season_number = ? AND episode_number > ?))
        ORDER BY season_number, episode_number LIMIT 1
        """,
        (show_id, season_number, season_number, episode_number),
        one=True,
    )
    return previous, following

def recently_watched(limit=12):
    return db.query(
        """
        SELECT e.*, s.name AS show_name, s.poster_path, w.watched_at
        FROM watched_episode w
        JOIN episode e ON e.id = w.episode_id
        JOIN show s ON s.id = e.show_id
        ORDER BY w.watched_at DESC, e.season_number DESC, e.episode_number DESC
        LIMIT ?
        """,
        (limit,),
    )

def movies(watched=None, shortlist=False, everything=False):
    clauses = []
    if not everything:
        clauses.append("t.shortlist = 1" if shortlist else "t.shortlist = 0")
        if watched is True:
            clauses.append("t.watched_at IS NOT NULL")
        elif watched is False:
            clauses.append("t.watched_at IS NULL")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return db.query(
        f"""
        SELECT m.*, t.added_at, t.watched_at, t.shortlist
        FROM movie m JOIN tracked_movie t ON t.movie_id = m.id
        {where}
        ORDER BY t.added_at DESC
        """
    )

def movie_list_state(movie_id):
    return db.query(
        "SELECT watched_at, shortlist FROM tracked_movie WHERE movie_id = ?",
        (movie_id,),
        one=True,
    )

def dismissed_ids(kind):
    return {
        row["item_id"]
        for row in db.query("SELECT item_id FROM dismissed WHERE kind = ?", (kind,))
    }

def known_ids():
    return (
        {row["show_id"] for row in db.query("SELECT show_id FROM tracked_show")},
        {row["movie_id"] for row in db.query("SELECT movie_id FROM tracked_movie")},
    )

def provider_names(row):
    value = row["providers"] if "providers" in row.keys() else None
    return [line for line in (value or "").split("\n") if line]

def is_streamable(row, cutoff=None):
    if provider_names(row):
        return True
    digital = row["digital_release"] if "digital_release" in row.keys() else None
    return bool(digital and digital <= (cutoff or available_cutoff_iso()))

def films_by_state():
    ready, waiting = [], []
    cutoff = available_cutoff_iso()
    for row in movies(watched=False, shortlist=False):
        (ready if is_streamable(row, cutoff) else waiting).append(row)
    return {
        "ready": dated(ready, lambda r: r["digital_release"] or r["release_date"]),
        "waiting": sorted(waiting, key=lambda r: r["digital_release"] or "9999-99-99"),
        "seen": dated(movies(watched=True), lambda r: r["watched_at"]),
        "maybe": movies(shortlist=True),
    }

def films_arriving(days=60):
    end = (clock.today_date() + timedelta(days=days)).isoformat()
    return db.query(
        """
        SELECT m.*, t.added_at FROM movie m
        JOIN tracked_movie t ON t.movie_id = m.id
        WHERE t.watched_at IS NULL AND t.shortlist = 0
          AND m.digital_release IS NOT NULL
          AND m.digital_release >= ? AND m.digital_release <= ?
        ORDER BY m.digital_release
        """,
        (clock.today(), end),
    )

def coming_soon(days=21, limit=12):
    items = [("episode", row["air_date"], row) for row in upcoming(days=days)]
    items += [("film", row["digital_release"], row) for row in films_arriving(days=days)]
    items.sort(key=lambda item: item[1])
    return items[:limit]

def dashboard_counts():
    row = db.query(
        """
        SELECT
            (SELECT COUNT(*) FROM tracked_show WHERE archived = 0 AND shortlist = 0) AS shows,
            (SELECT COUNT(*) FROM tracked_show WHERE shortlist = 1) AS maybe_shows,
            (SELECT COUNT(*) FROM watched_episode) AS episodes_watched,
            (SELECT COUNT(*) FROM tracked_movie WHERE watched_at IS NULL AND shortlist = 0) AS movies_to_watch,
            (SELECT COALESCE(SUM(COALESCE(e.runtime, s.episode_runtime, ?)), 0)
               FROM watched_episode w
               JOIN episode e ON e.id = w.episode_id
               JOIN show s ON s.id = e.show_id) AS minutes_watched
        """,
        (FALLBACK_RUNTIME,),
        one=True,
    )
    return dict(row)

