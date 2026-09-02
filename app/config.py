"""Runtime configuration.

Only the things that decide *where* the app lives come from the
environment. Third-party credentials never do - they are entered in the
Settings page and stored encrypted in the database.
"""
import os

DATA_DIR = os.environ.get("NEXTUP_DATA_DIR", "/data")
DB_PATH = os.path.join(DATA_DIR, "nextup.db")
CACHE_DIR = os.path.join(DATA_DIR, "images")
KEY_PATH = os.path.join(DATA_DIR, "secret.key")

HOST = os.environ.get("NEXTUP_HOST", "0.0.0.0")
PORT = int(os.environ.get("NEXTUP_PORT", "8080"))

# Hours between automatic refreshes of tracked shows.
SYNC_INTERVAL_HOURS = int(os.environ.get("NEXTUP_SYNC_HOURS", "12"))

DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "nextup"
