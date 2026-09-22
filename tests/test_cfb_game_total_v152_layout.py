from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "cfb_game_total_clean_page_v6.py"
V7 = ROOT / "cfb_game_total_clean_page_v7.py"
V8 = ROOT / "cfb_game_total_clean_page_v8.py"


def _source() -> str:
    return PAGE.read_text(encoding="utf-8")


def _v7_source() -> str:
    return V7.read_text(encoding="utf-8")


def _v8_source() -> str:
    return V8.read_text(encoding="utf-8")


def test_v6_is_additive_over_closed_v5_and_keeps_frozen_boundaries() -> None:
    source = _source()
    assert 'FROZEN_PRESENTATION = "cfb_game_total_clean_page_v5"' in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "selected_result = frozen_page.slate.analyze_game(game, selected_day)" in source
    assert "runtime_display.reconcile_display_bundle(" in source


def test_compact_dashboard_has_required_visual_sections() -> None:
    source = _source()
    for marker in (
        'data-testid="gt152-monster-matchup-hero"',
        'data-testid="gt152-compact-game-strip"',
        'data-testid="gt152-scoring-defense"',
        "MONSTER MATCHUP",
        "SCORING VS DEFENSE",
        "V152 PRODUCTION ACTIVE",
    ):
        assert marker in source


def test_compact_visual_hierarchy_precedes_model_and_deep_audits() -> None:
    source = _source()
    hero = source.index("_monster_matchup_hero(")
    game_strip = source.index("_compact_game_strip(", hero)
    scoring = source.index("_scoring_defense_summary(", game_strip)
    evidence = source.index("_render_steps_1_10_rail(", scoring)
    raw_evidence = source.index('st.expander("🔬 Raw Steps 1–10 evidence', evidence)
    model = source.index("_status_cards(", raw_evidence)
    deep = source.index('st.expander("📊 Deep model evidence', model)
    top5 = source.index('st.expander("🏆 Top-5 slate scanner', deep)
    assert hero < game_strip < scoring < evidence < raw_evidence < model < deep < top5


def test_deep_sections_stay_collapsed_and_mobile_reflows() -> None:
    source = _source()
    assert 'st.expander("🔬 Raw Steps 1–10 evidence", expanded=False)' in source
    assert 'st.expander("📊 Deep model evidence • Step 11 distribution", expanded=False)' in source
    assert 'st.expander("🏁 Deep model evidence • Step 12 final synthesis", expanded=False)' in source
    assert 'st.expander("🏆 Top-5 slate scanner", expanded=False)' in source
    assert "@media(max-width:760px)" in source
    assert "grid-template-columns:1fr" in source
    # Responsive media-query max-width is required. What we reject is a fixed
    # outer dashboard width that would make the phone layout scatter/overflow.
    assert not re.search(r"\.gt152-shell\{[^}]*max-width:", source)
    assert not re.search(r"\.gt152-hero\{[^}]*max-width:", source)


def test_color_roles_are_explicit_without_green_border_everywhere() -> None:
    source = _source()
    for token in (
        "--gt-green:",
        "--gt-red:",
        "--gt-amber:",
        "--gt-blue:",
        "--gt-purple:",
        "--gt-gray:",
    ):
        assert token in source
    assert "border:1px solid var(--gt-green)" not in source


def test_connected_evidence_shell_wraps_existing_flow_without_changing_math() -> None:
    source = _source()
    assert 'data-testid="gt153-connected-evidence-shell"' in source
    assert "with st.container(border=True):" in source

    shell = source.index('data-testid="gt153-connected-evidence-shell"')
    steps = source.index("_render_steps_1_10_rail(", shell)
    raw_evidence = source.index('st.expander("🔬 Raw Steps 1–10 evidence', steps)
    evidence = source.index("prior._render_evidence_center(", raw_evidence)
    model = source.index("_status_cards(", evidence)
    step11 = source.index('st.expander("📊 Deep model evidence', model)
    step12 = source.index('st.expander("🏁 Deep model evidence', step11)
    top5 = source.index('st.expander("🏆 Top-5 slate scanner', step12)
    assert shell < steps < raw_evidence < evidence < model < step11 < step12 < top5

    # Step 2 is presentation-only. The frozen model must still run exactly once
    # on the untouched selected game before display reconciliation.
    assert source.count("selected_result = frozen_page.slate.analyze_game(game, selected_day)") == 1
    assert source.index("selected_result = frozen_page.slate.analyze_game(game, selected_day)") < source.index(
        "runtime_display.reconcile_display_bundle("
    )
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source


