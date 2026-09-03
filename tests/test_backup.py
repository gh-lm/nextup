"""Taking everything out and putting it back."""
import io
import json
from datetime import date, timedelta


def _populate(app):
    from app import db, secretstore

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    db.execute("INSERT OR REPLACE INTO show (id, name, overview) VALUES (900, 'A Series', 'About things.')")
    db.execute(
        "INSERT OR REPLACE INTO tracked_show (show_id, added_at, favourite, shortlist)"
        " VALUES (900, '2026-01-01', 1, 0)"
    )
    db.execute("INSERT OR REPLACE INTO show (id, name) VALUES (901, 'A Maybe')")
    db.execute(
        "INSERT OR REPLACE INTO tracked_show (show_id, added_at, shortlist)"
        " VALUES (901, '2026-01-02', 1)"
    )
    db.execute(
        "INSERT OR REPLACE INTO episode (id, show_id, season_number, episode_number, name, air_date)"
        " VALUES (9001, 900, 1, 1, 'One', ?)",
        (yesterday,),
    )
    db.execute(
        "INSERT OR REPLACE INTO watched_episode (episode_id, show_id, watched_at)"
        " VALUES (9001, 900, '2026-02-02')"
    )
    db.execute("INSERT OR REPLACE INTO movie (id, title) VALUES (910, 'A Film')")
    db.execute("INSERT OR REPLACE INTO tracked_movie (movie_id, added_at) VALUES (910, '2026-01-03')")
    db.execute("INSERT OR REPLACE INTO dismissed (kind, item_id, dismissed_at) VALUES ('tv', 555, '2026-01-04')")
    secretstore.set("accent", "teal")
    secretstore.set("available_after_days", "2")
    secretstore.set("tmdb_api_key", "the-key-itself", encrypted=True)


def test_a_backup_holds_what_you_added_and_watched(app):
    from app import transfer

    with app.app_context():
        _populate(app)
        out = transfer.export_data()
        assert out["format"] == "nextup-backup"
        assert out["counts"]["tracked_show"] == 2
        assert out["counts"]["watched_episode"] == 1
        assert out["counts"]["tracked_movie"] == 1
        assert out["counts"]["dismissed"] == 1
        assert out["data"]["settings"]["accent"] == "teal"


def test_keys_are_left_out_unless_you_ask(app):
    from app import transfer

    with app.app_context():
        _populate(app)
        out = transfer.export_data()
        assert out["secrets_included"] is False
        assert "secrets" not in out["data"]
        assert "tmdb_api_key" in out["secrets_omitted"]
        assert "the-key-itself" not in json.dumps(out)


def test_asking_for_the_keys_puts_them_in(app):
    from app import transfer

    with app.app_context():
        _populate(app)
        out = transfer.export_data(include_secrets=True)
        assert out["secrets_included"] is True
        assert out["data"]["secrets"]["tmdb_api_key"] == "the-key-itself"


def test_a_backup_restores_onto_an_empty_copy(app):
    from app import db, queries, secretstore, transfer

    with app.app_context():
        _populate(app)
        saved = json.loads(json.dumps(transfer.export_data(include_secrets=True)))

        # Wipe it, the way a fresh machine would be.
        for table in ("watched_episode", "tracked_show", "tracked_movie", "dismissed",
                      "episode", "show", "movie", "settings"):
            db.execute(f"DELETE FROM {table}")
        assert queries.tracked_shows() == []

        restored = transfer.import_data(saved)
        assert restored["tracked_show"] == 2
        assert restored["watched_episode"] == 1

        # Everything is where it was.
        assert [r["id"] for r in queries.tracked_shows()] == [900]
        assert [r["id"] for r in queries.tracked_shows(shortlist=True)] == [901]
        assert queries.tracked_shows()[0]["favourite"] == 1
        assert queries.show_progress(900)["watched"] == 1
        assert [r["id"] for r in queries.movies()] == [910]
        assert queries.is_dismissed("tv", 555)
        assert secretstore.get("accent") == "teal"
        assert secretstore.get("tmdb_api_key") == "the-key-itself"


