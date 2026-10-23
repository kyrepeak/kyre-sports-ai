from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TERMINAL = ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_loading_progress_v1.py"
APP = ROOT / "app.py"
PRIOR = ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_navigation_speed_repair_v1.py"


def test_loading_progress_terminal_is_thin_successor_over_current_repair_terminal() -> None:
    assert TERMINAL.exists()
    source = TERMINAL.read_text(encoding="utf-8")
    assert "import streamlit_memory_lazy_router_universal_runtime_v5_navigation_speed_repair_v1 as prior" in source
    assert "from universal_page_experience_runtime_v4 import render_page_experience_app_v4" in source
    assert "resolve_destination = prior.resolve_destination" in source
    assert "frozen_runtime = prior.frozen_runtime" in source
    assert "record_bootstrap_import_ms = prior.record_bootstrap_import_ms" in source
    assert "return render_page_experience_app_v4(frozen_runtime)" in source


def test_prior_terminal_still_owns_nba_pra_cfb_top_picks_and_nfl_rushing_fixes() -> None:
    source = PRIOR.read_text(encoding="utf-8")
    nba_import = "import streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1 as prior"
    frozen_import = "import streamlit_memory_lazy_router_universal_runtime_v5 as frozen_runtime"
    assert source.index(nba_import) < source.index(frozen_import)
    assert 'route.sport_id == "cfb" and route.market_id == "top-picks"' in source
    assert "cfb_top_picks_page_v19" in source
    assert 'route.sport_id == "nfl" and route.market_id == "rushing-yards"' in source
    assert "canonical_loader.resolve_destination(route)" in source


def test_app_activates_loading_progress_terminal() -> None:
    source = APP.read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_universal_runtime_v5_loading_progress_v1" in source
