from __future__ import annotations

import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _snapshot() -> dict:
    return {
        "slate_date": "2026-10-26",
        "games": [
            {
                "away_tricode": "BKN",
                "home_tricode": "BOS",
                "start_time_utc": "2026-10-26T23:30:00Z",
            }
        ],
        "market": {},
        "profiles": {
            "derrickwhite": {
                "player_name": "Derrick White",
                "team": "BOS",
                "position": "SG",
                "usage_pct": 18.7,
                "usage_rank": 5,
                "usage_team_size": 15,
                "usage_source": "Basketball-Reference Advanced",
                "usage_period": "2026-27 REGULAR SEASON",
                "current_games": [
                    {"date": "2026-10-24", "opponent": "NY", "minutes": 36.0, "points": 18, "rebounds": 4, "assists": 8},
                    {"date": "2026-10-23", "opponent": "DET", "minutes": 34.0, "points": 16, "rebounds": 3, "assists": 7},
                ],
                "prior_games": [],
            }
        },
        "injury_players": {
            "derrickwhite": {
                "player_name": "Derrick White",
                "team": "BOS",
                "status": "NO OFFICIAL INJURY DESIGNATION",
            },
            "devincarter": {
                "player_name": "Devin Carter",
                "team": "BOS",
                "status": "OUT",
                "reason": "Illness",
            },
        },
        "sources": {
            "injuries": {
                "verification": "VERIFIED",
                "source": "NBA Official Injury Report",
            }
        },
    }


def test_history_only_context_keeps_verified_player_game_and_opponent() -> None:
    mod = importlib.import_module("nba_pra_page2_history_only_runtime_v1")
    context = mod.build_history_only_context(
        _snapshot(),
        "derrickwhite",
        {"player_key": "derrickwhite", "player_name": "Derrick White", "team": "BOS", "quote": {"line": None}},
    )
    assert context["state"] == "history_only"
    assert context["team"] == "BOS"
    assert context["opponent"] == "BKN"
    assert context["quotes"] == []
    assert context["selected_quote"] == {}
    assert context["player"]["player_name"] == "Derrick White"


def test_history_only_page_renders_deep_context_without_inventing_line() -> None:
    mod = importlib.import_module("nba_pra_page2_history_only_runtime_v1")
    context = mod.build_history_only_context(
        _snapshot(),
        "derrickwhite",
        {"player_key": "derrickwhite", "player_name": "Derrick White", "team": "BOS", "quote": {"line": None}},
    )
    html = mod.build_history_only_page_html(context, matchup={})
    assert "PLAYER COMMAND CENTER" in html
    assert "ROLE & AVAILABILITY" in html
    assert "FULL GAME LOG" in html
    assert "No verified sportsbook quote is currently available" in html
    assert "PASS / LINE NOT VERIFIED" in html
    assert "Derrick White" in html
    assert "NY" in html and "DET" in html
    assert "16.5" not in html


def test_history_only_mode_is_only_for_same_player_missing_line_handoff() -> None:
    mod = importlib.import_module("nba_pra_page2_history_only_runtime_v1")
    assert mod.should_render_history_only("derrickwhite", {"player_key": "derrickwhite", "quote": {"line": None}}) is True
    assert mod.should_render_history_only("derrickwhite", {"player_key": "derrickwhite", "quote": {"line": 16.5, "sportsbook": "FanDuel"}}) is False
    assert mod.should_render_history_only("derrickwhite", {"player_key": "someoneelse", "quote": {"line": None}}) is False


def test_overlay_installs_additively_without_editing_frozen_sync() -> None:
    mod = importlib.import_module("nba_pra_page2_history_only_runtime_v1")
    runtime = importlib.import_module("nba_pra_runtime_v2")
    original = runtime.render_nba_pra_runtime_v2
    mod.install()
    try:
        assert runtime.render_nba_pra_runtime_v2 is mod.render_nba_pra_runtime_history_overlay
    finally:
        runtime.render_nba_pra_runtime_v2 = original

    frozen_sync = (ROOT / "nba_pra_page2_sync_v1.py").read_text(encoding="utf-8")
    assert "Selected player or PRA market is no longer available" in frozen_sync


def test_app_installs_history_only_overlay_before_render() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    import_text = "from nba_pra_page2_history_only_runtime_v1 import install as install_nba_pra_page2_history_only_runtime_v1"
    call_text = "install_nba_pra_page2_history_only_runtime_v1()"
    assert import_text in source
    assert call_text in source
    assert source.index(import_text) < source.index(call_text) < source.index("render_app()")


def test_sportsbook_influence_remains_zero_and_no_disallowed_sources() -> None:
    source = (ROOT / "nba_pra_page2_history_only_runtime_v1.py").read_text(encoding="utf-8")
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    lowered = source.lower()
    assert "sgo" not in lowered
    assert "espn" not in lowered
    assert "espn bet" not in lowered
