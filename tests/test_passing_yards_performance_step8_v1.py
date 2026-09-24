from __future__ import annotations

import nfl_passing_yards_hub_v77 as v77
import streamlit_memory_lazy_router_v228 as v228


BODY = """
<section class="ks-py59" data-passing-yards-qb-detail="v59"
         data-passing-yards-explainability-ready="v71"
         data-passing-yards-matchup-intelligence-ready="v72"
         data-passing-yards-live-market-ready="v73"
         data-passing-yards-availability-game-day-ready="v74"
         data-passing-yards-failure-proofing-ready="v75"
         data-passing-yards-ux-presentation="v76"
         data-passing-yards-ux-presentation-ready="v76">
  <article class="ks-py59-player" id="ks-py76-overview">
    <span>Jordan Love</span>
    <span>Passing Yards</span>
  </article>
  <nav data-passing-yards-ux-guide="v76">
    <a href="#ks-py76-overview">Overview</a>
    <a href="#ks-py76-why">Why</a>
    <a href="#ks-py76-matchup">Matchup</a>
    <a href="#ks-py76-market">Market</a>
    <a href="#ks-py76-gameday">Game Day</a>
    <a href="#ks-py76-reliability">Reliability</a>
  </nav>
</section>
"""


def test_step8_contract_preserves_frozen_step7_and_math() -> None:
    assert v77.FROZEN_PRIOR == "nfl_passing_yards_hub_v76"
    assert v77.NEW_PHASE_STEP == 8
    assert v77.PRESENTATION_ONLY is True
    assert v77.MAY_MODIFY_PROJECTION is False
    assert v77.MAY_MODIFY_CONTEXT_MATH is False
    assert v77.MAY_MODIFY_PROBABILITY is False
    assert v77.MAY_MODIFY_MARKET_MATH is False
    assert v77.MAY_MODIFY_PERSONNEL_MATH is False
    assert v77.MAY_MODIFY_ENVIRONMENT_MATH is False
    assert v77.MAY_MODIFY_DATA_PROVIDER_BEHAVIOR is False
    assert v77.MAY_MODIFY_WIDGET_KEYS is False
    assert v77.MAY_MODIFY_NAVIGATION_STATE is False
    assert v77.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert v77.STAKE_SIZING_ENABLED is False
    assert v228.FROZEN_ROUTER == "streamlit_memory_lazy_router_v227"
    assert v228.PASSING_HUB == "nfl_passing_yards_hub_v77"
    assert v228.FALLBACK_HUB == "nfl_passing_yards_hub_v76"


def test_step8_compaction_reduces_only_intertag_whitespace() -> None:
    out = v77._compact_intertag_whitespace(BODY)
    assert len(out.encode("utf-8")) < len(BODY.encode("utf-8"))
    assert "<span>Jordan Love</span> <span>Passing Yards</span>" in out
    assert 'data-passing-yards-ux-presentation-ready="v76"' in out
    assert 'data-passing-yards-ux-guide="v76"' in out


def test_step8_performance_marker_is_once_only_and_non_destructive() -> None:
    compact = v77._compact_intertag_whitespace(BODY)
    once = v77._inject_performance_contract(
        compact,
        compose_ms=12.5,
        bytes_before=len(BODY.encode("utf-8")),
        bytes_after=len(compact.encode("utf-8")),
    )
    twice = v77._inject_performance_contract(
        once,
        compose_ms=99.9,
        bytes_before=999,
        bytes_after=998,
    )
    assert once == twice
    assert once.count('data-passing-yards-performance-ready="v77"') == 1
    assert 'data-passing-yards-performance="v77"' in once
    assert 'data-step8-compose-ms="12.500"' in once
    assert 'data-step8-compaction="intertag-whitespace-v1"' in once
    assert 'data-passing-yards-ux-presentation-ready="v76"' in once
    assert "Jordan Love" in once


def test_step8_router_preflight_fails_closed_and_custom_importer_is_testable() -> None:
    calls = []

    def ok(name):
        calls.append(name)
        return object()

    def bad(name):
        calls.append(name)
        raise ImportError(name)

    assert v228._step8_hub_importable(ok) is True
    assert v228._step8_hub_importable(bad) is False
    assert calls == [v228.PASSING_HUB, v228.PASSING_HUB]
