from pathlib import Path

import nfl_passing_yards_hub_v13 as hub
import streamlit_memory_lazy_router_v92 as router


def test_cleanup_css_retires_stale_build_chrome_and_keeps_mobile_strip():
    css = hub._CLEANUP_CSS
    assert ".kpy8-active,.kpy9-active,.kpy10-active,.kpy-head{display:none!important}" in css
    assert "grid-template-columns:repeat(2,minmax(0,1fr))!important" in css
    assert ".kpy-stat:last-child{grid-column:1/-1!important}" in css


def test_final_header_describes_completed_production_system():
    header = hub._FINAL_HEADER
    assert "NFL <span>Passing Yards</span>" in header
    assert "10 / 10 COMPLETE" in header
    assert "SPORTSBOOK PROJECTION 0%" in header
    assert "STAKE SIZING OFF" in header


def test_cleanup_wrapper_is_presentation_only(monkeypatch):
    rendered = []

    def fake_markdown(value, unsafe_allow_html=False):
        rendered.append((value, unsafe_allow_html))

    def fake_prior():
        rendered.append(("prior", True))
        return "ok"

    monkeypatch.setattr(hub.st, "markdown", fake_markdown)
    monkeypatch.setattr(hub.prior, "render_nfl_passing_yards_hub", fake_prior)

    result = hub.render_nfl_passing_yards_hub()

    assert result == "ok"
    assert rendered[0] == (hub._CLEANUP_CSS, True)
    assert rendered[1] == (hub._FINAL_HEADER, True)
    assert rendered[2] == ("prior", True)


def test_v92_temporarily_replaces_deepest_v80_nfl_handler(monkeypatch):
    original = router.deepest_nfl_router._render_nfl_v80
    observed = []

    def fake_prior_render_app():
        observed.append(router.deepest_nfl_router._render_nfl_v80)

    monkeypatch.setattr(router.prior, "render_app", fake_prior_render_app)
    router.render_app()

    assert observed == [router._render_nfl_v92]
    assert router.deepest_nfl_router._render_nfl_v80 is original


def test_v92_passing_yards_routes_to_v31(monkeypatch):
    calls = []

    class FakeHub:
        @staticmethod
        def render_nfl_hub(market):
            calls.append(("render", market))
            return "ok"

    def fake_import(name):
        calls.append(("import", name))
        return FakeHub

    monkeypatch.setattr(router.root, "_import", fake_import)
    result = router._render_nfl_v92("Passing Yards")

    assert result == "ok"
    assert calls == [("import", "nfl_hub_v31"), ("render", "Passing Yards")]


def test_entrypoint_activates_v92_and_preserves_v91_heartbeat():
    text = Path("app.py").read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_v92" in text
    assert "STREAMLIT_MAIN_V92_NFL_PASSING_YARDS_CLEANUP_STEP1_2026-09-11" in text
    assert "STREAMLIT_MAIN_V91_NFL_PASSING_YARDS_LIVE_ROUTE_AUTO_SLATE_2026-09-11" in text
    assert "sportsbook projection influence 0.0%" in text.lower()
