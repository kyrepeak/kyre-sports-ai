import nfl_passing_yards_hub_v72 as v72
import streamlit_memory_lazy_router_v223 as router


SOURCE = """
<section class="ks-py59" data-passing-yards-qb-detail="v59"
 data-passing-yards-detail-cleanup="v69"
 data-passing-yards-detail-cleanup-ready="v69"
 data-passing-yards-explainability-ready="v71">
 <section class="kpy-defense">
  <div class="kpy-grade favorable">FAVORABLE</div>
  <div><b>248.3</b><span>Pass Yds Allowed/G</span></div>
  <div><b>#24</b><span>Pass Yds Rank</span></div>
  <div><b>35.8</b><span>Attempts Allowed/G</span></div>
  <div><b>68.1%</b><span>Completion Allowed</span></div>
  <div><b>7.21</b><span>Yards/Att Allowed</span></div>
  <div class="kpy-drecent">Recent 3: <b>262.7</b> pass yds allowed/game • <b>69.0%</b> completion • <b>7.32</b> Y/A</div>
 </section>
 <section class="kpy-pressure">
  <div class="kpy-xsub">Green Bay Packers protection vs Atlanta Falcons rush • verified</div>
  <div class="kpy-xgrade moderate">MODERATE</div>
  <div><b>6.7%</b><span>Defense Sack Rate</span></div>
  <div><b>2.4</b><span>Defense Sacks/G</span></div>
  <div class="kpy-blitz">Blitz context: UNAVAILABLE — not synthesized</div>
 </section>
 <section class="kpy-env">
  <div class="kpy-envtitle">Game Environment • FAST pace context</div>
  <div class="kpy-envteam"><h4>Green Bay Packers • PASS-LEANING</h4></div>
 </section>
 <section class="ks-py71-explain" data-passing-yards-projection-explainability="v71"
  data-passing-yards-mobile-cleanup-runtime="v70"
  data-passing-yards-v222-runtime="projection-explainability-step2">
  <div><b>36.4</b><span>Expected Attempts</span></div>
 </section>
 <section class="ks-py69-clean-detail" data-passing-yards-clean-detail="projection"></section>
</section>
"""


def test_matchup_panel_surfaces_verified_existing_evidence():
    panel = v72.build_matchup_intelligence(SOURCE)
    assert 'data-passing-yards-matchup-intelligence="v72"' in panel
    assert 'data-passing-yards-v223-runtime="matchup-intelligence-step3"' in panel
    assert panel.count('data-matchup-hero=') == 4
    assert panel.count('data-matchup-intelligence-field=') == 8

    for token in (
        "#24",
        "248.3",
        "6.7%",
        "36.4",
        "35.8",
        "68.1%",
        "7.21",
        "262.7",
        "MODERATE",
        "FAST",
        "PASS-LEANING",
        "UNAVAILABLE — not synthesized",
    ):
        assert token.casefold() in panel.casefold()


def test_unsupported_coverage_and_explosives_fail_closed():
    panel = v72.build_matchup_intelligence(SOURCE)
    assert panel.count("UNAVAILABLE — NOT SYNTHESIZED") >= 2
    assert 'data-matchup-intelligence-source-gap="true"' in panel
    assert "rather than being estimated" in panel


def test_injection_preserves_step2_and_adds_step3_ready_marker():
    out = v72._inject_matchup_intelligence(SOURCE)
    assert out.count('data-passing-yards-projection-explainability="v71"') == 1
    assert out.count('data-passing-yards-matchup-intelligence="v72"') == 1
    assert 'data-passing-yards-matchup-intelligence-ready="v72"' in out
    assert 'data-passing-yards-explainability-ready="v71"' in out
    assert 'data-passing-yards-mobile-cleanup-runtime="v70"' in out
    assert 'data-passing-yards-v222-runtime="projection-explainability-step2"' in out

    step2 = out.index('data-passing-yards-projection-explainability="v71"')
    step3 = out.index('data-passing-yards-matchup-intelligence="v72"')
    projection = out.index('data-passing-yards-clean-detail="projection"')
    assert step2 < step3 < projection


def test_injection_is_idempotent():
    once = v72._inject_matchup_intelligence(SOURCE)
    twice = v72._inject_matchup_intelligence(once)
    assert twice.count('data-passing-yards-matchup-intelligence="v72"') == 1


def test_step3_is_presentation_only():
    assert v72.FROZEN_PRIOR == "nfl_passing_yards_hub_v71"
    assert v72.NEW_PHASE_STEP == 3
    assert v72.PRESENTATION_ONLY is True
    assert v72.MAY_MODIFY_PROJECTION is False
    assert v72.MAY_MODIFY_CONTEXT_MATH is False
    assert v72.MAY_MODIFY_PROBABILITY is False
    assert v72.MAY_MODIFY_MARKET_MATH is False
    assert v72.MAY_MODIFY_DATA is False
    assert v72.MAY_MODIFY_WIDGET_KEYS is False
    assert v72.MAY_MODIFY_NAVIGATION_STATE is False
    assert v72.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0


def test_router_only_advances_passing_yards_owner():
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v222"
    assert router.PASSING_HUB == "nfl_passing_yards_hub_v72"
    assert router.PRESENTATION_ONLY is True
    assert router.MAY_MODIFY_PROJECTION is False
    assert router.MAY_MODIFY_CONTEXT_MATH is False
    assert router.MAY_MODIFY_NAVIGATION_STATE is False
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
