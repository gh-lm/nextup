"""Poster and still proxy.

Images are fetched from TMDB once, written to the data directory and then
served from this app. Nothing in a page ever points at a third-party host.
"""
import os

from flask import Blueprint, abort, send_file, send_from_directory

from .. import config, posters
from ..auth import login_required

bp = Blueprint("images", __name__)


@bp.route("/img/<size>/<path:tmdb_path>")
@login_required
def poster(size, tmdb_path):
    """Serve one cached image. The caching itself lives in app.posters, so the
    morning email can attach the very same file."""
    if size not in posters.ALLOWED_SIZES:
        abort(404)
    clean = posters.normalise(tmdb_path)
    if clean is None:
        abort(404)

    path = posters.cached_file(size, clean)
    if path is None:
        return placeholder()

    return send_from_directory(
        config.CACHE_DIR, os.path.basename(path), max_age=60 * 60 * 24 * 30, conditional=True
    )


@bp.route("/img/placeholder")
def placeholder():
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "img")
    return send_file(os.path.join(static_dir, "placeholder.svg"), mimetype="image/svg+xml")
