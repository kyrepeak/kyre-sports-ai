from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "cfb_game_total_clean_page_v6.py"


def _source() -> str:
    return PAGE.read_text(encoding="utf-8")


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
    evidence = source.index("_render_evidence_center(", scoring)
    model = source.index("_status_cards(", evidence)
    deep = source.index('st.expander("📊 Deep model evidence', model)
    top5 = source.index('st.expander("🏆 Top-5 slate scanner', deep)
    assert hero < game_strip < scoring < evidence < model < deep < top5


def test_deep_sections_stay_collapsed_and_mobile_reflows() -> None:
    source = _source()
    assert 'st.expander("📊 Deep model evidence • Step 11 distribution", expanded=False)' in source
    assert 'st.expander("🏁 Deep model evidence • Step 12 final synthesis", expanded=False)' in source
    assert 'st.expander("🏆 Top-5 slate scanner", expanded=False)' in source
    assert "@media(max-width:760px)" in source
    assert "grid-template-columns:1fr" in source
    assert "max-width:" not in source


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


def test_router_targets_v6_only_for_v152_game_total() -> None:
    router = (ROOT / "streamlit_memory_lazy_router_v152.py").read_text(encoding="utf-8")
    assert 'ACTIVE_PAGE = "cfb_game_total_clean_page_v6"' in router
