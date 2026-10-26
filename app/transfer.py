"""Taking everything out, and putting it back."""
from datetime import datetime, timezone

from . import db, secretstore

FORMAT = "nextup-backup"
VERSION = 1

TABLES = [
    ("show", "id"),
    ("episode", "id"),
    ("movie", "id"),
    ("tracked_show", "show_id"),
    ("watched_episode", "episode_id"),
    ("tracked_movie", "movie_id"),
]

STUB_COLUMNS = {
    "show": ("id", "name"),
    "episode": ("id", "show_id", "season_number", "episode_number"),
    "movie": ("id", "title"),
}
SELECTS = {
    "show": "SELECT id, name FROM show WHERE id IN (SELECT show_id FROM tracked_show)",
    "episode": "SELECT id, show_id, season_number, episode_number FROM episode"
               " WHERE id IN (SELECT episode_id FROM watched_episode)",
    "movie": "SELECT id, title FROM movie WHERE id IN (SELECT movie_id FROM tracked_movie)",
}

NOT_BACKED_UP = (
    "session_epoch", "intro_seen", "tmdb_api_key", "tvdb_api_key", "source_first", "country",
    "watch_languages", "watch_all_languages", "countries_cache", "countries_fetched_at",
)

def _rows(table):
    return [dict(row) for row in db.query(SELECTS.get(table) or f"SELECT * FROM {table}")]

def counts():
    found = {
        table: len(_rows(table)) for table, _key in TABLES
    }
    found["settings"] = db.query(
        "SELECT COUNT(*) AS n FROM settings WHERE encrypted = 0 AND value IS NOT NULL"
        f" AND key NOT IN ({', '.join('?' for _ in NOT_BACKED_UP)})",
        NOT_BACKED_UP,
        one=True,
    )["n"]
    return found

def export_data(include_secrets=False):
    payload = {
        "format": FORMAT,
        "version": VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "counts": {},
        "data": {},
    }

    for table, _key in TABLES:
        rows = _rows(table)
        payload["data"][table] = rows
        payload["counts"][table] = len(rows)

    account = db.query("SELECT username, password_hash, created_at FROM admin_user WHERE id = 1", one=True)
    if account:
        payload["data"]["account"] = dict(account)

    plain, secrets = {}, {}
    for row in db.query("SELECT key, encrypted FROM settings"):
        if row["key"] in NOT_BACKED_UP:
            continue
        value = secretstore.get(row["key"])
        if value is None:
            continue
        if row["encrypted"]:
            secrets[row["key"]] = value
        else:
            plain[row["key"]] = value

    payload["data"]["settings"] = plain
    payload["counts"]["settings"] = len(plain)
    if include_secrets:
        payload["data"]["secrets"] = secrets
        payload["counts"]["secrets"] = len(secrets)
        payload["secrets_included"] = True
    else:
        payload["secrets_included"] = False
        payload["secrets_omitted"] = sorted(secrets)

    return payload

class BackupError(ValueError):
    pass

def _check(payload):
    if not isinstance(payload, dict):
        raise BackupError("That file does not contain a Nextup backup.")
    if payload.get("format") != FORMAT:
        raise BackupError("That is not a Nextup backup file.")
    version = payload.get("version")
    if not isinstance(version, int) or version > VERSION:
        raise BackupError(
            f"That backup was made by a newer version of Nextup (format {version}). "
            "Update this copy first."
        )
    if not isinstance(payload.get("data"), dict):
        raise BackupError("That backup has nothing in it.")

def _insert(conn, table, rows):
    if not rows:
        return 0
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    written = 0
    for row in rows:
        keep = {k: v for k, v in row.items() if k in columns}
        if not keep:
            continue
        names = ", ".join(keep)
        marks = ", ".join("?" for _ in keep)
        conn.execute(
            f"INSERT OR REPLACE INTO {table} ({names}) VALUES ({marks})", list(keep.values())
        )
        written += 1
    return written

def _put_setting(conn, key, stored_value, encrypted):
    conn.execute(
        "INSERT INTO settings (key, value, encrypted) VALUES (?, ?, ?)"
        " ON CONFLICT(key) DO UPDATE SET value = excluded.value,"
        " encrypted = excluded.encrypted",
        (str(key), stored_value, 1 if encrypted else 0),
    )

def import_data(payload):
    _check(payload)
    data = payload["data"]

    conn = db.get_db()
    restored = {}
    try:
        conn.execute("BEGIN")
        for table, _key in reversed(TABLES):
            conn.execute(f"DELETE FROM {table}")
        conn.execute("DELETE FROM settings")

        for table, _key in TABLES:
            rows = data.get(table) or []
            if table in STUB_COLUMNS:
                rows = [{k: r[k] for k in STUB_COLUMNS[table] if k in r} for r in rows]
            restored[table] = _insert(conn, table, rows)

        account = data.get("account")
        if isinstance(account, dict) and account.get("password_hash"):
            conn.execute(
                "UPDATE admin_user SET username = ?, password_hash = ? WHERE id = 1",
                (account.get("username") or "admin", account["password_hash"]),
            )
            restored["account"] = 1

        settings = data.get("settings")
        if isinstance(settings, dict):
            kept = {k: v for k, v in settings.items() if k not in NOT_BACKED_UP}
            for key, value in kept.items():
                _put_setting(conn, key, str(value), encrypted=False)
            restored["settings"] = len(kept)

        secrets = data.get("secrets")
        if isinstance(secrets, dict):
            secrets = {k: v for k, v in secrets.items() if k not in NOT_BACKED_UP}
            for key, value in secrets.items():
                _put_setting(conn, key, secretstore.encrypt(str(value)), encrypted=True)
            restored["secrets"] = len(secrets)

        conn.commit()
    except Exception as exc:  # noqa: BLE001 - anything at all means put it back
        conn.rollback()
        raise BackupError(f"Nothing was changed. The backup could not be read: {exc}") from exc

    return restored

def summarise(restored):
    bits = []
    for table, label in (
        ("tracked_show", "show"),
        ("watched_episode", "watched episode"),
        ("tracked_movie", "movie"),
    ):
        n = restored.get(table, 0)
        if n:
            bits.append(f"{n} {label}{'s' if n != 1 else ''}")
    if restored.get("secrets"):
        bits.append("your mail password")
    return ", ".join(bits) if bits else "nothing"
