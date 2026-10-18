"""Guard for the one thing that made ticking off a run of episodes painful.

Every "watched" button posts a form and comes back as a fresh page, which the
browser draws from the top. Without this, marking off a series means scrolling
back down after each click.
"""
import pathlib

JS = pathlib.Path(__file__).resolve().parent.parent / "app" / "static" / "js" / "main.js"


def script():
    return JS.read_text(encoding="utf-8")


def test_the_page_position_is_saved_when_a_form_posts():
    js = script()
    assert "document.addEventListener('submit', rememberPage, true);" in js


def test_the_page_position_is_put_back_on_the_way_in():
    js = script()
    assert "takeRememberedPage" in js
    assert "window.scrollTo(0, wanted);" in js


def test_forms_submitted_by_script_remember_it_too():
    """form.submit() raises no submit event, so those two call it themselves."""
    js = script()
    assert js.count("rememberPage(); form.submit();") == 2


def test_it_only_puts_back_a_position_from_the_same_page():
    js = script()
    assert "saved.path !== window.location.pathname" in js


def test_storage_being_unavailable_is_survivable():
    """Private windows can throw on sessionStorage rather than return null."""
    js = script()
    block = js[js.index("function rememberPage()"):js.index("function takeRememberedPage()")]
    assert "try {" in block and "catch (error)" in block


def test_the_season_you_were_in_stays_open():
    """Left to itself the page opens whichever season holds the next unwatched
    episode. Tick off the last of them and that threw you back to season one."""
    js = script()
    assert "openSeasons" in js
    assert "details.season[data-season]" in js
    assert "seasons: openSeasons()" in js


def test_every_season_carries_its_number_for_that():
    import pathlib

    show = (pathlib.Path(__file__).resolve().parent.parent
            / "app" / "templates" / "pages" / "show.html").read_text()
    assert 'data-season="{{ season.number }}"' in show
