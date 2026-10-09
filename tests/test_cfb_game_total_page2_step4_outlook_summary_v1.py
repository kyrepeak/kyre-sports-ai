from __future__ import annotations

from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "cfb_game_total_page2_step4_outlook_summary_v1.py"


def _load_module():
    assert MODULE.is_file(), "Page-2 Step-4 outlook-summary module must exist before GREEN"
    spec = importlib.util.spec_from_file_location("cfb_gt_page2_step4", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_step4_outlook_summary_component_exists_before_green() -> None:
    assert MODULE.is_file(), "Page-2 Step-4 outlook-summary module must exist before GREEN"


def test_step4_renders_owned_projection_probability_market_edge_and_confidence() -> None:
    step4 = _load_module()
    html = step4.build_outlook_projection_summary_html(
        over_probability=61.2,
        under_probability=38.8,
        projected_total=64.7,
        market_line=59.5,
        edge=5.2,
        confidence_label="79% • Grade B",
    )

    assert 'id="gtp2-outlook"' in html
    assert 'data-testid="gtp2s4-outlook"' in html
    assert "Outlook + Projection Summary" in html
    assert "Over Probability" in html and "61.2%" in html
    assert "Under Probability" in html and "38.8%" in html
    assert "Projected Total" in html and "64.7" in html
    assert "Market Line" in html and "59.5" in html
    assert "Edge" in html and "+5.2" in html
    assert "Confidence" in html and "79% • Grade B" in html


def test_step4_is_display_only_and_preserves_all_frozen_predecessors() -> None:
    step4 = _load_module()
    assert step4.STEP2_FREEZE_TOKEN == "CFB_GAME_TOTAL_PAGE2_V1_STEP2_MATCHUP_HERO_PHX_FROZEN"
    assert step4.STEP3_FREEZE_TOKEN == "CFB_GAME_TOTAL_PAGE2_V1_STEP3_INTEGRATED_FLOW_FROZEN"
    assert step4.FREEZE_TOKEN == "CFB_GAME_TOTAL_PAGE2_V1_STEP4_OUTLOOK_SUMMARY_FROZEN"
    assert step4.MAY_MODIFY_PAGE1 is False
    assert step4.MAY_MODIFY_PROJECTION is False
    assert step4.MAY_MODIFY_PROBABILITY is False
    assert step4.MAY_MODIFY_MODEL is False
    assert step4.MAY_MODIFY_MARKET_OWNERSHIP is False
    assert step4.NETWORK_CALLS_ADDED == 0
    assert step4.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0

    source = MODULE.read_text(encoding="utf-8").lower()
    assert "requests." not in source
    assert "httpx." not in source
    assert "urllib.request" not in source


def test_step4_missing_values_fail_soft_without_data_limited_copy() -> None:
    step4 = _load_module()
    html = step4.build_outlook_projection_summary_html(
        over_probability=None,
        under_probability=None,
        projected_total=None,
        market_line=None,
        edge=None,
        confidence_label=None,
    )

    assert html.count("—") >= 6
    assert "data limited" not in html.lower()
    assert "pending" not in html.lower()


def test_step4_escapes_text_and_is_mobile_responsive() -> None:
    step4 = _load_module()
    html = step4.build_outlook_projection_summary_html(
        over_probability="61%",
        under_probability="39%",
        projected_total="64.7",
        market_line="59.5",
        edge="+5.2",
        confidence_label='<script>alert("x")</script>',
    )

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "@media(max-width:760px)" in html
    assert "@media(max-width:480px)" in html
