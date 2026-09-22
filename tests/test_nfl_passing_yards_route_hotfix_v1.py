from datetime import date
from pathlib import Path

import nfl_passing_yards_hub_v12 as hub
import streamlit_memory_lazy_router_v91 as router


class _Games:
    def __init__(self, empty: bool):
        self.empty = empty


def test_next_verified_slate_finds_first_nonempty_verified_day():
    seen = []

    def loader(day):
        seen.append(day)
        return _Games(empty=day != "2026-09-13"), {"request_ok": True}

    resolved, offset, status = hub.find_next_verified_slate(
        date(2026, 9, 11), loader=loader, max_forward_days=7
    )

    assert resolved == date(2026, 9, 13)
    assert offset == 2
    assert status == "verified"
    assert seen == ["2026-09-11", "2026-09-12", "2026-09-13"]


def test_next_verified_slate_fails_closed_on_intermediate_verification_error():
    seen = []

    def loader(day):
        seen.append(day)
        if day == "2026-09-12":
            return _Games(empty=True), {"request_ok": False}
        return _Games(empty=True), {"request_ok": True}

    resolved, offset, status = hub.find_next_verified_slate(
        date(2026, 9, 11), loader=loader, max_forward_days=7
    )

    assert resolved == date(2026, 9, 11)
    assert offset is None
    assert status == "verification_failed"
    assert seen == ["2026-09-11", "2026-09-12"]


def test_v91_temporarily_replaces_deepest_v80_nfl_handler(monkeypatch):
    original = router.deepest_nfl_router._render_nfl_v80
    observed = []

    def fake_prior_render_app():
        observed.append(router.deepest_nfl_router._render_nfl_v80)

    monkeypatch.setattr(router.prior, "render_app", fake_prior_render_app)
    router.render_app()

    assert observed == [router._render_nfl_v91]
    assert router.deepest_nfl_router._render_nfl_v80 is original


def test_v91_passing_yards_routes_to_v30(monkeypatch):
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
    result = router._render_nfl_v91("Passing Yards")

    assert result == "ok"
    assert calls == [("import", "nfl_hub_v30"), ("render", "Passing Yards")]


def test_entrypoint_activates_v91_and_preserves_v90_heartbeat():
    text = Path("app.py").read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_v91" in text
    assert "STREAMLIT_MAIN_V91_NFL_PASSING_YARDS_LIVE_ROUTE_AUTO_SLATE_2026-09-11" in text
    assert "STREAMLIT_MAIN_V90_NFL_PASSING_YARDS_STEP10_MARKET_EDGE_FINAL_2026-09-11" in text
    assert "sportsbook projection influence 0.0%" in text.lower()
