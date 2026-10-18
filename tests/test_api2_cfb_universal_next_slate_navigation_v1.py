from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone
import importlib
from pathlib import Path
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _scheduled(day: date, hour: int = 18):
    return [{
        "status": "Scheduled",
        "kickoff_iso": datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc).isoformat(),
    }]


def test_resolver_skips_empty_and_finished_dates_and_returns_next_future_slate():
    nav = importlib.import_module("cfb_universal_next_slate_navigation_v1")
    start = date(2026, 10, 18)
    calls = []

    def loader(day):
        calls.append(day)
        if day == date(2026, 10, 18):
            return [{"status": "Final", "kickoff_iso": "2026-10-18T16:00:00+00:00"}]
        if day in {date(2026, 10, 19), date(2026, 10, 20), date(2026, 10, 21)}:
            return []
        if day == date(2026, 10, 22):
            return _scheduled(day, 23)
        return []

    resolved = nav.resolve_next_cfb_slate_date(
        start,
        loader,
        now_provider=lambda: datetime(2026, 10, 18, 23, 5, tzinfo=timezone.utc),
        max_days=14,
    )
    assert resolved == date(2026, 10, 22)
    assert calls == [date(2026, 10, 18), date(2026, 10, 19), date(2026, 10, 20), date(2026, 10, 21), date(2026, 10, 22)]


def test_resolver_keeps_today_when_a_future_game_remains():
    nav = importlib.import_module("cfb_universal_next_slate_navigation_v1")
    today = date(2026, 10, 18)
    resolved = nav.resolve_next_cfb_slate_date(
        today,
        lambda day: _scheduled(day, 23) if day == today else [],
        now_provider=lambda: datetime(2026, 10, 18, 22, 0, tzinfo=timezone.utc),
    )
    assert resolved == today


def test_resolver_fails_closed_when_no_future_verified_slate_exists():
    nav = importlib.import_module("cfb_universal_next_slate_navigation_v1")
    assert nav.resolve_next_cfb_slate_date(
        date(2026, 10, 18),
        lambda _day: [],
        now_provider=lambda: datetime(2026, 10, 18, 22, 0, tzinfo=timezone.utc),
        max_days=3,
    ) is None


def test_date_input_bridge_returns_resolved_date_without_calling_native(monkeypatch):
    fake_st = types.SimpleNamespace()
    native_calls = []
    captions = []

    def native(*args, **kwargs):
        native_calls.append((args, kwargs))
        return date(1999, 1, 1)

    fake_st.date_input = native
    fake_st.caption = captions.append
    monkeypatch.setitem(sys.modules, "streamlit", fake_st)
    sys.modules.pop("cfb_universal_next_slate_navigation_v1", None)
    nav = importlib.import_module("cfb_universal_next_slate_navigation_v1")

    target = date(2026, 10, 22)
    with nav.install_cfb_next_slate_date_bridge(target):
        assert fake_st.date_input("CFB Moneyline slate date", value=date(2026, 10, 18)) == target
    assert fake_st.date_input is native
    assert native_calls == []
    assert any("Next CFB slate" in text for text in captions)


