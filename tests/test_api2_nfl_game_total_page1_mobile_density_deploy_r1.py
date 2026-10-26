from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"


def test_density_deployment_heartbeat_is_browser_visible_and_terminal_route_is_preserved() -> None:
    source = APP.read_text(encoding="utf-8")
    assert 'API2_NFL_GAME_TOTAL_PAGE1_MOBILE_DENSITY_R1_20261026' in source
    assert 'streamlit_memory_lazy_router_universal_runtime_v5_nfl_rushing_route_restore_v1' in source
    assert '_STEP2G_DEPLOYMENT_MARKER' in source
    assert 'st.markdown(' in source
