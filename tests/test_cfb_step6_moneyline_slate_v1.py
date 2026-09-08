"""Regression checks for College Football Step 6 slate scanner."""
from __future__ import annotations

import cfb_moneyline_slate_v1 as slate


def test_analyze_game_runs_frozen_raw_then_final(monkeypatch):
    seen = []

    monkeypatch.setattr(
        slate.team_data,
        "load_matchup_team_data",
        lambda game, day: (
            {"away": {"team": "Away"}, "home": {"team": "Home"}},
            {"ok": True},
        ),
    )

    def fake_raw(game, away, home):
        seen.append(("raw", game["identity_key"], away["team"], home["team"]))
        return {
            "ready": True,
            "raw_probability_ready": True,
            "home_win_probability_raw": .60,
        }

    def fake_final(game, away, home, raw):
        seen.append(("final", raw["home_win_probability_raw"]))
        return {"ready": True, "winner_probability_final": .58}

    monkeypatch.setattr(slate.raw_model, "project_matchup", fake_raw)
    monkeypatch.setattr(slate.final_model, "synthesize", fake_final)

    out = slate.analyze_game.__wrapped__(
        {
            "identity_key": "ncaa:1",
            "identity_verified": True,
            "date_matches_query": True,
        },
        "2026-09-12",
    )

    assert seen == [
        ("raw", "ncaa:1", "Away", "Home"),
        ("final", .60),
    ]
    assert out["final"]["winner_probability_final"] == .58


def test_scan_slate_skips_unverified_games_and_counts_ready(monkeypatch):
    def fake_analyze(game, day):
        ready = game["identity_key"] != "ncaa:2"
        return {
            "game": game,
            "away": {},
            "home": {},
            "raw": {"ready": ready},
            "final": {"ready": ready},
            "team_diag": {},
        }

    monkeypatch.setattr(slate, "analyze_game", fake_analyze)

    games = [
        {
            "identity_key": "ncaa:1",
            "identity_verified": True,
            "date_matches_query": True,
            "kickoff_iso": "2026-09-12T12:00:00-04:00",
        },
        {
            "identity_key": "ncaa:2",
            "identity_verified": True,
            "date_matches_query": True,
            "kickoff_iso": "2026-09-12T13:00:00-04:00",
        },
        {
            "identity_key": "bad",
            "identity_verified": False,
            "date_matches_query": True,
            "kickoff_iso": "2026-09-12T14:00:00-04:00",
        },
    ]

    rows, diag = slate.scan_slate(games, "2026-09-12", workers=1)

    assert [r["game"]["identity_key"] for r in rows] == ["ncaa:1", "ncaa:2"]
    assert diag["games_requested"] == 3
    assert diag["games_analyzed"] == 2
    assert diag["games_ready"] == 1
    assert diag["games_gated"] == 1
    assert diag["market_price_used"] is False


def test_worker_count_is_hard_capped():
    assert slate.MAX_WORKERS == 2
