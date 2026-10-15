from __future__ import annotations

import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "nba_spread_page_provider_resilience_step3_r1.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_nba_spread_step2_activation_v1.py"


def test_production_nba_spread_route_activates_step2_resilience_loader():
    assert BRIDGE.exists(), "Step 3 page bridge must exist before production activation"

    bridge_source = BRIDGE.read_text()
    router_source = ROUTER.read_text()
    assert (
        "from nba_spread_schedule_provider_resilience_step2_r1 import load_verified_nba_schedule"
        in bridge_source
    )
    assert 'ACTIVE_PAGE = "nba_spread_page_v1"' in router_source
    assert 'PROVIDER_RESILIENCE_PAGE = "nba_spread_page_provider_resilience_step3_r1"' in router_source
    assert 'importlib.import_module(PROVIDER_RESILIENCE_PAGE)' in router_source

    bridge = importlib.import_module("nba_spread_page_provider_resilience_step3_r1")
    step2 = importlib.import_module("nba_spread_schedule_provider_resilience_step2_r1")
    frozen_page = importlib.import_module("nba_spread_page_v1")

    original_loader = frozen_page.load_verified_nba_schedule
    try:
        bridge._bind_resilient_schedule_loader()
        assert frozen_page.load_verified_nba_schedule is step2.load_verified_nba_schedule
        assert bridge.MAY_MODIFY_MODEL is False
        assert bridge.MAY_MODIFY_PROJECTION is False
        assert bridge.MAY_MODIFY_PROBABILITY is False
        assert bridge.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    finally:
        frozen_page.load_verified_nba_schedule = original_loader
