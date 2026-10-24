def _season(*eps):
    return {"season_number": 1, "episodes": [
        {"id": i, "season_number": 1, "episode_number": n, "name": f"e{i}"} for i, n in eps
    ]}

def test_episode_moved_to_a_new_slot_under_the_same_id_does_not_break_the_sync(app):
    from app import db, sync

    with app.app_context():
        sync.upsert_show({"id": 700, "name": "Moves"}, stamp=False)
        sync.upsert_episodes(700, _season((1, 1), (2, 2)))
        db.execute("INSERT INTO watched_episode (episode_id, show_id, watched_at) VALUES (2, 700, '2026-01-01')")
        sync.upsert_episodes(700, _season((2, 1), (1, 2)))
        sync.upsert_episodes(700, _season((3, 1), (2, 3)))
        rows = db.query("SELECT id, episode_number FROM episode WHERE show_id = 700 ORDER BY id")
        assert [(r["id"], r["episode_number"]) for r in rows] == [(1, 2), (2, 3), (3, 1)]
        assert db.query("SELECT 1 FROM watched_episode WHERE episode_id = 2", one=True)
