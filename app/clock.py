"""The one place that says what day and time it is."""
from datetime import date, datetime, timezone

def today_date():
    return date.today()

def today():
    return today_date().isoformat()

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
