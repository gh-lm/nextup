"""Taking everything out, and putting it back.

One JSON file holds what you added, what you watched and how you like things
set up, alongside enough of the show and film detail for a fresh copy to be
usable the moment it is restored, before it has spoken to TMDB at all.

Secrets are the exception. The TMDB key and the mail password are encrypted
with a key that lives beside the database, so they cannot travel as they are.
They are left out unless you ask for them, and asking means they are written
into the file as plain text.
"""
from datetime import datetime, timezone

from . import db, secretstore

FORMAT = "nextup-backup"
VERSION = 1

# Every table that carries something worth keeping, and the order to restore
# them in so a row never arrives before the row it points at.
TABLES = [
    ("show", "id"),
    ("episode", "id"),
    ("movie", "id"),
    ("tracked_show", "show_id"),
    ("watched_episode", "episode_id"),
    ("tracked_movie", "movie_id"),
    ("dismissed", None),
]


def _rows(table):
    return [dict(row) for row in db.query(f"SELECT * FROM {table}")]


def export_data(include_secrets=False):
    """Everything, as a plain dictionary ready to be written out as JSON."""
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

    # Settings split by how they are stored, not by guesswork.
    plain, secrets = {}, {}
    for row in db.query("SELECT key, encrypted FROM settings"):
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


class ImportError_(ValueError):
    """Raised when a file is not a Nextup backup, or is one we cannot read."""


def _check(payload):
    if not isinstance(payload, dict):
        raise ImportError_("That file does not contain a Nextup backup.")
    if payload.get("format") != FORMAT:
        raise ImportError_("That is not a Nextup backup file.")
    version = payload.get("version")
    if not isinstance(version, int) or version > VERSION:
        raise ImportError_(
            f"That backup was made by a newer version of Nextup (format {version}). "
            "Update this copy first."
        )
    if not isinstance(payload.get("data"), dict):
        raise ImportError_("That backup has nothing in it.")


def _insert(conn, table, rows):
    """Write rows back, keeping only columns this version still has."""
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


def import_data(payload):
    """Replace everything with the contents of a backup.

    All of it or none of it: if any part fails the database is left exactly as
    it was.
    """
    _check(payload)
    data = payload["data"]

    conn = db.get_db()
    restored = {}
    try:
        conn.execute("BEGIN")
        # Clear in reverse, so nothing is orphaned on the way out.
        for table, _key in reversed(TABLES):
            conn.execute(f"DELETE FROM {table}")
        conn.execute("DELETE FROM settings")

        for table, _key in TABLES:
            restored[table] = _insert(conn, table, data.get(table) or [])

        account = data.get("account")
        if isinstance(account, dict) and account.get("password_hash"):
            conn.execute(
                "UPDATE admin_user SET username = ?, password_hash = ? WHERE id = 1",
                (account.get("username") or "admin", account["password_hash"]),
            )
            restored["account"] = 1

        conn.commit()
    except Exception as exc:  # noqa: BLE001 - anything at all means put it back
        conn.rollback()
        raise ImportError_(f"Nothing was changed. The backup could not be read: {exc}") from exc

    # Settings go through the store so anything secret is encrypted on the way in.
    settings = data.get("settings")
    if isinstance(settings, dict):
        for key, value in settings.items():
            secretstore.set(key, str(value))
        restored["settings"] = len(settings)

    secrets = data.get("secrets")
    if isinstance(secrets, dict):
        for key, value in secrets.items():
            secretstore.set(key, str(value), encrypted=True)
        restored["secrets"] = len(secrets)

    return restored


def summarise(restored):
    """A sentence saying what came back."""
    bits = []
    for table, label in (
        ("tracked_show", "show"),
        ("watched_episode", "watched episode"),
        ("tracked_movie", "film"),
    ):
        n = restored.get(table, 0)
        if n:
            bits.append(f"{n} {label}{'s' if n != 1 else ''}")
    if restored.get("secrets"):
        bits.append("your keys")
    return ", ".join(bits) if bits else "nothing"
