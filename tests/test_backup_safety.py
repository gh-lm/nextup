"""Backups are never cached, and a restore is honest about the keys."""
import io


def test_the_backup_download_is_never_cached(signed_in):
    assert signed_in.get("/settings/export").headers["Cache-Control"] == "no-store"
    assert signed_in.get("/settings/export?secrets=1").headers["Cache-Control"] == "no-store"


def test_a_restore_without_keys_says_so_and_keeps_you_signed_in(signed_in):
    plain = signed_in.get("/settings/export").data
    response = signed_in.post("/settings/import", data={
        "backup": (io.BytesIO(plain), "nextup-backup.json"),
        "confirm": "replace",
    }, content_type="multipart/form-data")
    assert response.status_code == 302
    page = signed_in.get("/settings")
    assert page.status_code == 200
    assert b"type your TMDB key and mail password in again" in page.data
