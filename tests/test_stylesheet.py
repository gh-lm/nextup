"""Guards for layout rules that are easy to delete and hard to notice.

A grid track will not shrink below its content unless it is told to. Every
grid below holds something that does not wrap, so losing these rules pushes
the whole page sideways rather than scrolling inside the panel.
"""
import pathlib
import re

CSS = pathlib.Path(__file__).resolve().parent.parent / "app" / "static" / "css" / "main.css"
SITE_CSS = pathlib.Path(__file__).resolve().parent.parent / "docs" / "css" / "site.css"


def stylesheet():
    return CSS.read_text(encoding="utf-8")


def test_the_split_layout_lets_its_columns_shrink():
    assert ".split > * { min-width: 0; }" in stylesheet()


def test_the_cast_strip_scrolls_inside_itself():
    css = stylesheet()
    block = css[css.index(".cast-strip {"):]
    block = block[: block.index("}")]
    assert "overflow-x: auto" in block
    assert "min-width: 0" in block
    assert "max-width: 100%" in block


def test_the_show_hero_columns_can_shrink():
    assert ".show-hero > * { min-width: 0; }" in stylesheet()


def test_every_custom_property_used_is_defined():
    css = stylesheet()
    defined = set(re.findall(r"(--[a-z0-9-]+)\s*:", css))
    used = set(re.findall(r"var\((--[a-z0-9-]+)", css))
    missing = sorted(used - defined)
    assert not missing, f"undefined custom properties: {missing}"


def test_focus_is_never_removed_without_a_replacement():
    css = stylesheet()
    if re.search(r"outline\s*:\s*(none|0)\b", css):
        assert ":focus-visible" in css


def test_no_coloured_edges_anywhere():
    """A standing rule: status is carried by fill, glyph or text, never a
    coloured border. Checked declaration by declaration, because a filled
    button legitimately sets a coloured background and a transparent border on
    the same line. Focus outlines are not borders and are required to stay.
    """
    status = re.compile(r"var\(--(accent|success|danger|warning|info)")
    offenders = []
    for name, css in (("app", stylesheet()), ("site", SITE_CSS.read_text(encoding="utf-8"))):
        # Strip comments so prose about borders is not mistaken for a rule.
        body = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        for declaration in body.split(";"):
            declaration = declaration.strip().split("{")[-1].strip()
            prop, _, value = declaration.partition(":")
            prop = prop.strip()
            if not prop.startswith("border") or prop == "border-radius":
                continue
            if status.search(value):
                offenders.append(f"{name}: {prop}:{value.strip()}")
    assert not offenders, "coloured edges found:\n" + "\n".join(offenders)


def test_status_is_still_distinguishable_without_colour():
    """Removing the edges must not leave colour as the only signal."""
    note = (CSS.parent.parent.parent / "templates" / "partials" / "_note.html").read_text()
    assert "note-mark" in note
    # A drawn shape either way - alert for bad news, tick for good - so the
    # kind of note is never carried by its colour alone.
    assert "icons.alert() if item.kind == 'error' else icons.tick()" in note


def test_no_decorative_underlines():
    """Underlining as decoration is banned. Link hover underlines stay, because
    without them an inline link is told apart by colour alone."""
    offenders = []
    for name, css in (("app", stylesheet()), ("site", SITE_CSS.read_text(encoding="utf-8"))):
        body = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        for rule in body.split("}"):
            selector, _, block = rule.rpartition("{")
            selector = selector.strip().splitlines()[-1] if selector.strip() else ""
            if not block.strip():
                continue
            # The fake-underline trick: an inset shadow hugging the bottom edge.
            if re.search(r"box-shadow:\s*inset 0 -[\d.]+e?m? 0", block):
                offenders.append(f"{name}: {selector} uses an inset shadow as an underline")
            if "text-decoration" in block and "underline" in block:
                if ":hover" not in selector and ":focus" not in selector:
                    offenders.append(f"{name}: {selector} underlines text outright")
    assert not offenders, "decorative underlines found:\n" + "\n".join(offenders)


def test_no_left_hand_edges_on_boxes():
    for name, css in (("app", stylesheet()), ("site", SITE_CSS.read_text(encoding="utf-8"))):
        body = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        assert "border-left" not in body, f"{name} has a left-hand edge"


def test_no_toast_banners_remain():
    """Confirmations belong beside the control, not in a banner at the top."""
    css = stylesheet() + SITE_CSS.read_text(encoding="utf-8")
    assert ".flash" not in css
    templates = (CSS.parent.parent.parent / "templates")
    for page in templates.rglob("*.html"):
        assert 'class="flash' not in page.read_text(encoding="utf-8"), page.name


def test_controls_have_an_edge_you_can_actually_see():
    """A button whose border matches its background is indistinguishable from
    text. Both button styles and the form fields use the same visible edge."""
    css = stylesheet()
    for rule in (".btn {", ".btn-quiet {"):
        block = css[css.index(rule):]
        block = block[: block.index("}")]
        assert "var(--field-border)" in block, f"{rule} has no visible edge"
    assert "--field-border: #84848d" in css   # light, 3.71 against white
    assert "--field-border: #666a82" in css   # dark, 3.15 against the panel


def test_a_quiet_button_is_still_a_button():
    css = stylesheet()
    block = css[css.index(".btn-quiet {"):]
    block = block[: block.index("}")]
    assert "border-color: transparent" not in block
