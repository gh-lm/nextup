#!/usr/bin/env python3
"""Set the "Page last updated" date and sitemap entry of every docs page with changes not yet committed to today. With page names on the command line, only those pages are stamped. Run before committing a release."""
import datetime
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

def changed_on(page):
    if sys.argv[1:]:
        return datetime.date.today() if page.name in sys.argv[1:] else None
    rel = str(page.relative_to(ROOT))
    if subprocess.run(["git", "diff", "--quiet", "HEAD", "--", rel], cwd=ROOT).returncode:
        return datetime.date.today()
    return None

def main():
    dates = {}
    for page in sorted(DOCS.glob("*.html")):
        day = changed_on(page)
        text = page.read_text(encoding="utf-8")
        pattern = re.compile(r'(Page last updated: <time datetime=")[\d-]+(">)[^<]*(</time>)')
        if day and pattern.search(text):
            label = f"{day.day} {day.strftime('%B %Y')}"
            new = pattern.sub(lambda m: f"{m.group(1)}{day.isoformat()}{m.group(2)}{label}{m.group(3)}", text)
            if new != text:
                page.write_text(new, encoding="utf-8")
                print(page.name, day.isoformat())
        if day:
            dates[page.name] = day.isoformat()
    site = DOCS / "sitemap.xml"
    xml = site.read_text(encoding="utf-8")

    def fix(match):
        name = match.group(1).rsplit("/", 1)[-1] or "index.html"
        return match.group(0) if name not in dates else re.sub(r"<lastmod>[\d-]+</lastmod>", f"<lastmod>{dates[name]}</lastmod>", match.group(0))

    xml = re.sub(r"<url>\s*<loc>([^<]*)</loc>.*?</url>", fix, xml, flags=re.S)
    site.write_text(xml, encoding="utf-8")

if __name__ == "__main__":
    main()
