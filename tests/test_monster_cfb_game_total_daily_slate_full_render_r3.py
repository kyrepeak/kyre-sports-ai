from __future__ import annotations

import sys
from datetime import date

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_cfb_game_total_page1_daily_slate_v1 as router


def test_fresh_page1_import_after_route_purge_keeps_empty_primary_fallback(monkeypatch):
    selected = date(2026, 10, 16)
    fallback_calls: list[date] = []

    def fallback_builder(day: date, **_kwargs):
        fallback_calls.append(day)
        return {
            "requested_phoenix_date": day.isoformat(),
            "game_count": 4,
            "games": [{"event_id": f"live-{index}"} for index in range(4)],
            "fabrication": False,
        }

    previous_module = sys.modules.get(router.PAGE1_DAILY_SLATE_ROUTE)

    with router.install_daily_slate_page1():
        removed_module = sys.modules.pop(router.PAGE1_DAILY_SLATE_ROUTE, None)
        try:
            fresh_page = root._import(router.PAGE1_DAILY_SLATE_ROUTE)
            assert fresh_page is not removed_module

            monkeypatch.setattr(
                fresh_page,
                "_load_slate_cached_60",
                lambda _day_iso: {
                    "requested_phoenix_date": selected.isoformat(),
                    "game_count": 0,
                    "games": [],
                },
            )
            monkeypatch.setattr(
                router.daily_fallback,
                "build_requests_fallback_payload",
                fallback_builder,
            )

            payload = fresh_page._load_day(selected)
        finally:
            sys.modules.pop(router.PAGE1_DAILY_SLATE_ROUTE, None)
            if previous_module is not None:
                sys.modules[router.PAGE1_DAILY_SLATE_ROUTE] = previous_module

    assert payload["game_count"] == 4
    assert payload["transport"] == "requests_espn_fallback"
    assert payload["primary_empty"] is True
    assert payload["fabrication"] is False
    assert fallback_calls == [selected]


def test_full_render_repair_scope_does_not_expand_into_page2_or_model_logic():
    assert router.MAY_MODIFY_SELECTED_GAME_RUNTIME is False
    assert router.MAY_MODIFY_MODEL is False
    assert router.MAY_MODIFY_PROJECTION is False
    assert router.MAY_MODIFY_PROBABILITY is False
    assert router.MAY_MODIFY_RANKING is False
    assert router.MAY_MODIFY_SELECTION is False
    assert router.MAY_MODIFY_OTHER_SPORTS is False
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
