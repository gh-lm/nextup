"""What the pages actually contain: structure, headings, and a way through without scripting."""
import pathlib
import re

import pytest

from pagebits import declarations, headings, parse

TEMPLATES = pathlib.Path(__file__).resolve().parent.parent / "app" / "templates"
PAGES = ["/", "/shows", "/maybe", "/movies", "/upcoming", "/calendar", "/search",
         "/settings", "/show/900", "/movie/901", "/episode/9001"]

@pytest.fixture()
def seeded(signed_in, app, monkeypatch):
    from app import db, secretstore, tmdb

    def down(*a, **k):
        raise tmdb.TmdbError("TMDB is unreachable")

    monkeypatch.setattr(tmdb, "show_detail", down)
    monkeypatch.setattr(tmdb, "movie_detail", down)
    monkeypatch.setattr(tmdb, "countries", down)
    with app.app_context():
        db.execute("INSERT INTO show (id, name) VALUES (900, 'A Show')")
        db.execute("INSERT INTO tracked_show (show_id, added_at) VALUES (900, '2026-01-01')")
        for i, season in enumerate((1, 2), start=1):
            db.execute(
                "INSERT INTO episode (id, show_id, season_number, episode_number, name, air_date)"
                " VALUES (?, 900, ?, 1, 'Pilot', '2020-01-01')", (9000 + i, season))
        db.execute(
            "INSERT INTO episode (id, show_id, season_number, episode_number, name, air_date)"
            " VALUES (9003, 900, 1, 2, 'Second', '2020-01-08')")
        db.execute("INSERT INTO movie (id, title) VALUES (901, 'A Film')")
        db.execute("INSERT INTO tracked_movie (movie_id, added_at) VALUES (901, '2026-01-01')")
        secretstore.set("tmdb_api_key", "made-up-key", encrypted=True)
        for key, value in (("smtp_host", "mail.example.com"), ("mail_from", "a@example.com"),
                           ("mail_to", "b@example.com")):
            secretstore.set(key, value)
    return signed_in

def _page(client, path):
    return parse(client.get(path).get_data(as_text=True))

def test_the_only_inline_style_is_a_progress_bar_width():
    bar = re.compile(r'<span style="width: \{\{ [\w.]+percent \}\}%"></span>')
    for page in TEMPLATES.rglob("*.html"):
        text = bar.sub("", page.read_text(encoding="utf-8"))
        assert "style=" not in text, f"{page.name} sets a style outside a progress bar"

def test_no_rendered_page_carries_a_layout_style(seeded):
    for path in PAGES:
        for node in _page(seeded, path).walk():
            if "style" in node.attrs:
                assert node.tag == "span" and node.parent.has_class("progress"), (path, node.attrs)
                assert re.fullmatch(r"width: \d+%", node.attrs["style"]), (path, node.attrs)

def test_headings_never_skip_a_level(seeded):
    for path in PAGES:
        levels = headings(_page(seeded, path))
        assert levels.count(1) == 1, f"{path} should have one h1: {levels}"
        for before, after in zip(levels, levels[1:]):
            assert after <= before + 1, f"{path} jumps from h{before} to h{after}"

def test_every_season_is_shown_open_with_no_folding(seeded):
    page = _page(seeded, "/show/900")
    assert not page.find_all("details") and not page.find_all("summary")
    seasons = [n for n in page.find_all("section") if n.has_class("season")]
    assert [s.find_all("h2")[0].text.strip() for s in seasons] == ["Season 1", "Season 2"]

def test_the_season_buttons_are_in_the_opened_body_and_reach_their_form(seeded):
    page = _page(seeded, "/show/900")
    forms = {f.attrs.get("id") for f in page.find_all("form")}
    seasons = [n for n in page.find_all("section") if n.has_class("season")]
    assert seasons
    for season in seasons:
        number = season.attrs["data-season"]
        buttons = [b for b in season.find_all("button") if b.attrs.get("form")]
        assert [b.text for b in buttons] == ["Mark season watched", "Clear season"]
        assert {b.attrs["form"] for b in buttons} == {f"season-watch-{number}"} <= forms

