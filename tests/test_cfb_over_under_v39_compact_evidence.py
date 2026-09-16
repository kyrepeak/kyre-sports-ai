from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "cfb_over_under_clean_page_v39.py"


def _source() -> str:
    assert PAGE.exists(), "V39 compact evidence renderer must exist"
    return PAGE.read_text(encoding="utf-8")


def test_v39_is_additive_over_v38_and_keeps_frozen_boundaries() -> None:
    source = _source()
    assert 'FROZEN_PRESENTATION = "cfb_over_under_clean_page_v38"' in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "frozen_page.render_over_under_hub" not in source
    assert "runtime_slate.analyze_game(" in source


def test_v39_compact_foundation_replaces_legacy_giant_identity_renderer() -> None:
    source = _source()
    assert 'data-testid="ou39-matchup-foundation"' in source
    assert ".ou39-foundation-logo{width:52px;height:52px" in source
    assert "Coach unavailable" not in source
    assert "KICKOFF" in source
    assert "VENUE" in source
    assert "BROADCAST" in source
    assert "STATUS" in source

    render_body = source.split("def render_over_under_hub", 1)[1]
    assert "_presentation._step1(" not in render_body
    assert "_presentation._step2(" not in render_body


def test_v39_steps_5_to_10_and_model_audit_are_collapsed() -> None:
    source = _source()
    assert "def _render_compact_step_expanders" in source
    assert 'st.expander(f"Step {step} • {title}", expanded=False)' in source
    assert 'st.expander("Model Audit", expanded=False)' in source
    assert "Frozen O/U math • Mutation OFF • Sportsbook 0.0%" in source


def test_v39_mobile_layout_reflows_without_giant_step_logos() -> None:
    source = _source()
    assert "@media(max-width:760px)" in source
    assert "grid-template-columns:1fr" in source
    assert "width:300px" not in source
    assert "height:300px" not in source
