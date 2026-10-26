"""Every lookup goes to TheTVDB. Ids below tvdb.OFFSET belong to older installs and are resolved to their TheTVDB twin."""
from . import db, tvdb
from .tvdb import TvdbError

_legacy = {}

def _twin(record_id, kind):
    if tvdb.is_tvdb(record_id):
        return record_id
    key = (kind, record_id)
    if key not in _legacy:
        _legacy[key] = tvdb.find_by_tmdb(record_id, kind)
    if not _legacy[key]:
        raise TvdbError("TheTVDB has no match for this older entry.")
    return _legacy[key]

def _keep_ids(show_id, payload):
    known = {
        (row["season_number"], row["episode_number"]): row["id"]
        for row in db.query("SELECT id, season_number, episode_number FROM episode WHERE show_id = ?", (show_id,))
    }
    for ep in payload.get("episodes") or []:
        ep["id"] = known.get((ep.get("season_number"), ep.get("episode_number")), ep["id"])
    return payload

def _as(record_id, payload):
    payload["id"] = record_id
    return payload

def search_multi(query, page=1):
    return tvdb.search_multi(query, page=page)

def show(show_id):
    return _as(show_id, tvdb.show(_twin(show_id, "tv")))

def show_detail(show_id):
    return _as(show_id, tvdb.show_detail(_twin(show_id, "tv")))

def movie(movie_id):
    return _as(movie_id, tvdb.movie(_twin(movie_id, "movie")))

def movie_detail(movie_id):
    return _as(movie_id, tvdb.movie_detail(_twin(movie_id, "movie")))

def season(show_id, season_number):
    payload = tvdb.season(_twin(show_id, "tv"), season_number)
    return payload if tvdb.is_tvdb(show_id) else _keep_ids(show_id, payload)

def episode(show_id, season_number, episode_number):
    return tvdb.episode(_twin(show_id, "tv"), season_number, episode_number)
