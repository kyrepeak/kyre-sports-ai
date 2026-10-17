from __future__ import annotations

from importlib import import_module
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_entrypoint_boots_v3_router_and_v2_shell_and_forces_runtime_refresh():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "API2_UNIVERSAL_SHELL_ROUTE_TOP_V1_RUNTIME_REFRESH_2026_10_17" in app
    assert "from streamlit_memory_lazy_router_universal_nav_v3 import record_bootstrap_import_ms, render_app" in app
    assert "from kyre_universal_shell_runtime_v2 import activate_universal_shell" in app


def test_shell_v2_keeps_kyre_sports_ai_visible_and_has_fixed_top_control():
    shell = import_module("kyre_universal_shell_runtime_v2")
    html = shell.build_universal_shell_v2_html()
    css = shell.build_universal_shell_v2_css()
    assert "KYRE" in html and "SPORTS AI" in html
    assert 'id="kyre-universal-top-anchor"' in html
    assert 'href="#kyre-universal-top-anchor"' in html
    assert "Top" in html
    normalized = css.replace(" ", "").lower()
    assert "position:sticky" in normalized
    assert "position:fixed" in normalized
    assert "scroll-behavior:smooth" in normalized


def test_router_v3_retires_stale_mlb_owner_before_nfl_delegate():
    router = import_module("streamlit_memory_lazy_router_universal_nav_v3")
    session = {
        "ks_universal_sport": "nfl",
        "ks_universal_market": "slate",
        "ks_universal_nav_source": "tap",
        "ks_universal_epoch": 12,
        "ks_universal_last_market_by_sport": {"mlb": "slate", "nfl": "slate"},
        "ks_sport_touch": "MLB",
        "ks_mlb_market_touch": "Slate",
        "ks_mlb_live_odds_route": True,
    }
    result = router._enforce_canonical_legacy_owner(session)
    assert result["sport_id"] == "nfl"
    assert result["market_id"] == "slate"
    assert session["ks_sport_touch"] == "NFL"
    assert session["ks_nfl_market_touch"] == "Slate"
    assert "ks_mlb_market_touch" not in session
    assert "ks_mlb_live_odds_route" not in session


def test_router_v3_does_not_overwrite_a_fresh_pending_tap():
    router = import_module("streamlit_memory_lazy_router_universal_nav_v3")
    session = {
        router.PENDING_INTENT_KEY: {"source": "tap", "sport_id": "nba", "market_id": "spread"},
        "ks_universal_sport": "nfl",
        "ks_universal_market": "slate",
    }
    assert router._should_sync_steady_state(session) is False
