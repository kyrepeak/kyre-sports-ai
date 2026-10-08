from pathlib import Path


def _src(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


RUSH = _src("nfl_rushing_yards_hub_v4.py")
RECV = _src("nfl_receiving_yards_hub_v13.py")
RECV_V16 = _src("nfl_receiving_yards_hub_v16.py")
RUSH_ROUTER = _src("streamlit_memory_lazy_router_v111.py")
RECV_ROUTER = _src("streamlit_memory_lazy_router_v147.py")
HARDENED_HTML = _src("nfl_prop_analytics_page2_responsive_polish_v1.py")
RUSH_BROWSER = _src("devsystem/nfl_rushing_yards_html_render_browser_v1.py")


def test_rushing_runtime_and_mobile_screenshot_signature_are_exact() -> None:
    assert 'ACTIVE_PAGE = "nfl_rushing_yards_hub_v15"' in RUSH_ROUTER
    for token in (
        "Projected Rush Yards",
        "FanDuel Line",
        "Projection − Line",
        "Expected Carries",
        "Expected YPC",
        "Over Price",
    ):
        assert token in RUSH


def test_receiving_runtime_and_mobile_screenshot_signature_are_exact() -> None:
    assert 'ACTIVE_RECEIVING_YARDS_HUB = "nfl_receiving_yards_hub_v16"' in RECV_ROUTER
    assert 'FROZEN_PRIOR = "nfl_receiving_yards_hub_v15"' in RECV_V16
    for token in (
        "CERTIFIED PROJECTION",
        "Projected Rec Yds",
        "FanDuel Rec Yds",
        "frozen V9 matchup classification",
        "projection influence 0.0%",
    ):
        assert token in RECV


def test_broken_surfaces_depend_on_markdown_injected_css_for_block_layout() -> None:
    assert ".krush4-main{position:relative;z-index:1;display:grid" in RUSH
    assert ".krush4-metric b{display:block" in RUSH
    assert ".krush4-metric span{display:block" in RUSH
    assert "st.markdown(_COMPACT_CSS, unsafe_allow_html=True)" in RUSH
    assert "compact_slot.markdown(board, unsafe_allow_html=True)" in RUSH

    assert ".krecv13-grid{display:grid" in RECV
    assert ".krecv13-metric b{display:block" in RECV
    assert ".krecv13-metric span{display:block" in RECV
    assert "st.markdown(_STEP13_CSS, unsafe_allow_html=True)" in RECV


def test_repository_has_certified_hardened_html_transport_precedent() -> None:
    assert "st.html(" in HARDENED_HTML
    assert "st.markdown(" not in HARDENED_HTML
    assert 'data-prop-page2-responsive-polish-css="v1"' in HARDENED_HTML


def test_existing_rushing_browser_witness_has_computed_style_gap() -> None:
    assert "getComputedStyle" not in RUSH_BROWSER
    assert "locator(" in RUSH_BROWSER
