from __future__ import annotations

from types import SimpleNamespace

import pytest

import streamlit_memory_lazy_router_universal_nav_v4 as router


class _RerunSignal(BaseException):
    pass


class _Placeholder:
    def __init__(self) -> None:
        self.markdowns: list[tuple[str, bool]] = []
        self.empty_calls = 0

    def markdown(self, body: str, *, unsafe_allow_html: bool = False):
        self.markdowns.append((body, unsafe_allow_html))
        return self

    def empty(self) -> None:
        self.empty_calls += 1


class _FakeSt:
    def __init__(self) -> None:
        self.session_state: dict[str, object] = {}
        self.query_params: dict[str, object] = {}
        self.placeholder = _Placeholder()

    def empty(self) -> _Placeholder:
        return self.placeholder

    def rerun(self) -> None:
        raise _RerunSignal()


def _state(sport_id: str, market_id: str, epoch: int):
    return SimpleNamespace(
        sport_id=sport_id,
        market_id=market_id,
        source="tap",
        epoch=epoch,
        last_market_by_sport={},
    )


def test_atomic_callback_records_exact_transition_before_rerun(monkeypatch):
    fake = _FakeSt()
    fake.session_state["sport-widget"] = "cfb"
    source = _state("mlb", "slate", 9)
    target = _state("cfb", "game-total", 10)

    monkeypatch.setattr(router, "st", fake)
    monkeypatch.setattr(router.v2.prior, "_apply_intent", lambda _state, _intent: target)
    monkeypatch.setattr(router.v2.prior, "_persist_state", lambda *_args: None)
    monkeypatch.setattr(router.v2.prior, "apply_legacy_route_state", lambda *_args: None)
    monkeypatch.setattr(router.v2.prior, "query_patch_for_state", lambda *_args: {})
    monkeypatch.setattr(router.v2.prior, "apply_query_patch", lambda *_args: None)
    monkeypatch.setattr(router.v2, "_clear_cross_route_query_context", lambda *_args: None)
    monkeypatch.setattr(router.v2, "_clear_cross_route_session_context", lambda *_args: None)

    with pytest.raises(_RerunSignal):
        router._commit_pill_intent(source, sport_widget_key="sport-widget")

    assert fake.session_state[router.ROUTE_TRANSITION_KEY] == {
        "sport_id": "cfb",
        "market_id": "game-total",
        "epoch": 10,
        "confirmed": False,
    }


def test_transition_mask_stays_until_exact_terminal_owner_confirms(monkeypatch):
    fake = _FakeSt()
    target = _state("cfb", "game-total", 10)
    wrong = _state("mlb", "slate", 9)

    monkeypatch.setattr(router, "st", fake)
    router._record_route_transition(target)

    placeholder = router._render_pending_transition_mask()
    assert placeholder is fake.placeholder
    assert fake.placeholder.markdowns
    html, unsafe = fake.placeholder.markdowns[-1]
    assert unsafe is True
    assert "KYRE SPORTS AI" in html
    assert "Loading CFB" in html
    assert "Game Total" in html

    assert router._confirm_route_transition(wrong) is False
    router._finish_route_transition(placeholder)
    assert fake.placeholder.empty_calls == 0
    assert router.ROUTE_TRANSITION_KEY in fake.session_state

    assert router._confirm_route_transition(target) is True
    router._finish_route_transition(placeholder)
    assert fake.placeholder.empty_calls == 1
    assert router.ROUTE_TRANSITION_KEY not in fake.session_state
