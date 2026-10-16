from __future__ import annotations

import importlib
import importlib.util
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GAME_KEY = "BKN@MIA:2026-10-16"


def _module():
    spec = importlib.util.find_spec("nba_spread_fair_spread_probability_v1")
    assert spec is not None, "Step-9 fair-spread / cover-probability module is missing"
    return importlib.import_module("nba_spread_fair_spread_probability_v1")


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
    }


def _history():
    rows = []
    # Identical score-derived margins from two independent providers.
    samples = {
        "BKN": [-8, -4, 2, -6, 1, -3, 4, -7],
        "MIA": [6, 4, -2, 8, 3, 5, -1, 7],
    }
    for team, margins in samples.items():
        for idx, margin in enumerate(margins, start=1):
            rows.append(
                {
                    "game_id": f"{team}-{idx}",
                    "team_tricode": team,
                    "margin": float(margin),
                    "game_date": f"2026-10-{idx:02d}",
                    "is_home": bool(idx % 2),
                }
            )
    return deepcopy(rows), deepcopy(rows)


def test_step9_owns_model_and_probability_but_not_ranking_or_pick_logic():
    mod = _module()
    assert mod.MODEL_VERSION == "NBA_SPREAD_STEP9_FAIR_SPREAD_COVER_V1"
    assert mod.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert mod.MAY_MODIFY_MODEL is True
    assert mod.MAY_MODIFY_PROJECTION is True
    assert mod.MAY_MODIFY_PROBABILITY is True
    assert mod.MAY_MODIFY_RANKING is False
    assert mod.MAY_ACTIVATE_EDGE is False
    assert mod.MAY_ACTIVATE_PICK is False


def test_fair_spread_is_independent_of_sportsbook_line():
    mod = _module()
    official, espn = _history()
    left = mod.build_fair_spread_context(
        _game(), official, espn, market_home_spread=-3.5
    )
    right = mod.build_fair_spread_context(
        _game(), official, espn, market_home_spread=-8.5
    )
    assert left["verification"] == "VERIFIED"
    assert right["verification"] == "VERIFIED"
    assert left["projected_home_margin"] == right["projected_home_margin"]
    assert left["fair_home_spread"] == right["fair_home_spread"]
    assert left["home_cover_probability"] != right["home_cover_probability"]
    assert left["sportsbook_projection_influence"] == 0.0


def test_cover_probabilities_sum_to_one_and_integer_line_keeps_push_mass():
    mod = _module()
    integer = mod.cover_probabilities(4.0, 11.0, -4.0)
    half = mod.cover_probabilities(4.0, 11.0, -4.5)
    assert abs(sum(integer.values()) - 1.0) < 1e-12
    assert integer["push"] > 0.0
    assert abs(sum(half.values()) - 1.0) < 1e-12
    assert half["push"] == 0.0


def test_source_conflict_fails_closed_instead_of_averaging_disagreement():
    mod = _module()
    official, espn = _history()
    espn[0]["margin"] = espn[0]["margin"] + 1.0
    result = mod.build_fair_spread_context(
        _game(), official, espn, market_home_spread=-4.5
    )
    assert result["verification"] == "UNAVAILABLE"
    assert result["diagnostic_state"] == "PERFORMANCE_SOURCE_CONFLICT"
    assert "projected_home_margin" not in result


def test_insufficient_history_fails_closed():
    mod = _module()
    official, espn = _history()
    official = [row for row in official if row["team_tricode"] == "MIA"][:2]
    espn = deepcopy(official)
    result = mod.build_fair_spread_context(
        _game(), official, espn, market_home_spread=-4.5
    )
    assert result["verification"] == "UNAVAILABLE"
    assert result["diagnostic_state"] == "INSUFFICIENT_VERIFIED_HISTORY"


def test_step9_live_final_history_freezes_exact_pregame_model():
    mod = _module()
    official, espn = _history()
    model = mod.build_fair_spread_context(
        _game(), official, espn, market_home_spread=-4.5
    )
    first = mod.reconcile_step9_history(
        [_game("UPCOMING")], {}, model_by_game={GAME_KEY: model}
    )
    frozen = deepcopy(first["history"][GAME_KEY]["pregame_model"])

    changed = deepcopy(model)
    changed["projected_home_margin"] = 99.0
    live = mod.reconcile_step9_history(
        [_game("LIVE")], first["history"], model_by_game={GAME_KEY: changed}
    )
    assert live["history"][GAME_KEY]["pregame_model"] == frozen
    assert live["history"][GAME_KEY]["snapshot_frozen"] is True

    final = mod.reconcile_step9_history([_game("FINAL")], live["history"])
    assert final["history"][GAME_KEY]["pregame_model"] == frozen
    assert final["history"][GAME_KEY]["phase"] == "FINAL"


def test_first_seen_live_without_step9_pregame_model_fails_closed():
    mod = _module()
    result = mod.reconcile_step9_history([_game("LIVE")], {})
    record = result["history"][GAME_KEY]
    assert record["verification"] == "UNAVAILABLE"
    assert record["diagnostic_state"] == "PREGAME_MODEL_MISSING"
    assert record["pregame_model"] is None


def test_step9_page_wrapper_preserves_step8_and_adds_fair_spread_surface():
    wrapper = ROOT / "nba_spread_page_v4.py"
    assert wrapper.exists(), "Step-9 page wrapper is missing"
    source = wrapper.read_text(encoding="utf-8")
    assert "import nba_spread_page_v3 as step8" in source
    assert "NBA_SPREAD_STEP9_FAIR_SPREAD_ACTIVE" in source
    assert "Kyre Fair Spread" in source
    assert "Cover Probability" in source
    assert 'data-testid="nba-spread-step9-fair-spread"' in source


def test_step9_router_preserves_step8_target_and_dispatches_step9_wrapper():
    router = (ROOT / "streamlit_memory_lazy_router_nba_spread_step2_activation_v1.py").read_text(encoding="utf-8")
    assert 'STEP8_ACTIVE_PAGE = "nba_spread_page_v3"' in router
    assert 'STEP9_ACTIVE_PAGE = "nba_spread_page_v4"' in router
    assert "importlib.import_module(STEP9_ACTIVE_PAGE)" in router
