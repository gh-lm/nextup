"""The hidden attribute has to win over component display rules.

The browser hides [hidden] with display:none from its own stylesheet, but any
author rule setting display beats that. Several components here set display,
so without an explicit rule a hidden button stays on screen.
"""
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
