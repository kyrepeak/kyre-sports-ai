from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
OVERLAY = ROOT / "streamlit_memory_lazy_router_nfl_spread_mobile_repair_v1.py"


def test_production_keeps_existing_mobile_overlay_entrypoint():
    app_source = APP.read_text(encoding="utf-8")
    expected = (
        "from streamlit_memory_lazy_router_nfl_spread_mobile_repair_v1 import "
        "record_bootstrap_import_ms, render_app"
    )
    assert expected in app_source


def test_overlay_intercepts_certified_direct_spread_fast_route_with_v7():
    source = OVERLAY.read_text(encoding="utf-8")
    assert "import nfl_spread_hub_v7 as spread_v7" in source
    assert "import streamlit_memory_lazy_router_v132 as spread_fast_route" in source
    assert "import streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_v1 as prior" in source
    assert "original_direct_spread = spread_fast_route._render_direct_spread" in source
    assert "spread_fast_route._render_direct_spread = _render_v7_direct_spread" in source
    assert "spread_fast_route._render_direct_spread = original_direct_spread" in source
    assert "return spread_v7.render_nfl_hub(\"Spread\")" in source
    assert "prior.spread_v5 = spread_v7" in source
    assert "st.popover" in source
    assert "st.button" in source
    assert "st.text_input" not in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
