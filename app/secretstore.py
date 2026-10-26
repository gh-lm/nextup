"""Encrypted settings."""
import logging
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
            if db.query("SELECT 1 FROM settings WHERE encrypted = 1 LIMIT 1", one=True):
                logging.getLogger(__name__).error(
                    "secret.key is missing but encrypted settings exist. A new key is "
                    "being made, so the saved mail password cannot be read "
                    "and must be entered again."
                )
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

LABELS = {"smtp_password": "mail password"}

def unreadable():
    broken = []
    for row in db.query("SELECT key, value FROM settings WHERE encrypted = 1"):
        try:
            _load_fernet().decrypt((row["value"] or "").encode())
        except (InvalidToken, ValueError):
            broken.append(LABELS.get(row["key"], row["key"]))
    return sorted(broken)

def encrypt(value):
    return _load_fernet().encrypt(value.encode()).decode()

def set(key, value, encrypted=False):
    stored = value
    if encrypted and value:
        stored = encrypt(value)
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
