"""Regression checks for College Football Step 12 Game Total Slate V1."""
from __future__ import annotations

import cfb_game_total_slate_v1 as slate


def _game(identity, verified=True):
    return {
        "identity_key": identity,
        "game_id": identity,
        "identity_verified": verified,
        "date_matches_query": True,
        "away_team": "Away",
        "home_team": "Home",
        "kickoff_iso": "2026-09-12T12:00:00-04:00",
    }


def test_scan_slate_analyzes_only_verified_games(monkeypatch):
    seen = []

    def fake_analyze(game, day):
        seen.append((game["identity_key"], day))
        return {
            "game": dict(game),
            "raw": {"ready": True},
            "final": {"ready": True, "rank_eligible": True},
        }

    monkeypatch.setattr(slate, "analyze_game", fake_analyze)

    rows, diag = slate.scan_slate(
        [_game("g1"), _game("g2", verified=False), _game("g3")],
        "2026-09-12",
        workers=1,
    )

    assert [x[0] for x in seen] == ["g1", "g3"]
    assert len(rows) == 2
    assert diag["games_analyzed"] == 2
    assert diag["qualified_forecasts"] == 2
    assert diag["sportsbook_input_used"] is False
    assert diag["market_probability_used"] is False
    assert diag["edge_or_ev_used"] is False
    assert diag["monte_carlo_used"] is False


def test_scan_diagnostics_count_gated_and_qualified(monkeypatch):
    def fake_analyze(game, day):
        ident = game["identity_key"]
        if ident == "a":
            return {"game": dict(game), "raw": {"ready": True}, "final": {"ready": True, "rank_eligible": True}}
        if ident == "b":
            return {"game": dict(game), "raw": {"ready": True}, "final": {"ready": True, "rank_eligible": False}}
        return {"game": dict(game), "raw": {"ready": False}, "final": {"ready": False, "rank_eligible": False}}

    monkeypatch.setattr(slate, "analyze_game", fake_analyze)

    rows, diag = slate.scan_slate(
        [_game("a"), _game("b"), _game("c")],
        "2026-09-12",
        workers=1,
    )

    assert len(rows) == 3
    assert diag["raw_ready"] == 2
    assert diag["final_ready"] == 2
    assert diag["qualified_forecasts"] == 1
    assert diag["games_gated"] == 1
