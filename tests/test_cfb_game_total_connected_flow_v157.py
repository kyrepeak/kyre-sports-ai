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
    assert "evidence_owner._render_compact_team_cards(away_evidence, home_evidence)" in source
    assert "evidence_owner._render_raw_team_evidence(away_evidence, home_evidence)" in source


def test_v9_puts_steps_1_through_12_in_one_connected_flow() -> None:
    import cfb_game_total_clean_page_v9 as page

    statuses = {step: "READY" for step in range(1, 11)}
    details = {step: f"Step {step} verified" for step in range(1, 11)}
    raw = {
        "ready": True,
        "projected_combined_total": 52.4,
    }
    final = {
        "ready": True,
        "projected_combined_total": 52.4,
        "core_50_range": {"low": 48, "high": 57},
        "most_likely_band": {"label": "49–56"},
        "grade": "A",
        "forecast_strength": 0.78,
    }

    html = page._combined_flow_html(statuses, details, raw, final)

    assert 'data-testid="gt157-connected-all-steps"' in html
    for step in range(1, 13):
        assert f'data-testid="gt157-step-{step}"' in html
    assert "STEP 11 • Distribution" in html
    assert "STEP 12 • Final Synthesis" in html
    assert "TOP-5 • SLATE SCANNER" in html
    assert "Frozen ranking unchanged" in html


def test_v9_renders_connected_flow_directly_without_monkeypatching() -> None:
    source = (ROOT / "cfb_game_total_clean_page_v9.py").read_text(encoding="utf-8")

    assert "statuses = step_owner._existing_step_status(identity, away_evidence, home_evidence, display_game)" in source
    assert "details = step_owner._step_details(identity, away_evidence, home_evidence, statuses)" in source
    assert "st.markdown(_combined_flow_html(statuses, details, raw, final), unsafe_allow_html=True)" in source
    assert "_render_steps_1_10_rail =" not in source
    assert "_status_cards =" not in source
    assert "render_game_total_hub(section_header" in source


def test_v9_reuses_exact_frozen_model_and_top5_owners() -> None:
    source = (ROOT / "cfb_game_total_clean_page_v9.py").read_text(encoding="utf-8")

    assert "selected_result = frozen_page.slate.analyze_game(game, selected_day)" in source
    assert "runtime_display.reconcile_display_bundle(" in source
    assert "frozen_page.slate.scan_slate(games, selected_day)" in source
    assert "frozen_page.final_model.rank_slate(rows, limit=5)" in source
    assert "projected_combined_total" in source
    assert "core_50_range" in source
    assert "most_likely_band" in source
    assert "forecast_strength" in source


def test_v9_keeps_deep_evidence_collapsed_and_sportsbook_influence_zero() -> None:
    source = (ROOT / "cfb_game_total_clean_page_v9.py").read_text(encoding="utf-8")

    assert 'st.expander("🔬 Raw Steps 1–10 evidence", expanded=False)' in source
    assert 'st.expander("📊 Deep model evidence • Step 11 distribution", expanded=False)' in source
    assert 'st.expander("🏁 Deep model evidence • Step 12 final synthesis", expanded=False)' in source
    assert 'st.expander("🏆 Top-5 slate scanner", expanded=False)' in source
    assert "sportsbook projection influence 0.0%" in source
