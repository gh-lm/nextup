"""Working out where a form should send you back to."""
from urllib.parse import urlparse

from flask import redirect, request, url_for

def is_local_path(target):
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
