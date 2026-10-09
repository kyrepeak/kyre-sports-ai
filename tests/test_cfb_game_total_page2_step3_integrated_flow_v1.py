from __future__ import annotations

from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "cfb_game_total_page2_step3_integrated_flow_v1.py"


def _load_module():
    assert MODULE.is_file(), "Page-2 Step-3 integrated-flow module must exist before GREEN"
    spec = importlib.util.spec_from_file_location("cfb_gt_page2_step3", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_step3_integrated_flow_component_exists_before_green() -> None:
    assert MODULE.is_file(), "Page-2 Step-3 integrated-flow module must exist before GREEN"


def test_step3_flow_has_five_tappable_owned_sections() -> None:
    step3 = _load_module()
    assert step3.FLOW_STEPS == (
        (1, "Outlook", "gtp2-outlook"),
        (2, "Team Snapshot", "gtp2-team-snapshot"),
        (3, "Trends", "gtp2-trends"),
        (4, "Line Lab", "gtp2-line-lab"),
        (5, "Best Bet", "gtp2-best-bet"),
    )

    html = step3.build_integrated_game_total_flow_html(active_step=1)
    assert 'data-testid="gtp2s3-flow"' in html
    assert html.count('class="gtp2s3-step') == 5
    assert html.count('aria-current="step"') == 1
    for number, label, anchor in step3.FLOW_STEPS:
        assert f">{number}<" in html
        assert label in html
        assert f'href="#{anchor}"' in html


def test_step3_active_step_is_accessible_and_validated() -> None:
    step3 = _load_module()
    html = step3.build_integrated_game_total_flow_html(active_step=4)
    assert 'data-active-step="4"' in html
    assert 'href="#gtp2-line-lab" aria-current="step"' in html

    try:
        step3.build_integrated_game_total_flow_html(active_step=0)
    except ValueError as exc:
        assert "active_step" in str(exc)
    else:
        raise AssertionError("invalid Step-3 active_step must fail closed")


def test_step3_is_presentation_only_and_preserves_step2() -> None:
    step3 = _load_module()
    assert step3.STEP2_FREEZE_TOKEN == "CFB_GAME_TOTAL_PAGE2_V1_STEP2_MATCHUP_HERO_PHX_FROZEN"
    assert step3.FREEZE_TOKEN == "CFB_GAME_TOTAL_PAGE2_V1_STEP3_INTEGRATED_FLOW_FROZEN"
    assert step3.MAY_MODIFY_PAGE1 is False
    assert step3.MAY_MODIFY_PROJECTION is False
    assert step3.MAY_MODIFY_PROBABILITY is False
    assert step3.MAY_MODIFY_MODEL is False
    assert step3.MAY_MODIFY_MARKET_OWNERSHIP is False
    assert step3.NETWORK_CALLS_ADDED == 0
    assert step3.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0

    source = MODULE.read_text(encoding="utf-8")
    assert "overflow-x:auto" in source
    assert "javascript:" not in source.lower()
    assert "requests." not in source
    assert "httpx." not in source
