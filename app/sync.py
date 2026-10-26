"""Pulling show and episode data from TheTVDB into the local database."""
import threading
import time
from datetime import datetime, timedelta, timezone

from . import catalog, clock, config, db, queries, secretstore, tvdb

_sync_lock = threading.Lock()
_running = False

def _age(stamp):
    try:
        then = datetime.fromisoformat(stamp)
    except (TypeError, ValueError):
        return None
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - then

def _network_name(payload):
    networks = payload.get("networks") or []
    if networks:
        return networks[0].get("name")
    return None

def _runtime(payload):
    times = payload.get("episode_run_time") or []
    return times[0] if times else None

def upsert_show(payload, stamp=True):
    db.execute(
        """
        INSERT INTO show (id, name, overview, poster_path, backdrop_path,
                          first_air_date, last_air_date, status, network,
                          episode_runtime, vote_average, original_language, synced_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            original_language = excluded.original_language,
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
            payload.get("original_language"),
            clock.now_iso() if stamp else None,
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
    for row in rows:
        conn.execute(
            "UPDATE episode SET episode_number = -id WHERE id = ?"
            " AND NOT (show_id = ? AND season_number = ? AND episode_number = ?)",
            (row[0], *row[1:4]),
        )
    for row in rows:
        slot = row[1:4]
        carried = conn.execute(
            "SELECT w.watched_at FROM watched_episode w JOIN episode e ON e.id = w.episode_id"
            " WHERE e.show_id = ? AND e.season_number = ? AND e.episode_number = ? AND e.id != ?",
            (*slot, row[0]),
        ).fetchone()
        conn.execute(
            "DELETE FROM episode WHERE show_id = ? AND season_number = ? AND episode_number = ? AND id != ?",
            (*slot, row[0]),
        )
        conn.execute(
            """
            INSERT INTO episode (id, show_id, season_number, episode_number,
                                 name, overview, air_date, runtime, still_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                show_id = excluded.show_id,
                season_number = excluded.season_number,
                episode_number = excluded.episode_number,
                name = excluded.name,
                overview = excluded.overview,
                air_date = excluded.air_date,
                runtime = excluded.runtime,
                still_path = excluded.still_path
            """,
            row,
        )
        if carried:
            conn.execute(
                "INSERT OR IGNORE INTO watched_episode (episode_id, show_id, watched_at) VALUES (?, ?, ?)",
                (row[0], show_id, carried["watched_at"]),
            )
    conn.commit()
    return len(rows)

def _note_archived_season(show_id):
    db.execute(
        "UPDATE tracked_show SET archived_season = ?"
        " WHERE show_id = ? AND archived = 1 AND archived_season IS NULL",
        (queries.latest_season(show_id), show_id),
    )

def _unarchive_if_new_season(show_id):
    db.execute(
        "UPDATE tracked_show SET archived = 0"
        " WHERE show_id = ? AND archived = 1 AND auto_unarchive = 1 AND archived_season < ?",
        (show_id, queries.latest_season(show_id)),
    )

def sync_show(show_id, failed=None):
    _note_archived_season(show_id)
    payload = catalog.show(show_id)
    upsert_show(payload, stamp=False)
    missed = []
    for season in payload.get("seasons", []):
        number = season.get("season_number")
        if number is None:
            continue
        try:
            upsert_episodes(show_id, catalog.season(show_id, number))
        except catalog.TvdbError:
            missed.append(number)
    if missed:
        if failed is not None:
            failed.extend(missed)
    else:
        db.execute("UPDATE show SET synced_at = ? WHERE id = ?", (clock.now_iso(), show_id))
    _unarchive_if_new_season(show_id)
    return payload.get("name")

def upsert_movie(payload):
    db.execute(
        """
        INSERT INTO movie (id, title, overview, poster_path, release_date,
                           runtime, vote_average, original_language, synced_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            overview = excluded.overview,
            poster_path = excluded.poster_path,
            release_date = excluded.release_date,
            runtime = excluded.runtime,
            vote_average = excluded.vote_average,
            original_language = excluded.original_language,
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
            payload.get("original_language"),
            clock.now_iso(),
        ),
    )

def sync_movie(movie_id):
    upsert_movie(catalog.movie(movie_id))

def sync_all_movies(force=False):
    rows = db.query(
        "SELECT m.id, m.synced_at FROM movie m"
        " JOIN tracked_movie t ON t.movie_id = m.id"
        " WHERE t.watched_at IS NULL"
    )
    done = 0
    for row in rows:
        age = _age(row["synced_at"])
        if not force and age is not None and age < timedelta(days=3):
            continue
        try:
            sync_movie(row["id"])
            done += 1
        except catalog.TvdbError:
            continue
    return done

def _needs_refresh(row, force):
    age = _age(row["synced_at"])
    if force or age is None:
        return True
    ended = (row["status"] or "").lower() in {"ended", "canceled", "cancelled"}
    return age > timedelta(days=14) if ended else age > timedelta(hours=config.SYNC_INTERVAL_HOURS)

def sync_all(force=False):
    global _running
    if not _sync_lock.acquire(blocking=False):
        return (0, 0, ["A sync is already running."])
    done = skipped = 0
    errors = []
    try:
        _running = True
        run_id = db.execute(
            "INSERT INTO sync_run (started_at) VALUES (?)", (clock.now_iso(),)
        ).lastrowid
        rows = db.query(
            "SELECT s.id, s.name, s.status, s.synced_at FROM show s"
            " JOIN tracked_show t ON t.show_id = s.id"
            " WHERE t.shortlist = 0 AND (t.archived = 0 OR t.auto_unarchive = 1)"
        )
        for row in rows:
            if not _needs_refresh(row, force):
                skipped += 1
                continue
            try:
                failed = []
                sync_show(row["id"], failed)
                if failed:
                    seasons = ", ".join(str(n) for n in failed)
                    errors.append(f"{row['name']}: season {seasons} could not be fetched")
                else:
                    done += 1
            except Exception as exc:  # noqa: BLE001 - one bad show must not stop the rest
                errors.append(f"{row['name']}: {exc}")
        try:
            sync_all_movies(force=force)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Movies: {exc}")

        db.execute(
            "UPDATE sync_run SET finished_at = ?, shows_done = ?, status = ?,"
            " message = ? WHERE id = ?",
            (
                clock.now_iso(),
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

def start_now(app, force=True):
    if _sync_lock.locked():
        return False

    def work():
        tvdb.patient()
        with app.app_context():
            try:
                sync_all(force=force)
            except Exception:
                app.logger.exception("Refresh failed")

    threading.Thread(target=work, name="nextup-sync-now", daemon=True).start()
    return True

def start_background(app):

    def loop():
        tvdb.patient()
        time.sleep(20)
        while True:
            with app.app_context():
                try:
                    sync_all(force=False)
                except Exception:
                    app.logger.exception("Background sync failed")
            time.sleep(config.SYNC_INTERVAL_HOURS * 3600)

    thread = threading.Thread(target=loop, name="nextup-sync", daemon=True)
    thread.start()
    return thread
