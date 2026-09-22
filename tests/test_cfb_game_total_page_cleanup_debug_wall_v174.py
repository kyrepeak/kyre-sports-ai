from __future__ import annotations

import streamlit_memory_lazy_router_v160 as heartbeat_owner
import streamlit_memory_lazy_router_v174 as router


def test_v174_suppresses_only_visible_heartbeat(monkeypatch) -> None:
    calls: list[str] = []

    def visible_heartbeat() -> None:
        calls.append("visible")

    def callback() -> str:
        heartbeat_owner._render_production_heartbeat()
        return "ok"

    monkeypatch.setattr(heartbeat_owner, "_render_production_heartbeat", visible_heartbeat)

    assert router._hide_legacy_visible_heartbeat(callback) == "ok"
    assert calls == []
    assert heartbeat_owner._render_production_heartbeat is visible_heartbeat


def test_v174_preserves_certified_route_and_model_guards() -> None:
    assert router.ACTIVE_PAGE == "cfb_game_total_clean_page_v28"
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v173"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.MAY_MODIFY_PROJECTION is False
    assert "DEBUG_WALL_HIDDEN" in router.PAGE_CLEANUP_STEP1_MARKER
