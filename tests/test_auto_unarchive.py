def _season(number):
    return {"season_number": number, "episodes": [
        {"id": 9100 + number, "season_number": number, "episode_number": 1, "name": "x", "air_date": "2026-01-01"}
    ]}

def _set_up(app, monkeypatch, seasons):
    from app import db, tvdb

    payload = {"id": 600, "name": "Returning", "seasons": [{"season_number": n} for n in seasons]}
    monkeypatch.setattr(tvdb, "show", lambda show_id: payload)
    monkeypatch.setattr(tvdb, "season", lambda show_id, number: _season(number))
    return db

def _archived(db):
    return db.query("SELECT archived FROM tracked_show WHERE show_id = 600", one=True)["archived"]

def test_archived_show_comes_back_when_a_new_season_appears(signed_in, app, monkeypatch):
    from app import sync

    db = _set_up(app, monkeypatch, [1])
    with app.app_context():
        sync.sync_show(600)
        db.execute("INSERT INTO tracked_show (show_id, added_at) VALUES (600, '2026-01-01')")
    signed_in.post("/show/600/archive", data={"to": "1"})
    with app.app_context():
        sync.sync_show(600)
        assert _archived(db) == 1
        _set_up(app, monkeypatch, [1, 2])
        sync.sync_show(600)
        assert _archived(db) == 0

def test_archived_show_stays_put_when_the_box_is_unticked(signed_in, app, monkeypatch):
    from app import sync

    db = _set_up(app, monkeypatch, [1])
    with app.app_context():
        sync.sync_show(600)
        db.execute("INSERT INTO tracked_show (show_id, added_at) VALUES (600, '2026-01-01')")
    signed_in.post("/show/600/archive", data={"to": "1"})
    signed_in.post("/show/600/auto-unarchive", data={})
    with app.app_context():
        _set_up(app, monkeypatch, [1, 2])
        sync.sync_show(600)
        assert _archived(db) == 1
