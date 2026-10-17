from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LINE_LAB = ROOT / "cfb_game_total_page2_line_lab_v2.py"
PAGE2 = ROOT / "cfb_game_total_page2_complete_repair_r1.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_complete_repair_r1.py"
APP = ROOT / "app.py"


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
    assert "install_page2_live_data_repair" in src
    assert "cfb_game_total_page2_network_free_v2" not in src
    assert "MULTI_SOURCE_REQUIRED = True" in src


def test_page2_has_canonical_back_to_page1_and_selected_event_identity() -> None:
    src = _text(PAGE2)
    assert "?sport=cfb&amp;market=game-total" in src
    assert "Back to CFB Game Totals" in src
    assert "data-event-id" in src
    assert "SELECTED_GAME_ONLY = True" in src


def test_page2_replaces_legacy_tail_and_formats_expected_total_cleanly() -> None:
    src = _text(PAGE2)
    assert "LEGACY_TAIL_SUPPRESSED = True" in src
    assert "gt204-team-evidence" in src
    assert "data-testid=\"gtp2r1-team-evidence\"" in src
    assert "format_optional_number" in src
    assert "</div>" not in src.split("STRAY_MARKUP_GUARD =", 1)[-1][:80]


def test_router_overlay_is_additive_and_restores_the_single_cfb_runtime_seam() -> None:
    src = _text(ROUTER)
    assert "import streamlit_memory_lazy_router_universal_nav_v2 as prior" in src
    assert "import streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_frozen_v1 as cfb_fast" in src
    assert 'PAGE2_RUNTIME = "cfb_game_total_page2_complete_repair_r1"' in src
    assert "original_runtime = cfb_fast.SAME_PAGE_RUNTIME" in src
    assert "cfb_fast.SAME_PAGE_RUNTIME = PAGE2_RUNTIME" in src
    assert "cfb_fast.SAME_PAGE_RUNTIME = original_runtime" in src


def test_app_activates_additive_page2_repair_without_touching_page1_owner() -> None:
    app = _text(APP)
    assert "from streamlit_memory_lazy_router_cfb_game_total_page2_complete_repair_r1 import record_bootstrap_import_ms, render_app" in app
    router = _text(ROUTER)
    assert "cfb_game_total_clean_page_v45" not in router
    assert "MAY_MODIFY_PAGE1 = False" in router
