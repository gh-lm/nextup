"""One place that turns a stored image path into a file on this server."""
import hashlib
import os
import re
import tempfile

import requests

from . import config, tvdb

ALLOWED_SIZES = {"w92", "w154", "w185", "w300", "w342", "w500", "w780", "original"}
MAX_BYTES = 10 * 1024 * 1024
PATH_RE = re.compile(r"/?[A-Za-z0-9_-]+\.(jpg|png|webp)")

def cache_name(size, clean_path):
    suffix = os.path.splitext(clean_path)[1]
    return hashlib.sha256(f"{size}{clean_path}".encode()).hexdigest() + suffix

def normalise(image_path):
    if not image_path:
        return None
    clean = "/" + str(image_path).lstrip("/")
    return clean if PATH_RE.fullmatch(clean) else None

def cached_file(size, image_path):
    if size not in ALLOWED_SIZES:
        return None
    clean = normalise(image_path)
    if clean is None:
        return None

    os.makedirs(config.CACHE_DIR, exist_ok=True)
    name = cache_name(size, clean)
    path = os.path.join(config.CACHE_DIR, name)
    if os.path.exists(path):
        return path

    url = tvdb.image_url(clean)
    body = _download(url) if url else None
    if body is None:
        return None

    fd, tmp = tempfile.mkstemp(dir=config.CACHE_DIR, suffix=".part")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(body)
        os.replace(tmp, path)
    except OSError:
        if os.path.exists(tmp):
            os.remove(tmp)
        return None
    return path

def _download(url):
    try:
        with requests.get(url, timeout=20, stream=True) as resp:
            if not resp.ok or not resp.headers.get("Content-Type", "").startswith("image/"):
                return None
            try:
                expected = int(resp.headers.get("Content-Length"))
            except (TypeError, ValueError):
                expected = None
            if expected is not None and expected > MAX_BYTES:
                return None
            body = bytearray()
            for chunk in resp.iter_content(64 * 1024):
                body += chunk
                if len(body) > MAX_BYTES:
                    return None
    except requests.RequestException:
        return None
    if not body or (expected is not None and expected != len(body)):
        return None
    return bytes(body)

def read_bytes(size, image_path):
    path = cached_file(size, image_path)
    if path is None:
        return None, None
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return None, None
    subtype = {".png": "png", ".webp": "webp"}.get(os.path.splitext(path)[1], "jpeg")
    return data, subtype
