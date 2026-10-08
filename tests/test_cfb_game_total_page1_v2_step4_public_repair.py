from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
WRAPPER = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page1_v2_step4_public_repair.py"


def test_public_repair_wrapper_exists_and_is_entrypoint_owner() -> None:
    assert WRAPPER.exists(), "Step-4 public repair wrapper is missing"
    app = APP.read_text(encoding="utf-8")
    assert (
        "from streamlit_memory_lazy_router_cfb_game_total_page1_v2_step4_public_repair "
        "import record_bootstrap_import_ms, render_app"
    ) in app


def test_public_repair_targets_the_actual_late_v21_owner() -> None:
    source = WRAPPER.read_text(encoding="utf-8")
    assert (
        "import streamlit_memory_lazy_router_wnba_pra_repair_v1_step7_final_integration as prior"
        in source
    )
    assert "import streamlit_memory_lazy_router_v181 as game_total_router" in source
    assert "import cfb_game_total_clean_page_v21 as v21_owner" in source
    assert "import cfb_game_total_clean_page_v38 as step4" in source
    assert (
        "v21_owner._game_total_hero_html_v21 = step4._step4_prediction_market_html_v38"
        in source
    )
    assert "v21_owner._game_total_hero_html_v21 = original" in source


def test_public_repair_is_exact_route_only_and_preserves_frozen_math() -> None:
    source = WRAPPER.read_text(encoding="utf-8")
    assert "if not game_total_router._game_total_route_active():" in source
    assert "return prior.render_app()" in source
    assert "MAY_MODIFY_OTHER_SPORTS = False" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert 'FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_repair_v1_step7_final_integration"' in source


def test_v38_and_v21_frozen_sources_are_not_edited_by_this_repair() -> None:
    source = WRAPPER.read_text(encoding="utf-8")
    assert "_game_total_hero_html_v21" in source
    assert "_step4_prediction_market_html_v38" in source
    # The repair owns only runtime symbol substitution. Frozen source files remain untouched.
    assert "NETWORK_CALLS_ADDED = 0" in source
