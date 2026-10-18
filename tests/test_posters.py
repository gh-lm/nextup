"""The picture cache keeps only whole images and never trusts a path or a reply."""
import os

from app import config, posters


class _Reply:
    def __init__(self, body, content_type="image/jpeg", length=None):
        self.ok = True
        self.content = body
        self.headers = {"Content-Type": content_type}
        if length is not None:
            self.headers["Content-Length"] = str(length)


def test_a_trailing_newline_is_not_a_good_path():
    assert posters.normalise("/abc.jpg\n") is None
    assert posters.normalise("/abc.jpg") == "/abc.jpg"


def test_a_good_picture_is_cached_and_no_temporary_file_is_left(data_dir, monkeypatch):
    monkeypatch.setattr(posters.requests, "get", lambda *a, **k: _Reply(b"image-bytes"))
    path = posters.cached_file("w92", "/abc.jpg")
    assert open(path, "rb").read() == b"image-bytes"
    assert not [n for n in os.listdir(config.CACHE_DIR) if n.endswith(".part")]


def test_something_that_is_not_an_image_is_not_cached(data_dir, monkeypatch):
    monkeypatch.setattr(posters.requests, "get", lambda *a, **k: _Reply(b"<html>", "text/html"))
    assert posters.cached_file("w92", "/abc.jpg") is None
    assert os.listdir(config.CACHE_DIR) == []


def test_a_truncated_picture_is_not_cached(data_dir, monkeypatch):
    monkeypatch.setattr(posters.requests, "get", lambda *a, **k: _Reply(b"short", length=500))
    assert posters.cached_file("w92", "/abc.jpg") is None
    assert os.listdir(config.CACHE_DIR) == []
