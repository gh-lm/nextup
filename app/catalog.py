"""Picks between TMDB and TheTVDB for every lookup, and lets the second fill what the first left empty."""
from . import secretstore, tmdb, tvdb
from .tmdb import TmdbError

SOURCES = {"tmdb": tmdb, "tvdb": tvdb}
KEY_NAMES = {"tmdb": "tmdb_api_key", "tvdb": "tvdb_api_key"}
SHOW_GAPS = ("overview", "poster_path", "backdrop_path", "first_air_date", "last_air_date", "status", "original_language")
MOVIE_GAPS = ("overview", "poster_path", "release_date", "runtime", "original_language")
EPISODE_GAPS = ("name", "overview", "air_date", "runtime", "still_path")

_counterparts = {}

def configured(name):
    return secretstore.has(KEY_NAMES[name])

def any_key():
    return configured("tmdb") or configured("tvdb")

def first_name():
    return "tmdb" if secretstore.get("source_first") == "tmdb" else "tvdb"

def order():
    first = first_name()
    names = [first, "tmdb" if first == "tvdb" else "tvdb"]
    have = [name for name in names if configured(name)]
    return have or ["tmdb"]

def _home(record_id):
    return "tvdb" if tvdb.is_tvdb(record_id) else "tmdb"

def _other(name):
    other = "tmdb" if name == "tvdb" else "tvdb"
    return other if configured(other) else None

def _fill(target, source, fields):
    for field in fields:
        if not target.get(field) and source.get(field):
            target[field] = source[field]
    return target

def _counterpart(record_id, kind):
    key = (kind, record_id)
    if key in _counterparts:
        return _counterparts[key]
    found = None
    try:
        if tvdb.is_tvdb(record_id):
            payload = tvdb.show(record_id) if kind == "tv" else tvdb.movie(record_id)
            found = payload.get("tmdb_id")
        elif configured("tvdb"):
            found = tvdb.find_by_tmdb(record_id, kind)
    except TmdbError:
        return None
    _counterparts[key] = found
    return found

def _needs(payload, fields):
    return any(not payload.get(field) for field in fields)

def search_multi(query, page=1):
    names = order()
    for name in names:
        result = SOURCES[name].search_multi(query, page=page)
        if result["results"] or name == names[-1]:
            return result

def _record(record_id, call, kind, fields):
    home = _home(record_id)
    payload = getattr(SOURCES[home], call)(record_id)
    other = _other(home)
    if other and _needs(payload, fields):
        twin = _counterpart(record_id, kind)
        if twin:
            try:
                _fill(payload, getattr(SOURCES[other], call)(twin), fields)
            except TmdbError:
                pass
    return payload

def show(show_id):
    return _record(show_id, "show", "tv", SHOW_GAPS)

def movie(movie_id):
    return _record(movie_id, "movie", "movie", MOVIE_GAPS)

def show_detail(show_id):
    if tvdb.is_tvdb(show_id) and configured("tmdb"):
        twin = _counterpart(show_id, "tv")
        if twin:
            try:
                return tmdb.show_detail(twin)
            except TmdbError:
                pass
    return (tvdb if tvdb.is_tvdb(show_id) else tmdb).show_detail(show_id)

def movie_detail(movie_id):
    if tvdb.is_tvdb(movie_id) and configured("tmdb"):
        twin = _counterpart(movie_id, "movie")
        if twin:
            try:
                return tmdb.movie_detail(twin)
            except TmdbError:
                pass
    return (tvdb if tvdb.is_tvdb(movie_id) else tmdb).movie_detail(movie_id)

def season(show_id, season_number):
    home = _home(show_id)
    payload = SOURCES[home].season(show_id, season_number)
    other = _other(home)
    episodes = payload.get("episodes") or []
    if other and any(_needs(ep, EPISODE_GAPS) for ep in episodes):
        twin = _counterpart(show_id, "tv")
        if twin:
            try:
                extra = SOURCES[other].season(twin, season_number)
            except TmdbError:
                return payload
            by_number = {ep.get("episode_number"): ep for ep in extra.get("episodes") or []}
            for ep in episodes:
                match = by_number.get(ep.get("episode_number"))
                if match:
                    _fill(ep, match, EPISODE_GAPS)
    return payload

def episode(show_id, season_number, episode_number):
    if tvdb.is_tvdb(show_id):
        twin = _counterpart(show_id, "tv") if configured("tmdb") else None
        if twin:
            try:
                return tmdb.episode(twin, season_number, episode_number)
            except TmdbError:
                pass
        return tvdb.episode(show_id, season_number, episode_number)
    return tmdb.episode(show_id, season_number, episode_number)

def _tmdb_twin(record_id, kind):
    if not tvdb.is_tvdb(record_id):
        return record_id
    twin = _counterpart(record_id, kind) if configured("tmdb") else None
    if not twin:
        raise tvdb.TvdbError("Streaming dates and services come from TMDB. Add a TMDB key on the Settings page.")
    return twin

def show_providers(show_id):
    return tmdb.show_providers(_tmdb_twin(show_id, "tv"))

def movie_providers(movie_id):
    return tmdb.movie_providers(_tmdb_twin(movie_id, "movie"))

def movie_release_dates(movie_id):
    return tmdb.movie_release_dates(_tmdb_twin(movie_id, "movie"))

def __getattr__(name):
    return getattr(tmdb, name)
