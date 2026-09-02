"""Poster and still proxy.

Images are fetched from TMDB once, written to the data directory and then
served from this app. Nothing in a page ever points at a third-party host.
"""
import hashlib
import os
import re

import requests
from flask import Blueprint, abort, send_file, send_from_directory

from .. import config
from ..auth import login_required
from ..tmdb import IMAGE_BASE

bp = Blueprint("images", __name__)

ALLOWED_SIZES = {"w92", "w154", "w185", "w300", "w342", "w500", "w780", "original"}
PATH_RE = re.compile(r"^/?[A-Za-z0-9]+\.(jpg|png|svg)$")


@bp.route("/img/<size>/<path:tmdb_path>")
@login_required
def poster(size, tmdb_path):
    if size not in ALLOWED_SIZES:
        abort(404)
    clean = "/" + tmdb_path.lstrip("/")
    if not PATH_RE.match(clean):
        abort(404)

    os.makedirs(config.CACHE_DIR, exist_ok=True)
    name = hashlib.sha256(f"{size}{clean}".encode()).hexdigest() + os.path.splitext(clean)[1]
    cached = os.path.join(config.CACHE_DIR, name)

    if not os.path.exists(cached):
        try:
            resp = requests.get(f"{IMAGE_BASE}/{size}{clean}", timeout=20)
        except requests.RequestException:
            return placeholder()
        if not resp.ok:
            return placeholder()
        tmp = cached + ".part"
        with open(tmp, "wb") as fh:
            fh.write(resp.content)
        os.replace(tmp, cached)

    return send_from_directory(
        config.CACHE_DIR, name, max_age=60 * 60 * 24 * 30, conditional=True
    )


@bp.route("/img/placeholder")
def placeholder():
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "img")
    return send_file(os.path.join(static_dir, "placeholder.svg"), mimetype="image/svg+xml")
