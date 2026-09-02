"""Pulling show and episode data from TMDB into the local database.

Sync is deliberately dumb: for each tracked show we refresh the series
record, then walk its seasons and upsert every episode. Shows that have
finished are refreshed far less often than ones still airing.
"""
import threading
from datetime import datetime, timedelta, timezone

from . import config, db, tmdb

_sync_lock = threading.Lock()
_running = False


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _network_name(payload):
    networks = payload.get("networks") or []
    if networks:
        return networks[0].get("name")
    return None


def _runtime(payload):
    times = payload.get("episode_run_time") or []
    return times[0] if times else None


def upsert_show(payload):
    db.execute(
        """
        INSERT INTO show (id, name, overview, poster_path, backdrop_path,
                          first_air_date, last_air_date, status, network,
                          episode_runtime, vote_average, synced_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            overview = excluded.overview,
            poster_path = excluded.poster_path,
            backdrop_path = excluded.backdrop_path,
            first_air_date = excluded.first_air_date,
            last_air_date = excluded.last_air_date,
            status = excluded.status,
            network = excluded.network,
            episode_runtime = excluded.episode_runtime,
            vote_average = excluded.vote_average,
            synced_at = excluded.synced_at
        """,
        (
            payload["id"],
            payload.get("name") or "Untitled",
            payload.get("overview"),
            payload.get("poster_path"),
            payload.get("backdrop_path"),
            payload.get("first_air_date") or None,
            payload.get("last_air_date") or None,
            payload.get("status"),
            _network_name(payload),
            _runtime(payload),
            payload.get("vote_average"),
            now_iso(),
        ),
    )


def upsert_episodes(show_id, season_payload):
    conn = db.get_db()
    rows = []
    for ep in season_payload.get("episodes", []):
        rows.append(
            (
                ep["id"],
                show_id,
                ep.get("season_number", season_payload.get("season_number", 0)),
                ep.get("episode_number", 0),
                ep.get("name"),
                ep.get("overview"),
                ep.get("air_date") or None,
                ep.get("runtime"),
                ep.get("still_path"),
            )
        )
    if not rows:
        return 0
    conn.executemany(
        """
        INSERT INTO episode (id, show_id, season_number, episode_number,
                             name, overview, air_date, runtime, still_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(show_id, season_number, episode_number) DO UPDATE SET
            name = excluded.name,
            overview = excluded.overview,
            air_date = excluded.air_date,
            runtime = excluded.runtime,
            still_path = excluded.still_path
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def sync_show(show_id):
    """Refresh one show and all of its episodes. Returns the show name."""
    payload = tmdb.show(show_id)
    upsert_show(payload)
    for season in payload.get("seasons", []):
        number = season.get("season_number")
        if number is None:
            continue
        try:
            upsert_episodes(show_id, tmdb.season(show_id, number))
        except tmdb.TmdbError:
            # A season TMDB cannot serve should not abandon the whole show.
            continue
    return payload.get("name")


def upsert_movie(payload):
    db.execute(
        """
        INSERT INTO movie (id, title, overview, poster_path, release_date,
                           runtime, vote_average, synced_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            overview = excluded.overview,
            poster_path = excluded.poster_path,
            release_date = excluded.release_date,
            runtime = excluded.runtime,
            vote_average = excluded.vote_average,
            synced_at = excluded.synced_at
        """,
        (
            payload["id"],
            payload.get("title") or "Untitled",
            payload.get("overview"),
            payload.get("poster_path"),
            payload.get("release_date") or None,
            payload.get("runtime"),
            payload.get("vote_average"),
            now_iso(),
        ),
    )


def sync_movie_availability(movie_id):
    """Refresh when a film reaches streaming, and which services carry it."""
    digital = None
    names, link = [], None
    try:
        digital = tmdb.digital_release_date(tmdb.movie_release_dates(movie_id))
    except tmdb.TmdbError:
        pass
    try:
        names, link = tmdb.uk_providers(tmdb.movie_providers(movie_id))
    except tmdb.TmdbError:
        pass

    db.execute(
        "UPDATE movie SET digital_release = COALESCE(?, digital_release),"
        " providers = ?, provider_link = ?, providers_checked_at = ?"
        " WHERE id = ?",
        (digital, "\n".join(names) if names else None, link, now_iso(), movie_id),
    )
    return digital, names


def sync_all_movies(force=False):
    """Refresh availability for every film still waiting to be watched."""
    rows = db.query(
        "SELECT m.id, m.providers_checked_at FROM movie m"
        " JOIN tracked_movie t ON t.movie_id = m.id"
        " WHERE t.watched_at IS NULL"
    )
    done = 0
    for row in rows:
        if not force and row["providers_checked_at"]:
            try:
                last = datetime.fromisoformat(row["providers_checked_at"])
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) - last < timedelta(days=3):
                    continue
            except ValueError:
                pass
        try:
            sync_movie_availability(row["id"])
            done += 1
        except tmdb.TmdbError:
            continue
    return done


def _needs_refresh(row, force):
    if force or not row["synced_at"]:
        return True
    try:
        last = datetime.fromisoformat(row["synced_at"])
    except ValueError:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - last
    ended = (row["status"] or "").lower() in {"ended", "canceled", "cancelled"}
    return age > timedelta(days=14) if ended else age > timedelta(hours=config.SYNC_INTERVAL_HOURS)


def sync_all(force=False):
    """Refresh every tracked show. Returns (done, skipped, errors)."""
    global _running
    if not _sync_lock.acquire(blocking=False):
        return (0, 0, ["A sync is already running."])
    _running = True
    done = skipped = 0
    errors = []
    run = db.execute(
        "INSERT INTO sync_run (started_at) VALUES (?)", (now_iso(),)
    )
    run_id = run.lastrowid
    try:
        rows = db.query(
            "SELECT s.id, s.name, s.status, s.synced_at FROM show s"
            " JOIN tracked_show t ON t.show_id = s.id"
            " WHERE t.archived = 0 AND t.shortlist = 0"
        )
        for row in rows:
            if not _needs_refresh(row, force):
                skipped += 1
                continue
            try:
                sync_show(row["id"])
                done += 1
            except tmdb.TmdbError as exc:
                errors.append(f"{row['name']}: {exc}")
        try:
            sync_all_movies(force=force)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Films: {exc}")

        db.execute(
            "UPDATE sync_run SET finished_at = ?, shows_done = ?, status = ?,"
            " message = ? WHERE id = ?",
            (
                now_iso(),
                done,
                "error" if errors else "ok",
                "; ".join(errors)[:500] if errors else None,
                run_id,
            ),
        )
    finally:
        _running = False
        _sync_lock.release()
    return (done, skipped, errors)


def is_running():
    return _running


def last_run():
    return db.query(
        "SELECT * FROM sync_run ORDER BY id DESC LIMIT 1", one=True
    )


def start_background(app):
    """A daemon thread that syncs on boot and then on a fixed interval."""

    def loop():
        import time

        time.sleep(20)
        while True:
            with app.app_context():
                try:
                    from . import secretstore

                    if secretstore.has("tmdb_api_key"):
                        sync_all(force=False)
                except Exception:  # keep the thread alive whatever happens
                    app.logger.exception("Background sync failed")
            time.sleep(max(1, config.SYNC_INTERVAL_HOURS) * 3600)

    thread = threading.Thread(target=loop, name="nextup-sync", daemon=True)
    thread.start()
    return thread
