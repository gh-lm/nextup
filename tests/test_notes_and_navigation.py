"""Confirmations appear beside what caused them, and the top bar stays tidy."""

def _settings(client):
    return client.get("/settings").data.decode()

def test_a_confirmation_lands_beside_its_own_panel(signed_in):
    resp = signed_in.post("/settings/availability", data={"available_after_days": "2"})
    assert resp.status_code == 302
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
    assert 'title="Next up"' in body

def test_the_search_box_is_still_reachable(signed_in):
    body = signed_in.get("/").data.decode()
    assert 'id="q"' in body
    assert "Search shows and movies" in body

def test_there_is_no_appearance_switch_any_more(signed_in):
    body = signed_in.get("/").data.decode()
    assert "/theme" not in body
    assert "data-theme" not in body
