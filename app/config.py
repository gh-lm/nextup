"""Runtime configuration."""
import os

DATA_DIR = os.environ.get("NEXTUP_DATA_DIR", "/data")
DB_PATH = os.path.join(DATA_DIR, "nextup.db")
CACHE_DIR = os.path.join(DATA_DIR, "images")
KEY_PATH = os.path.join(DATA_DIR, "secret.key")

HOST = os.environ.get("NEXTUP_HOST", "0.0.0.0")
PORT = int(os.environ.get("NEXTUP_PORT", "8080"))

SYNC_INTERVAL_HOURS = int(os.environ.get("NEXTUP_SYNC_HOURS", "12"))

DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "nextup"
