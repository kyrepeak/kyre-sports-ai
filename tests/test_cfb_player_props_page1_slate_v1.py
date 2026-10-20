from __future__ import annotations

from datetime import date, datetime, timezone

import pytest


def _game(game_id: str, kickoff: str, *, verified: bool = True):
    return {
        "game_id": game_id,
        "identity_key": f"ncaa:{game_id}",
        "identity_verified": verified,
        "game_date": "2026-10-24",
        "kickoff_iso": kickoff,
        "status": "Scheduled",
        "away_team": f"Away {game_id}",
        "away_team_slug": f"away-{game_id}",
        "away_rank": 7,
        "away_espn_team_id": "101",
        "home_team": f"Home {game_id}",
        "home_team_slug": f"home-{game_id}",
        "home_rank": 12,
        "home_espn_team_id": "202",
    }


def test_normalize_preserves_official_identity_and_derives_phoenix_time():
    import cfb_player_props_page1_slate_v1 as slate
    row = slate.normalize_page1_game(_game("401999001", "2026-10-24T19:30:00-04:00"), date(2026, 10, 24))
    assert row["official_game_id"] == "401999001"
    assert row["identity_key"] == "ncaa:401999001"
    assert row["kickoff_iso"] == "2026-10-24T19:30:00-04:00"
    assert row["kickoff_phoenix"] == "4:30 PM MST"
    assert row["away_team_id"] == "101"
    assert row["home_team_id"] == "202"


def test_load_next_slate_reuses_existing_resolver_and_keeps_every_verified_game(monkeypatch):
    import cfb_player_props_page1_slate_v1 as slate
    games = [_game("401999001", "2026-10-24T19:30:00-04:00"), _game("401999002", "2026-10-24T22:00:00-04:00"), _game("bad", "2026-10-24T23:00:00-04:00", verified=False)]
    seen = {}
    def fake_resolver(*, games_loader, now_provider, max_days=14):
        seen["loader"] = games_loader
        return date(2026, 10, 24)
    def fake_games_for_date(day):
        seen.setdefault("days", []).append(day)
        return games
    monkeypatch.setattr(slate.next_slate, "resolve_runtime_cfb_slate_date", fake_resolver)
    monkeypatch.setattr(slate.schedule, "games_for_date", fake_games_for_date)
    result = slate.load_next_player_prop_slate(now_provider=lambda: datetime(2026, 10, 20, 4, 0, tzinfo=timezone.utc))
    assert seen["loader"] is fake_games_for_date
    assert result["state"] == "live"
    assert result["slate_date"] == date(2026, 10, 24)
    assert [g["official_game_id"] for g in result["games"]] == ["401999001", "401999002"]


def test_schedule_unavailable_fails_closed_without_synthesizing_games(monkeypatch):
    import cfb_player_props_page1_slate_v1 as slate
    monkeypatch.setattr(slate.next_slate, "resolve_runtime_cfb_slate_date", lambda **kwargs: None)
    result = slate.load_next_player_prop_slate()
    assert result["state"] == "unavailable"
    assert result["games"] == []
    assert result["slate_date"] is None


def test_normalize_rejects_unverified_or_missing_official_game_identity():
    import cfb_player_props_page1_slate_v1 as slate
    with pytest.raises(ValueError):
        slate.normalize_page1_game(_game("bad", "2026-10-24T19:30:00-04:00", verified=False), date(2026, 10, 24))
    row = _game("", "2026-10-24T19:30:00-04:00")
    with pytest.raises(ValueError):
        slate.normalize_page1_game(row, date(2026, 10, 24))
