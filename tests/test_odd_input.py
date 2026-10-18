"""Strange query strings and form values give a normal page or a polite refusal, never a 500."""
import pytest


@pytest.mark.parametrize("path", [
    "/?page=²",
    "/?page=-3",
    "/?page=99999999999999999999",
    "/upcoming?days=²",
    "/upcoming?days=0",
    "/calendar?y=9999&m=12",
    "/calendar?y=1&m=1",
    "/calendar?y=²&m=³",
    "/calendar?y=2026&m=13",
    "/search?q=x&page=²",
    "/discover/tv?days=²",
    "/discover/films?days=²",
])
def test_odd_query_strings_do_not_crash(signed_in, path):
    assert signed_in.get(path).status_code in (200, 302)


def test_odd_numbers_on_the_mail_forms_are_refused_politely(signed_in):
    schedule = signed_in.post(
        "/settings/mail/schedule", data={"send_hour": "²", "send_minute": "0"}
    )
    assert schedule.status_code == 302
    port = signed_in.post("/settings/mail", data={"smtp_host": "mail.invalid", "smtp_port": "²"})
    assert port.status_code == 302
    huge = signed_in.post("/settings/mail", data={"smtp_host": "mail.invalid", "smtp_port": "70000"})
    assert huge.status_code == 302
