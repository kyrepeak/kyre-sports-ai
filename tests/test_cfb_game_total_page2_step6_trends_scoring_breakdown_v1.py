from __future__ import annotations

from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "cfb_game_total_page2_step6_trends_scoring_breakdown_v1.py"


def _load_module():
    assert MODULE.is_file(), "Page-2 Step-6 trends/scoring module must exist before GREEN"
    spec = importlib.util.spec_from_file_location("cfb_gt_page2_step6", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sample_html():
    step6 = _load_module()
    return step6.build_trends_scoring_breakdown_html(
        recent_totals=[55, 63, 47, 71, 60],
        market_line=58.5,
        scoring_breakdown={
            "away_1h": 17.2,
            "home_1h": 14.8,
            "away_2h": 16.4,
            "home_2h": 15.1,
            "q1": 14.0,
            "q2": 18.0,
            "q3": 13.5,
            "q4": 18.0,
        },
        explosive_scoring="21.4 pts/game",
        scoring_opportunities="8.2 drives/game",
        red_zone_finishing="72% TD rate",
    )


def test_step6_module_exists_before_green() -> None:
    assert MODULE.is_file(), "Page-2 Step-6 trends/scoring module must exist before GREEN"


def test_step6_renders_recent_totals_and_market_reference() -> None:
    html = _sample_html()
    assert 'id="gtp2-trends"' in html
    assert 'data-testid="gtp2s6-trends"' in html
    assert "Trends + Scoring Breakdown" in html
    assert "Recent Totals" in html
    for value in (55, 63, 47, 71, 60):
        assert f">{value}<" in html
    assert "Market Line" in html and "58.5" in html


def test_step6_renders_half_and_quarter_scoring_breakdown() -> None:
    html = _sample_html()
    for label in ("1H Away", "1H Home", "2H Away", "2H Home", "Q1", "Q2", "Q3", "Q4"):
        assert label in html
    for value in ("17.2", "14.8", "16.4", "15.1", "14.0", "18.0", "13.5"):
        assert value in html


def test_step6_renders_scoring_driver_cards() -> None:
    html = _sample_html()
    assert "Explosive Scoring" in html and "21.4 pts/game" in html
    assert "Scoring Opportunities" in html and "8.2 drives/game" in html
    assert "Red-Zone Finishing" in html and "72% TD rate" in html


def test_step6_nonfinite_recent_totals_fail_soft() -> None:
    step6 = _load_module()
    html = step6.build_trends_scoring_breakdown_html(
        recent_totals=[float("nan"), float("inf"), float("-inf")],
        market_line=58.5,
        scoring_breakdown={},
        explosive_scoring=None,
        scoring_opportunities=None,
        red_zone_finishing=None,
    )
    assert html.count("—") >= 3
    assert ">nan<" not in html.lower()
    assert ">inf<" not in html.lower()
    assert ">-inf<" not in html.lower()


def test_step6_is_display_only_and_preserves_frozen_predecessors() -> None:
    step6 = _load_module()
    assert step6.STEP3_FREEZE_TOKEN == "CFB_GAME_TOTAL_PAGE2_V1_STEP3_INTEGRATED_FLOW_FROZEN"
    assert step6.STEP4_FREEZE_TOKEN == "CFB_GAME_TOTAL_PAGE2_V1_STEP4_OUTLOOK_SUMMARY_FROZEN"
    assert step6.STEP5_FREEZE_TOKEN == "CFB_GAME_TOTAL_PAGE2_V1_STEP5_TEAM_SNAPSHOT_KEY_DRIVERS_FROZEN"
    assert step6.FREEZE_TOKEN == "CFB_GAME_TOTAL_PAGE2_V1_STEP6_TRENDS_SCORING_BREAKDOWN_FROZEN"
    assert step6.MAY_MODIFY_PAGE1 is False
    assert step6.MAY_MODIFY_PROJECTION is False
    assert step6.MAY_MODIFY_PROBABILITY is False
    assert step6.MAY_MODIFY_MODEL is False
    assert step6.MAY_MODIFY_MARKET_OWNERSHIP is False
    assert step6.NETWORK_CALLS_ADDED == 0
    assert step6.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0

    source = MODULE.read_text(encoding="utf-8").lower()
    assert "requests." not in source
    assert "httpx." not in source
    assert "urllib.request" not in source


def test_step6_missing_values_fail_soft_without_fake_data_copy() -> None:
    step6 = _load_module()
    html = step6.build_trends_scoring_breakdown_html(
        recent_totals=[],
        market_line=None,
        scoring_breakdown={},
        explosive_scoring=None,
        scoring_opportunities=None,
        red_zone_finishing=None,
    )
    assert html.count("—") >= 12
    assert "data limited" not in html.lower()
    assert "mock data" not in html.lower()
    assert "pending" not in html.lower()


def test_step6_escapes_text_and_is_responsive() -> None:
    step6 = _load_module()
    html = step6.build_trends_scoring_breakdown_html(
        recent_totals=['<script>alert(1)</script>'],
        market_line="58.5",
        scoring_breakdown={"q1": '<img src=x onerror=alert(1)>'},
        explosive_scoring='<script>alert("x")</script>',
        scoring_opportunities="8.2",
        red_zone_finishing="72%",
    )
    assert "<script>" not in html
    assert "<img" not in html
    assert "&lt;script&gt;" in html
    assert "@media(max-width:760px)" in html
    assert "@media(max-width:480px)" in html