def test_marking_a_season_still_works_from_its_new_place(seeded, app):
    from app import db

    seeded.post("/show/900/season/1/watch", data={"mode": "watch"})
    with app.app_context():
        n = db.query("SELECT COUNT(*) AS n FROM watched_episode WHERE episode_id IN (9001, 9003)",
                     one=True)["n"]
    assert n == 2

def _noscript_boxes(form):
    return [i for ns in form.find_all("noscript") for i in ns.find_all("input", type="checkbox")]

@pytest.mark.parametrize("path", ["/show/900", "/movie/901"])
def test_removing_a_show_or_film_needs_a_second_step_without_scripting(seeded, path):
    page = _page(seeded, path)
    forms = [f for f in page.find_all("form") if "data-confirm" in f.attrs]
    assert len(forms) == 1
    boxes = _noscript_boxes(forms[0])
    assert len(boxes) == 1 and "required" in boxes[0].attrs
    assert "Yes, remove it" in forms[0].text

def test_removing_a_saved_key_or_password_needs_a_second_step(seeded):
    page = _page(seeded, "/settings")
    forms = {f.attrs["id"]: f for f in page.find_all("form") if "data-confirm" in f.attrs}
    assert {k: v.attrs["action"] for k, v in forms.items()} == {
        "clear-mail-form": "/settings/mail/clear", "clear-tmdb-form": "/settings/tmdb/clear"}
    for form_id in forms:
        buttons = [b for b in page.find_all("button") if b.attrs.get("form") == form_id]
        boxes = [i for i in page.find_all("input", type="checkbox") if i.attrs.get("form") == form_id]
        assert len(buttons) == 1 and buttons[0].attrs.get("data-confirm-label", "").startswith("Really")
        assert len(boxes) == 1 and "required" in boxes[0].attrs and boxes[0].inside("noscript")

def test_a_save_form_never_asks_for_the_remove_box(seeded):
    page = _page(seeded, "/settings")
    for form in page.find_all("form"):
        if form.attrs.get("action", "").endswith(("/settings/tmdb", "/settings/mail")):
            assert not [i for i in form.walk() if i.tag == "input" and "required" in i.attrs
                        and i.attrs.get("type") == "checkbox" and "form" not in i.attrs]

def test_the_waiting_rule_is_pointed_to_by_name_not_by_position(seeded):
    text = _page(seeded, "/settings").text
    assert "same rule as above" not in text
    assert "When something counts as watchable" in text

def test_a_note_inside_the_status_area_does_not_announce_itself_twice(seeded):
    with seeded.session_transaction() as sess:
        sess["_flashes"] = [("success", "Added.")]
    page = _page(seeded, "/shows")
    areas = page.find_all("div", role="status")
    assert len(areas) == 1 and "Added." in areas[0].text
    assert not [n for n in areas[0].walk() if n is not areas[0] and "role" in n.attrs]

def test_a_note_beside_its_panel_is_announced_once(seeded):
    seeded.post("/settings/availability", data={"available_after_days": "2"})
    page = _page(seeded, "/settings")
    panel = [s for s in page.find_all("section") if s.attrs.get("id") == "availability"][0]
    notes = [p for p in panel.find_all("p") if p.has_class("note")]
    assert len(notes) == 1 and notes[0].attrs.get("role") == "status"

def test_notes_are_words_only_with_no_tick_or_mark(seeded):
    seeded.post("/settings/availability", data={"available_after_days": "2"})
    ok = _page(seeded, "/settings")
    seeded.post("/settings/availability", data={"available_after_days": "99"})
    bad = _page(seeded, "/settings")
    for page in (ok, bad):
        notes = [p for p in page.find_all("p") if p.has_class("note")]
        assert notes and all(not n.find_all("svg") and not n.find_all("span") for n in notes)