def test_step2_has_one_compact_steps_1_10_rail_with_approved_labels() -> None:
    source = _source()
    assert 'data-testid="gt154-steps-1-10-rail"' in source
    assert 'data-testid="gt154-step-summary"' in source
    assert "def _render_steps_1_10_rail(" in source

    approved_labels = (
        "Team Identity",
        "Team Profile",
        "Matchup",
        "Pace",
        "Explosive Plays",
        "Red Zone",
        "Third Down",
        "Turnovers",
        "Environment",
        "History",
    )
    for number, label in enumerate(approved_labels, start=1):
        assert f'({number}, "{label}"' in source
        assert f'gt154-step-{number}' in source


def test_step2_cards_use_right_status_badges_and_preserve_ready_check_truth() -> None:
    source = _source()
    assert ".gt154-step-status" in source
    assert "margin-left:auto" in source
    assert "READY" in source
    assert "CHECK" in source
    assert "_existing_step_status(" in source
    # Step 10 History must fail closed when the existing history evidence is absent.
    assert '10: "CHECK"' in source


def test_step2_raw_evidence_is_collapsed_below_compact_story() -> None:
    source = _source()
    rail = source.index("_render_steps_1_10_rail(")
    raw = source.index('st.expander("🔬 Raw Steps 1–10 evidence", expanded=False)', rail)
    legacy = source.index("prior._render_evidence_center(", raw)
    summary = source.index('data-testid="gt154-step-summary"')
    assert summary < raw < legacy


def test_step3_v7_is_additive_over_closed_v6_and_keeps_frozen_boundaries() -> None:
    source = _v7_source()
    assert 'FROZEN_PRESENTATION = "cfb_game_total_clean_page_v6"' in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "import cfb_game_total_clean_page_v6 as prior" in source


def test_step3_team_cards_join_connected_story_before_raw_drawer() -> None:
    source = _v7_source()
    assert 'data-testid="gt155-team-evidence-flow"' in source
    assert 'data-testid="gt155-away-team-card"' in source
    assert 'data-testid="gt155-home-team-card"' in source
    assert "_ORIGINAL_STEPS_1_10(identity, away, home, display_game)" in source
    assert "_render_compact_team_cards(away, home)" in source
    assert source.index("_ORIGINAL_STEPS_1_10(identity, away, home, display_game)") < source.index(
        "_render_compact_team_cards(away, home)"
    )


def test_step3_uses_one_existing_raw_drawer_for_both_full_team_bodies() -> None:
    source = _v7_source()
    assert "def _render_raw_team_evidence(" in source
    assert source.count("prior.prior._render_team_evidence_body(") == 2
    assert "st.expander(" not in source
    assert "prior.prior._render_evidence_center = _render_raw_team_evidence" in source


def test_step3_hooks_are_restored_after_render() -> None:
    source = _v7_source()
    assert "finally:" in source
    assert "prior._render_steps_1_10_rail = original_steps" in source
    assert "prior.prior._render_evidence_center = original_evidence" in source


def test_step4_v8_compacts_existing_model_truth_without_new_math() -> None:
    source = _v8_source()
    assert 'FROZEN_PRESENTATION = "cfb_game_total_clean_page_v7"' in source
    assert "import cfb_game_total_clean_page_v7 as prior" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert 'step11_ready = bool(raw.get("ready"))' in source
    assert 'step12_ready = bool(final.get("ready"))' in source
    assert "slate.analyze_game" not in source
    assert "scan_slate" not in source


def test_step4_v8_has_connected_step11_step12_and_final_summary() -> None:
    source = _v8_source()
    for marker in (
        'data-testid="gt156-step11-card"',
        'data-testid="gt156-step12-card"',
        'data-testid="gt156-final-summary"',
        "STEP 11 • DISTRIBUTION",
        "STEP 12 • FINAL SYNTHESIS",
        "FINAL • MODEL SUMMARY",
    ):
        assert marker in source
    assert "st.expander(" not in source
    assert "status_owner._status_cards = _compact_model_summary" in source
    assert "status_owner._status_cards = original_status_cards" in source
    assert "@media(max-width:760px)" in source
    assert ".gt156-model-grid{grid-template-columns:1fr}" in source


def test_step5_router_targets_v8_and_top5_stays_in_connected_shell() -> None:
    router = (ROOT / "streamlit_memory_lazy_router_v152.py").read_text(encoding="utf-8")
    assert 'ACTIVE_PAGE = "cfb_game_total_clean_page_v8"' in router

    source = _source()
    shell = source.index('data-testid="gt153-connected-evidence-shell"')
    top5 = source.index('st.expander("🏆 Top-5 slate scanner", expanded=False)', shell)
    assert shell < top5
