import nfl_passing_yards_hub_v71 as v71
import streamlit_memory_lazy_router_v222 as router


SOURCE = """
<section class="ks-py59" data-passing-yards-qb-detail="v59"
 data-passing-yards-detail-cleanup="v69"
 data-passing-yards-detail-cleanup-ready="v69">
  <div><b>268.4</b><span>Baseline Pass Yards</span></div>
  <div><b>36.2</b><span>Expected Attempts</span></div>
  <div><b>7.41</b><span>Expected YPA</span></div>
  <div><b>100%</b>Attempt-source coverage</div>
  <div><b>95%</b>Efficiency-source coverage</div>
  <div><b>CHECK</b>Pressure context • not numerically adjusted</div>
  <div><b>GREEN</b>Personnel context • not numerically adjusted</div>

  <div><b>OVER</b><span>Final Lean</span></div>
  <div><b>252.5</b><span>Market Line</span></div>
  <div><b>HIGH</b><span>Model Confidence</span></div>
  <div><b>+8.2% / -8.2%</b>Model edge Over / Under</div>

  <section class="ks-py69-clean-detail" data-passing-yards-clean-detail="projection"
    data-passing-yards-detail-cleanup-panel="v69"></section>
</section>
"""


def test_explainability_panel_copies_frozen_values_and_five_driver_groups():
    panel = v71.build_projection_explainability(SOURCE)
    assert 'data-passing-yards-projection-explainability="v71"' in panel
    assert 'data-passing-yards-explainability-method="v71"' in panel
    assert panel.count('data-explainability-driver=') == 5

    for token in (
        "268.4",
        "36.2",
        "7.41",
        "100% / 95%",
        "252.5",
        "OVER",
        "+8.2% / -8.2%",
        "HIGH",
        "QB season workload",
        "QB recent workload",
        "Opponent pass-defense volume + efficiency",
        "QB passing efficiency",
        "Team passing pace",
        "Sportsbook projection influence remains 0.0%",
    ):
        assert token in panel


def test_injection_adds_ready_marker_before_projection_detail():
    out = v71._inject_projection_explainability(SOURCE)
    assert out.count('data-passing-yards-projection-explainability="v71"') == 1
    assert 'data-passing-yards-explainability-ready="v71"' in out
    explain_pos = out.index('data-passing-yards-projection-explainability="v71"')
    projection_pos = out.index('data-passing-yards-clean-detail="projection"')
    assert explain_pos < projection_pos


def test_injection_is_idempotent():
    once = v71._inject_projection_explainability(SOURCE)
    twice = v71._inject_projection_explainability(once)
    assert twice.count('data-passing-yards-projection-explainability="v71"') == 1


def test_step2_is_presentation_only_and_market_independent():
    assert v71.PRESENTATION_ONLY is True
    assert v71.MAY_MODIFY_PROJECTION is False
    assert v71.MAY_MODIFY_CONTEXT is False
    assert v71.MAY_MODIFY_PROBABILITY is False
    assert v71.MAY_MODIFY_MARKET_MATH is False
    assert v71.MAY_MODIFY_DATA is False
    assert v71.MAY_MODIFY_NAVIGATION_STATE is False
    assert v71.MAY_MODIFY_WIDGET_KEYS is False
    assert v71.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert v71.STAKE_SIZING_ENABLED is False


def test_router_only_advances_passing_yards_owner():
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v221"
    assert router.PASSING_HUB == "nfl_passing_yards_hub_v71"
    assert router.PRESENTATION_ONLY is True
    assert router.MAY_MODIFY_PROJECTION is False
    assert router.MAY_MODIFY_NAVIGATION_STATE is False
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
