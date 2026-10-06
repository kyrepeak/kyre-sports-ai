from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'sports_api' / 'nfl_game_totals_market_read_v1.py'
STEP9 = ROOT / 'nfl_game_totals_hub_v9.py'
STEP10 = ROOT / 'nfl_game_totals_hub_v10.py'
ROUTER = ROOT / 'nfl_hub_v18.py'


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8') if path.exists() else ''


def _load_helper():
    assert HELPER.exists(), 'Task 15 market-read helper is missing'
    spec = importlib.util.spec_from_file_location('task15_market_read', HELPER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _projection(total=50.6, low=47.6, high=53.6):
    return {
        'ready': True,
        'projected_total': total,
        'range_low': low,
        'range_high': high,
        'sportsbook_projection_weight': 0.0,
    }


def _snapshot(total=45.5, over=-110, under=-110):
    return {
        'ready': True,
        'market_available': True,
        'markets': [{
            'active': True,
            'total': total,
            'over_price': over,
            'under_price': under,
            'market_id': 'fd-total-1',
        }],
    }


def test_task15_runtime_files_exist():
    assert HELPER.exists()
    assert STEP9.exists()
    assert STEP10.exists()


def test_market_read_uses_market_only_after_projection_is_complete():
    module = _load_helper()
    result = module.build_market_final_read(_projection(), _snapshot(45.5))
    assert result['ready'] is True
    assert result['market_total'] == pytest.approx(45.5)
    assert result['model_total'] == pytest.approx(50.6)
    assert result['edge_points'] == pytest.approx(5.1)
    assert result['final_read'] == 'OVER'
    assert result['sportsbook_projection_weight'] == 0.0
    assert result['comparison_only'] is True
    assert result['stake_sizing_enabled'] is False
    assert result['wager_actions_enabled'] is False


def test_market_read_is_under_only_when_market_sits_above_model_range():
    module = _load_helper()
    result = module.build_market_final_read(_projection(), _snapshot(55.5))
    assert result['ready'] is True
    assert result['final_read'] == 'UNDER'
    assert result['edge_points'] == pytest.approx(-4.9)


def test_market_read_passes_when_market_is_inside_model_range():
    module = _load_helper()
    result = module.build_market_final_read(_projection(), _snapshot(50.5))
    assert result['ready'] is True
    assert result['final_read'] == 'PASS'
    assert result['edge_points'] == pytest.approx(0.1)


def test_market_read_fails_closed_for_missing_projection_or_ambiguous_market():
    module = _load_helper()
    missing_projection = module.build_market_final_read({'ready': False}, _snapshot())
    assert missing_projection['ready'] is False
    assert missing_projection['final_read'] == 'UNAVAILABLE'

    ambiguous = _snapshot()
    ambiguous['markets'].append(dict(ambiguous['markets'][0], market_id='duplicate'))
    missing_market = module.build_market_final_read(_projection(), ambiguous)
    assert missing_market['ready'] is False
    assert missing_market['final_read'] == 'UNAVAILABLE'


def test_step9_turns_on_market_comparison_but_not_wager_actions():
    source = _read(STEP9)
    assert 'PAGE_BUILD_STEP = 9' in source
    assert 'PAGE_BUILD_TOTAL = 10' in source
    assert 'MARKET_COMPARISON_ENABLED = True' in source
    assert 'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0' in source
    assert 'STAKE_SIZING_ENABLED = False' in source
    assert 'WAGER_ACTIONS_ENABLED = False' in source
    assert 'build_market_final_read(' in source
    assert '("9", "MARKET + FINAL READ", True)' in source
    assert '("10", "FINAL CERTIFICATION", False)' in source


def test_step10_finalizes_page_without_enabling_stakes_or_wagers():
    source = _read(STEP10)
    assert 'PAGE_BUILD_STEP = 10' in source
    assert 'PAGE_BUILD_TOTAL = 10' in source
    assert 'FINAL_CERTIFICATION_ENABLED = True' in source
    assert 'MARKET_COMPARISON_ENABLED = True' in source
    assert 'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0' in source
    assert 'STAKE_SIZING_ENABLED = False' in source
    assert 'WAGER_ACTIONS_ENABLED = False' in source
    assert '("10", "FINAL CERTIFICATION", True)' in source


def test_router_advances_only_game_total_to_v10():
    source = _read(ROUTER)
    assert 'if market == "Game Total":' in source
    assert 'from nfl_game_totals_hub_v10 import render_nfl_game_totals_hub' in source
    assert 'from nfl_moneyline_hub_v9 import render_nfl_moneyline_hub' in source
