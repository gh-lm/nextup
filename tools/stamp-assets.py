#!/usr/bin/env python3
"""Stamp the stylesheet and script links in docs/*.html with a short hash of"""
import hashlib
import pathlib
import re

DOCS = pathlib.Path(__file__).resolve().parent.parent / "docs"
ASSETS = {"css/site.css": None, "js/typed.js": None}

def short_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()[:10]

def main():
    for name in ASSETS:
        ASSETS[name] = short_hash(DOCS / name)

    changed = []
    for page in sorted(DOCS.glob("*.html")):
        text = page.read_text(encoding="utf-8")
        before = text
        for name, digest in ASSETS.items():
            pattern = re.compile(r'((?:/)?%s)(\?v=[^"\']*)?' % re.escape(name))
            text = pattern.sub(lambda m: m.group(1) + "?v=" + digest, text)
        if text != before:
            page.write_text(text, encoding="utf-8")
            changed.append(page.name)

    for name, digest in ASSETS.items():
        print("%s -> ?v=%s" % (name, digest))
    print("%d page(s) updated" % len(changed))

if __name__ == "__main__":
    main()
