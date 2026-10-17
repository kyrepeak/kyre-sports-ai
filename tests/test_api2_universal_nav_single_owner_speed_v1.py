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


def test_nav_css_is_emitted_once_per_session_for_fast_rerenders():
    ui = _read("universal_sports_nav_ui_v1.py")
    assert "ks_universal_nav_css_loaded" in ui
    assert "if not st.session_state.get(_CSS_SESSION_KEY" in ui


def test_route_state_writes_remain_change_only():
    compat = _read("universal_sports_nav_compat_v1.py")
    assert "_set_if_changed" in compat
    assert "if session.get(key) != value" in compat
