"""Confirmations appear beside what caused them, and the top bar stays tidy."""


def _settings(client):
    return client.get("/settings").data.decode()


def test_a_confirmation_lands_beside_its_own_panel(signed_in):
    resp = signed_in.post("/settings/availability", data={"available_after_days": "2"})
    assert resp.status_code == 302
    # The redirect carries the panel, so the browser returns there.
    assert resp.headers["Location"].endswith("#availability")

    body = _settings(signed_in)
    section = body.split('id="availability"')[1].split("</section>")[0]
    assert "watchable 2 days after they air" in section
    assert "note-success" in section


def test_a_refusal_lands_beside_the_same_panel(signed_in):
    resp = signed_in.post("/settings/availability", data={"available_after_days": "99"})
    assert resp.headers["Location"].endswith("#availability")
    section = _settings(signed_in).split('id="availability"')[1].split("</section>")[0]
    assert "between 0 and 14" in section
    assert "note-error" in section


def test_one_panel_does_not_show_another_panel_message(signed_in):
    signed_in.post("/settings/clock", data={"clock_format": "12"})
    signed_in.post("/settings/mail/schedule", data={"send_hour": "7", "send_minute": "12",
                                                    "send_meridiem": "am"})
    body = _settings(signed_in)
    mail = body.split('id="mail"')[1].split("</section>")[0]
    account = body.split('id="account"')[1].split("</section>")[0]
    assert "07:12" in mail or "7:12" in mail
    assert "note" not in account


def test_nothing_renders_as_a_toast_any_more(signed_in):
    signed_in.post("/settings/availability", data={"available_after_days": "1"})
    body = _settings(signed_in)
    assert "flash-success" not in body
    assert 'class="flash' not in body


def test_the_top_bar_no_longer_repeats_next_up(signed_in):
    body = signed_in.get("/").data.decode()
    nav = body.split('<nav class="nav"')[1].split("</nav>")[0]
    assert "Next up" not in nav
    # The logo covers it instead.
    assert 'title="Next up"' in body


def test_the_search_box_is_still_reachable(signed_in):
    body = signed_in.get("/").data.decode()
    assert 'id="q"' in body
    assert "Search shows and films" in body


def test_the_theme_button_is_an_icon_with_a_spoken_label(signed_in):
    body = signed_in.get("/").data.decode()
    toggle = body.split('action="/theme"')[1].split("</form>")[0]
    assert "btn-icon" in toggle
    # No visible word, but it still says what it does.
    assert "<span>Auto</span>" not in toggle
    assert "aria-label=" in toggle


def test_the_note_styling_is_not_a_banner():
    import pathlib

    css = (pathlib.Path(__file__).resolve().parent.parent
           / "app" / "static" / "css" / "main.css").read_text()
    assert ".flash-success" not in css
    block = css[css.index(".note {"):]
    block = block[: block.index("}")]
    assert "background: var(--muted)" in block
    assert "border" not in block.replace("border-radius", "")


def test_the_search_row_fills_the_width_when_it_wraps():
    """Otherwise it sits marooned against the right edge with a gap beside it."""
    import pathlib

    css = (pathlib.Path(__file__).resolve().parent.parent
           / "app" / "static" / "css" / "main.css").read_text()
    block = css[css.index("@media (max-width: 1080px)"):]
    block = block[: block.index("}\n}") + 2]
    assert "flex: 1 1 100%" in block
    assert ".searchbox input { width: 100%; }" in block


def test_the_preferences_save_themselves(signed_in):
    """Accent, the watchable delay and the email schedule need no button."""
    body = _settings(signed_in)
    for form_action in ("/settings/accent", "/settings/availability", "/settings/mail/schedule"):
        chunk = body.split(f'action="{form_action}"')[0]
        assert chunk.rstrip().endswith("<form data-autosave method=\"post\"") or \
               "data-autosave" in body.split(form_action)[0][-200:], form_action


def test_they_still_work_with_scripting_off(signed_in):
    """Each auto-saving form keeps a real submit button underneath."""
    body = _settings(signed_in)
    for marker, button in (
        ("settings.save_accent", "Apply colour"),
        ("settings/availability", "Save"),
        ("mail/schedule", "Save schedule"),
    ):
        assert button in body, button
    import pathlib
    js = (pathlib.Path(__file__).resolve().parent.parent
          / "app" / "static" / "js" / "main.js").read_text()
    assert "data-autosave" in js
    assert "hidden = true" in js
