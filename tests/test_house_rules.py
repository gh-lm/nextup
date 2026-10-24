"""Small rules about the words on screen."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"

def _text_people_read():
    for path in APP.rglob("*"):
        if path.suffix in {".html", ".py", ".js", ".css"} and "__pycache__" not in path.parts:
            yield path
    yield from (ROOT / "docs").glob("*.html")
    yield ROOT / "README.md"
    yield ROOT / "CHANGELOG.md"

def test_no_em_dashes_in_text_people_read():
    offenders = [
        str(path.relative_to(ROOT))
        for path in _text_people_read()
        if "—" in path.read_text(encoding="utf-8")
    ]
    assert not offenders, f"em dash found in: {offenders}"
