from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_universal_nav_is_the_only_visible_global_navigation_owner():
    overlay = _read("streamlit_memory_lazy_router_universal_nav_v1.py")
    compat = _read("universal_sports_nav_compat_v1.py")
    assert "make_legacy_selectbox_bridge" in overlay
    assert "LEGACY_TOP_LEVEL_LABELS" in compat
    assert '"🏟️ Sport"' in compat
    assert '"🎯 NFL Market"' in compat


def test_nav_css_remains_in_streamlit_output_and_static_options_are_cached():
    ui = _read("universal_sports_nav_ui_v1.py")
    assert "st.markdown(_NAV_CSS" in ui
    assert "ks_universal_nav_css_loaded" not in ui
    assert "_SPORT_IDS" in ui
    assert "_MARKET_IDS_BY_SPORT" in ui


def test_route_state_writes_remain_change_only():
    compat = _read("universal_sports_nav_compat_v1.py")
    assert "_set_if_changed" in compat
    assert "if session.get(key) != value" in compat


def test_nav_css_survives_real_streamlit_rerun(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.syspath_prepend(str(ROOT))
    app_file = tmp_path / "nav_css_rerun_app.py"
    app_file.write_text(
        "from universal_sports_nav_controller_v1 import RouteState\n"
        "from universal_sports_nav_ui_v1 import render_universal_nav\n"
        "render_universal_nav(RouteState('nfl','slate','default',1,{'nfl':'slate'}))\n",
        encoding="utf-8",
    )

    at = AppTest.from_file(str(app_file), default_timeout=15)
    at.run()
    assert not at.exception
    assert any(".st-key-ks_universal_nav_shell" in item.value for item in at.markdown)

    at.run()
    assert not at.exception
    assert any(".st-key-ks_universal_nav_shell" in item.value for item in at.markdown)


def test_nav_static_option_metadata_is_cached_not_rebuilt_per_rerun():
    ui = _read("universal_sports_nav_ui_v1.py")
    assert "_SPORT_IDS" in ui
    assert "_SPORT_LABELS" in ui
    assert "_MARKET_IDS_BY_SPORT" in ui
    assert "_MARKET_LABELS_BY_SPORT" in ui
