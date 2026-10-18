"""The one place that says what day and time it is.

SQLite's own date('now') is UTC, while the rest of the app works in local
time, so the two disagree for an hour after midnight in British summer time.
Every query is given today's date from here instead.
"""
from datetime import date, datetime, timezone


def today():
    """Today's local date as YYYY-MM-DD, for comparing with stored air dates."""
    return date.today().isoformat()


def now_iso():
    """The current moment in UTC, for stamping rows."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
