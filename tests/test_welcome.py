import pytest

@pytest.fixture()
def fresh(signed_in):
    with signed_in.session_transaction() as sess:
        sess.pop("skip_welcome")
    return signed_in

def test_no_key_shows_the_welcome_page_with_steps(fresh):
    body = fresh.get("/").get_data(as_text=True)
    assert "One step to start" in body
    assert "themoviedb.org/signup" in body

def test_a_bad_key_is_explained_under_the_box_and_nothing_is_saved(fresh, app, monkeypatch):
    from app import secretstore, tmdb

    def refuse(key):
        raise tmdb.TmdbError("TMDB did not accept that key.")

    monkeypatch.setattr(tmdb, "verify_key", refuse)
    body = fresh.post("/welcome", data={"tmdb_api_key": "nope"}).get_data(as_text=True)
    assert "TMDB did not accept that key." in body
    with app.app_context():
        assert not secretstore.has("tmdb_api_key")

def test_a_good_key_is_saved_and_the_dashboard_opens(fresh, app, monkeypatch):
    from app import secretstore, sync, tmdb

    monkeypatch.setattr(tmdb, "verify_key", lambda key: None)
    monkeypatch.setattr(sync, "start_now", lambda app: None)
    response = fresh.post("/welcome", data={"tmdb_api_key": "abc"})
    assert response.status_code == 302
    with app.app_context():
        assert secretstore.has("tmdb_api_key")
    assert "One step to start" not in fresh.get("/").get_data(as_text=True)

def test_do_this_later_goes_to_the_dashboard_with_the_old_reminder(fresh):
    assert fresh.post("/welcome/later").status_code == 302
    body = fresh.get("/").get_data(as_text=True)
    assert "One step to start" not in body
    assert "No TheTVDB or TMDB key yet" in body
