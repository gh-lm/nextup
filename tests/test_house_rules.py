"""Small rules about the words on screen."""
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"

def test_no_em_dashes_in_text_people_read():
    offenders = []
    for path in APP.rglob("*"):
        if path.suffix in {".html", ".py", ".js", ".css"} and "__pycache__" not in path.parts:
            if "—" in path.read_text(encoding="utf-8"):
                offenders.append(str(path.relative_to(APP)))
    assert not offenders, f"em dash found in: {offenders}"
