"""Encrypted settings.

Third-party credentials are typed into the Settings page and stored
encrypted in the database - never in a plaintext env file. The key that
does the encrypting lives beside the database in the data directory,
generated on first boot with 0600 permissions.
"""
import os
import threading

from cryptography.fernet import Fernet, InvalidToken

from . import config, db

_lock = threading.Lock()
_fernet = None


def _load_fernet():
    global _fernet
    if _fernet is not None:
        return _fernet
    with _lock:
        if _fernet is not None:
            return _fernet
        os.makedirs(config.DATA_DIR, exist_ok=True)
        if os.path.exists(config.KEY_PATH):
            with open(config.KEY_PATH, "rb") as fh:
                key = fh.read().strip()
        else:
            key = Fernet.generate_key()
            fd = os.open(config.KEY_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "wb") as fh:
                fh.write(key)
        _fernet = Fernet(key)
    return _fernet


def get(key, default=None):
    row = db.query("SELECT value, encrypted FROM settings WHERE key = ?", (key,), one=True)
    if row is None or row["value"] is None:
        return default
    if not row["encrypted"]:
        return row["value"]
    try:
        return _load_fernet().decrypt(row["value"].encode()).decode()
    except (InvalidToken, ValueError):
        return default


def set(key, value, encrypted=False):
    stored = value
    if encrypted and value:
        stored = _load_fernet().encrypt(value.encode()).decode()
    db.execute(
        "INSERT INTO settings (key, value, encrypted) VALUES (?, ?, ?)"
        " ON CONFLICT(key) DO UPDATE SET value = excluded.value,"
        " encrypted = excluded.encrypted",
        (key, stored, 1 if encrypted else 0),
    )


def delete(key):
    db.execute("DELETE FROM settings WHERE key = ?", (key,))


def has(key):
    return bool(get(key))
