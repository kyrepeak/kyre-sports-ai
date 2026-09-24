from __future__ import annotations

import nfl_passing_yards_hub_v82 as v82
import streamlit_memory_lazy_router_v233 as v233


def test_speed_step6_contract_preserves_frozen_behavior():
    assert v82.FROZEN_PRIOR == "nfl_passing_yards_hub_v81"
    assert v82.SPEED_PHASE_STEP == 6
    assert v82.CONCURRENCY_VERSION == "v82"
    assert v82.TRANSPORT_SCHEDULING_ONLY is True
    assert v82.MAX_PREFETCH_WORKERS == 10
    assert v82.BASELINE_FULL_READY_SECONDS == 42.594
    assert v82.FULL_READY_TARGET_SECONDS == 24.0
    assert v82.REDUCTION_TARGET_PCT == 40.0
    assert v82.MAY_MODIFY_PROJECTION is False
    assert v82.MAY_MODIFY_CONTEXT_MATH is False
    assert v82.MAY_MODIFY_PROBABILITY is False
    assert v82.MAY_MODIFY_MARKET_MATH is False
    assert v82.MAY_MODIFY_SPORTSBOOK_BEHAVIOR is False
    assert v82.MAY_MODIFY_DATA_PROVIDER_BEHAVIOR is False
    assert v82.MAY_MODIFY_WIDGET_KEYS is False
    assert v82.MAY_MODIFY_NAVIGATION_STATE is False
    assert v82.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert v82.STAKE_SIZING_ENABLED is False


def test_speed_step6_keys_are_deterministic():
    assert v82._profile_key("123", "Jordan Love", 2026, 2) == ("123", "Jordan Love", 2026, 2)
    assert v82._defense_key("9", "Packers", 2026, 2, "2026-09-24") == (
        "9", "Packers", 2026, 2, "2026-09-24"
    )
    assert v82._pressure_key("1", "Falcons", "9", "Packers", 2026, 2, "2026-09-24") == (
        "1", "Falcons", "9", "Packers", 2026, 2, "2026-09-24"
    )


def test_speed_step6_router_advances_only_passing_yards():
    assert v233.FROZEN_ROUTER == "streamlit_memory_lazy_router_v232"
    assert v233.PASSING_HUB == "nfl_passing_yards_hub_v82"
    assert v233.FALLBACK_HUB == "nfl_passing_yards_hub_v81"
    assert v233.CONCURRENCY_VERSION == "v82"
    assert v233.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
