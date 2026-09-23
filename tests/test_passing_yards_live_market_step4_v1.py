from pathlib import Path

import nfl_passing_yards_hub_v73 as v73
import streamlit_memory_lazy_router_v224 as router


SOURCE = """
<section class="ks-py59" data-passing-yards-qb-detail="v59"
 data-passing-yards-explainability-ready="v71"
 data-passing-yards-matchup-intelligence-ready="v72">
 <section class="ks-py63-market-detail" data-passing-yards-market-detail="v63">
  <div data-market-field="lean"><b>LEAN OVER</b><span>Final Lean</span></div>
  <div data-market-field="line"><b>247.5</b><span>Market Line</span></div>
  <div data-market-field="confidence"><b>MEDIUM</b><span>Model Confidence</span></div>
  <div data-market-field="offered-odds"><b>-108 / -112</b><span>Offered Odds</span></div>
  <div class="ks-py63-market-source"><strong>Source:</strong> Kyre Sports API • FanDuel • sportsbook projection influence 0.0% • stake sizing OFF</div>
 </section>
 <section class="kpy10-card">
  <div class="kpy10-hero">
   <div><b>LEAN OVER</b><span>Final Lean</span></div>
   <div><b>247.5</b><span>Market Line</span></div>
   <div><b>MEDIUM</b><span>Model Confidence</span></div>
  </div>
  <div class="kpy10-metrics">
   <div><b>-108 / -112</b>Offered Over / Under</div>
  </div>
 </section>
 <section class="ks-py72-matchup" data-passing-yards-matchup-intelligence="v72"></section>
</section>
"""


def _snap(line=247.5, over=-108, under=-112, stamp="2026-09-23T21:00:00+00:00"):
    return {
        "ready": True,
        "certified": True,
        "slot": 2,
        "source": "Kyre Sports API • FanDuel",
        "sportsbook": "FanDuel",
        "line": float(line),
        "over_odds": int(over),
        "under_odds": int(under),
        "captured_at_utc": stamp,
        "projection_weight": 0.0,
    }


def test_step4_parses_current_certified_market_snapshot():
    row = v73.build_snapshot(SOURCE, 2, timestamp="2026-09-23T21:00:00+00:00")
    assert row["ready"] is True
    assert row["certified"] is True
    assert row["sportsbook"] == "FanDuel"
    assert row["line"] == 247.5
    assert row["over_odds"] == -108
    assert row["under_odds"] == -112
    assert row["projection_weight"] == 0.0


def test_step4_bounded_parser_survives_proven_contaminated_v63_fields():
    contaminated = SOURCE.replace(
        '<div data-market-field="line"><b>247.5</b><span>Market Line</span></div>',
        '<div data-market-field="line"><b>4036378ESPN Athlete ID9ESPN Team IDNo listed injuryAvailabilityESPN CORE DEPTH CHART Current Market + Edge Jordan Love 226.5</b><span>Market Line</span></div>',
    ).replace(
        '<div data-market-field="offered-odds"><b>-108 / -112</b><span>Offered Odds</span></div>',
        '<div data-market-field="offered-odds"><b>4036378ESPN Athlete ID Current Market + Edge 55.3% / 44.7% Model Over / Under -123 / +123 Model fair Over / Under -114 / -114</b><span>Offered Odds</span></div>',
    ).replace(
        '<div><b>247.5</b><span>Market Line</span></div>',
        '<div><b>226.5</b><span>Market Line</span></div>',
    ).replace(
        '<div><b>-108 / -112</b>Offered Over / Under</div>',
        '<div><b>-114 / -114</b>Offered Over / Under</div>',
    )
    row = v73.build_snapshot(contaminated, 2, timestamp="2026-09-23T21:44:00+00:00")
    assert row["ready"] is True
    assert row["line"] == 226.5
    assert row["over_odds"] == -114
    assert row["under_odds"] == -114


def test_step4_bounded_parser_fails_closed_when_exact_values_are_malformed():
    malformed = SOURCE.replace(
        '<div data-market-field="line"><b>247.5</b><span>Market Line</span></div>',
        '<div data-market-field="line"><b>not-a-line</b><span>Market Line</span></div>',
    ).replace(
        '<div data-market-field="offered-odds"><b>-108 / -112</b><span>Offered Odds</span></div>',
        '<div data-market-field="offered-odds"><b>bad / bad</b><span>Offered Odds</span></div>',
    ).replace(
        '<div><b>247.5</b><span>Market Line</span></div>',
        '<div><b>not-a-line</b><span>Market Line</span></div>',
    ).replace(
        '<div><b>-108 / -112</b>Offered Over / Under</div>',
        '<div><b>bad / bad</b>Offered Over / Under</div>',
    )
    row = v73.build_snapshot(malformed, 2)
    assert row["ready"] is False
    assert row["line"] != row["line"]
    assert row["over_odds"] is None
    assert row["under_odds"] is None


