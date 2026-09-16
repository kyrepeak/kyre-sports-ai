from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "streamlit_memory_lazy_router_v137.py"
APP = ROOT / "app.py"


def test_v137_owns_only_exact_nfl_passing_yards_v36_route() -> None:
    source = ROUTER.read_text(encoding="utf-8")

    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v136"' in source
    assert 'ACTIVE_PASSING_YARDS_HUB = "nfl_passing_yards_hub_v36"' in source
    assert 'PASSING_YARDS_MARKET = "Passing Yards"' in source
    assert 'NFL_SPORT_LABEL = "NFL"' in source
    assert 'ks_sport_touch' in source
    assert 'ks_nfl_market_touch' in source
    assert "return prior.render_app()" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "STAKE_SIZING_ENABLED = False" in source


def test_app_boots_v137_and_keeps_v136_as_frozen_heartbeat() -> None:
    source = APP.read_text(encoding="utf-8")

    assert "FROZEN_V136_DEPLOYMENT_HEARTBEAT" in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V137_NFL_PASSING_YARDS_COMPACT_DASHBOARD_2026-09-15"' in source
    assert "from streamlit_memory_lazy_router_v137 import record_bootstrap_import_ms, render_app" in source
