from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "nfl_game_totals_hub_v8.py"
HELPER = ROOT / "sports_api" / "nfl_game_totals_total_projection_v1.py"
ROUTER = ROOT / "nfl_hub_v18.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _load_helper():
    if not HELPER.exists():
        pytest.fail("Step 8 total-projection helper has not been implemented yet")
    spec = importlib.util.spec_from_file_location("step8_projection", HELPER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sample_contexts():
    scoring = {
        "ready": True,
        "away": {"offense_ppg": 27.0, "opponent_defense_papg": 24.0},
        "home": {"offense_ppg": 24.0, "opponent_defense_papg": 23.0},
    }
    pace = {"ready": True, "matchup": {"average_plays_per_game": 68.0}}
    explosive = {"ready": True, "matchup": {"average_explosive_plays_per_game": 4.5}}
    sustainability = {
        "ready": True,
        "matchup": {
            "average_red_zone_td_pct": 62.0,
            "average_third_down_conv_pct": 46.0,
            "average_first_downs_per_game": 23.5,
        },
    }
    environment = {
        "ready": True,
        "indoor": False,
        "weather_pressure": "HIGH",
        "temperature": 31.0,
        "precipitation": 10.0,
        "gust": 27.0,
    }
    return scoring, pace, explosive, sustainability, environment


def test_step8_runtime_files_exist_and_build_state_advances():
    assert PAGE.exists(), "Step 8 page module has not been implemented yet"
    assert HELPER.exists(), "Step 8 total-projection helper has not been implemented yet"
    source = _read(PAGE)
    assert 'PAGE_BUILD_STEP = 8' in source
    assert 'PAGE_BUILD_TOTAL = 10' in source
    assert 'PROJECTION_MODEL_ENABLED = True' in source
    assert 'TOTAL_PROJECTION_ENABLED = True' in source
    assert 'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0' in source


def test_projection_helper_has_no_market_or_sportsbook_input():
    module = _load_helper()
    signature = inspect.signature(module.build_total_projection)
    assert list(signature.parameters) == [
        "scoring_context",
        "pace_context",
        "explosive_context",
        "red_zone_drive_context",
        "environment_context",
    ]
    forbidden = {"market", "line", "snapshot", "fanduel", "sportsbook", "odds"}
    assert not any(any(token in name.lower() for token in forbidden) for name in signature.parameters)
    assert module.SPORTSBOOK_PROJECTION_WEIGHT == 0.0


def test_projection_recipe_is_deterministic_and_auditable():
    module = _load_helper()
    result = module.build_total_projection(*_sample_contexts())
    assert result["ready"] is True
    assert result["baseline_total"] == pytest.approx(49.0)
    assert result["adjustments"]["pace"] == pytest.approx(1.4)
    assert result["adjustments"]["explosive"] == pytest.approx(1.125)
    assert result["adjustments"]["sustainability"] == pytest.approx(1.58)
    assert result["adjustments"]["environment"] == pytest.approx(-2.5)
    assert result["projected_total"] == pytest.approx(50.6)
    assert result["sportsbook_projection_weight"] == 0.0
    assert result["market_comparison_enabled"] is False


def test_projection_fails_closed_when_any_certified_context_is_missing():
    module = _load_helper()
    contexts = list(_sample_contexts())
    contexts[4] = {"ready": False, "diagnostics": ["weather unavailable"]}
    result = module.build_total_projection(*contexts)
    assert result["ready"] is False
    assert result["projected_total"] is None
    assert result["market_comparison_enabled"] is False
    assert result["sportsbook_projection_weight"] == 0.0


def test_indoor_environment_is_neutral_not_weather_penalized():
    module = _load_helper()
    contexts = list(_sample_contexts())
    contexts[4] = {
        "ready": True,
        "indoor": True,
        "weather_pressure": "INDOOR",
        "temperature": 10.0,
        "precipitation": 100.0,
        "gust": 50.0,
    }
    result = module.build_total_projection(*contexts)
    assert result["ready"] is True
    assert result["adjustments"]["environment"] == 0.0


def test_step8_same_matchup_card_grows_downward_from_v7():
    source = _read(PAGE)
    assert "import nfl_game_totals_hub_v7 as v7" in source
    assert "v7._game_card(" in source
    assert "_projection_html(" in source
    assert "build_total_projection(" in source
    assert "STEP 8" in source
    assert "TOTAL PROJECTION" in source


def test_step8_progress_preserves_steps_1_through_8_and_leaves_9_10_off():
    source = _read(PAGE)
    for number, label in (
        ("1", "VERIFIED SLATE"),
        ("2", "LIVE TOTAL"),
        ("3", "OFFENSE VS DEFENSE"),
        ("4", "PACE + POSSESSION"),
        ("5", "EXPLOSIVE SCORING"),
        ("6", "RED ZONE + DRIVES"),
        ("7", "GAME ENVIRONMENT"),
        ("8", "TOTAL PROJECTION"),
    ):
        assert f'("{number}", "{label}", True)' in source
    assert '("9", "MARKET + FINAL READ", False)' in source
    assert '("10", "FINAL CERTIFICATION", False)' in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "STAKE_SIZING_ENABLED = False" in source
    assert "WAGER_ACTIONS_ENABLED = False" in source


def test_existing_nfl_router_preserves_current_game_total_target():
    source = _read(ROUTER)
    assert 'if market == "Game Total":' in source
    assert "from nfl_game_totals_hub_v8_1 import render_nfl_game_totals_hub" in source
    assert "from nfl_moneyline_hub_v9 import render_nfl_moneyline_hub" in source
