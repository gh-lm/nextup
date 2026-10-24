"""Rules the stylesheet must keep, read from its parsed rules rather than its text."""
import pathlib
import re

from pagebits import contrast, css_rules, declarations

ROOT = pathlib.Path(__file__).resolve().parent.parent
CSS = ROOT / "app" / "static" / "css" / "main.css"
SITE_CSS = ROOT / "docs" / "css" / "site.css"

def stylesheet():
    return CSS.read_text(encoding="utf-8")

def _sheets():
    return (("app", stylesheet()), ("site", SITE_CSS.read_text(encoding="utf-8")))

def test_hidden_elements_are_really_hidden():
    rule = declarations(stylesheet(), "[hidden]")
    assert rule.get("display") == "none !important"

def test_grids_let_their_columns_shrink():
    css = stylesheet()
    for selector in (".split > *", ".show-hero > *"):
        assert declarations(css, selector).get("min-width") == "0", selector

def test_the_cast_strip_scrolls_inside_itself():
    strip = declarations(stylesheet(), ".cast-strip")
    assert strip.get("overflow-x") == "auto"
    assert strip.get("min-width") == "0"
    assert strip.get("max-width") == "100%"

def test_every_custom_property_used_is_defined():
    css = stylesheet()
    defined = set(re.findall(r"(--[a-z0-9-]+)\s*:", css))
    used = set(re.findall(r"var\((--[a-z0-9-]+)", css))
    missing = sorted(used - defined)
    assert not missing, f"undefined custom properties: {missing}"

def test_every_custom_property_defined_is_used():
    css = stylesheet()
    defined = set(re.findall(r"(--[a-z0-9-]+)\s*:", css))
    used = set(re.findall(r"var\((--[a-z0-9-]+)", css))
    assert not sorted(defined - used), f"unused custom properties: {sorted(defined - used)}"

def test_focus_is_never_removed_without_a_replacement():
    css = stylesheet()
    if re.search(r"outline\s*:\s*(none|0)\b", css):
        assert ":focus-visible" in css

def test_no_coloured_edges_anywhere():
    status = re.compile(r"var\(--(accent|success|danger|warning|info)")
    offenders = []
    for name, css in _sheets():
        for selector, decls in css_rules(css):
            for prop, value in decls.items():
                if prop.startswith("border") and prop != "border-radius" and status.search(value):
                    offenders.append(f"{name}: {selector} {prop}: {value}")
    assert not offenders, "coloured edges found:\n" + "\n".join(offenders)

def test_no_underlines_anywhere():
    offenders = []
    for name, css in _sheets():
        for selector, decls in css_rules(css):
            if re.search(r"inset 0 -[\d.]+(em|px)? 0", decls.get("box-shadow", "")):
                offenders.append(f"{name}: {selector} uses an inset shadow as an underline")
            if "underline" in decls.get("text-decoration", "") or "text-decoration-thickness" in decls:
                offenders.append(f"{name}: {selector} underlines text")
        rules = dict(css_rules(css))
        assert rules["a"].get("text-decoration") == "none", name
        assert rules["a:hover"].get("color") == "var(--link-hover)", name
    assert not offenders, "underlines found:\n" + "\n".join(offenders)

def test_no_left_hand_edges_on_boxes():
    for name, css in _sheets():
        for selector, decls in css_rules(css):
            assert not any(p.startswith("border-left") for p in decls), f"{name}: {selector}"

def test_no_toast_banners_remain():
    css = stylesheet() + SITE_CSS.read_text(encoding="utf-8")
    assert ".flash" not in css
    for page in (ROOT / "app" / "templates").rglob("*.html"):
        assert 'class="flash' not in page.read_text(encoding="utf-8"), page.name

def test_controls_have_an_edge_you_can_actually_see():
    css = stylesheet()
    for selector in (".btn", ".btn-quiet"):
        decls = declarations(css, selector)
        assert "var(--field-border)" in decls.get("border", "") + decls.get("border-color", ""), selector
    root = dict(re.findall(r"(--[a-z-]+):\s*(#[0-9a-f]{6})", "".join(
        f"{k}:{v};" for k, v in declarations(css, ":root").items())))
    assert contrast(root["--field-border"], root["--panel"]) >= 3

def test_a_quiet_button_is_still_a_button():
    assert declarations(stylesheet(), ".btn-quiet").get("border-color") != "transparent"

def test_the_stylesheet_is_dark_only():
    css = stylesheet()
    assert "prefers-color-scheme" not in css
    assert "data-theme" not in css
    assert declarations(css, ":root").get("color-scheme") == "dark"

def test_a_note_is_a_quiet_strip_not_a_banner():
    note = declarations(stylesheet(), ".note")
    assert note.get("background") == "var(--muted)"
    assert not [p for p in note if p.startswith("border") and p != "border-radius"]

def test_the_search_row_fills_the_width_when_it_wraps():
    rules = dict()
    for selector, decls in css_rules(stylesheet()):
        if selector.startswith("@media (max-width: 1080px) ::"):
            rules[selector.split(":: ")[1]] = decls
    assert rules[".topbar-right"]["flex"] == "1 1 100%"
    assert rules[".searchbox input"]["width"] == "100%"

def test_the_link_hover_colour_still_stands_out_from_text_and_background():
    for name, css in _sheets():
        block = re.search(r":root\s*\{([^}]*)\}", css).group(1)
        root = dict(re.findall(r"(--[a-z-]+):\s*(#[0-9a-fA-F]{6})", block))
        for colour in (root["--link"], root["--link-hover"]):
            assert contrast(colour, root["--fg"]) >= 3, (name, colour)
            for back in (root["--bg"], root["--panel"]):
                assert contrast(colour, back) >= 4.5, (name, colour, back)