def test_uncertified_or_missing_market_fails_closed():
    bad = SOURCE.replace("Kyre Sports API • FanDuel", "Manual verified market")
    row = v73.build_snapshot(bad, 2)
    assert row["ready"] is False
    panel = v73.build_live_market_panel(row, [])
    assert 'data-passing-yards-live-market-ready="false"' in panel
    assert "No live line" in panel
    assert "fabricated" in panel


def test_first_snapshot_never_claims_true_sportsbook_open():
    history = v73.update_history([], _snap())
    out = v73.movement_summary(history)
    assert out["ready"] is True
    assert out["observation_count"] == 1
    assert out["state"] == "NO PRIOR CERTIFIED SNAPSHOT"
    panel = v73.build_live_market_panel(history[-1], history)
    assert "First Certified Session Line" in panel
    assert "not represented as the sportsbook’s historical opening line" in panel
    assert "NOT YET PROVABLE" in panel


def test_line_up_and_down_are_measured_from_first_certified_snapshot():
    history = []
    history = v73.update_history(history, _snap(247.5, -108, -112))
    history = v73.update_history(history, _snap(249.5, -105, -115))
    up = v73.movement_summary(history)
    assert up["state"] == "LINE UP 2"
    assert up["line_delta"] == 2.0

    history = v73.update_history(history, _snap(245.5, -110, -110))
    down = v73.movement_summary(history)
    assert down["state"] == "LINE DOWN 2"
    assert down["line_delta"] == -2.0


def test_price_only_move_is_distinguished_from_line_move():
    history = v73.update_history([], _snap(247.5, -108, -112))
    history = v73.update_history(history, _snap(247.5, -115, -105))
    out = v73.movement_summary(history)
    assert out["state"] == "PRICE MOVE • LINE FLAT"
    assert out["line_delta"] == 0.0


def test_duplicate_snapshot_does_not_fake_a_second_observation():
    history = v73.update_history([], _snap())
    history = v73.update_history(history, _snap(stamp="2026-09-23T21:01:00+00:00"))
    assert len(history) == 1
    assert history[0]["captured_at_utc"] == "2026-09-23T21:01:00+00:00"
    assert v73.movement_summary(history)["state"] == "NO PRIOR CERTIFIED SNAPSHOT"


def test_history_is_bounded():
    history = []
    for i in range(20):
        history = v73.update_history(history, _snap(240.5 + i, -110, -110), limit=12)
    assert len(history) == 12
    assert history[0]["line"] == 248.5
    assert history[-1]["line"] == 259.5


def test_step4_panel_exposes_required_live_market_contract():
    history = v73.update_history([], _snap())
    panel = v73.build_live_market_panel(history[-1], history)
    assert 'data-passing-yards-live-market="v73"' in panel
    assert 'data-passing-yards-live-market-ready="true"' in panel
    assert 'data-passing-yards-v224-runtime="live-market-step4"' in panel
    for field in ("current-line", "prices", "first-line", "movement"):
        assert f'data-live-market-field="{field}"' in panel
    assert "1 certified book" in panel
    assert "Best available among certified books" in panel
    assert "sportsbook projection influence 0.0%" in panel.lower()


def test_step4_is_presentation_only_and_preserves_step3():
    assert v73.FROZEN_PRIOR == "nfl_passing_yards_hub_v72"
    assert v73.NEW_PHASE_STEP == 4
    assert v73.PRESENTATION_ONLY is True
    assert v73.MAY_MODIFY_PROJECTION is False
    assert v73.MAY_MODIFY_CONTEXT_MATH is False
    assert v73.MAY_MODIFY_PROBABILITY is False
    assert v73.MAY_MODIFY_MARKET_MATH is False
    assert v73.MAY_MODIFY_DATA_PROVIDER is False
    assert v73.MAY_MODIFY_WIDGET_KEYS is False
    assert v73.MAY_MODIFY_NAVIGATION_STATE is False
    assert v73.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    source = Path("nfl_passing_yards_hub_v73.py").read_text()
    assert "evaluate_market(" not in source
    assert "build_baseline_projection(" not in source


def test_router_only_advances_passing_yards():
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v223"
    assert router.PASSING_HUB == "nfl_passing_yards_hub_v73"
    assert router.PRESENTATION_ONLY is True
    assert router.MAY_MODIFY_PROJECTION is False
    assert router.MAY_MODIFY_CONTEXT_MATH is False
    assert router.MAY_MODIFY_MARKET_MATH is False
    assert router.MAY_MODIFY_NAVIGATION_STATE is False
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
