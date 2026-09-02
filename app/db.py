"""SQLite access. One connection per request, stored on `g`."""
import os
import sqlite3
from flask import g

from . import config


def connect():
    os.makedirs(config.DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def get_db():
    if "db" not in g:
        g.db = connect()
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows


def execute(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur


# Columns added after the first release. SQLite has no "ADD COLUMN IF NOT
# EXISTS", so each one is checked against the table before it is added.
MIGRATIONS = [
    ("tracked_show", "shortlist", "INTEGER NOT NULL DEFAULT 0"),
    ("movie", "digital_release", "TEXT"),
    ("movie", "providers", "TEXT"),
    ("movie", "provider_link", "TEXT"),
    ("movie", "providers_checked_at", "TEXT"),
    ("tracked_movie", "shortlist", "INTEGER NOT NULL DEFAULT 0"),
]


def _apply_migrations(conn):
    for table, column, spec in MIGRATIONS:
        columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {spec}")


def init_db():
    """Create tables, apply migrations, and seed the admin user if absent."""
    from datetime import datetime, timezone
    from werkzeug.security import generate_password_hash

    here = os.path.dirname(__file__)
    with open(os.path.join(here, "schema.sql"), "r", encoding="utf-8") as fh:
        schema = fh.read()

    conn = connect()
    conn.executescript(schema)
    _apply_migrations(conn)
    row = conn.execute("SELECT 1 FROM admin_user WHERE id = 1").fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO admin_user (id, username, password_hash, created_at)"
            " VALUES (1, ?, ?, ?)",
            (
                config.DEFAULT_USERNAME,
                generate_password_hash(config.DEFAULT_PASSWORD),
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )
    conn.commit()
    conn.close()
