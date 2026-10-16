from __future__ import annotations

import importlib
import importlib.util
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GAME_KEY = "BKN@MIA:2026-10-16"


def _module():
    spec = importlib.util.find_spec("nba_spread_live_final_v1")
    assert spec is not None, "Step-8 live/final behavior module is missing"
    return importlib.import_module("nba_spread_live_final_v1")


def _game(status: str = "UPCOMING") -> dict:
    return {
        "game_key": GAME_KEY,
        "away_tricode": "BKN",
        "away_name": "Brooklyn Nets",
        "home_tricode": "MIA",
        "home_name": "Miami Heat",
        "game_date_phoenix": "2026-10-16",
        "tip_utc": "2026-10-17T00:30:00Z",
        "tip_phoenix": "5:30 PM MST",
        "status": status,
        "venue": "Kaseya Center",
    }


def test_step8_is_state_behavior_only_and_cannot_modify_model_probability_or_ranking():
    mod = _module()
    assert mod.MODEL_VERSION == "NBA_SPREAD_STEP8_LIVE_FINAL_BEHAVIOR_V1"
    assert mod.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert mod.MAY_MODIFY_MODEL is False
    assert mod.MAY_MODIFY_PROJECTION is False
    assert mod.MAY_MODIFY_PROBABILITY is False
    assert mod.MAY_MODIFY_RANKING is False


def test_pregame_snapshot_freezes_exact_context_at_live_transition():
    mod = _module()
    upcoming = _game("UPCOMING")
    pregame_context = {
        "market": {"consensus_home_spread": -4.5},
        "injuries": {"verification": "VERIFIED", "home_out": 1},
        "sharp_money": {"side": "MIA", "gap": 8},
    }
    first = mod.reconcile_preview_history(
        [upcoming],
        {},
        context_by_game={GAME_KEY: pregame_context},
    )
    record = first["history"][GAME_KEY]
    assert record["phase"] == "PREGAME"
    assert record["snapshot_frozen"] is False
    frozen_snapshot = deepcopy(record["pregame_snapshot"])

    live = _game("LIVE")
    later_context = {"market": {"consensus_home_spread": -7.0}}
    second = mod.reconcile_preview_history(
        [live],
        first["history"],
        context_by_game={GAME_KEY: later_context},
    )
    live_record = second["history"][GAME_KEY]
    assert live_record["phase"] == "LIVE"
    assert live_record["snapshot_frozen"] is True
    assert live_record["pregame_snapshot"] == frozen_snapshot
    assert live_record["pregame_snapshot"]["context"] == pregame_context
    assert live_record["state_history"] == ["UPCOMING", "LIVE"]


def test_final_transition_keeps_same_frozen_pregame_snapshot_and_history():
    mod = _module()
    initial = mod.reconcile_preview_history(
        [_game("UPCOMING")], {}, context_by_game={GAME_KEY: {"preview": "original"}}
    )
    live = mod.reconcile_preview_history([_game("LIVE")], initial["history"])
    frozen_snapshot = deepcopy(live["history"][GAME_KEY]["pregame_snapshot"])
    final = mod.reconcile_preview_history([_game("FINAL")], live["history"])
    record = final["history"][GAME_KEY]
    assert record["phase"] == "FINAL"
    assert record["snapshot_frozen"] is True
    assert record["pregame_snapshot"] == frozen_snapshot
    assert record["state_history"] == ["UPCOMING", "LIVE", "FINAL"]


def test_stale_state_regression_cannot_rewrite_terminal_record():
    mod = _module()
    initial = mod.reconcile_preview_history([_game("UPCOMING")], {})
    live = mod.reconcile_preview_history([_game("LIVE")], initial["history"])
    final = mod.reconcile_preview_history([_game("FINAL")], live["history"])
    stale = mod.reconcile_preview_history([_game("LIVE")], final["history"])
    record = stale["history"][GAME_KEY]
    assert record["phase"] == "FINAL"
    assert record["current_status"] == "FINAL"
    assert record["diagnostic_state"] == "STALE_STATE_IGNORED"
    assert record["state_history"] == ["UPCOMING", "LIVE", "FINAL"]


def test_first_seen_live_game_fails_closed_instead_of_reconstructing_pregame_snapshot():
    mod = _module()
    result = mod.reconcile_preview_history(
        [_game("LIVE")], {}, context_by_game={GAME_KEY: {"market": "current-live-value"}}
    )
    record = result["history"][GAME_KEY]
    assert record["verification"] == "UNAVAILABLE"
    assert record["diagnostic_state"] == "PREGAME_SNAPSHOT_MISSING"
    assert record["pregame_snapshot"] is None
    assert record["snapshot_frozen"] is False
    assert result["games"][0]["step8_preview"]["verification"] == "UNAVAILABLE"


def test_history_is_retained_when_game_leaves_current_rolling_window():
    mod = _module()
    initial = mod.reconcile_preview_history([_game("UPCOMING")], {})
    final = mod.reconcile_preview_history([_game("FINAL")], initial["history"])
    retained = mod.reconcile_preview_history([], final["history"])
    assert GAME_KEY in retained["history"]
    assert retained["history"][GAME_KEY]["phase"] == "FINAL"
    assert retained["games"] == []


def test_step8_page_wrapper_preserves_step7_and_adds_preview_live_final_hooks():
    wrapper = ROOT / "nba_spread_page_v3.py"
    assert wrapper.exists(), "Step-8 wrapper page is missing"
    source = wrapper.read_text(encoding="utf-8")
    assert "import nba_spread_page_v2 as step7" in source
    assert "import nba_spread_page_v1 as page_v1" in source
    assert "NBA_SPREAD_STEP8_LIVE_FINAL_ACTIVE" in source
    assert "PREVIEW_STATE_KEY" in source
    assert "_load_verified_schedule" in source
    assert "_game_card" in source
    assert 'data-testid="nba-spread-step8-preview"' in source


def test_step8_router_preserves_step7_target_and_dispatches_step8_wrapper():
    router = (ROOT / "streamlit_memory_lazy_router_nba_spread_step2_activation_v1.py").read_text(encoding="utf-8")
    assert 'STEP7_ACTIVE_PAGE = "nba_spread_page_v2"' in router
    assert 'STEP8_ACTIVE_PAGE = "nba_spread_page_v3"' in router
    assert "importlib.import_module(STEP8_ACTIVE_PAGE)" in router
