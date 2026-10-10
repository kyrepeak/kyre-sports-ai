from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "cfb_game_total_page2_step7_line_lab_best_bet_v1.py"


def _load_module():
    assert MODULE.is_file(), "Page-2 Step-7 Line Lab + Best Bet module must exist before GREEN"
    spec = importlib.util.spec_from_file_location("cfb_gt_page2_step7", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _scenarios():
    return [
        {"line": 55.5, "over_probability": "67%", "under_probability": "33%"},
        {"line": 58.5, "over_probability": "61%", "under_probability": "39%"},
        {"line": 61.5, "over_probability": "54%", "under_probability": "46%"},
    ]


def _recommendation():
    return {
        "side": "OVER",
        "line": 58.5,
        "probability": "61%",
        "expected_total": 63.8,
        "edge": "+5.3",
        "confidence": "Strong",
        "rationale": "Pace and red-zone finishing support the higher-scoring path.",
    }


def _sample_html():
    step7 = _load_module()
    return step7.build_line_lab_best_bet_html(
        line_scenarios=_scenarios(),
        selected_line=58.5,
        recommendation=_recommendation(),
    )


def test_step7_module_exists_before_green() -> None:
    assert MODULE.is_file(), "Page-2 Step-7 Line Lab + Best Bet module must exist before GREEN"


def test_step7_renders_reserved_line_lab_and_best_bet_anchors() -> None:
    html = _sample_html()
    assert 'id="gtp2-line-lab"' in html
    assert 'data-testid="gtp2s7-line-lab"' in html
    assert 'id="gtp2-best-bet"' in html
    assert 'data-testid="gtp2s7-best-bet"' in html
    assert "Line Lab" in html
    assert "Best Bet" in html


def test_step7_line_lab_uses_only_precomputed_scenarios() -> None:
    html = _sample_html()
    for line in ("55.5", "58.5", "61.5"):
        assert line in html
    for probability in ("67%", "33%", "61%", "39%", "54%", "46%"):
        assert probability in html
    assert 'data-line-option-count="3"' in html
    assert 'data-selected-line="58.5"' in html
    assert 'data-selected-over="61%"' in html
    assert 'data-selected-under="39%"' in html


def test_step7_line_choices_switch_visible_precomputed_scenario_without_script() -> None:
    html = _sample_html()
    assert html.count('type="radio" name="gtp2s7-line-choice"') == 3
    for index, line in enumerate(("55.5", "58.5", "61.5")):
        assert f'id="gtp2s7-line-{index}"' in html
        assert f'for="gtp2s7-line-{index}"' in html
        assert f'class="gtp2s7-scenario gtp2s7-scenario-{index}"' in html
        assert f'data-scenario-line="{line}"' in html
        selector = (
            f'#gtp2s7-line-{index}:checked~.gtp2s7-scenario-stage '
            f'.gtp2s7-scenario-{index}' + '{display:grid}'
        )
        assert selector in html
    assert 'id="gtp2s7-line-1" type="radio" name="gtp2s7-line-choice" checked' in html
    assert "<script" not in html.lower()


def test_step7_best_bet_renders_owned_recommendation_values() -> None:
    html = _sample_html()
    for value in (
        "OVER",
        "58.5",
        "61%",
        "63.8",
        "+5.3",
        "Strong",
        "Pace and red-zone finishing support the higher-scoring path.",
    ):
        assert value in html
    for label in ("Recommendation", "Expected Total", "Edge", "Confidence"):
        assert label in html


def test_step7_is_display_only_and_preserves_frozen_predecessors() -> None:
    step7 = _load_module()
    assert step7.STEP3_FREEZE_TOKEN == "CFB_GAME_TOTAL_PAGE2_V1_STEP3_INTEGRATED_FLOW_FROZEN"
    assert step7.STEP4_FREEZE_TOKEN == "CFB_GAME_TOTAL_PAGE2_V1_STEP4_OUTLOOK_SUMMARY_FROZEN"
    assert step7.STEP5_FREEZE_TOKEN == "CFB_GAME_TOTAL_PAGE2_V1_STEP5_TEAM_SNAPSHOT_KEY_DRIVERS_FROZEN"
    assert step7.STEP6_FREEZE_TOKEN == "CFB_GAME_TOTAL_PAGE2_V1_STEP6_TRENDS_SCORING_BREAKDOWN_FROZEN"
    assert step7.FREEZE_TOKEN == "CFB_GAME_TOTAL_PAGE2_V1_STEP7_LINE_LAB_BEST_BET_FROZEN"
    assert step7.MAY_MODIFY_PAGE1 is False
    assert step7.MAY_MODIFY_PROJECTION is False
    assert step7.MAY_MODIFY_PROBABILITY is False
    assert step7.MAY_MODIFY_MODEL is False
    assert step7.MAY_MODIFY_MARKET_OWNERSHIP is False
    assert step7.RECOMMENDATION_LOGIC_ADDED is False
    assert step7.NETWORK_CALLS_ADDED == 0
    assert step7.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0

    source = MODULE.read_text(encoding="utf-8").lower()
    assert "requests." not in source
    assert "httpx." not in source
    assert "urllib.request" not in source


def test_step7_missing_and_nonfinite_values_fail_soft() -> None:
    step7 = _load_module()
    html = step7.build_line_lab_best_bet_html(
        line_scenarios=[
            {
                "line": Decimal("NaN"),
                "over_probability": Decimal("Infinity"),
                "under_probability": Decimal("-Infinity"),
            },
        ],
        selected_line=Decimal("NaN"),
        recommendation={
            "side": None,
            "line": Decimal("Infinity"),
            "probability": Decimal("NaN"),
            "expected_total": None,
            "edge": Decimal("-Infinity"),
            "confidence": None,
            "rationale": None,
        },
    )
    assert html.count("—") >= 10
    lowered = html.lower()
    assert "nan" not in lowered
    assert "infinity" not in lowered
    assert "data limited" not in lowered
    assert "mock data" not in lowered
    assert "pending" not in lowered


def test_step7_escapes_text_and_is_responsive() -> None:
    step7 = _load_module()
    html = step7.build_line_lab_best_bet_html(
        line_scenarios=[
            {"line": '<script>alert(1)</script>', "over_probability": "60%", "under_probability": "40%"},
        ],
        selected_line='<script>alert(1)</script>',
        recommendation={
            "side": '<img src=x onerror=alert(1)>',
            "rationale": '<script>alert("x")</script>',
        },
    )
    assert "<script>" not in html
    assert "<img" not in html
    assert "&lt;script&gt;" in html
    assert "@media(max-width:760px)" in html
    assert "@media(max-width:480px)" in html
