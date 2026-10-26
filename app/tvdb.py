"""TheTVDB v4 client. It answers in the shapes tmdb.py returns, so the rest of the app does not care which source a record came from."""
import re
import threading
import time
from urllib.parse import urlsplit

import requests

from . import secretstore
from .tmdb import TmdbError

BASE = "https://api4.thetvdb.com/v4"
IMAGE_HOST = "artworks.thetvdb.com"
TIMEOUT = 20
OFFSET = 10**9
IMAGE_PREFIX = "/tvdb__"
EPISODES_KEPT = 60

LANGUAGES = {
    "eng": "en", "fra": "fr", "deu": "de", "spa": "es", "ita": "it", "jpn": "ja",
    "kor": "ko", "por": "pt", "rus": "ru", "nld": "nl", "swe": "sv", "nor": "no",
    "dan": "da", "fin": "fi", "pol": "pl", "tur": "tr", "zho": "zh", "hin": "hi",
    "ces": "cs", "hun": "hu", "heb": "he", "ell": "el", "ara": "ar", "tha": "th",
}
STATUSES = {"Continuing": "Returning Series", "Ended": "Ended", "Upcoming": "In Production"}

class TvdbError(TmdbError):
    pass

class MissingKey(TvdbError):
    pass

_token = {"value": None, "at": 0.0}
_token_lock = threading.Lock()
_episodes = {}

def is_tvdb(record_id):
    return record_id is not None and int(record_id) >= OFFSET

def raw(record_id):
    return int(record_id) - OFFSET

def internal(tvdb_id):
    return OFFSET + int(tvdb_id)

RELAY_URL = "https://tvdb-relay.lightmorphic.com"

def own_key():
    return secretstore.get("tvdb_api_key")

def using_relay():
    return not own_key() and RELAY_URL is not None

def api_key():
    key = own_key()
    if not key:
        raise MissingKey("No TheTVDB API key saved. Add one on the Settings page.")
    return key

def has_key():
    return bool(own_key()) or RELAY_URL is not None

def _target():
    if using_relay():
        return f"{RELAY_URL}/v4", {"User-Agent": "Nextup"}
    return BASE, {"Authorization": f"Bearer {_bearer()}"}

def _unreachable(exc):
    return TvdbError(f"Could not reach TheTVDB ({type(exc).__name__}).")

def _login(key):
    try:
        resp = requests.post(f"{BASE}/login", json={"apikey": key}, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise _unreachable(exc) from None
    if resp.status_code == 401:
        raise TvdbError("TheTVDB rejected that key.")
    if not resp.ok:
        raise TvdbError(f"TheTVDB returned {resp.status_code}.")
    try:
        return resp.json()["data"]["token"]
    except (ValueError, KeyError, TypeError):
        raise TvdbError("TheTVDB sent a reply Nextup could not read.") from None

def _bearer(fresh=False):
    with _token_lock:
        if fresh or not _token["value"] or time.time() - _token["at"] > 20 * 24 * 3600:
            _token["value"] = _login(api_key())
            _token["at"] = time.time()
        return _token["value"]

def _get(path, params=None, tries=3):
    refreshed = False
    for attempt in range(tries):
        last = attempt == tries - 1
        try:
            base, headers = _target()
            resp = requests.get(f"{base}{path}", params=params, timeout=TIMEOUT, headers=headers)
        except requests.RequestException as exc:
            if last:
                raise _unreachable(exc) from None
            time.sleep(1 + attempt)
            continue
        if resp.status_code == 401 and not refreshed and not using_relay():
            refreshed = True
            _bearer(fresh=True)
            continue
        if resp.status_code == 401:
            raise TvdbError("TheTVDB rejected the API key. Check it on the Settings page.")
        if resp.status_code == 404:
            raise TvdbError("TheTVDB has no record of that.")
        if resp.status_code == 429 or not resp.ok:
            if last:
                raise TvdbError(f"TheTVDB returned {resp.status_code}.")
            time.sleep(1 + attempt)
            continue
        try:
            return resp.json().get("data")
        except ValueError:
            raise TvdbError("TheTVDB sent a reply Nextup could not read.") from None
    raise TvdbError("TheTVDB kept refusing the request.")

def verify_key(candidate):
    _login(candidate)

def image(url):
    try:
        parts = urlsplit(url or "")
    except ValueError:
        return None
    if parts.scheme != "https" or parts.netloc != IMAGE_HOST:
        return None
    segments = [s for s in parts.path.split("/") if s]
    path = IMAGE_PREFIX + "__".join(segments)
    return path if re.fullmatch(r"/[A-Za-z0-9_-]+\.(jpg|png|webp)", path) else None

def image_url(clean_path):
    if not clean_path.startswith(IMAGE_PREFIX):
        return None
    return f"https://{IMAGE_HOST}/" + "/".join(clean_path[len(IMAGE_PREFIX):].split("__"))

def _language(code):
    return LANGUAGES.get(code)

def _remote(record, source):
    for entry in record.get("remoteIds") or []:
        if entry.get("sourceName") == source and entry.get("id"):
            return str(entry["id"])
    return None

def _tmdb_id(record):
    value = _remote(record, "TheMovieDB.com")
    return int(value) if value and value.isdigit() else None

def _overview(kind, number, record):
    if record.get("overview"):
        return record["overview"]
    try:
        return (_get(f"/{kind}/{number}/translations/eng") or {}).get("overview")
    except TvdbError:
        return None

def _trailers(record):
    results = []
    for item in record.get("trailers") or []:
        match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{6,})", item.get("url") or "")
        if match:
            results.append({"site": "YouTube", "type": "Trailer", "key": match.group(1), "name": item.get("name")})
    return {"results": results}

