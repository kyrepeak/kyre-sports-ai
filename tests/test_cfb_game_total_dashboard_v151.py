from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _source(name: str) -> str:
    path = ROOT / name
    assert path.exists(), f"missing required V151 file: {name}"
    return path.read_text(encoding="utf-8")


def test_v151_repairs_display_data_without_touching_frozen_game_total_math():
    source = _source("cfb_game_total_clean_page_v2.py")

    assert 'FROZEN_GAME_TOTAL_HUB = "cfb_game_total_hub_v3"' in source
    assert 'FROZEN_PRESENTATION = "cfb_game_total_clean_page_v1"' in source
    assert "runtime_display.reconcile_runtime" in source
    assert "dict(game)" in source
    assert "frozen_page.slate.analyze_game(game, selected_day)" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source


def test_v151_uses_reconciled_profiles_for_records_logos_and_visible_evidence():
    source = _source("cfb_game_total_clean_page_v2.py")

    assert "display_game, display_away, display_home, display_diag" in source
    assert "prior._hero(display_game, display_away, display_home)" in source
    assert "logo_v3.resolve_visuals(display_game)" in source
    assert "LIVE TEAM EVIDENCE" in source
    assert "PPG" in source
    assert "ALLOWED / GAME" in source
    assert "RECENT FORM" in source
    assert "DATA SOURCE" in source
    assert "Evidence locker" in source


def test_v151_does_not_hide_all_evidence_when_step_11_or_12_is_gated():
    source = _source("cfb_game_total_clean_page_v2.py")

    evidence_index = source.index("LIVE TEAM EVIDENCE")
    step11_index = source.index("Deep model evidence • Step 11")
    assert evidence_index < step11_index
    assert "display_away" in source[evidence_index:step11_index]
    assert "display_home" in source[evidence_index:step11_index]


def test_v151_router_is_additive_over_frozen_v150_and_targets_only_game_total():
    source = _source("streamlit_memory_lazy_router_v151.py")

    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v150"' in source
    assert 'CFB_SPORT_LABEL = "College Football"' in source
    assert 'GAME_TOTAL_MARKET = "Game Total"' in source
    assert 'ACTIVE_PAGE = "cfb_game_total_clean_page_v2"' in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "return prior.render_app()" in source


def test_existing_v149_entry_handoff_advances_only_game_total_to_v151():
    source = _source("streamlit_memory_lazy_router_v149.py")

    assert (
        "from streamlit_memory_lazy_router_v151 import _render_direct_cfb_game_total"
        in source
    )
    assert 'OVER_UNDER_MARKET = "Over/Under"' in source
    assert 'GAME_TOTAL_MARKET = "Game Total"' in source


def test_v151_keeps_model_and_sportsbook_logic_frozen():
    source = _source("cfb_game_total_clean_page_v2.py")

    forbidden = (
        "projected_combined_total =",
        "forecast_strength =",
        "sportsbook_line =",
        "market_probability =",
        "monte_carlo",
    )
    for token in forbidden:
        assert token not in source.lower()
