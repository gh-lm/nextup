"""Where a show or movie can be watched, from Movie of the Night through Nextup's own relay."""
import re
import time
from urllib.parse import urlsplit

import requests

from . import secretstore, tvdb

TIMEOUT = 4
KEPT_SECONDS = 6 * 3600
DEFAULT_COUNTRY = "gb"
COUNTRIES = {
    "ar": "Argentina", "au": "Australia", "at": "Austria", "be": "Belgium", "br": "Brazil",
    "ca": "Canada", "cl": "Chile", "co": "Colombia", "cz": "Czechia", "dk": "Denmark",
    "fi": "Finland", "fr": "France", "de": "Germany", "gr": "Greece", "hk": "Hong Kong",
    "hu": "Hungary", "in": "India", "id": "Indonesia", "ie": "Ireland", "il": "Israel",
    "it": "Italy", "jp": "Japan", "my": "Malaysia", "mx": "Mexico", "nl": "Netherlands",
    "nz": "New Zealand", "no": "Norway", "pe": "Peru", "ph": "Philippines", "pl": "Poland",
    "pt": "Portugal", "ro": "Romania", "sg": "Singapore", "za": "South Africa",
    "kr": "South Korea", "es": "Spain", "se": "Sweden", "ch": "Switzerland", "th": "Thailand",
    "tr": "Turkey", "ae": "United Arab Emirates", "gb": "United Kingdom", "us": "United States",
}
SERVICES = (
    ("netflix", "Netflix"), ("prime", "Prime Video"), ("disney", "Disney+"), ("apple", "Apple TV"),
    ("paramount", "Paramount+"), ("now", "Now"), ("hulu", "Hulu"),
)
GROUPS = (("subscription", "Stream"), ("free", "Free"), ("rent", "Rent"), ("buy", "Buy"))
_kept = {}

DISCOVER_DAYS = (7, 14, 30, 60)
DEFAULT_DISCOVER_DAYS = 30

def country():
    value = secretstore.get("watch_country", DEFAULT_COUNTRY)
    return value if value in COUNTRIES else ""

def _link(url):
    parts = urlsplit(url or "")
    return url if parts.scheme == "https" and parts.netloc else None

def _grouped(options):
    buckets = {kind: {} for kind, _ in GROUPS}
    for o in options:
        kind = "subscription" if o.get("type") == "addon" else o.get("type")
        name = o.get("service") or ""
        if o.get("type") == "addon":
            name = f"{name} ({o.get('addon') or 'channel'})"
        if kind in buckets and name and name not in buckets[kind]:
            buckets[kind][name] = _link(o.get("link"))
    return [
        {"label": label, "services": [{"name": n, "link": l} for n, l in buckets[kind].items()]}
        for kind, label in GROUPS if buckets[kind]
    ]

def lookup(imdb_id, code=None):
    code = code or country()
    if not code or not re.fullmatch(r"tt\d{1,10}", str(imdb_id or "")) or not tvdb.RELAY_URL:
        return None
    key = (imdb_id, code)
    hit = _kept.get(key)
    if hit and time.monotonic() - hit[0] < KEPT_SECONDS:
        return hit[1]
    try:
        resp = requests.get(f"{tvdb.RELAY_URL}/motn/shows/{imdb_id}", params={"country": code},
                            timeout=TIMEOUT, headers={"User-Agent": "Nextup"})
        if not resp.ok:
            return None
        options = resp.json().get("options") or []
    except (requests.RequestException, ValueError, AttributeError):
        return None
    groups = _grouped(options)
    _kept[key] = (time.monotonic(), groups)
    return groups

def discover(kind, when, code=None):
    code = code or country()
    if not code or kind not in ("movie", "series") or when not in ("upcoming", "out") or not tvdb.RELAY_URL:
        return None
    key = ("discover", kind, when, code)
    hit = _kept.get(key)
    if hit and time.monotonic() - hit[0] < KEPT_SECONDS:
        return hit[1]
    try:
        resp = requests.get(f"{tvdb.RELAY_URL}/motn/discover", params={"country": code, "type": kind, "when": when},
                            timeout=TIMEOUT, headers={"User-Agent": "Nextup"})
        if not resp.ok:
            return None
        items = resp.json().get("items") or []
    except (requests.RequestException, ValueError, AttributeError):
        return None
    items = [i for i in items if re.fullmatch(r"tt\d{1,10}", str(i.get("imdb", ""))) and re.fullmatch(r"\d{4}-\d\d-\d\d", str(i.get("date", "")))]
    _kept[key] = (time.monotonic(), items)
    return items
