from __future__ import annotations

import threading
import time

import nfl_passing_yards_hub_v75 as v75
import streamlit_memory_lazy_router_v226 as v226


STEP4_BODY = """
<section data-passing-yards-qb-detail="v59" data-passing-yards-live-market-ready="v73">
  <section class="ks-py73-market" data-passing-yards-live-market="v73"></section>
</section>
"""

STEP5_BODY = """
<section data-passing-yards-qb-detail="v59"
         data-passing-yards-live-market-ready="v73"
         data-passing-yards-availability-game-day-ready="v74">
  <section class="ks-py73-market" data-passing-yards-live-market="v73"></section>
  <section class="ks-py74" data-passing-yards-availability-game-day="v74"
           data-passing-yards-availability-ready="true" data-game-day-state="PENDING"></section>
</section>
"""


def test_step6_contract_is_additive_and_math_frozen() -> None:
    assert v75.FROZEN_PRIOR == "nfl_passing_yards_hub_v74"
    assert v75.FROZEN_FALLBACK == "nfl_passing_yards_hub_v73"
    assert v75.NEW_PHASE_STEP == 6
    assert v75.PRESENTATION_ONLY is True
    assert v75.MAY_MODIFY_PROJECTION is False
    assert v75.MAY_MODIFY_CONTEXT_MATH is False
    assert v75.MAY_MODIFY_PROBABILITY is False
    assert v75.MAY_MODIFY_MARKET_MATH is False
    assert v75.MAY_MODIFY_PERSONNEL_MATH is False
    assert v75.MAY_MODIFY_ENVIRONMENT_MATH is False
    assert v75.MAY_MODIFY_DATA_PROVIDER_BEHAVIOR is False
    assert v75.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert v75.STAKE_SIZING_ENABLED is False
    assert v75.PUBLIC_RENDER_SERIALIZATION == "passing-yards-global-render-rlock-v1"
    assert v226.FROZEN_ROUTER == "streamlit_memory_lazy_router_v225"
    assert v226.PASSING_HUB == "nfl_passing_yards_hub_v75"
    assert v226.FALLBACK_HUB == "nfl_passing_yards_hub_v74"


def test_healthy_step6_preserves_step5_and_marks_reliability_ready() -> None:
    out = v75._inject_failure_proofing(STEP5_BODY, "HEALTHY")
    assert 'data-passing-yards-availability-game-day="v74"' in out
    assert 'data-passing-yards-failure-proofing="v75"' in out
    assert 'data-passing-yards-failure-proofing-ready="v75"' in out
    assert 'data-passing-yards-failure-mode="HEALTHY"' in out
    assert 'data-failure-proofing-mode="HEALTHY"' in out
    assert "Failure-proofing active" in out
    assert "no unavailable evidence was synthesized" not in out


def test_failure_proofing_injection_is_once_only() -> None:
    once = v75._inject_failure_proofing(STEP5_BODY, "HEALTHY")
    twice = v75._inject_failure_proofing(once, "HEALTHY")
    assert once.count('data-passing-yards-failure-proofing="v75"') == 1
    assert twice.count('data-passing-yards-failure-proofing="v75"') == 1


def test_step5_additive_exception_falls_back_to_frozen_step4_without_fabrication() -> None:
    original_step5 = v75._FROZEN_SELECTED_ANALYSIS
    original_step4 = v75._FROZEN_STEP4_SELECTED_ANALYSIS
    try:
        def explode(captured, slot):
            raise RuntimeError("synthetic step5 additive failure")

        v75._FROZEN_SELECTED_ANALYSIS = explode
        v75._FROZEN_STEP4_SELECTED_ANALYSIS = lambda captured, slot: STEP4_BODY
        out = v75._selected_analysis_v75({}, 2)
    finally:
        v75._FROZEN_SELECTED_ANALYSIS = original_step5
        v75._FROZEN_STEP4_SELECTED_ANALYSIS = original_step4

    assert 'data-passing-yards-live-market="v73"' in out
    assert 'data-passing-yards-failure-proofing="v75"' in out
    assert 'data-passing-yards-failure-mode="DEGRADED"' in out
    assert 'data-failure-proofing-mode="DEGRADED"' in out
    assert "Failure contained" in out
    assert "RuntimeError" in out
    assert "Frozen Steps 1-4 remain available" in out
    assert "no unavailable evidence was synthesized" in out
    assert 'data-passing-yards-availability-game-day="v74"' not in out


def test_step6_router_preflight_fails_closed_to_frozen_step5() -> None:
    def broken_importer(name):
        raise ImportError(name)

    assert v226._step6_hub_importable(broken_importer) is False
    assert v226._step6_hub_importable(lambda name: object()) is True
    assert v226.FALLBACK_HUB == "nfl_passing_yards_hub_v74"


def test_step6_global_render_serialization_allows_only_one_critical_section() -> None:
    active = 0
    maximum = 0
    state_lock = threading.Lock()

    def probe() -> None:
        nonlocal active, maximum
        with state_lock:
            active += 1
            maximum = max(maximum, active)
        time.sleep(0.05)
        with state_lock:
            active -= 1

    threads = [
        threading.Thread(target=lambda: v75._run_serialized(probe))
        for _ in range(3)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2)
        assert not thread.is_alive()

    assert maximum == 1
