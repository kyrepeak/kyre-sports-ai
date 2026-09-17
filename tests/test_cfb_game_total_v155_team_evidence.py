from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "cfb_game_total_clean_page_v7.py"


def _source() -> str:
    return PAGE.read_text(encoding="utf-8")


def test_v7_is_presentation_only_over_frozen_v6() -> None:
    source = _source()
    assert "import cfb_game_total_clean_page_v6 as prior" in source
    assert 'FROZEN_PRESENTATION = "cfb_game_total_clean_page_v6"' in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "prior.render_game_total_hub(" in source


def test_v7_adds_compact_two_team_evidence_to_main_flow() -> None:
    source = _source()
    for marker in (
        'data-testid="gt155-team-evidence-flow"',
        'data-testid="gt155-team-evidence-away"',
        'data-testid="gt155-team-evidence-home"',
        "TEAM EVIDENCE",
        "PPG",
        "Allowed / game",
        "Point diff",
        "Recent form",
        "SOS",
        "Data source",
    ):
        assert marker in source


def test_v7_flattens_legacy_team_details_inside_single_existing_drawer() -> None:
    source = _source()
    assert "def _render_flat_team_evidence(" in source
    assert "_render_team_evidence_body(away)" in source
    assert "_render_team_evidence_body(home)" in source
    assert "old_evidence = prior.prior._render_evidence_center" in source
    assert "prior.prior._render_evidence_center = _render_flat_team_evidence" in source
    assert "prior.prior._render_evidence_center = old_evidence" in source
    # V7 must not create another team expander; V6 already owns the one raw drawer.
    assert "st.expander(" not in source


def test_v7_injects_team_cards_after_existing_steps_1_10_without_touching_math() -> None:
    source = _source()
    assert "old_steps = prior._render_steps_1_10_rail" in source
    assert "old_steps(identity, away, home, display_game)" in source
    assert "_render_team_evidence_flow(away, home)" in source
    assert "prior._render_steps_1_10_rail = _render_steps_with_team_evidence" in source
    assert "prior._render_steps_1_10_rail = old_steps" in source


def test_router_targets_v7_for_v155_team_evidence() -> None:
    router = (ROOT / "streamlit_memory_lazy_router_v152.py").read_text(encoding="utf-8")
    assert 'ACTIVE_PAGE = "cfb_game_total_clean_page_v7"' in router
