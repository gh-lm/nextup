"""Guard for the one thing that made ticking off a run of episodes painful."""
import pathlib

JS = pathlib.Path(__file__).resolve().parent.parent / "app" / "static" / "js" / "main.js"

def script():
    return JS.read_text(encoding="utf-8")

def test_the_page_position_is_saved_when_a_form_posts():
    js = script()
    assert "document.addEventListener('submit', rememberScroll, true);" in js

def test_the_page_position_is_put_back_on_the_way_in():
    js = script()
    assert "takeRememberedScroll" in js
    assert "window.scrollTo(0, wanted);" in js

def test_forms_submitted_by_script_remember_it_too():
    js = script()
    assert js.count("rememberScroll(); form.submit();") == 2

def test_it_only_puts_back_a_position_from_the_same_page():
    js = script()
    assert "saved.path !== window.location.pathname" in js

def test_storage_being_unavailable_is_survivable():
    js = script()
    block = js[js.index("function rememberScroll()"):js.index("function takeRememberedScroll()")]
    assert "try {" in block and "catch (error)" in block