def test_the_restored_key_is_encrypted_again_not_left_in_the_clear(app):
    from app import db, transfer

    with app.app_context():
        _populate(app)
        saved = json.loads(json.dumps(transfer.export_data(include_secrets=True)))
        transfer.import_data(saved)
        row = db.query("SELECT value, encrypted FROM settings WHERE key = 'tmdb_api_key'", one=True)
        assert row["encrypted"] == 1
        assert "the-key-itself" not in row["value"]


def test_a_file_that_is_not_a_backup_is_refused(app):
    from app import transfer

    with app.app_context():
        for junk in [{"hello": "world"}, [], "text", {"format": "something-else"}]:
            try:
                transfer.import_data(junk)
            except transfer.ImportError_:
                pass
            else:
                raise AssertionError(f"should have refused {junk!r}")


def test_a_newer_backup_is_refused_rather_than_half_read(app):
    from app import transfer

    with app.app_context():
        try:
            transfer.import_data({"format": "nextup-backup", "version": 99, "data": {}})
        except transfer.ImportError_ as exc:
            assert "newer version" in str(exc)
        else:
            raise AssertionError("should have refused")


def test_a_broken_backup_changes_nothing(app):
    from app import queries, transfer

    with app.app_context():
        _populate(app)
        before = [r["id"] for r in queries.tracked_shows()]

        # A row pointing at a show that is not in the file at all.
        bad = {
            "format": "nextup-backup", "version": 1,
            "data": {"tracked_show": [{"show_id": 12345, "added_at": "2026-01-01"}]},
        }
        try:
            transfer.import_data(bad)
        except transfer.ImportError_ as exc:
            assert "Nothing was changed" in str(exc)
        else:
            raise AssertionError("should have refused")

        assert [r["id"] for r in queries.tracked_shows()] == before


def test_downloading_gives_you_a_file(signed_in, app):
    with app.app_context():
        _populate(app)
    resp = signed_in.get("/settings/export")
    assert resp.status_code == 200
    assert resp.mimetype == "application/json"
    assert "attachment" in resp.headers["Content-Disposition"]
    assert "nextup-backup-" in resp.headers["Content-Disposition"]
    assert json.loads(resp.data)["format"] == "nextup-backup"


def test_the_plain_download_carries_no_secrets(signed_in, app):
    with app.app_context():
        _populate(app)
    assert b"the-key-itself" not in signed_in.get("/settings/export").data
    assert b"the-key-itself" in signed_in.get("/settings/export?secrets=1").data


def test_uploading_restores_through_the_page(signed_in, app):
    from app import db, queries

    with app.app_context():
        _populate(app)
    saved = signed_in.get("/settings/export?secrets=1").data

    with app.app_context():
        for table in ("watched_episode", "tracked_show", "tracked_movie"):
            db.execute(f"DELETE FROM {table}")

    resp = signed_in.post("/settings/import", data={
        "backup": (io.BytesIO(saved), "nextup-backup.json"),
        "confirm": "replace",
    }, content_type="multipart/form-data")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("#transfer")

    with app.app_context():
        assert len(queries.tracked_shows(everything=True)) == 2


def test_restoring_without_ticking_the_box_does_nothing(signed_in, app):
    from app import db, queries

    with app.app_context():
        _populate(app)
    saved = signed_in.get("/settings/export").data
    with app.app_context():
        db.execute("DELETE FROM tracked_show")

    signed_in.post("/settings/import", data={
        "backup": (io.BytesIO(saved), "b.json"),
    }, content_type="multipart/form-data")

    with app.app_context():
        assert queries.tracked_shows(everything=True) == []


def test_the_upload_limit_is_bigger_than_a_real_backup(app):
    """A large library exports to a few megabytes; the old ceiling was two."""
    assert app.config["MAX_CONTENT_LENGTH"] >= 32 * 1024 * 1024