def test_v13_wraps_every_cfb_adapter_with_tap_only_and_auto_date(monkeypatch):
    calls = []

    class Adapter:
        route_key = ("cfb", "moneyline")
        source_version = "source"
        ttl_ms = 30_000
        def loader(self):
            return "payload"
        def renderer(self, payload):
            calls.append(("render", payload))
            return "ok"

    class DestinationAdapter:
        def __init__(self, route_key, loader, renderer, source_version, ttl_ms):
            self.route_key = route_key
            self.loader = loader
            self.renderer = renderer
            self.source_version = source_version
            self.ttl_ms = ttl_ms

    prior = types.SimpleNamespace(resolve_destination=lambda route: Adapter())
    base = types.SimpleNamespace(DestinationAdapter=DestinationAdapter, choose_prefetch=object(), load_destination=object(), run_prefetch=object())
    state = types.SimpleNamespace(RuntimeRoute=object)

    @contextmanager
    def tap_only():
        calls.append(("tap-enter", None))
        yield
        calls.append(("tap-exit", None))

    @contextmanager
    def date_bridge(day):
        calls.append(("date-enter", day))
        yield
        calls.append(("date-exit", day))

    selector = types.SimpleNamespace(install_universal_tap_only_selectboxes=tap_only)
    nav = types.SimpleNamespace(
        resolve_runtime_cfb_slate_date=lambda **kwargs: date(2026, 10, 22),
        install_cfb_next_slate_date_bridge=date_bridge,
    )
    schedule = types.SimpleNamespace(games_for_date=lambda day: [])
    fake_st = types.SimpleNamespace(session_state={})

    monkeypatch.setitem(sys.modules, "universal_runtime_v5_loader_v12", prior)
    monkeypatch.setitem(sys.modules, "universal_runtime_v5_loader", base)
    monkeypatch.setitem(sys.modules, "universal_runtime_v5_state", state)
    monkeypatch.setitem(sys.modules, "universal_tap_only_selector_v2", selector)
    monkeypatch.setitem(sys.modules, "cfb_universal_next_slate_navigation_v1", nav)
    monkeypatch.setitem(sys.modules, "cfb_schedule_v1", schedule)
    monkeypatch.setitem(sys.modules, "streamlit", fake_st)
    sys.modules.pop("universal_runtime_v5_loader_v13", None)
    v13 = importlib.import_module("universal_runtime_v5_loader_v13")

    route = types.SimpleNamespace(sport_id="cfb", market_id="moneyline")
    adapter = v13.resolve_destination(route)
    assert adapter.renderer(adapter.loader()) == "ok"
    assert fake_st.session_state["cfb_universal_next_slate_date"] == "2026-10-22"
    assert calls == [
        ("tap-enter", None),
        ("date-enter", date(2026, 10, 22)),
        ("render", "payload"),
        ("date-exit", date(2026, 10, 22)),
        ("tap-exit", None),
    ]


def test_v13_non_cfb_routes_delegate_unchanged(monkeypatch):
    sentinel = object()
    prior = types.SimpleNamespace(resolve_destination=lambda route: sentinel)
    base = types.SimpleNamespace(DestinationAdapter=object, choose_prefetch=object(), load_destination=object(), run_prefetch=object())
    state = types.SimpleNamespace(RuntimeRoute=object)
    monkeypatch.setitem(sys.modules, "universal_runtime_v5_loader_v12", prior)
    monkeypatch.setitem(sys.modules, "universal_runtime_v5_loader", base)
    monkeypatch.setitem(sys.modules, "universal_runtime_v5_state", state)
    sys.modules.pop("universal_runtime_v5_loader_v13", None)
    v13 = importlib.import_module("universal_runtime_v5_loader_v13")
    route = types.SimpleNamespace(sport_id="nfl", market_id="spread")
    assert v13.resolve_destination(route) is sentinel


def test_runtime_handoff_points_to_v13_only():
    source = (ROOT / "streamlit_memory_lazy_router_universal_runtime_v5.py").read_text(encoding="utf-8")
    assert "from universal_runtime_v5_loader_v13 import choose_prefetch, load_destination, resolve_destination" in source


def test_runtime_resolver_uses_espn_navigation_fallback_when_primary_is_empty(monkeypatch):
    nav = importlib.import_module("cfb_universal_next_slate_navigation_v1")
    start = datetime(2026, 10, 18, 23, 5, tzinfo=timezone.utc)
    fallback_calls = []

    def fallback(day):
        fallback_calls.append(day)
        if day == date(2026, 10, 22):
            return _scheduled(day, 23)
        return []

    monkeypatch.setattr(nav, "espn_navigation_games_for_date", fallback, raising=False)
    resolved = nav.resolve_runtime_cfb_slate_date(
        games_loader=lambda _day: [],
        now_provider=lambda: start,
        max_days=5,
    )
    assert resolved == date(2026, 10, 22)
    assert fallback_calls[-1] == date(2026, 10, 22)
