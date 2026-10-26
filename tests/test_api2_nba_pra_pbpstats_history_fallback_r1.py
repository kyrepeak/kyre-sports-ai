from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import sports_api.api.nba_pra_pbpstats_history_fallback_v1 as fb


def test_pbp_identity_resolves_normalized_player_name() -> None:
    payload = {"players": {"1629675": "Naz Reid", "123": "Other Player"}}
    out = fb._identity_index(payload)
    assert out["nazreid"] == "1629675"


def test_pbp_game_logs_normalize_opponent_minutes_and_pra() -> None:
    payload = {"multi_row_table_data": [{
        "Date": "2026-10-21", "Team": "MIN", "Opponent": "GS",
        "Minutes": "32:41", "Points": 20, "Rebounds": 11, "Assists": 7,
    }]}
    rows = fb._parse_game_logs(payload)
    assert rows == [{
        "game_date": "2026-10-21", "team": "MIN", "opponent": "GSW",
        "minutes": 32.68333333333333, "points": 20.0, "rebounds": 11.0,
        "assists": 7.0, "pra": 38.0,
    }]


def test_successor_fills_only_empty_history_and_preserves_verified_history() -> None:
    calls: list[tuple[str, str]] = []
    base = SimpleNamespace()
    base._norm = fb._norm
    base._text = lambda v: str(v or "").strip()
    base._health = lambda status, detail, attempted: {"status": status, "detail": detail, "attempted": attempted}

    def prior(slate_date, player_names, **kwargs):
        return {
            "verification": "PARTIAL",
            "profiles": {
                "nazreid": {"player_name": "Naz Reid", "team": "", "provider_ids": {}, "current_games": [], "prior_games": [], "data_state": "DATA_UNAVAILABLE"},
                "derrickwhite": {"player_name": "Derrick White", "team": "BOS", "provider_ids": {"basketball_reference": "whitede01"}, "current_games": [{"game_date": "2026-10-24", "opponent": "NYK", "minutes": 33.0, "points": 18.0, "rebounds": 4.0, "assists": 5.0}], "prior_games": [], "data_state": "VERIFIED"},
            },
            "provider_health": {},
        }
    base.collect_nba_pra_player_context = prior

    fb.install(base)

    identity = lambda: {"nazreid": "1629675", "derrickwhite": "1628401"}
    def history(season: str, player_id: str):
        calls.append((season, player_id))
        if player_id != "1629675":
            raise AssertionError("verified Derrick White history must not be replaced")
        if season == "2026-27":
            return {"multi_row_table_data": [{"Date":"2026-10-21","Team":"MIN","Opponent":"SAC","Minutes":"30:00","Points":17,"Rebounds":8,"Assists":3}]}
        return {"multi_row_table_data": [{"Date":"2026-04-12","Team":"MIN","Opponent":"LAL","Minutes":"29:00","Points":15,"Rebounds":7,"Assists":2}]}

    out = base.collect_nba_pra_player_context(
        date(2026, 10, 26), ["Naz Reid", "Derrick White"],
        team_codes=["MIN", "BOS"], pbp_identity_loader=identity, pbp_history_loader=history,
    )
    naz = out["profiles"]["nazreid"]
    assert naz["provider_ids"]["nba"] == "1629675"
    assert naz["current_games"][0]["opponent"] == "SAC"
    assert naz["prior_games"][0]["opponent"] == "LAL"
    assert naz["data_state"] == "VERIFIED"
    assert naz["stats_source"] == "PBP Stats"
    assert out["profiles"]["derrickwhite"]["current_games"][0]["opponent"] == "NYK"
    assert calls == [("2026-27", "1629675"), ("2025-26", "1629675")]
    assert out["provider_health"]["pbpstats_history"]["status"] == "HEALTHY"


def test_fallback_does_not_change_model_or_page1_ownership() -> None:
    source = open("nba_pra_page2_role_runtime_v4.py", encoding="utf-8").read()
    assert 'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0' in source
