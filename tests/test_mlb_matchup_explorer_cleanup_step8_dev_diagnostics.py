from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_app_routes_through_clean_router_v2():
    source = _text("app.py")
    assert "from streamlit_memory_lazy_router_v2 import render_app" in source
    assert "from streamlit_memory_lazy_router_v1 import render_app" not in source


def test_step8_wraps_frozen_router_without_reimplementing_routing():
    source = _text("streamlit_memory_lazy_router_v2.py")
    assert "import streamlit_memory_lazy_router_v1 as frozen" in source
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v1"' in source
    assert "frozen.render_app()" in source


def test_step8_hides_router_and_route_diagnostics_from_normal_view():
    source = _text("streamlit_memory_lazy_router_v2.py")
    assert 'class="ks-route"' in source
    assert '"lazy route:" in lowered' in source
    assert 'text.startswith("Live odds bridge fallback:")' in source
    assert 'text.startswith("WNBA API schedule bridge fallback:")' in source
    assert "diagnostics.append" in source
    assert "return None" in source


def test_step8_replaces_technical_shell_subtitle_with_user_facing_copy():
    source = _text("streamlit_memory_lazy_router_v2.py")
    assert "Memory-safe lazy loading • one sport + one market loaded at a time." in source
    assert 'Fast, focused sports projection intelligence.' in source
    assert "text.replace(" in source


def test_step8_keeps_diagnostics_available_but_collapsed():
    source = _text("streamlit_memory_lazy_router_v2.py")
    assert 'st.sidebar.expander("🛠️ Developer Diagnostics", expanded=False)' in source
    assert 'st.caption(f"Router: {frozen.MODEL_VERSION}")' in source
    assert "for item in diagnostics:" in source


def test_step8_restores_streamlit_patches_even_if_frozen_router_raises():
    source = _text("streamlit_memory_lazy_router_v2.py")
    assert "original_markdown = st.markdown" in source
    assert "original_caption = st.caption" in source
    assert "finally:" in source
    assert "st.caption = original_caption" in source
    assert "st.markdown = original_markdown" in source


def test_step8_does_not_filter_legal_disclaimer():
    source = _text("streamlit_memory_lazy_router_v2.py")
    start = source.index("def _is_internal_caption")
    end = source.index("def _markdown_capture", start)
    internal_filter = source[start:end]
    assert "DISCLAIMER" not in internal_filter
    assert "Educational purposes only" not in internal_filter


def test_step8_is_presentation_only():
    source = _text("streamlit_memory_lazy_router_v2.py")
    for forbidden in (
        "build_probability_profile(",
        "build_final_intelligence(",
        "5_000_000",
        "np.random",
        "monte_carlo",
        "render_daily_rankings(",
        "mlb_moneyline_hub_v164",
        "mlb_matchup_probability_v1",
        "mlb_matchup_calibration_v1",
    ):
        assert forbidden not in source
