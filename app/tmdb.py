"""Thin TMDB client."""
import time

import requests

from . import secretstore

BASE = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p"
TIMEOUT = 20

class TmdbError(RuntimeError):
    pass

class MissingKey(TmdbError):
    pass

def api_key():
    key = secretstore.get("tmdb_api_key")
    if not key:
        raise MissingKey("No TMDB API key saved. Add one on the Settings page.")
    return key

def _unreachable(exc):
    return TmdbError(f"Could not reach TMDB ({type(exc).__name__}).")

MAX_WAIT = 10

def _wait_seconds(retry_after):
    try:
        asked = int(retry_after)
    except (TypeError, ValueError):
        asked = 2
    return min(max(asked, 0), MAX_WAIT) + 1

def _get(path, params=None, **kwargs):
    params = dict(params or {})
    params.update(kwargs)
    params["api_key"] = api_key()
    params.setdefault("language", "en-GB")
    url = f"{BASE}{path}"
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, timeout=TIMEOUT)
        except requests.RequestException as exc:
            if attempt == 2:
                raise _unreachable(exc) from None
            time.sleep(1 + attempt)
            continue
        if resp.status_code == 429:
            time.sleep(_wait_seconds(resp.headers.get("Retry-After")))
            continue
        if resp.status_code == 401:
            raise TmdbError("TMDB rejected the API key. Check it on the Settings page.")
        if resp.status_code == 404:
            raise TmdbError("TMDB has no record of that.")
        if not resp.ok:
            if attempt == 2:
                raise TmdbError(f"TMDB returned {resp.status_code}.")
            time.sleep(1 + attempt)
            continue
        return resp.json()
    raise TmdbError("TMDB kept rate-limiting the request.")

def search_multi(query, page=1):
    data = _get("/search/multi", query=query, page=page, include_adult="false")
    results = []
    for item in data.get("results", []):
        kind = item.get("media_type")
        if kind == "tv":
            results.append(
                {
                    "kind": "tv",
                    "id": item["id"],
                    "title": item.get("name") or "Untitled",
                    "date": item.get("first_air_date") or "",
                    "overview": item.get("overview") or "",
                    "poster_path": item.get("poster_path"),
                    "vote_average": item.get("vote_average") or 0,
                }
            )
        elif kind == "movie":
            results.append(
                {
                    "kind": "movie",
                    "id": item["id"],
                    "title": item.get("title") or "Untitled",
                    "date": item.get("release_date") or "",
                    "overview": item.get("overview") or "",
                    "poster_path": item.get("poster_path"),
                    "vote_average": item.get("vote_average") or 0,
                }
            )
    return {"results": results, "total_pages": data.get("total_pages", 1), "page": data.get("page", 1)}

def show(show_id):
    return _get(f"/tv/{show_id}")

def show_detail(show_id):
    return _get(f"/tv/{show_id}", {
        "append_to_response": "aggregate_credits,watch/providers,external_ids,videos,content_ratings"
    })

def movie_detail(movie_id):
    return _get(f"/movie/{movie_id}", {
        "append_to_response": "credits,watch/providers,external_ids,videos,release_dates"
    })

def season(show_id, season_number):
    return _get(f"/tv/{show_id}/season/{season_number}")

def episode(show_id, season_number, episode_number):
    return _get(f"/tv/{show_id}/season/{season_number}/episode/{episode_number}")

def movie(movie_id):
    return _get(f"/movie/{movie_id}")

RELEASE_DIGITAL = 4
RELEASE_PHYSICAL = 5
RELEASE_TV = 6

COUNTRIES = ("GB", "IE", "US")

def movie_release_dates(movie_id):
    return _get(f"/movie/{movie_id}/release_dates")

def movie_providers(movie_id):
    return _get(f"/movie/{movie_id}/watch/providers")

def digital_release_date(payload):
    by_country = {}
    for entry in payload.get("results", []):
        code = entry.get("iso_3166_1")
        dates = []
        for release in entry.get("release_dates", []):
            if release.get("type") in (RELEASE_DIGITAL, RELEASE_PHYSICAL, RELEASE_TV):
                value = (release.get("release_date") or "")[:10]
                if value:
                    dates.append(value)
        if dates:
            by_country[code] = min(dates)

    for code in COUNTRIES:
        if code in by_country:
            return by_country[code]
    return min(by_country.values()) if by_country else None

