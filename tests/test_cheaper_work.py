"""The cheaper routes must give the same answers as the slow ones they replaced."""

def test_grouped_progress_matches_the_one_at_a_time_answer(app):
    from app import db, queries

    with app.app_context():
        for show_id in (810, 811):
            db.execute("INSERT INTO show (id, name) VALUES (?, ?)", (show_id, f"S{show_id}"))
            db.execute("INSERT INTO tracked_show (show_id, added_at) VALUES (?, '2026-01-01')", (show_id,))
        rows = [
            (8101, 810, 1, 1, "2020-01-01"), (8102, 810, 1, 2, "2020-01-08"),
            (8103, 810, 1, 3, "2999-01-01"), (8111, 811, 1, 1, "2020-01-01"),
            (8100, 810, 0, 1, "2020-01-01"),
        ]
        for ep_id, show_id, season, number, day in rows:
            db.execute(
                "INSERT INTO episode (id, show_id, season_number, episode_number, name, air_date)"
                " VALUES (?, ?, ?, ?, 'x', ?)",
                (ep_id, show_id, season, number, day),
            )
        db.execute("INSERT INTO watched_episode (episode_id, show_id, watched_at) VALUES (8101, 810, 'x')")
        grouped = queries.all_progress()
        for show_id in (810, 811):
            assert grouped[show_id] == queries.show_progress(show_id)
        assert queries.show_progress(810)["aired"] == 2

def test_the_cheap_counts_match_a_real_export(app):
    from app import transfer

    with app.app_context():
        assert transfer.counts() == transfer.export_data()["counts"]

def test_refresh_now_returns_straight_away_and_runs_in_the_background(signed_in, app, monkeypatch):
    import threading

    from app import sync

    started = threading.Event()
    release = threading.Event()

    def slow(force=False):
        started.set()
        release.wait(5)
        return 0, 0, []

    monkeypatch.setattr(sync, "sync_all", slow)
    response = signed_in.post("/settings/sync")
    assert response.status_code == 302
    assert started.wait(5)
    release.set()