def _external_ids(record):
    imdb = _remote(record, "IMDB")
    return {"imdb_id": imdb} if imdb else {}

def search_multi(query, page=1):
    data = _get("/search", {"query": query, "limit": 20, "page": max(page - 1, 0)})
    results = []
    for item in data or []:
        kind = item.get("type")
        if kind not in ("series", "movie") or not str(item.get("tvdb_id", "")).isdigit():
            continue
        results.append({
            "kind": "tv" if kind == "series" else "movie",
            "id": internal(item["tvdb_id"]),
            "title": item.get("name") or "Untitled",
            "date": item.get("first_air_time") or item.get("year") or "",
            "overview": item.get("overview") or "",
            "poster_path": image(item.get("image_url")),
            "vote_average": 0,
            "language": _language(item.get("primary_language")),
        })
    return {"results": results, "total_pages": 1, "page": page}

def _credits(record):
    actors = [c for c in record.get("characters") or [] if c.get("peopleType") == "Actor" and c.get("personName")]
    actors.sort(key=lambda c: c.get("sort") or 0)
    return {"cast": [
        {"name": c["personName"], "character": c.get("name"), "profile_path": image(c.get("personImgURL") or c.get("image"))}
        for c in actors
    ]}

def show(show_id, full=False):
    number = raw(show_id)
    record = _get(f"/series/{number}/extended", None if full else {"short": "true"}) or {}
    default_type = record.get("defaultSeasonType")
    seasons = sorted({
        s.get("number") for s in record.get("seasons") or []
        if (s.get("type") or {}).get("id") == default_type and s.get("number") is not None
    })
    network = (record.get("latestNetwork") or record.get("originalNetwork") or {}).get("name")
    runtime = record.get("averageRuntime")
    return {
        "id": internal(number),
        "name": record.get("name"),
        "overview": _overview("series", number, record),
        "poster_path": image(record.get("image")),
        "backdrop_path": None,
        "first_air_date": record.get("firstAired") or None,
        "last_air_date": record.get("lastAired") or None,
        "status": STATUSES.get((record.get("status") or {}).get("name")),
        "networks": [{"name": network}] if network else [],
        "episode_run_time": [runtime] if runtime else [],
        "vote_average": None,
        "original_language": _language(record.get("originalLanguage")),
        "seasons": [{"season_number": n} for n in seasons],
        "genres": [{"name": g.get("name")} for g in record.get("genres") or []],
        "videos": _trailers(record),
        "external_ids": _external_ids(record),
        "tmdb_id": _tmdb_id(record),
        "credits": _credits(record),
    }

def show_detail(show_id):
    return show(show_id, full=True)

def _all_episodes(number):
    now = time.time()
    kept = _episodes.get(number)
    if kept and now - kept[0] < EPISODES_KEPT:
        return kept[1]
    episodes, page = [], 0
    while True:
        data = _get(f"/series/{number}/episodes/default/eng", {"page": page}) or {}
        episodes.extend(data.get("episodes") or [])
        if page >= 50 or len(data.get("episodes") or []) == 0 or not (data.get("links") or {}).get("next"):
            break
        page += 1
    _episodes[number] = (now, episodes)
    return episodes

def season(show_id, season_number):
    episodes = [
        {
            "id": internal(ep["id"]),
            "season_number": ep.get("seasonNumber"),
            "episode_number": ep.get("number"),
            "name": ep.get("name"),
            "overview": ep.get("overview"),
            "air_date": ep.get("aired") or None,
            "runtime": ep.get("runtime"),
            "still_path": image(ep.get("image")),
        }
        for ep in _all_episodes(raw(show_id))
        if ep.get("seasonNumber") == season_number and ep.get("number") is not None
    ]
    return {"season_number": season_number, "episodes": episodes}

def episode(show_id, season_number, episode_number):
    for ep in season(show_id, season_number)["episodes"]:
        if ep["episode_number"] == episode_number:
            return ep
    raise TvdbError("TheTVDB has no record of that.")

def movie(movie_id, full=False):
    number = raw(movie_id)
    record = _get(f"/movies/{number}/extended", None if full else {"short": "true"}) or {}
    first = (record.get("first_release") or {}).get("date")
    return {
        "id": internal(number),
        "title": record.get("name"),
        "overview": _overview("movies", number, record),
        "poster_path": image(record.get("image")),
        "release_date": first or None,
        "runtime": record.get("runtime"),
        "vote_average": None,
        "original_language": _language(record.get("originalLanguage")),
        "genres": [{"name": g.get("name")} for g in record.get("genres") or []],
        "videos": _trailers(record),
        "external_ids": _external_ids(record),
        "tmdb_id": _tmdb_id(record),
        "credits": _credits(record),
    }

def movie_detail(movie_id):
    return movie(movie_id, full=True)

def find_by_tmdb(tmdb_id, kind):
    try:
        found = _get(f"/search/remoteid/{int(tmdb_id)}") or []
    except TvdbError:
        return None
    for entry in found:
        record = entry.get("series" if kind == "tv" else "movie")
        if record and record.get("id"):
            return internal(record["id"])
    return None