def test_the_preferences_save_themselves_and_keep_a_button_for_no_scripting(seeded):
    page = _page(seeded, "/settings")
    expected = {"/settings/accent": "Apply colour", "/settings/availability": "Save",
                "/settings/mail/schedule": "Save schedule"}
    for form in page.find_all("form"):
        action = form.attrs.get("action", "")
        if action in expected:
            assert "data-autosave" in form.attrs, action
            assert expected[action] in [b.text for b in form.find_all("button")], action
            del expected[action]
    assert not expected, f"forms not found: {sorted(expected)}"

def test_the_search_box_names_its_shortcut_and_it_needs_a_modifier(seeded):
    box = [i for i in _page(seeded, "/").find_all("input") if i.attrs.get("id") == "q"][0]
    assert box.attrs["aria-keyshortcuts"] == "Alt+/"

def test_the_dashboard_shows_an_icon_not_a_chart_beside_every_number(seeded):
    page = _page(seeded, "/")
    stats = [n for n in page.find_all("div") if n.has_class("stat")]
    assert len(stats) == 4
    assert all(len(s.find_all("svg")) == 1 and s.find_all("svg")[0].attrs.get("aria-hidden") == "true" for s in stats)
    assert not [n for n in page.find_all("div") if n.has_class("progress")]

def test_the_last_refresh_says_what_the_problems_were(seeded, app):
    from app import db
    with app.app_context():
        db.execute(
            "INSERT INTO sync_run (started_at, shows_done, status, message)"
            " VALUES ('2026-10-24T09:00:00', 3, 'error', 'A Show: season 2 could not be fetched; Movies: timed out')"
        )
    text = seeded.get("/").get_data(as_text=True)
    assert "A Show: season 2 could not be fetched" in text and "Movies: timed out" in text

def test_a_sign_in_error_is_red_words_under_the_password_in_space_already_kept(client):
    empty = parse(client.get("/login").get_data(as_text=True))
    wrong = parse(client.post("/login", data={"username": "admin", "password": "wrong"}).get_data(as_text=True))
    for page in (empty, wrong):
        box = page.find_all("p", id="sign-in-error")
        assert len(box) == 1 and box[0].has_class("sign-in-error")
        password = page.find_all("input", id="password")[0]
        assert password.attrs["aria-describedby"] == "sign-in-error"
        assert not [n for n in page.find_all("p") if n.has_class("note")]
    assert empty.find_all("p", id="sign-in-error")[0].text == ""
    assert wrong.find_all("p", id="sign-in-error")[0].text == "Those details did not match."
    assert wrong.find_all("input", id="password")[0].attrs.get("aria-invalid") == "true"
    assert [i.attrs["id"] for i in empty.find_all("input") if "autofocus" in i.attrs] == ["username"]
    assert [i.attrs["id"] for i in wrong.find_all("input") if "autofocus" in i.attrs] == ["password"]
    css = (pathlib.Path(__file__).resolve().parent.parent / "app" / "static" / "css" / "main.css").read_text(encoding="utf-8")
    rule = declarations(css, ".sign-in-error")
    assert rule["color"] == "var(--danger)" and rule["min-height"] == "3em"

def test_watched_buttons_carry_the_word_with_no_tick_or_green(seeded):
    seeded.post("/episode/9001/watch", data={"to": "1"})
    page = _page(seeded, "/show/900")
    toggles = [b for b in page.find_all("button") if b.has_class("watch-toggle")]
    assert sorted(b.text for b in toggles) == ["Mark watched", "Mark watched", "Watched"]
    for b in toggles:
        assert not b.find_all("svg")
        assert b.attrs["aria-label"].startswith(b.text)
        assert b.has_class("on") == (b.text == "Watched")
    dashboard = _page(seeded, "/")
    for b in dashboard.find_all("button"):
        if b.text == "Watched":
            assert not b.find_all("svg")
    for path in PAGES:
        assert "badge-success" not in seeded.get(path).get_data(as_text=True), path
    css = (TEMPLATES.parent / "static" / "css" / "main.css").read_text()
    assert "--success" not in css and ".tick" not in css

def test_a_button_that_asks_you_to_mark_something_never_says_just_watched(seeded):
    page = _page(seeded, "/")
    labels = [b.text for b in page.find_all("button") if b.attrs.get("name") == "to"]
    assert labels and "Watched" not in labels
