"""Thin TMDB client.

Only the handful of endpoints Nextup needs. Every call takes the API key
from the encrypted settings store, so a missing key surfaces as a clear
error rather than a 401 from TMDB.
"""
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


def _get(path, params=None, **kwargs):
    """GET a TMDB endpoint.

    Some Discover filters are named with a dot, such as release_date.gte, so
    they come in through `params` rather than as keyword arguments.
    """
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
                raise TmdbError(f"Could not reach TMDB: {exc}") from exc
            time.sleep(1 + attempt)
            continue
        if resp.status_code == 429:
            time.sleep(int(resp.headers.get("Retry-After", "2")) + 1)
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
    """Everything the show page needs, in one request."""
    return _get(f"/tv/{show_id}", {
        "append_to_response": "aggregate_credits,watch/providers,external_ids,videos,content_ratings"
    })


def movie_detail(movie_id):
    """Everything the film page needs, in one request."""
    return _get(f"/movie/{movie_id}", {
        "append_to_response": "credits,watch/providers,external_ids,videos,release_dates"
    })


def season(show_id, season_number):
    return _get(f"/tv/{show_id}/season/{season_number}")


def episode(show_id, season_number, episode_number):
    return _get(f"/tv/{show_id}/season/{season_number}/episode/{episode_number}")


def movie(movie_id):
    return _get(f"/movie/{movie_id}")


# TMDB release types. 4 is the digital release, which for anyone who does not
# go to the cinema is the date that actually matters.
RELEASE_DIGITAL = 4
RELEASE_PHYSICAL = 5
RELEASE_TV = 6

# Preferred country order when reading dates and services.
COUNTRIES = ("GB", "IE", "US")


def movie_release_dates(movie_id):
    return _get(f"/movie/{movie_id}/release_dates")


def movie_providers(movie_id):
    return _get(f"/movie/{movie_id}/watch/providers")


def digital_release_date(payload):
    """The earliest date a film becomes watchable at home.

    Preference goes to a UK date. Failing that, Ireland or the US, and failing
    that the earliest digital date anywhere, which at least gives a hint.
    """
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
    """Which services carry the film, and the page listing them.

    Rental and purchase are left out on purpose: the question is what you can
    put on tonight without paying again.
    """
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
    """Films whose home release falls inside a window.

    Release type 4 is digital and 6 is television. Cinema releases, types 2
    and 3, are deliberately left out.
    """
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
    """Series whose first episode falls inside a window."""
    return _get("/discover/tv", {
        "first_air_date.gte": start,
        "first_air_date.lte": end,
        "sort_by": "popularity.desc",
        "include_adult": "false",
        "page": page,
    })


def discover_returning_series(start, end, page=1):
    """Series with an episode airing inside a window, new or long-running."""
    return _get("/discover/tv", {
        "air_date.gte": start,
        "air_date.lte": end,
        "sort_by": "popularity.desc",
        "include_adult": "false",
        "page": page,
    })


def cast_from(payload, limit=14):
    """Top-billed cast, from either a film's credits or a show's aggregate ones."""
    credits = payload.get("aggregate_credits") or payload.get("credits") or {}
    people = []
    for person in (credits.get("cast") or [])[:limit]:
        # A film gives one character; a show gives a list of roles across seasons.
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
    """A YouTube trailer, if TMDB knows of one. Linked, never embedded."""
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
    """The UK age rating, falling back to Ireland then the US."""
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
    """Where to watch, read from an appended watch/providers block."""
    return uk_providers(payload.get("watch/providers") or {})


def trending_tv():
    return _get("/trending/tv/week").get("results", [])


def verify_key(candidate):
    """Check a key works before saving it."""
    try:
        resp = requests.get(
            f"{BASE}/configuration", params={"api_key": candidate}, timeout=TIMEOUT
        )
    except requests.RequestException as exc:
        raise TmdbError(f"Could not reach TMDB: {exc}") from exc
    if resp.status_code == 401:
        raise TmdbError("TMDB rejected that key.")
    if not resp.ok:
        raise TmdbError(f"TMDB returned {resp.status_code}.")
    return True
