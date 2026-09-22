"""Regression checks for College Football Step 9 Over/Under Slate V1."""
from __future__ import annotations

import cfb_over_under_slate_v1 as slate


def _game(identity, away="Away", home="Home"):
    return {
        "identity_key": identity,
        "game_id": identity,
        "identity_verified": True,
        "date_matches_query": True,
        "away_team": away,
        "home_team": home,
        "kickoff_iso": f"2026-09-12T1{identity[-1]}:00:00-04:00",
    }


def test_scan_slate_requires_explicit_per_game_lines(monkeypatch):
    seen = []

    def fake_analyze(game, as_of_day, analysis_line):
        seen.append((game["identity_key"], as_of_day, analysis_line))
        return {
            "game": dict(game),
            "raw": {"ready": True},
            "final": {"ready": True, "rank_eligible": True},
        }

    monkeypatch.setattr(slate, "analyze_game", fake_analyze)

    games = [_game("g1"), _game("g2"), _game("g3")]
    rows, diag = slate.scan_slate(
        games,
        "2026-09-12",
        {"g1": 50.5, "g3": 57.0},
        workers=1,
    )

    assert len(rows) == 2
    assert sorted(seen) == [
        ("g1", "2026-09-12", 50.5),
        ("g3", "2026-09-12", 57.0),
    ]
    assert diag["games_with_lines"] == 2
    assert diag["skipped_missing_line"] == 1
    assert diag["analysis_line_projection_weight"] == 0.0
    assert diag["sportsbook_input_used"] is False
    assert diag["market_price_used"] is False
    assert diag["edge_or_ev_used"] is False
    assert diag["monte_carlo_used"] is False


def test_unverified_game_is_not_submitted(monkeypatch):
    seen = []

    def fake_analyze(game, as_of_day, analysis_line):
        seen.append(game["identity_key"])
        return {"game": dict(game), "raw": {"ready": True}, "final": {"ready": True}}

    monkeypatch.setattr(slate, "analyze_game", fake_analyze)

    good = _game("g1")
    bad = _game("g2")
    bad["identity_verified"] = False

    rows, diag = slate.scan_slate(
        [good, bad],
        "2026-09-12",
        {"g1": 50.5, "g2": 51.5},
        workers=1,
    )

    assert seen == ["g1"]
    assert len(rows) == 1
    assert diag["games_with_lines"] == 1


def test_scan_diagnostics_count_ready_gated_and_qualified(monkeypatch):
    def fake_analyze(game, as_of_day, analysis_line):
        identity = game["identity_key"]
        if identity == "g1":
            final = {"ready": True, "rank_eligible": True}
            raw = {"ready": True}
        elif identity == "g2":
            final = {"ready": True, "rank_eligible": False}
            raw = {"ready": True}
        else:
            final = {"ready": False, "rank_eligible": False}
            raw = {"ready": False}
        return {"game": dict(game), "raw": raw, "final": final}

    monkeypatch.setattr(slate, "analyze_game", fake_analyze)

    games = [_game("g1"), _game("g2"), _game("g3")]
    rows, diag = slate.scan_slate(
        games,
        "2026-09-12",
        {"g1": 50.5, "g2": 51.5, "g3": 52.5},
        workers=1,
    )

    assert len(rows) == 3
    assert diag["raw_ready"] == 2
    assert diag["final_ready"] == 2
    assert diag["qualified_plays"] == 1
    assert diag["games_gated"] == 1
