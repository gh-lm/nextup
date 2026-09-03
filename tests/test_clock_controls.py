"""The time controls on the Settings page."""


import re


def _settings(client):
    return client.get("/settings").data.decode()


def _options(body, select_id):
    """The visible text of every option in one dropdown."""
    block = body.split(f'id="{select_id}"')[1].split("</select>")[0]
    return [text.strip() for text in re.findall(r"<option[^>]*>(.*?)</option>", block)]


def test_the_hours_are_padded_on_the_24_hour_clock(signed_in, app):
    from app import secretstore

    with app.app_context():
        secretstore.set("clock_format", "24")
        secretstore.set("daily_email_time", "08:05")

    hours = _options(_settings(signed_in), "send_hour")
    # Midnight through nine read as 00 to 09, not 0 to 9.
    assert hours[:3] == ["00", "01", "02"]
    assert "08" in hours and "09" in hours and "23" in hours
    assert "8" not in hours and "9" not in hours
    assert len(hours) == 24


def test_the_minutes_are_padded_too(signed_in, app):
    from app import secretstore

    with app.app_context():
        secretstore.set("daily_email_time", "08:05")
    minutes = _options(_settings(signed_in), "send_minute")
    assert minutes[0] == "00" and minutes[5] == "05" and minutes[-1] == "59"
    assert "5" not in minutes
    assert len(minutes) == 60


def test_the_twelve_hour_clock_counts_one_to_twelve(signed_in, app):
    from app import secretstore

    with app.app_context():
        secretstore.set("clock_format", "12")
        secretstore.set("daily_email_time", "19:12")
    body = _settings(signed_in)
    hours = _options(body, "send_hour")
    assert hours == [str(h) for h in range(1, 13)]
    assert 'id="send_meridiem"' in body


def test_the_meridiem_only_appears_on_the_twelve_hour_clock(signed_in, app):
    from app import secretstore

    with app.app_context():
        secretstore.set("clock_format", "24")
    assert 'id="send_meridiem"' not in _settings(signed_in)


def test_the_switch_sits_with_the_time_and_offers_both_clocks(signed_in):
    body = _settings(signed_in)
    # Inside the same row as the time, not up beside the heading.
    row = body.split('class="timerow"')[1].split("</div>\n          <p class=\"hint\"")[0]
    assert "12 hours" in row and "24 hours" in row
    assert 'name="clock_format"' in row


def test_the_switch_works_without_scripting(signed_in):
    """Its inputs belong to a real form with a real submit button."""
    body = _settings(signed_in)
    assert 'id="clock-form"' in body
    assert 'form="clock-form"' in body
    assert "clock-toggle-go" in body


def test_choosing_a_clock_sticks_and_redraws_the_controls(signed_in, app):
    from app import mailer

    signed_in.post("/settings/clock", data={"clock_format": "12"})
    with app.app_context():
        assert mailer.clock_format() == "12"
    assert 'id="send_meridiem"' in _settings(signed_in)

    signed_in.post("/settings/clock", data={"clock_format": "24"})
    with app.app_context():
        assert mailer.clock_format() == "24"
    assert 'id="send_meridiem"' not in _settings(signed_in)


def test_a_time_chosen_on_one_clock_survives_the_switch(signed_in, app):
    from app import secretstore

    signed_in.post("/settings/mail/schedule", data={"send_hour": "19", "send_minute": "12"})
    with app.app_context():
        assert secretstore.get("daily_email_time") == "19:12"

    signed_in.post("/settings/clock", data={"clock_format": "12"})
    body = _settings(signed_in)
    hour_block = body.split('id="send_hour"')[1].split("</select>")[0]
    assert re.search(r'value="7"[^>]*selected', hour_block)
    assert re.search(r'value="pm"[^>]*selected', body)
