from sports_api.api import cfb_official_games_v1 as identity


def test_official_games_returns_only_requested_verified_date(monkeypatch):
    verified_games = [
        {
            "event_id": "401752999",
            "game_date": "2026-09-19",
            "away_team": "Example State",
            "home_team": "Example Tech",
            "away_team_id": "100",
            "home_team_id": "200",
            "venue": "Example Stadium",
            "broadcast": "ESPN",
            "status": "Scheduled",
            "sources": ["verified fixture"],
        },
        {
            "event_id": "401753000",
            "game_date": "2026-09-20",
            "away_team": "Other State",
            "home_team": "Other Tech",
            "away_team_id": "300",
            "home_team_id": "400",
            "venue": "Other Stadium",
            "broadcast": "ABC",
            "status": "Scheduled",
            "sources": ["verified fixture"],
        },
    ]

    monkeypatch.setattr(
        identity,
        "load_verified_games",
        lambda: (verified_games, {"snapshot_present": True, "verified_games": 2}),
    )
    monkeypatch.setattr(
        identity,
        "_fetch_github_verified_games",
        lambda: ([], {"source": "test", "ok": True, "verified_games": 0}),
    )
    monkeypatch.setattr(
        identity,
        "_fetch_espn_verified_games",
        lambda requested_day: ([], {"date": requested_day, "ok": True, "games": 0}),
    )

    payload = identity.official_games(game_date="2026-09-19")

    assert payload["game_date"] == "2026-09-19"
    assert payload["verified"] is True
    assert payload["synthetic_ids"] is False
    assert payload["sportsbook_projection_influence_pct"] == 0.0
    assert payload["game_count"] == 1
    assert payload["games"] == [verified_games[0]]


def test_official_games_rejects_invalid_date():
    try:
        identity.official_games(game_date="09/19/2026")
    except identity.HTTPException as exc:
        assert exc.status_code == 400
        assert "YYYY-MM-DD" in str(exc.detail)
    else:
        raise AssertionError("invalid game_date must fail closed")
