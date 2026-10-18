"""One place that turns a TMDB image path into a file on this server.

The web pages serve these so no browser ever calls TMDB directly, and the
morning email attaches them so no mail client has to reach back here for a
picture. Both need the same caching, so it lives here rather than in either.
"""
import hashlib
import os
import re
import tempfile

import requests

from . import config
from .tmdb import IMAGE_BASE

ALLOWED_SIZES = {"w92", "w154", "w185", "w300", "w342", "w500", "w780", "original"}
PATH_RE = re.compile(r"/?[A-Za-z0-9_-]+\.(jpg|png|svg|webp)")


def cache_name(size, clean_path):
    suffix = os.path.splitext(clean_path)[1]
    return hashlib.sha256(f"{size}{clean_path}".encode()).hexdigest() + suffix


def normalise(tmdb_path):
    """The leading-slash form TMDB uses, or None if it is not a sane path."""
    if not tmdb_path:
        return None
    clean = "/" + str(tmdb_path).lstrip("/")
    return clean if PATH_RE.fullmatch(clean) else None


def cached_file(size, tmdb_path):
    """The local file for one image, fetching it once if it is not here yet.

    Returns None rather than raising, because a missing poster should never be
    the reason an email does not go out or a page does not render.
    """
    if size not in ALLOWED_SIZES:
        return None
    clean = normalise(tmdb_path)
    if clean is None:
        return None

    os.makedirs(config.CACHE_DIR, exist_ok=True)
    name = cache_name(size, clean)
    path = os.path.join(config.CACHE_DIR, name)
    if os.path.exists(path):
        return path

    try:
        resp = requests.get(f"{IMAGE_BASE}/{size}{clean}", timeout=20)
    except requests.RequestException:
        return None
    if not resp.ok or not resp.content:
        return None
    if not resp.headers.get("Content-Type", "").startswith("image/"):
        return None
    expected = resp.headers.get("Content-Length")
    if expected and expected.isdigit() and int(expected) != len(resp.content):
        return None

    # Each fetch writes its own temporary file, so two threads asking for the
    # same picture cannot trample one another's half-written copy.
    fd, tmp = tempfile.mkstemp(dir=config.CACHE_DIR, suffix=".part")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(resp.content)
        os.replace(tmp, path)
    except OSError:
        if os.path.exists(tmp):
            os.remove(tmp)
        return None
    return path


def read_bytes(size, tmdb_path):
    """The image itself, or None. Used to attach pictures to the email."""
    path = cached_file(size, tmdb_path)
    if path is None:
        return None, None
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return None, None
    subtype = "png" if path.endswith(".png") else "jpeg"
    return data, subtype
