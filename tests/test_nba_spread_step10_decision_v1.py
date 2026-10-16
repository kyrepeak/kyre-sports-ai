from __future__ import annotations

import importlib
import importlib.util
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GAME_KEY = "BKN@MIA:2026-10-16"


def _module():
    spec = importlib.util.find_spec("nba_spread_decision_v1")
    assert spec is not None, "Step-10 decision module is missing"
    return importlib.import_module("nba_spread_decision_v1")


def _step9_record(*, status: str = "UPCOMING", home_cover: float = 0.62, away_cover: float = 0.34, push: float = 0.04, market_home: float = -3.0, fair_home: float = -5.5) -> dict:
    model = {
        "verification": "VERIFIED",
        "cover_verification": "VERIFIED",
        "game_key": GAME_KEY,
        "away_tricode": "BKN",
        "home_tricode": "MIA",
        "projected_home_margin": -fair_home,
        "fair_home_spread": fair_home,
        "fair_away_spread": -fair_home,
        "market_home_spread": market_home,
        "market_away_spread": -market_home,
        "home_cover_probability": home_cover,
        "away_cover_probability": away_cover,
        "push_probability": push,
        "sportsbook_projection_influence": 0.0,
    }
    phase = "PREGAME" if status in {"UPCOMING", "DELAYED"} else status
    return {
        "game_key": GAME_KEY,
        "verification": "VERIFIED",
        "diagnostic_state": "PREGAME_MODEL_CAPTURED" if phase == "PREGAME" else "PREGAME_MODEL_FROZEN_LIVE",
        "phase": phase,
        "current_status": status,
        "snapshot_frozen": phase != "PREGAME",
        "pregame_model": model,
    }


def test_step10_owns_decision_ranking_and_pick_but_not_step9_model_math():
    mod = _module()
    assert mod.MODEL_VERSION == "NBA_SPREAD_STEP10_DECISION_V1"
    assert mod.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert mod.MAY_MODIFY_MODEL is False
    assert mod.MAY_MODIFY_PROJECTION is False
    assert mod.MAY_MODIFY_PROBABILITY is False
    assert mod.MAY_MODIFY_RANKING is True
    assert mod.MAY_ACTIVATE_EDGE is True
    assert mod.MAY_ACTIVATE_PICK is True


def test_verified_step9_record_yields_home_pick_and_no_push_edge():
    mod = _module()
    result = mod.build_decision_from_step9(_step9_record())
    assert result["verification"] == "VERIFIED"
    assert result["decision_state"] == "PLAY"
    assert result["selected_side"] == "HOME"
    assert result["selected_team"] == "MIA"
    assert result["selected_market_spread"] == -3.0
    assert result["selected_cover_probability"] == 0.62
    assert abs(result["selected_cover_probability_no_push"] - (0.62 / 0.96)) < 1e-12
    assert result["cover_edge_pp"] > 0.0
    assert result["spread_edge_points"] == 2.5
    assert result["pick_text"] == "MIA -3.0"


def test_decision_is_symmetric_and_chooses_away_when_away_probability_is_higher():
    mod = _module()
    result = mod.build_decision_from_step9(
        _step9_record(home_cover=0.37, away_cover=0.63, push=0.0, market_home=-4.5, fair_home=-2.0)
    )
    assert result["decision_state"] == "PLAY"
    assert result["selected_side"] == "AWAY"
    assert result["selected_team"] == "BKN"
    assert result["selected_market_spread"] == 4.5
    assert result["pick_text"] == "BKN +4.5"


def test_missing_or_unverified_step9_inputs_fail_closed_to_no_play():
    mod = _module()
    missing = mod.build_decision_from_step9({"verification": "UNAVAILABLE", "pregame_model": None})
    assert missing["verification"] == "UNAVAILABLE"
    assert missing["decision_state"] == "NO_PLAY"
    assert missing["pick_strength"] == "NO PLAY"

    bad = _step9_record()
    bad["pregame_model"]["cover_verification"] = "UNAVAILABLE"
    result = mod.build_decision_from_step9(bad)
    assert result["verification"] == "UNAVAILABLE"
    assert result["decision_state"] == "NO_PLAY"


def test_tie_or_subthreshold_edge_is_no_play():
    mod = _module()
    tie = mod.build_decision_from_step9(_step9_record(home_cover=0.50, away_cover=0.50, push=0.0, market_home=-3.0, fair_home=-3.0))
    assert tie["decision_state"] == "NO_PLAY"
    assert tie["diagnostic_state"] == "NO_MEANINGFUL_EDGE"

    tiny = mod.build_decision_from_step9(_step9_record(home_cover=0.509, away_cover=0.491, push=0.0, market_home=-3.0, fair_home=-3.2))
    assert tiny["decision_state"] == "NO_PLAY"
    assert tiny["pick_strength"] == "NO PLAY"


