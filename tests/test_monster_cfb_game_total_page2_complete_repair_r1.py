from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LINE_LAB = ROOT / "cfb_game_total_page2_line_lab_v2.py"
PAGE2 = ROOT / "cfb_game_total_page2_complete_repair_r1.py"
ACTIVE_ROUTER = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_v1.py"
PAGE1 = ROOT / "cfb_game_total_clean_page_v45.py"


def _text(path: Path) -> str:
    assert path.exists(), f"required successor is missing: {path.name}"
    return path.read_text(encoding="utf-8")


def _load_line_lab():
    assert LINE_LAB.exists(), "Line Lab V2 must exist before probability tests can run"
    spec = importlib.util.spec_from_file_location("cfb_game_total_page2_line_lab_v2", LINE_LAB)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_line_lab_is_full_zero_to_sixty_half_point_control() -> None:
    src = _text(PAGE2)
    helper = _text(LINE_LAB)
    assert "LINE_MIN = 0.0" in helper
    assert "LINE_MAX = 60.0" in helper
    assert "LINE_STEP = 0.5" in helper
    assert "st.slider(" in src
    assert "min_value=line_lab.LINE_MIN" in src
    assert "max_value=line_lab.LINE_MAX" in src
    assert "step=line_lab.LINE_STEP" in src
    assert "event_id" in src and "line_lab" in src


def test_line_probability_contract_counts_pushes_without_model_rerun() -> None:
    line_lab = _load_line_lab()
    distribution = [
        {"total": 50, "probability": 0.10},
        {"total": 51, "probability": 0.40},
        {"total": 52, "probability": 0.50},
    ]
    whole = line_lab.line_probabilities(distribution, 51.0)
    assert whole == {"over": 0.5, "under": 0.1, "push": 0.4}
    half = line_lab.line_probabilities(distribution, 51.5)
    assert half == {"over": 0.5, "under": 0.5, "push": 0.0}
    assert line_lab.MODEL_RERUNS == 0
    assert line_lab.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0


def test_custom_line_is_analysis_only_and_best_bet_stays_on_verified_market() -> None:
    src = _text(PAGE2)
    assert "CUSTOM_LINE_MAY_MODIFY_BEST_BET = False" in src
    assert "page2._recommendation(raw, final, display_game)" in src
    assert "selected_line" not in src.split("page2._recommendation(raw, final, display_game)")[0][-220:]
    assert "data-line-lab-analysis-only=\"true\"" in src


def test_page2_uses_verified_multi_source_owners_not_network_free_only_bridge() -> None:
    src = _text(PAGE2)
    assert "cfb_game_total_page2_live_data_unified_repair_v1 as live_data" in src
    assert "live_data._live_enrich(payload)" in src
    assert "cfb_game_total_page2_network_free_v2" not in src
    assert "MULTI_SOURCE_REQUIRED = True" in src
    assert "market_truth.enrich_games_with_market_truth" in src
    assert "_fetch_action_json_board" in src


def test_page2_has_canonical_back_to_page1_and_selected_event_identity() -> None:
    src = _text(PAGE2)
    assert "?sport=cfb&amp;market=game-total" in src
    assert "Back to CFB Game Totals" in src
    assert "data-event-id" in src
    assert "SELECTED_GAME_ONLY = True" in src
    assert "sync_id != event_id" in src


def test_page2_replaces_legacy_tail_and_formats_expected_total_cleanly() -> None:
    src = _text(PAGE2)
    assert "LEGACY_TAIL_SUPPRESSED = True" in src
    assert "gt204-team-evidence" in src
    assert "data-testid=\"gtp2r1-team-evidence\"" in src
    assert "format_optional_number" in src
    assert "round(expected, 1)" in src
    assert "STRAY_MARKUP_GUARD" in src


def test_current_router_activates_and_restores_one_page2_runtime_seam() -> None:
    src = _text(ACTIVE_ROUTER)
    assert "import streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_frozen_v1 as prior" in src
    assert 'CFB_PAGE2_RUNTIME = "cfb_game_total_page2_complete_repair_r1"' in src
    assert "original_page2_runtime = prior.SAME_PAGE_RUNTIME" in src
    assert "prior.SAME_PAGE_RUNTIME = CFB_PAGE2_RUNTIME" in src
    assert "prior.SAME_PAGE_RUNTIME = original_page2_runtime" in src
    assert "MAY_MODIFY_PAGE1 = False" in src


def test_current_router_preserves_and_restores_existing_nfl_spread_bridge() -> None:
    src = _text(ACTIVE_ROUTER)
    assert "import nfl_spread_hub_v5 as spread_v5" in src
    assert "def _make_render_nfl_bridge" in src
    assert "original_root_render_nfl = _patch_loaded_router_seams()" in src
    assert "_restore_loaded_router_seams(original_root_render_nfl)" in src
    assert 'ACTIVE_SPREAD_PAGE = "nfl_spread_hub_v5"' in src
    assert "MAY_MODIFY_OTHER_SPORTS = False" in src


def test_page1_owner_is_not_edited_by_the_successor_contract() -> None:
    page1 = _text(PAGE1)
    assert "cfb_game_total_page2_complete_repair_r1" not in page1
    page2 = _text(PAGE2)
    assert "MAY_MODIFY_PAGE1 = False" in page2
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in page2
