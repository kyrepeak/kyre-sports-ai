from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(name: str) -> str:
    return (ROOT / name).read_text()

def test_step5_is_responsive_only_over_step4() -> None:
    body = read("nfl_passing_yards_hub_v50.py")
    assert 'FROZEN_PRIOR = "nfl_passing_yards_hub_v49"' in body
    assert "PRESENTATION_ONLY = True" in body
    assert "MAY_MODIFY_PROJECTION = False" in body
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in body
    assert "st.text_input(" not in body
    assert "st.selectbox(" not in body
    assert "st.date_input(" not in body

def test_step5_covers_desktop_tablet_mobile_breakpoints() -> None:
    body = read("nfl_passing_yards_hub_v50.py")
    for bp in (
        "@media(max-width:1120px)",
        "@media(max-width:820px)",
        "@media(max-width:620px)",
        "@media(max-width:430px)",
    ):
        assert bp in body
    assert "min-height:48px!important" in body
    assert ".ks-py48-grid" in body
    assert ".st-key-kyre_passing_yards_top_v46" in body
    assert 'input[aria-label="Sportsbook / source"]' in body

def test_step5_preserves_all_frozen_upgrade_layers() -> None:
    for name in (
        "nfl_passing_yards_hub_v46.py",
        "nfl_passing_yards_hub_v47.py",
        "nfl_passing_yards_hub_v48.py",
        "nfl_passing_yards_hub_v49.py",
    ):
        assert (ROOT / name).is_file()

def test_step5_router_advances_only_passing_yards() -> None:
    body = read("streamlit_memory_lazy_router_v196.py")
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v195"' in body
    assert 'PASSING_HUB = "nfl_passing_yards_hub_v50"' in body
    assert 'if sport != "NFL" or market != PASSING_MARKET:' in body
    assert "return prior.render_app()" in body

def test_step5_app_boots_v196() -> None:
    app = read("app.py")
    assert "from streamlit_memory_lazy_router_v196 import record_bootstrap_import_ms, render_app" in app
