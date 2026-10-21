"""The one place that says what day and time it is."""
from datetime import date, datetime, timezone

def today():
    return date.today().isoformat()

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