def uk_providers(payload):
    results = payload.get("results", {})
    for code in COUNTRIES:
        country = results.get(code)
        if not country:
            continue
        names = []
        for key in ("flatrate", "free", "ads"):
            for provider in country.get(key, []):
                name = provider.get("provider_name")
                if name and name not in names:
                    names.append(name)
        if names:
            return names, country.get("link")
    return [], None

def discover_films_reaching_streaming(start, end, page=1):
    return _get("/discover/movie", {
        "region": "GB",
        "with_release_type": "4|6",
        "release_date.gte": start,
        "release_date.lte": end,
        "sort_by": "popularity.desc",
        "vote_count.gte": 0,
        "include_adult": "false",
        "page": page,
    })

def discover_new_series(start, end, page=1):
    return _get("/discover/tv", {
        "first_air_date.gte": start,
        "first_air_date.lte": end,
        "sort_by": "popularity.desc",
        "include_adult": "false",
        "page": page,
    })

def discover_returning_series(start, end, page=1):
    return _get("/discover/tv", {
        "air_date.gte": start,
        "air_date.lte": end,
        "sort_by": "popularity.desc",
        "include_adult": "false",
        "page": page,
    })

def cast_from(payload, limit=14):
    credits = payload.get("aggregate_credits") or payload.get("credits") or {}
    people = []
    for person in (credits.get("cast") or [])[:limit]:
        role = person.get("character")
        if not role:
            roles = person.get("roles") or []
            role = roles[0].get("character") if roles else None
        people.append({
            "name": person.get("name"),
            "role": role,
            "profile_path": person.get("profile_path"),
        })
    return [person for person in people if person["name"]]

def crew_from(payload, jobs=("Director", "Writer", "Screenplay")):
    credits = payload.get("credits") or {}
    seen, people = set(), []
    for person in credits.get("crew") or []:
        if person.get("job") in jobs and person.get("name") not in seen:
            seen.add(person.get("name"))
            people.append({"name": person.get("name"), "role": person.get("job")})
    return people[:6]

def creators_from(payload):
    return [
        person.get("name")
        for person in (payload.get("created_by") or [])
        if person.get("name")
    ]

def genres_from(payload):
    return [g.get("name") for g in (payload.get("genres") or []) if g.get("name")]

def trailer_from(payload):
    for video in ((payload.get("videos") or {}).get("results") or []):
        if video.get("site") == "YouTube" and video.get("type") in ("Trailer", "Teaser"):
            return {
                "name": video.get("name"),
                "url": f"https://www.youtube.com/watch?v={video.get('key')}",
            }
    return None

def imdb_from(payload):
    imdb_id = payload.get("imdb_id") or (payload.get("external_ids") or {}).get("imdb_id")
    return f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else None

def certification_from(payload):
    ratings = (payload.get("content_ratings") or {}).get("results")
    if ratings:
        by_country = {r.get("iso_3166_1"): r.get("rating") for r in ratings}
        for code in COUNTRIES:
            if by_country.get(code):
                return by_country[code]
        return None

    releases = (payload.get("release_dates") or {}).get("results") or []
    by_country = {}
    for entry in releases:
        for release in entry.get("release_dates", []):
            if release.get("certification"):
                by_country.setdefault(entry.get("iso_3166_1"), release["certification"])
    for code in COUNTRIES:
        if by_country.get(code):
            return by_country[code]
    return None

def providers_from(payload):
    return uk_providers(payload.get("watch/providers") or {})

def verify_key(candidate):
    try:
        resp = requests.get(
            f"{BASE}/configuration", params={"api_key": candidate}, timeout=TIMEOUT
        )
    except requests.RequestException as exc:
        raise _unreachable(exc) from None
    if resp.status_code == 401:
        raise TmdbError("TMDB rejected that key.")
    if not resp.ok:
        raise TmdbError(f"TMDB returned {resp.status_code}.")
    return True
