from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V8 = ROOT / "cfb_game_total_clean_page_v8.py"


def _source() -> str:
    return V8.read_text(encoding="utf-8")


def test_v8_is_additive_over_frozen_v7() -> None:
    source = _source()
    assert 'FROZEN_PRESENTATION = "cfb_game_total_clean_page_v7"' in source
    assert "import cfb_game_total_clean_page_v7 as prior" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source


def test_v8_uses_existing_step11_step12_truth_only() -> None:
    source = _source()
    assert 'step11_ready = bool(raw.get("ready"))' in source
    assert 'step12_ready = bool(final.get("ready"))' in source
    assert 'raw.get("projected_combined_total")' in source
    assert 'final.get("projected_combined_total")' in source
    assert 'final.get("core_50_range")' in source
    assert 'final.get("most_likely_band")' in source
    assert 'final.get("grade")' in source
    assert 'final.get("forecast_strength")' in source
    assert "slate.analyze_game" not in source
    assert "scan_slate" not in source


def test_v8_has_compact_step11_step12_and_final_summary_cards() -> None:
    source = _source()
    for marker in (
        'data-testid="gt156-step11-card"',
        'data-testid="gt156-step12-card"',
        'data-testid="gt156-final-summary"',
        "STEP 11 • DISTRIBUTION",
        "STEP 12 • FINAL SYNTHESIS",
        "FINAL • MODEL SUMMARY",
    ):
        assert marker in source


def test_v8_preserves_deep_evidence_in_inherited_collapsed_expanders() -> None:
    source = _source()
    assert "st.expander(" not in source
    assert "return prior.render_game_total_hub(" in source
    assert "status_owner._status_cards = _compact_model_summary" in source
    assert "status_owner._status_cards = original_status_cards" in source


def test_v8_mobile_cards_reflow_to_one_column() -> None:
    source = _source()
    assert "@media(max-width:760px)" in source
    assert ".gt156-model-grid{grid-template-columns:1fr}" in source
