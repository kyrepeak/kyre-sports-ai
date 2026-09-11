"""Regression tests for CFB O/U performance Step 3 cache stability."""
from __future__ import annotations

from pathlib import Path

import cfb_over_under_clean_page_v33 as page
import cfb_over_under_slate_v16_cache_stable as runtime
import streamlit_memory_lazy_router_v74 as router


def _game() -> dict:
    return {
        "identity_key": "2026-09-12:401864571",
        "game_id": "401864571",
        "espn_event_id": "401864571",
        "game_date": "2026-09-12",
        "away_team": "App State",
        "home_team": "East Carolina",
        "venue": "Dowdy-Ficklen Stadium",
        "broadcast": "ESPNU",
        "market_line_available": True,
        "market_identity_verified": True,
        "market_total": 56.5,
        "market_sportsbook": "FanDuel",
        "market_status": "active",
        "market_updated_at_utc": "2026-09-11T17:00:00Z",
        "market_captured_at_utc": "2026-09-11T17:00:01Z",
        "market_projection_weight": 0.0,
        "market_context_only": True,
        "market_may_modify_projection": False,
    }


def test_cache_stable_game_removes_only_market_context():
    game = _game()
    stable = runtime.cache_stable_game(game)

    assert stable["identity_key"] == game["identity_key"]
    assert stable["espn_event_id"] == "401864571"
    assert stable["venue"] == "Dowdy-Ficklen Stadium"
    assert stable["broadcast"] == "ESPNU"
    assert not any(key.startswith("market_") for key in stable)


def test_analyze_game_uses_stable_cache_input_and_restores_latest_market(monkeypatch):
    seen = {}

    monkeypatch.setattr(
        runtime.prior,
        "hydrate_game_identity",
        lambda game, day: (dict(game), {"matched": True}),
    )

    def fake_analyze(game, day, line):
        seen["game"] = dict(game)
        seen["day"] = day
        seen["line"] = line
        return {
            "game": dict(game),
            "raw": {"projected_total": 52.25},
            "final": {"selection": "UNDER"},
        }

    monkeypatch.setattr(runtime.frozen, "analyze_game", fake_analyze)

    game = _game()
    result = runtime.analyze_game(game, "2026-09-12", 56.5)

    assert not any(key.startswith("market_") for key in seen["game"])
    assert seen["game"]["espn_event_id"] == "401864571"
    assert seen["line"] == 56.5
    assert result["raw"]["projected_total"] == 52.25
    assert result["game"]["market_total"] == 56.5
    assert result["game"]["market_sportsbook"] == "FanDuel"
    assert result["game"]["market_updated_at_utc"] == "2026-09-11T17:00:00Z"
    assert result["sportsbook_projection_weight"] == 0.0


def test_market_timestamp_churn_does_not_change_stable_analysis_mapping():
    first = _game()
    second = _game()
    second["market_updated_at_utc"] = "2026-09-11T17:01:00Z"
    second["market_captured_at_utc"] = "2026-09-11T17:01:01Z"
    second["market_status"] = "updated"

    assert runtime.cache_stable_game(first) == runtime.cache_stable_game(second)


def test_market_line_stays_explicit_analysis_threshold_not_game_cache_input():
    first = _game()
    second = _game()
    second["market_total"] = 57.0

    # Market data remains display/context only in the mapping. A line move is
    # represented by the separate analyze_game analysis_line argument.
    assert runtime.cache_stable_game(first) == runtime.cache_stable_game(second)
    assert runtime.MARKET_PROJECTION_WEIGHT == 0.0


def test_scan_slate_sanitizes_frozen_inputs_and_restores_market(monkeypatch):
    monkeypatch.setattr(
        runtime.prior,
        "hydrate_game_identity",
        lambda game, day: (dict(game), {"matched": True}),
    )
    seen = {}

    def fake_scan(games, day, analysis_lines, workers=2):
        seen["games"] = [dict(game) for game in games]
        seen["lines"] = dict(analysis_lines)
        return ([{"game": dict(games[0]), "analysis_line": 56.5}], {"games_analyzed": 1})

    monkeypatch.setattr(runtime.frozen, "scan_slate", fake_scan)

    rows, diag = runtime.scan_slate(
        [_game()],
        "2026-09-12",
        {"2026-09-12:401864571": 56.5},
    )

    assert not any(key.startswith("market_") for key in seen["games"][0])
    assert rows[0]["game"]["market_total"] == 56.5
    assert diag["cache_stable_market_metadata"] is True
    assert diag["sportsbook_projection_weight"] == 0.0
    assert diag["projection_math"] == "frozen_v14_unchanged"


def test_clean_page_v33_keeps_profiler_and_activates_v16_runtime():
    assert page.ACTIVE_RUNTIME_SLATE == "cfb_over_under_slate_v16_cache_stable"
    assert page.ACTIVE_PERFORMANCE_PROFILER == "cfb_over_under_performance_profiler_v1"
    assert page._PAGE_PROXY.runtime_slate._base is runtime
    assert "0.0% SPORTSBOOK PROJECTION INFLUENCE" in page._V33_MARKER
    assert "FROZEN V14 PROJECTION MATH PRESERVED" in page._V33_MARKER


def test_router_v74_targets_v33_only_for_direct_cfb_ou():
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v73"
    assert router.ACTIVE_PAGE == "cfb_over_under_clean_page_v33"
    assert router.OVER_UNDER_MARKET == "Over/Under"


def test_app_entrypoint_advances_to_v74_and_retains_v73_guard():
    text = Path("app.py").read_text(encoding="utf-8")
    assert "from streamlit_memory_lazy_router_v73 import render_app as _frozen_v73_render_app" in text
    assert "from streamlit_memory_lazy_router_v74 import render_app" in text
    assert (
        'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V74_CFB_OU_CACHE_STABLE_ANALYSIS_2026-09-11"'
        in text
    )
    assert "0.0% sportsbook projection influence" in text
