from __future__ import annotations

from pathlib import Path

import nfl_passing_yards_hub_v14 as hub
import streamlit_memory_lazy_router_v93 as router


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_step2_footer_filter_only_targets_build_version_captions():
    assert hub._is_build_footer_caption("NFL PASSING YARDS V11 • certified Steps 1–9") is True
    assert hub._is_build_footer_caption(" nfl passing yards v8 • something ") is True
    assert hub._is_build_footer_caption("Sportsbook hold before no-vig: 4.2%") is False
    assert hub._is_build_footer_caption("Observed recent-game variance") is False


def test_step2_suppresses_success_spam_but_restores_streamlit_methods(monkeypatch):
    success_calls = []
    caption_calls = []
    markdown_calls = []

    def original_success(*args, **kwargs):
        success_calls.append((args, kwargs))

    def original_caption(body, *args, **kwargs):
        caption_calls.append(body)

    def original_markdown(body, *args, **kwargs):
        markdown_calls.append(body)

    monkeypatch.setattr(hub.st, "success", original_success)
    monkeypatch.setattr(hub.st, "caption", original_caption)
    monkeypatch.setattr(hub.st, "markdown", original_markdown)

    def fake_prior_render():
        hub.st.success("✅ STEP GREEN")
        hub.st.caption("NFL PASSING YARDS V11 • repeated footer")
        hub.st.caption("Useful evidence caption")
        return "rendered"

    monkeypatch.setattr(hub.prior, "render_nfl_passing_yards_hub", fake_prior_render)

    result = hub.render_nfl_passing_yards_hub()

    assert result == "rendered"
    assert success_calls == []
    assert caption_calls == ["Useful evidence caption"]
    assert markdown_calls and "stExpander" in markdown_calls[0]
    assert hub.st.success is original_success
    assert hub.st.caption is original_caption


def test_step2_css_is_mobile_first_and_preserves_warning_surfaces():
    css = hub._CLEANUP_STEP2_CSS
    assert 'div[data-testid="stAlert"]' in css
    assert 'div[data-testid="stExpander"]' in css
    assert "grid-template-columns:1fr!important" in css
    assert ".kpy10-grid" in css
    assert "display:none" not in css


def test_v93_temporarily_replaces_deepest_v80_handler(monkeypatch):
    original = router.deepest_nfl_router._render_nfl_v80
    observed = []

    def fake_prior_render_app():
        observed.append(router.deepest_nfl_router._render_nfl_v80)

    monkeypatch.setattr(router.prior, "render_app", fake_prior_render_app)
    router.render_app()

    assert observed == [router._render_nfl_v93]
    assert router.deepest_nfl_router._render_nfl_v80 is original


def test_v93_passing_yards_routes_to_v32(monkeypatch):
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
    result = router._render_nfl_v93("Passing Yards")

    assert result == "ok"
    assert calls == [("import", "nfl_hub_v32"), ("render", "Passing Yards")]


def test_cleanup_step2_route_and_entrypoint_contracts():
    hub_route = _read("nfl_hub_v32.py")
    router_text = _read("streamlit_memory_lazy_router_v93.py")
    app = _read("app.py")

    assert "import nfl_hub_v31 as base" in hub_route
    assert "nfl_passing_yards_hub_v14" in hub_route
    assert "import streamlit_memory_lazy_router_v92 as prior" in router_text
    assert 'ACTIVE_NFL_HUB = "nfl_hub_v32"' in router_text
    assert "streamlit_memory_lazy_router_v93" in app
    assert "STREAMLIT_MAIN_V92_NFL_PASSING_YARDS_CLEANUP_STEP1_2026-09-11" in app
    assert "STREAMLIT_MAIN_V93_NFL_PASSING_YARDS_CLEANUP_STEP2_2026-09-11" in app
    assert "sportsbook projection influence" in app.lower()
    assert "stake sizing OFF" in app
