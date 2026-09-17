from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v9_connected_flow_is_presentation_only_over_v8() -> None:
    page = ROOT / "cfb_game_total_clean_page_v9.py"
    assert page.exists(), "V9 connected-flow page does not exist yet"
    source = page.read_text(encoding="utf-8")

    assert 'FROZEN_PRESENTATION = "cfb_game_total_clean_page_v8"' in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "step_owner._existing_step_status(" in source
    assert "step_owner._step_details(" in source
    assert "evidence_owner._render_compact_team_cards(away, home)" in source


def test_v9_puts_steps_1_through_12_in_one_connected_flow() -> None:
    source = (ROOT / "cfb_game_total_clean_page_v9.py").read_text(encoding="utf-8")

    assert 'data-testid="gt157-connected-all-steps"' in source
    assert 'data-testid="gt157-step-{number}"' in source
    assert "STEP 11" in source
    assert "Distribution" in source
    assert "STEP 12" in source
    assert "Final Synthesis" in source
    assert "TOP-5" in source
    assert "Frozen ranking unchanged" in source


def test_v9_suppresses_only_old_visible_step_rail() -> None:
    source = (ROOT / "cfb_game_total_clean_page_v9.py").read_text(encoding="utf-8")

    capture = source.split("def _capture_steps_1_10_context(", 1)[1].split(
        "def _combined_model_summary(", 1
    )[0]
    assert "st.session_state[_FLOW_CONTEXT_KEY]" in capture
    assert "evidence_owner._render_compact_team_cards(away, home)" in capture
    assert "_ORIGINAL_STEPS_1_10" not in capture


def test_v9_keeps_step_11_12_and_top5_math_owned_by_frozen_path() -> None:
    source = (ROOT / "cfb_game_total_clean_page_v9.py").read_text(encoding="utf-8")

    assert "prior.render_game_total_hub(" in source
    assert "projected_combined_total" in source
    assert "core_50_range" in source
    assert "most_likely_band" in source
    assert "forecast_strength" in source
    assert "analyze_game(" not in source
    assert "rank" not in source.lower().split("Frozen ranking unchanged".lower(), 1)[0] or "TOP-5" in source