def test_strength_thresholds_are_deterministic():
    mod = _module()
    assert mod.pick_strength_for_edge(1.99) == ("NO PLAY", "WATCH")
    assert mod.pick_strength_for_edge(2.0) == ("LEAN", "C")
    assert mod.pick_strength_for_edge(4.0) == ("MEDIUM", "B")
    assert mod.pick_strength_for_edge(7.0) == ("STRONG", "A-")
    assert mod.pick_strength_for_edge(10.0) == ("ELITE", "A")


def test_slate_ranking_orders_only_playable_verified_decisions_and_is_stable():
    mod = _module()
    games = [
        {"game_key": "A@B:1", "step9_fair_spread": _step9_record(home_cover=0.58, away_cover=0.42, push=0.0)},
        {"game_key": "C@D:1", "step9_fair_spread": _step9_record(home_cover=0.66, away_cover=0.34, push=0.0)},
        {"game_key": "E@F:1", "step9_fair_spread": _step9_record(home_cover=0.505, away_cover=0.495, push=0.0)},
    ]
    games[0]["step9_fair_spread"]["game_key"] = "A@B:1"
    games[0]["step9_fair_spread"]["pregame_model"]["game_key"] = "A@B:1"
    games[1]["step9_fair_spread"]["game_key"] = "C@D:1"
    games[1]["step9_fair_spread"]["pregame_model"]["game_key"] = "C@D:1"
    games[2]["step9_fair_spread"]["game_key"] = "E@F:1"
    games[2]["step9_fair_spread"]["pregame_model"]["game_key"] = "E@F:1"
    result = mod.decorate_and_rank_games(games)
    ranked = [g["step10_decision"] for g in result["games"] if g["step10_decision"]["slate_rank"] is not None]
    assert [row["slate_rank"] for row in ranked] == [2, 1]
    top = [row for row in ranked if row["slate_rank"] == 1][0]
    assert top["top_pick"] is True
    no_play = result["games"][2]["step10_decision"]
    assert no_play["decision_state"] == "NO_PLAY"
    assert no_play["slate_rank"] is None


def test_live_final_uses_exact_frozen_step9_pregame_inputs():
    mod = _module()
    pre = _step9_record(status="UPCOMING")
    live = deepcopy(pre)
    live.update({"phase": "LIVE", "current_status": "LIVE", "snapshot_frozen": True, "diagnostic_state": "PREGAME_MODEL_FROZEN_LIVE"})
    final = deepcopy(live)
    final.update({"phase": "FINAL", "current_status": "FINAL", "diagnostic_state": "PREGAME_MODEL_RETAINED_FINAL"})
    a = mod.build_decision_from_step9(pre)
    b = mod.build_decision_from_step9(live)
    c = mod.build_decision_from_step9(final)
    frozen_fields = ["selected_side", "selected_team", "selected_market_spread", "selected_cover_probability_no_push", "cover_edge_pp", "spread_edge_points", "pick_strength", "production_grade", "pick_text", "ranking_score"]
    assert {k: a[k] for k in frozen_fields} == {k: b[k] for k in frozen_fields} == {k: c[k] for k in frozen_fields}
    assert b["snapshot_frozen"] is True
    assert c["phase"] == "FINAL"


def test_step10_page_wrapper_preserves_step9_and_adds_decision_surface():
    wrapper = ROOT / "nba_spread_page_v5.py"
    assert wrapper.exists(), "Step-10 page wrapper is missing"
    source = wrapper.read_text(encoding="utf-8")
    assert "import nba_spread_page_v4 as step9" in source
    assert "NBA_SPREAD_STEP10_DECISION_ACTIVE" in source
    assert "Pick Strength" in source
    assert "Cover Edge" in source
    assert 'data-testid="nba-spread-step10-decision"' in source


def test_step10_router_preserves_step9_target_and_dispatches_step10_wrapper():
    router = (ROOT / "streamlit_memory_lazy_router_nba_spread_step2_activation_v1.py").read_text(encoding="utf-8")
    assert 'STEP9_ACTIVE_PAGE = "nba_spread_page_v4"' in router
    assert 'STEP10_ACTIVE_PAGE = "nba_spread_page_v5"' in router
    assert "importlib.import_module(STEP10_ACTIVE_PAGE)" in router
