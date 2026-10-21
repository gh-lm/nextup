"""Every query takes today's date from app.clock, not from SQLite's own UTC clock."""

def test_aired_and_upcoming_follow_the_app_clock(app, monkeypatch):
    from app import clock, db, queries

    monkeypatch.setattr(clock, "today", lambda: "2030-06-15")
    with app.app_context():
        db.execute("INSERT INTO show (id, name) VALUES (600, 'Clocked')")
        db.execute("INSERT INTO tracked_show (show_id, added_at) VALUES (600, '2030-01-01')")
        for ep_id, number, day in ((6001, 1, "2030-06-15"), (6002, 2, "2030-06-16")):
            db.execute(
                "INSERT INTO episode (id, show_id, season_number, episode_number, name, air_date)"
                " VALUES (?, 600, 1, ?, 'x', ?)",
                (ep_id, number, day),
            )
        assert queries.show_progress(600)["aired"] == 1
        assert queries.next_airing(600)["air_date"] == "2030-06-16"
        assert [e["air_date"] for e in queries.upcoming(days=3650)] == ["2030-06-15", "2030-06-16"]
