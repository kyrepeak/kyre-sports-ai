from __future__ import annotations

import inspect

from cfb_player_props_identity_v1 import CanonicalPlayerIdentity
from cfb_player_props_market_v1 import PropObservation
from cfb_player_props_page2_roster_v1 import Page2Player
import cfb_player_props_model_v1 as frozen_model


def _player(pid="p1", team="101", pos="QB"):
    return Page2Player(CanonicalPlayerIdentity(pid, team, "Player One", pos, "Away State", "AWY"))


def _history(n=8, market="passing_yards"):
    return [
        {
            "event_id": f"g{i}", "completed": True, "source": "ESPN CFB athlete gamelog",
            "market_key": market, "value": float(200 + i * 10), "game_date": f"2026-10-{20-i:02d}",
        }
        for i in range(n)
    ]


def _obs(side="over", price=-110):
    return PropObservation(
        "401999001", "p1", "Player One", "101", "passing_yards", "FanDuel", side,
        235.5, price, "2026-10-20T04:00:00Z", "SportsGameOdds", "evt", "p1", f"odd-{side}", True,
    )


def _context():
    return {
        "state": "ready", "official_game_id": "401999001", "game_date": "2026-10-24",
        "slate_date": "2026-10-24", "away_team_id": "101", "away_team": "Away State",
        "home_team_id": "202", "home_team": "Home Tech",
        "game": {
            "official_game_id": "401999001", "game_date": "2026-10-24",
            "away_team_id": "101", "away_team": "Away State",
            "home_team_id": "202", "home_team": "Home Tech",
        },
    }


def test_recent_production_caps_at_frozen_eight_and_exposes_last_three(monkeypatch):
    import cfb_player_props_page2_matchup_v1 as matchup

    rows = _history(10)
    monkeypatch.setattr(matchup.history_owner, "load_verified_player_history", lambda player, market, season: rows)
    out = matchup.build_recent_production(_player(), "passing_yards", season=2026)
    assert out["sample_count"] == 8
    assert out["values"] == tuple(row["value"] for row in rows[:8])
    assert out["last3"] == tuple(row["value"] for row in rows[:3])
    assert out["season_average"] == sum(row["value"] for row in rows[:8]) / 8


def test_zero_to_three_verified_games_never_publish_probability():
    import cfb_player_props_page2_matchup_v1 as matchup

    player = _player()
    signal = matchup.build_page2_signal(player, "passing_yards", _history(3), [_obs("over"), _obs("under")])
    assert signal["model_ready"] is False
    assert signal["model_probability"] is None
    assert signal["sportsbook_projection_influence"] == 0.0


def test_page2_signal_is_exact_frozen_model_delegation():
    import cfb_player_props_page2_matchup_v1 as matchup

    player = _player()
    history = _history(8)
    observations = [_obs("over", -115), _obs("under", -105)]
    direct = frozen_model.build_page1_signal(player.identity, "passing_yards", history, observations)
    page2 = matchup.build_page2_signal(player, "passing_yards", history, observations)
    for key in ("projection", "uncertainty", "sample_count", "consensus_line", "side", "model_probability", "market_probability", "edge", "book_count", "sportsbook_projection_influence"):
        assert page2[key] == direct[key]


def test_matchup_context_reuses_team_data_and_engine_without_applying_to_model(monkeypatch):
    import cfb_player_props_page2_matchup_v1 as matchup

    calls = []
    profiles = {"away": {"team": "Away State"}, "home": {"team": "Home Tech"}}
    monkeypatch.setattr(matchup.team_data, "load_matchup_team_data", lambda game, day: calls.append((game["official_game_id"], day)) or (profiles, {"ok": True}))
    monkeypatch.setattr(matchup.matchup_engine, "build_matchup_engine", lambda game, away, home: {"model_ready": True, "away_offense": {}, "home_offense": {}})
    out = matchup.load_game_matchup_context(_context())
    assert calls == [("401999001", "2026-10-24")]
    assert out["engine"]["model_ready"] is True
    assert "apply_to_raw" not in inspect.getsource(matchup.load_game_matchup_context)


def test_verified_defensive_dimension_reduces_to_favorable_neutral_tough_or_check():
    import cfb_player_props_page2_matchup_v1 as matchup

    context = _context()
    base = {
        "context": context,
        "engine": {
            "away_offense": {"dimensions": {
                "passing": {"ready": True, "edge": 0.25, "defense_rank": 92, "defense_value": "280.0"},
                "rushing": {"ready": True, "edge": -0.30, "defense_rank": 8, "defense_value": "88.0"},
                "red_zone": {"ready": False, "edge": None, "defense_rank": None},
            }},
            "home_offense": {"dimensions": {}},
        },
    }
    assert matchup.grade_player_matchup(_player(pos="QB"), "passing_yards", base)["label"] == "FAVORABLE"
    assert matchup.grade_player_matchup(_player(pos="RB"), "rushing_yards", base)["label"] == "TOUGH"
    assert matchup.grade_player_matchup(_player(pos="RB"), "touchdowns", base)["label"] == "CHECK"
    unavailable = matchup.grade_player_matchup(_player("other", "999", "QB"), "passing_yards", base)
    assert unavailable["label"] == "CHECK"
    assert unavailable["message"] == "Defense data unavailable"
