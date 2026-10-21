"""The hidden attribute has to win over component display rules."""
import pathlib
import re

CSS = pathlib.Path(__file__).resolve().parent.parent / "app" / "static" / "css" / "main.css"

def test_hidden_elements_are_really_hidden():
    css = CSS.read_text(encoding="utf-8")
    assert re.search(r"\[hidden\]\s*\{[^}]*display:\s*none\s*!important", css)

def test_the_clock_fallback_button_is_the_one_being_hidden():
    js = (CSS.parent.parent / "js" / "main.js").read_text(encoding="utf-8")
    assert "clock-toggle-go" in js
    assert "hidden = true" in js
