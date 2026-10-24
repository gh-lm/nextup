from datetime import date, timedelta

def test_discover_movies_split_days_ahead_from_the_last_two_weeks(signed_in, monkeypatch):
    from app import tmdb

    today = date.today()
    ahead_day = (today + timedelta(days=3)).isoformat()
    past_day = (today - timedelta(days=5)).isoformat()
    calls = []

    def fake_discover(start, end, page=1):
        calls.append((start, end))
        if end >= today.isoformat() and start == today.isoformat():
            return {"results": [{"id": 1, "title": "Coming Film", "release_date": "2026-01-01"}], "total_pages": 1}
        return {"results": [{"id": 2, "title": "Gone Film", "release_date": "2026-01-02"}], "total_pages": 1}

    def fake_dates(movie_id):
        day = ahead_day if movie_id == 1 else past_day
        return {"results": [{"iso_3166_1": "GB", "release_dates": [{"type": 4, "release_date": day + "T00:00:00.000Z"}]}]}

    monkeypatch.setattr(tmdb, "discover_films_reaching_streaming", fake_discover)
    monkeypatch.setattr(tmdb, "movie_release_dates", fake_dates)

    body = signed_in.get("/discover/films?days=7").get_data(as_text=True)
    assert "Released in the last 14 days" in body
    assert body.index("Coming Film") < body.index("Released in the last 14 days") < body.index("Gone Film")
    assert (today.isoformat(), (today + timedelta(days=7)).isoformat()) in calls
    assert ((today - timedelta(days=14)).isoformat(), (today - timedelta(days=1)).isoformat()) in calls
