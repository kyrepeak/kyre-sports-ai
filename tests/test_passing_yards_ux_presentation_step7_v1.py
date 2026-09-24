from __future__ import annotations

import nfl_passing_yards_hub_v76 as v76
import streamlit_memory_lazy_router_v227 as v227


BODY = """
<section class="ks-py59" data-passing-yards-qb-detail="v59"
         data-passing-yards-explainability-ready="v71"
         data-passing-yards-matchup-intelligence-ready="v72"
         data-passing-yards-live-market-ready="v73"
         data-passing-yards-availability-game-day-ready="v74"
         data-passing-yards-failure-proofing-ready="v75">
  <article class="ks-py59-player"><b>Jordan Love</b></article>
  <section class="ks-py71-explain" data-passing-yards-projection-explainability="v71"></section>
  <section class="ks-py72-matchup" data-passing-yards-matchup-intelligence="v72"></section>
  <section class="ks-py73-market" data-passing-yards-live-market="v73"></section>
  <section class="ks-py74" data-passing-yards-availability-game-day="v74"></section>
  <section class="ks-py75" data-passing-yards-failure-proofing="v75"
           data-failure-proofing-mode="HEALTHY"></section>
</section>
"""


def test_step7_contract_is_presentation_only_and_prior_is_frozen() -> None:
    assert v76.FROZEN_PRIOR == "nfl_passing_yards_hub_v75"
    assert v76.NEW_PHASE_STEP == 7
    assert v76.PRESENTATION_ONLY is True
    assert v76.DISPLAY_ONLY is True
    assert v76.MAY_MODIFY_PROJECTION is False
    assert v76.MAY_MODIFY_CONTEXT_MATH is False
    assert v76.MAY_MODIFY_PROBABILITY is False
    assert v76.MAY_MODIFY_MARKET_MATH is False
    assert v76.MAY_MODIFY_PERSONNEL_MATH is False
    assert v76.MAY_MODIFY_ENVIRONMENT_MATH is False
    assert v76.MAY_MODIFY_DATA_PROVIDER_BEHAVIOR is False
    assert v76.MAY_MODIFY_WIDGET_KEYS is False
    assert v76.MAY_MODIFY_NAVIGATION_STATE is False
    assert v76.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert v76.STAKE_SIZING_ENABLED is False
    assert v227.FROZEN_ROUTER == "streamlit_memory_lazy_router_v226"
    assert v227.PASSING_HUB == "nfl_passing_yards_hub_v76"
    assert v227.FALLBACK_HUB == "nfl_passing_yards_hub_v75"


def test_step7_adds_guide_anchors_and_ready_marker_once() -> None:
    once = v76._inject_ux_presentation(BODY)
    twice = v76._inject_ux_presentation(once)

    assert 'data-passing-yards-ux-presentation="v76"' in once
    assert 'data-passing-yards-ux-presentation-ready="v76"' in once
    assert once.count('data-passing-yards-ux-guide="v76"') == 1
    assert twice.count('data-passing-yards-ux-guide="v76"') == 1

    for anchor in (
        "ks-py76-overview",
        "ks-py76-why",
        "ks-py76-matchup",
        "ks-py76-market",
        "ks-py76-gameday",
        "ks-py76-reliability",
    ):
        assert f'id="{anchor}"' in once
        assert f'href="#{anchor}"' in once

    for frozen in (
        'data-passing-yards-projection-explainability="v71"',
        'data-passing-yards-matchup-intelligence="v72"',
        'data-passing-yards-live-market="v73"',
        'data-passing-yards-availability-game-day="v74"',
        'data-passing-yards-failure-proofing="v75"',
    ):
        assert frozen in once


def test_missing_frozen_step6_contract_fails_closed_without_partial_ux() -> None:
    broken = BODY.replace('data-passing-yards-failure-proofing="v75"', "")
    out = v76._inject_ux_presentation(broken)
    assert out == broken
    assert 'data-passing-yards-ux-presentation="v76"' not in out
    assert 'data-passing-yards-ux-guide="v76"' not in out


def test_step7_router_preflight_falls_back_to_frozen_step6() -> None:
    def broken_importer(name):
        raise ImportError(name)

    assert v227._step7_hub_importable(broken_importer) is False
    assert v227._step7_hub_importable(lambda name: object()) is True
    assert v227.FALLBACK_HUB == "nfl_passing_yards_hub_v75"
