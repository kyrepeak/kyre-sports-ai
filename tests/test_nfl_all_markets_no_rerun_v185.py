from __future__ import annotations

from pathlib import Path

import streamlit_memory_lazy_router_v1 as base
import streamlit_memory_lazy_router_v185 as router


ROOT = Path(__file__).resolve().parents[1]


def test_v185_accepts_every_frozen_nfl_category_and_rejects_invalid() -> None:
    assert tuple(base.NFL_MARKETS) == router.NFL_MARKETS

    for market in router.NFL_MARKETS:
        assert router._valid_nfl_category_jump("NFL", market) is True

    assert router._valid_nfl_category_jump("CFB", "Passing Yards") is False
    assert router._valid_nfl_category_jump("NFL", "Fake Market") is False


def test_v185_all_nfl_handoff_sets_existing_route_state(monkeypatch) -> None:
    state: dict[str, object] = {}
    monkeypatch.setattr(router.st, "session_state", state)

    for market in router.NFL_MARKETS:
        state.clear()

        if market == router.PASSING_YARDS_MARKET:
            monkeypatch.setattr(
                router.prior,
                "_prime_fresh_passing_yards_state",
                lambda s, today_et: (
                    s.__setitem__(router.prior.V8_DATE_KEY, today_et),
                    s.__setitem__(router.prior.V8_DATE_INPUT_KEY, today_et),
                ),
            )

        router._apply_nfl_category_state(market)

        assert state[router.SPORT_KEY] == "NFL"
        assert state[router.NFL_MARKET_KEY] == market


def test_v185_executable_handoff_does_not_call_rerun() -> None:
    assert "rerun" not in router._consume_any_nfl_category_without_rerun.__code__.co_names
    assert "rerun" not in router.render_app.__code__.co_names


def test_v185_preserves_v184_and_projection_guardrails() -> None:
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v184"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.MAY_MODIFY_PROJECTION is False


def test_app_boots_v185() -> None:
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "from streamlit_memory_lazy_router_v185 import record_bootstrap_import_ms, render_app" in app
