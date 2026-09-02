"""Working out where a form should send you back to.

Forms post a `next` field where they can. Where they cannot, the referrer is
used - but only its path, and only when it points at this same host, so the
value can never be turned into an open redirect.
"""
from urllib.parse import urlparse

from flask import redirect, request, url_for


def back(default_url):
    target = request.form.get("next")
    if target and target.startswith("/") and not target.startswith("//"):
        return redirect(target)

    referrer = request.referrer
    if referrer:
        parts = urlparse(referrer)
        if not parts.netloc or parts.netloc == request.host:
            path = parts.path or "/"
            if parts.query:
                path = f"{path}?{parts.query}"
            if path.startswith("/") and not path.startswith("//"):
                return redirect(path)

    return redirect(default_url)


def back_to(endpoint, **values):
    return back(url_for(endpoint, **values))
