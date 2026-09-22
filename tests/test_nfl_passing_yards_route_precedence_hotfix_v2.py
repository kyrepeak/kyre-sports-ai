from __future__ import annotations

from pathlib import Path

import streamlit_memory_lazy_router_v80 as v80
import streamlit_memory_lazy_router_v91 as v91
import streamlit_memory_lazy_router_v95 as v95
import streamlit_memory_lazy_router_v96 as v96


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_v96_patches_the_actual_v91_overwrite_point(monkeypatch) -> None:
    """Prove the handler V91 installs into V80 is the newest V96 handler."""
    observed = {"deepest_is_v96": False}

    def fake_v90_render_app() -> None:
        observed["deepest_is_v96"] = v80._render_nfl_v80 is v96._render_nfl_v96

    # Collapse V95's outer wrapper chain to the precedence owner itself so this
    # test targets the bug: V91 performs the last assignment into V80.
    monkeypatch.setattr(v95, "render_app", v91.render_app)
    monkeypatch.setattr(v91.prior, "render_app", fake_v90_render_app)

    original_v91 = v91._render_nfl_v91
    original_v80 = v80._render_nfl_v80
    v96.render_app()

    assert observed["deepest_is_v96"] is True
    assert v91._render_nfl_v91 is original_v91
    assert v80._render_nfl_v80 is original_v80


def test_v96_routes_passing_yards_to_cleanup_step4_hub() -> None:
    source = _read("streamlit_memory_lazy_router_v96.py")
    app = _read("app.py")
    assert "streamlit_memory_lazy_router_v91 as precedence_owner" in source
    assert 'PRECEDENCE_ANCHOR = "streamlit_memory_lazy_router_v91._render_nfl_v91"' in source
    assert 'ACTIVE_NFL_HUB = "nfl_hub_v34"' in source
    assert "precedence_owner._render_nfl_v91 = _render_nfl_v96" in source
    assert "streamlit_memory_lazy_router_v96" in app
    assert "STREAMLIT_MAIN_V95_NFL_PASSING_YARDS_CLEANUP_STEP4_2026-09-11" in app
    assert "STREAMLIT_MAIN_V96_NFL_PASSING_YARDS_ROUTE_PRECEDENCE_HOTFIX_V2_2026-09-11" in app


def test_hotfix_does_not_change_model_or_market_math() -> None:
    source = _read("streamlit_memory_lazy_router_v96.py")
    app = _read("app.py")
    assert "No model, loader, probability, market, grading, CFB, or other sport logic changes" in source
    assert "Sportsbook projection influence remains 0.0%" in app
    assert "stake sizing remains OFF" in app
