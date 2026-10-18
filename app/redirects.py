"""Working out where a form should send you back to.

Forms post a `next` field where they can. Where they cannot, the referrer is
used - but only its path, and only when it points at this same host, so the
value can never be turned into an open redirect.
"""
from urllib.parse import urlparse

from flask import redirect, request, url_for


def is_local_path(target):
    """True only for a plain path on this site.

    Browsers drop tabs and newlines inside a URL and read a backslash as a
    slash, so "/<tab>/evil.example" and "/\\evil.example" both mean
    "//evil.example". Control characters and backslashes are refused outright.
    """
    if not target or not target.startswith("/") or target.startswith("//"):
        return False
    return not any(ch == "\\" or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in target)


def back(default_url):
    target = request.form.get("next")
    if is_local_path(target):
        return redirect(target)

    referrer = request.referrer
    if referrer:
        parts = urlparse(referrer)
        if not parts.netloc or parts.netloc == request.host:
            path = parts.path or "/"
            if parts.query:
                path = f"{path}?{parts.query}"
            if is_local_path(path):
                return redirect(path)

    return redirect(default_url)


def back_to(endpoint, **values):
    return back(url_for(endpoint, **values))
