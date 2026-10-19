from __future__ import annotations

import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "cfb_over_under_clean_page_v40.py"
LOADER = ROOT / "universal_runtime_v5_loader_v18.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_universal_runtime_v5.py"


def test_v40_is_additive_presentation_only_and_keeps_model_frozen() -> None:
    source = PAGE.read_text(encoding="utf-8")
    assert "import cfb_over_under_clean_page_v39 as frozen_page" in source
    assert 'FROZEN_PRESENTATION = "cfb_over_under_clean_page_v39"' in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "runtime_slate = frozen_page.runtime_slate" in source
    assert "final_model = frozen_page.final_model" in source


def test_v40_decision_state_reads_certified_result_without_parallel_probability_math() -> None:
    page = importlib.import_module("cfb_over_under_clean_page_v40")
    result = {
        "raw": {
            "projected_total": 40.7,
            "model_lean": "UNDER",
            "under_probability": 0.639,
            "over_probability": 0.361,
        },
        "final": {"selection": "UNDER", "selection_probability": 0.639},
    }
    state = page._decision_state(result, 45.5)
    assert state["selection"] == "UNDER"
    assert state["projected_total"] == 40.7
    assert state["analysis_line"] == 45.5
    assert state["edge_points"] == 4.8
    assert state["selection_probability"] == 0.639
    assert state["over_probability"] == 0.361
    assert state["under_probability"] == 0.639


def test_v40_has_decision_first_sections_and_hides_engineering_clutter() -> None:
    source = PAGE.read_text(encoding="utf-8")
    for label in (
        "MODEL PICK",
        "LINE LAB",
        "WHY THE MODEL LIKES IT",
        "WHAT MOVES THE TOTAL",
        "TEAM MATCHUP",
        "MARKET INTELLIGENCE",
        "ADVANCED ANALYTICS",
        "SOURCE & DATA QUALITY",
        "MODEL TRANSPARENCY",
        "DIAGNOSTICS",
    ):
        assert label in source
    assert "trace.compact_caption" not in source
    assert "CLEAN PAGE V39 ACTIVE" not in source
    assert "CFB O/U PERF V1" not in source
    assert "Runtime data {runtime_status}" not in source


def test_v40_line_lab_reuses_analysis_line_as_threshold_only() -> None:
    source = PAGE.read_text(encoding="utf-8")
    assert '"🎚️ Line Lab total"' in source
    assert "step=0.5" in source
    assert "runtime_slate.analyze_game(selected_game, day, float(line))" in source
    assert "0.0% model influence" in source


def test_loader_v18_routes_only_cfb_over_under_to_v40_and_preserves_v17() -> None:
    source = LOADER.read_text(encoding="utf-8")
    assert "import universal_runtime_v5_loader_v17 as prior" in source
    assert 'route.sport_id == "cfb" and route.market_id == "over-under"' in source
    assert 'importlib.import_module("cfb_over_under_clean_page_v40")' in source
    assert "return prior.resolve_destination(route)" in source
    router_source = ROUTER.read_text(encoding="utf-8")
    assert "from universal_runtime_v5_loader_v18 import choose_prefetch, load_destination, resolve_destination" in router_source
