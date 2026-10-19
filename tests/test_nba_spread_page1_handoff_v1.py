from __future__ import annotations

import importlib
import importlib.util


def _handoff():
    spec = importlib.util.find_spec("nba_spread_page1_handoff_v1")
    assert spec is not None, "nba_spread_page1_handoff_v1 must exist"
    return importlib.import_module("nba_spread_page1_handoff_v1")


def _teams():
    spec = importlib.util.find_spec("nba_spread_team_identity_v1")
    assert spec is not None, "nba_spread_team_identity_v1 must exist"
    return importlib.import_module("nba_spread_team_identity_v1")


def _game(away, home):
    return {
        "game_key": f"{away}@{home}:2026-10-20",
        "game_date_phoenix": "2026-10-20",
        "away_tricode": away,
        "home_tricode": home,
    }


def test_exact_team_logos_resolve_only_for_canonical_nba_tricodes():
    mod = _teams()
    for code in ("BOS", "DET", "PHI", "NYK", "OKC", "SAS"):
        value = mod.resolve_nba_team_logo(code)
        assert isinstance(value, str) and value.startswith("https://") and code.lower() in value.lower()
    assert mod.resolve_nba_team_logo("XYZ") is None
    assert mod.resolve_nba_team_logo("Boston Celtics") is None


def test_build_analysis_params_requires_exact_date_and_game_key():
    mod = _handoff()
    assert mod.build_analysis_params(_game("BOS", "DET")) == {
        "date": "2026-10-20",
        "game_id": "BOS@DET:2026-10-20",
    }
    assert mod.build_analysis_params({"game_date_phoenix": "2026-10-20"}) == {}
    assert mod.build_analysis_params({"game_key": "BOS@DET:2026-10-20"}) == {}


def test_repeated_analysis_handoffs_latest_exact_game_wins_and_clears_player_identity():
    mod = _handoff()
    session = {"sport": "nfl", "market": "passing-yards", "game_id": "old", "player_id": "qb1"}
    query = {"sport": "nfl", "market": "passing-yards", "game_id": "old", "player_id": "qb1"}

    for away, home in (("BOS", "DET"), ("PHI", "NYK"), ("OKC", "SAS")):
        returned = mod.apply_analysis_handoff(session, query, _game(away, home))
        expected = f"{away}@{home}:2026-10-20"
        assert returned == {"sport": "nba", "market": "spread", "date": "2026-10-20", "game_id": expected}
        assert query["sport"] == "nba" and query["market"] == "spread"
        assert query["game_id"] == expected and query["date"] == "2026-10-20"
        assert session["game_id"] == expected and session["date"] == "2026-10-20"
        assert "player_id" not in query and "player_id" not in session
