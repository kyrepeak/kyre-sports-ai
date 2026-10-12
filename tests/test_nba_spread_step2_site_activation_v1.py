from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "streamlit_memory_lazy_router_nba_spread_step2_activation_v1.py"
CONTRACT = ROOT / "nba_spread_step2_activation_v1.py"
PAGE = ROOT / "nba_spread_page_v1.py"
APP = ROOT / "app.py"
MANIFEST = ROOT / "devsystem" / "devsystem_manifest_v1.json"


def _load_contract():
    spec = importlib.util.spec_from_file_location("nba_spread_step2_activation_v1", CONTRACT)
    if spec is None or spec.loader is None:
        raise AssertionError("NBA Spread Step-2 activation contract must be importable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_nba_spread_step2_activation_contract_extends_sports_without_reordering_existing_options():
    assert CONTRACT.exists(), "NBA Spread Step-2 activation contract must exist"
    contract = _load_contract()
    original = ["MLB", "WNBA", "NFL", "College Football"]
    assert contract.extend_sport_options(original) == [
        "MLB",
        "WNBA",
        "NFL",
        "College Football",
        "NBA",
    ]
    assert contract.extend_sport_options(original + ["NBA"]) == original + ["NBA"]
    assert contract.NBA_MARKETS == ("Spread",)
    assert contract.is_nba_spread_route("NBA", "Spread") is True
    assert contract.is_nba_spread_route("NBA", "Moneyline") is False
    assert contract.is_nba_spread_route("NFL", "Spread") is False


def test_nba_spread_step2_router_is_additive_over_current_production_owner():
    assert ROUTER.exists(), "NBA Spread Step-2 production router must exist"
    source = ROUTER.read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1 as prior" in source
    assert "streamlit_memory_lazy_router_v1 as root" in source
    assert 'NBA_SPORT_LABEL = "NBA"' in source
    assert 'NBA_MARKET_LABEL = "🎯 NBA Market"' in source
    assert 'ACTIVE_PAGE = "nba_spread_page_v1"' in source
    assert "MAY_MODIFY_OTHER_SPORTS = False" in source
    assert "MAY_MODIFY_EXISTING_NBA_WORKSTREAMS = False" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "return prior.render_app()" in source


def test_nba_spread_step2_page_shell_is_reachable_and_fail_closed():
    assert PAGE.exists(), "NBA Spread Page-1 shell must exist"
    source = PAGE.read_text(encoding="utf-8")
    assert 'data-testid="nba-spread-step2-active"' in source
    assert "NBA Spread" in source
    assert "Phoenix, Arizona" in source
    assert "nba_over_under" not in source.lower()
    assert "sportsbook_projection_influence = 0.0" in source.lower()


def test_app_boots_nba_spread_step2_router_without_removing_current_parent_compatibility():
    source = APP.read_text(encoding="utf-8")
    runtime = source[source.find("try:"):]
    assert (
        "from streamlit_memory_lazy_router_nba_spread_step2_activation_v1 import "
        "record_bootstrap_import_ms, render_app"
    ) in runtime
    assert "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1" in source


def test_nba_domain_becomes_active_only_with_step2_critical_test_and_browser_contract():
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    nba = payload["domains"]["nba"]
    assert nba["status"] == "active"
    assert nba["critical_job"] == "nba-critical"
    assert "tests/test_nba_spread_step2_site_activation_v1.py" in nba["critical_tests"]
    assert "NBA -> Spread" in nba["browser_coverage"]
    assert "Streamlit NBA Spread" in nba["production_probe"]
