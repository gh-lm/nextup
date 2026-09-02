"""The read-side of the app: what to watch, what is coming, how far in.

Season 0 (specials) is deliberately excluded from progress and from
"next up", because counting specials makes every show look unfinished.
Specials are still visible on the show page.
"""
from datetime import date, timedelta

from . import db

TODAY = "date('now')"


def tracked_shows(include_archived=False, shortlist=False, everything=False):
    """Shows you follow. Set shortlist=True for the maybe list instead."""
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
    """None if untracked, otherwise the row saying which list it is on."""
    return db.query(
        "SELECT archived, favourite, shortlist FROM tracked_show WHERE show_id = ?",
        (show_id,),
        one=True,
    )


def is_tracked(show_id):
    return db.query("SELECT 1 FROM tracked_show WHERE show_id = ?", (show_id,), one=True) is not None


def is_tracked_movie(movie_id):
    return db.query("SELECT 1 FROM tracked_movie WHERE movie_id = ?", (movie_id,), one=True) is not None


def show_progress(show_id):
    row = db.query(
        """
        SELECT
            (SELECT COUNT(*) FROM episode e
              WHERE e.show_id = ? AND e.season_number > 0
                AND e.air_date IS NOT NULL AND e.air_date <= date('now')) AS aired,
            (SELECT COUNT(*) FROM episode e
              JOIN watched_episode w ON w.episode_id = e.id
              WHERE e.show_id = ? AND e.season_number > 0) AS watched,
            (SELECT COUNT(*) FROM episode e
              WHERE e.show_id = ? AND e.season_number > 0) AS total
        """,
        (show_id, show_id, show_id),
        one=True,
    )
    aired = row["aired"] or 0
    watched = row["watched"] or 0
    return {
        "aired": aired,
        "watched": watched,
        "total": row["total"] or 0,
        "remaining": max(0, aired - watched),
        "percent": round(100 * watched / aired) if aired else 0,
        "complete": aired > 0 and watched >= aired,
    }


def next_unwatched(show_id):
    """The earliest aired episode not yet ticked off."""
    return db.query(
        """
        SELECT e.* FROM episode e
        LEFT JOIN watched_episode w ON w.episode_id = e.id
        WHERE e.show_id = ? AND e.season_number > 0 AND w.episode_id IS NULL
          AND e.air_date IS NOT NULL AND e.air_date <= date('now')
        ORDER BY e.season_number, e.episode_number
        LIMIT 1
        """,
        (show_id,),
        one=True,
    )


def next_airing(show_id):
    """The next episode still to be broadcast."""
    return db.query(
        """
        SELECT e.* FROM episode e
        WHERE e.show_id = ? AND e.air_date IS NOT NULL AND e.air_date > date('now')
        ORDER BY e.air_date, e.season_number, e.episode_number
        LIMIT 1
        """,
        (show_id,),
        one=True,
    )


def to_watch():
    """Every tracked show with something aired and unwatched, oldest first."""
    out = []
    for show in tracked_shows():
        episode = next_unwatched(show["id"])
        if episode is None:
            continue
        progress = show_progress(show["id"])
        out.append({"show": show, "episode": episode, "progress": progress})
    out.sort(key=lambda item: (item["episode"]["air_date"] or "9999-99-99"))
    return out


def upcoming(days=30, limit=None):
    """Episodes of tracked shows airing between today and `days` ahead."""
    end = (date.today() + timedelta(days=days)).isoformat()
    sql = """
        SELECT e.*, s.name AS show_name, s.poster_path, s.network
        FROM episode e
        JOIN show s ON s.id = e.show_id
        JOIN tracked_show t ON t.show_id = e.show_id
             AND t.archived = 0 AND t.shortlist = 0
        WHERE e.air_date IS NOT NULL AND e.air_date >= date('now') AND e.air_date <= ?
        ORDER BY e.air_date, s.name COLLATE NOCASE, e.season_number, e.episode_number
    """
    if limit:
        sql += f" LIMIT {int(limit)}"
    return db.query(sql, (end,))


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


def show_seasons(show_id):
    """Every episode grouped by season, with a watched flag on each."""
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
        aired = [e for e in episodes if e["air_date"] and e["air_date"] <= date.today().isoformat()]
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
    return ordered


def episode_neighbours(show_id, season_number, episode_number):
    """The episode before and after this one, for stepping through a series."""
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
    """Films on your list. Set shortlist=True for the maybe list instead."""
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
    """Everything you said no to on the Discover pages."""
    return {
        row["item_id"]
        for row in db.query("SELECT item_id FROM dismissed WHERE kind = ?", (kind,))
    }


def is_dismissed(kind, item_id):
    return db.query(
        "SELECT 1 FROM dismissed WHERE kind = ? AND item_id = ?", (kind, item_id), one=True
    ) is not None


def known_ids():
    """Every show and film already on a list, so Discover can skip them."""
    return (
        {row["show_id"] for row in db.query("SELECT show_id FROM tracked_show")},
        {row["movie_id"] for row in db.query("SELECT movie_id FROM tracked_movie")},
    )


def provider_names(row):
    value = row["providers"] if "providers" in row.keys() else None
    return [line for line in (value or "").split("\n") if line]


def is_streamable(row):
    """True once a film can actually be watched at home."""
    if provider_names(row):
        return True
    digital = row["digital_release"] if "digital_release" in row.keys() else None
    return bool(digital and digital <= date.today().isoformat())


def films_by_state():
    """Films split into ready to watch, still waiting, and already seen."""
    ready, waiting = [], []
    for row in movies(watched=False, shortlist=False):
        (ready if is_streamable(row) else waiting).append(row)
    waiting.sort(key=lambda r: (r["digital_release"] or "9999-99-99"))
    return {
        "ready": ready,
        "waiting": waiting,
        "seen": movies(watched=True),
        "maybe": movies(shortlist=True),
    }


def films_arriving(days=60):
    """Films whose streaming date falls inside the window."""
    end = (date.today() + timedelta(days=days)).isoformat()
    return db.query(
        """
        SELECT m.*, t.added_at FROM movie m
        JOIN tracked_movie t ON t.movie_id = m.id
        WHERE t.watched_at IS NULL AND t.shortlist = 0
          AND m.digital_release IS NOT NULL
          AND m.digital_release >= date('now') AND m.digital_release <= ?
        ORDER BY m.digital_release
        """,
        (end,),
    )


def dashboard_counts():
    row = db.query(
        """
        SELECT
            (SELECT COUNT(*) FROM tracked_show WHERE archived = 0 AND shortlist = 0) AS shows,
            (SELECT COUNT(*) FROM tracked_show WHERE shortlist = 1) AS maybe_shows,
            (SELECT COUNT(*) FROM watched_episode) AS episodes_watched,
            (SELECT COUNT(*) FROM tracked_movie WHERE watched_at IS NULL AND shortlist = 0) AS movies_to_watch,
            (SELECT COALESCE(SUM(COALESCE(e.runtime, s.episode_runtime, 45)), 0)
               FROM watched_episode w
               JOIN episode e ON e.id = w.episode_id
               JOIN show s ON s.id = e.show_id) AS minutes_watched
        """,
        one=True,
    )
    return dict(row)
