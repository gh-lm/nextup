"""Every colour pair that carries text or a mark reaches 4.5 to 1 (WCAG 1.4.3)."""
import pathlib
import re

from pagebits import contrast, declarations

CSS = (pathlib.Path(__file__).resolve().parent.parent / "app" / "static" / "css" / "main.css").read_text(encoding="utf-8")
COLOUR = re.compile(r"(--[a-z-]+):\s*(#[0-9a-fA-F]{6})")

def _accents():
    root = dict(COLOUR.findall(declarations_text(":root")))
    found = {"brand": {
        "accent": root["--accent"], "hover": root["--accent-hover"], "on": root["--on-accent"],
        "container": root["--accent-container"], "on_container": root["--on-accent-container"],
    }}
    for name, block in re.findall(r':root\[data-accent="(\w+)"\]\s*\{([^}]*)\}', CSS):
        d = dict(COLOUR.findall(block))
        found[name] = {
            "accent": d["--accent-dark"], "hover": d["--accent-hover-dark"], "on": d["--on-accent"],
            "container": d["--accent-container-dark"], "on_container": d["--on-accent-container-dark"],
        }
    return found

def declarations_text(selector):
    return "".join(f"{k}:{v};" for k, v in declarations(CSS, selector).items())

def test_every_accent_pair_reaches_4_5_to_1():
    failures = []
    for name, c in _accents().items():
        for label, fg, bg in (("rest", c["on"], c["accent"]), ("hover", c["on"], c["hover"]),
                              ("container", c["on_container"], c["container"])):
            ratio = contrast(fg, bg)
            if ratio < 4.5:
                failures.append(f"{name} {label}: {ratio:.2f}")
    assert not failures, failures

def test_every_accent_the_settings_page_offers_has_its_colours():
    from app.routes.settings import ACCENTS

    assert sorted(_accents()) == sorted(key for key, _, _ in ACCENTS)

def test_every_swatch_has_a_colour_to_show():
    from app.routes.settings import ACCENTS

    for key, _, hex_ in ACCENTS:
        assert declarations(CSS, f".swatch-{key} span").get("background") == hex_, key

def test_the_delete_button_reaches_4_5_to_1_at_rest_and_on_hover():
    root = dict(COLOUR.findall(declarations_text(":root")))
    danger = declarations(CSS, ".btn-danger")
    hover = declarations(CSS, ".btn-danger:hover")
    assert danger["color"] == "#fff"
    assert danger["background"] == "var(--danger-solid)"
    assert hover["background"] == "var(--danger-solid-hover)"
    assert contrast("#ffffff", root["--danger-solid"]) >= 4.5
    assert contrast("#ffffff", root["--danger-solid-hover"]) >= 4.5

def test_the_primary_button_and_the_marks_use_the_pair_that_was_checked():
    for selector in (".btn-primary", ".brand-mark", ".calendar td.today .cal-daynum"):
        d = declarations(CSS, selector)
        assert d.get("color") == "var(--on-accent)", selector
        assert d.get("background") == "var(--accent)", selector
    assert declarations(CSS, ".btn-primary:hover")["background"] == "var(--accent-hover)"

def test_a_control_edge_stands_out_from_the_panel_behind_it():
    root = dict(COLOUR.findall(declarations_text(":root")))
    assert contrast(root["--field-border"], root["--panel"]) >= 3

def test_the_ring_on_the_chosen_swatch_stands_out_by_3_to_1():
    root = dict(COLOUR.findall(declarations_text(":root")))
    ring = declarations(CSS, ".swatch input:checked + span")["box-shadow"]
    assert ring == "0 0 0 3px var(--panel), 0 0 0 6px var(--fg)"
    assert contrast(root["--fg"], root["--panel"]) >= 3

def test_the_watched_button_is_grey_and_readable():
    root = dict(COLOUR.findall(declarations_text(":root")))
    on = declarations(CSS, ".watch-toggle.on")
    assert on["color"] == "var(--muted-fg)" and on["background"] == "transparent"
    assert contrast(root["--muted-fg"], root["--panel"]) >= 4.5

def test_red_words_reach_4_5_to_1_on_every_surface_they_sit_on():
    root = dict(COLOUR.findall(declarations_text(":root")))
    for back in ("--panel", "--muted", "--danger-bg", "--bg"):
        assert contrast(root["--danger"], root[back]) >= 4.5, back

def test_the_empty_part_of_a_progress_bar_stands_out_by_3_to_1():
    root = dict(COLOUR.findall(declarations_text(":root")))
    assert declarations(CSS, ".progress")["background"] == "var(--field-border)"
    assert contrast(root["--field-border"], root["--panel"]) >= 3

def test_cast_and_details_are_the_same_size_with_tops_level():
    even = declarations(CSS, ".split-even")
    assert even["grid-template-columns"] == "1fr 1fr" and even["align-items"] == "stretch"
    assert declarations(CSS, ".split > .panel")["margin-top"] == "0"
