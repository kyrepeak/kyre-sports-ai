from __future__ import annotations

from types import SimpleNamespace

import streamlit_memory_lazy_router_wnba_pra_repair_v1_step7_final_integration as router


def _fake_streamlit():
    return SimpleNamespace(session_state={}, query_params={})


def test_explicit_player_transition_emits_one_shot_wnba_pra_shell_handoff(monkeypatch):
    fake_st = _fake_streamlit()
    monkeypatch.setattr(router, "st", fake_st)
    monkeypatch.setattr(router.deep_route, "st", fake_st)
    monkeypatch.setattr(router.deep_route, "_protect_explicit_cfb_top_picks_route", lambda: False)

    state = router.navigation.NavigationState(
        page=router.navigation.PAGE_PLAYER,
        game_id="game-1",
        player_id="player-1",
    )
    resolved = router._pin_deep_wnba_session_route(state)

    assert resolved == state
    assert fake_st.session_state[router.deep_route.SHELL_SPORT_SESSION_KEY] == "WNBA"
    assert fake_st.session_state[router.deep_route.SHELL_MARKET_SESSION_KEY] == "PRA"
    assert fake_st.query_params[router.deep_route.SHELL_SPORT_QUERY_KEY] == "WNBA"
    assert fake_st.query_params[router.deep_route.SHELL_MARKET_QUERY_KEY] == "PRA"


def test_passive_deep_rerender_does_not_reinject_one_shot_jump(monkeypatch):
    fake_st = _fake_streamlit()
    monkeypatch.setattr(router, "st", fake_st)
    monkeypatch.setattr(router.deep_route, "st", fake_st)
    monkeypatch.setattr(router.deep_route, "_protect_explicit_cfb_top_picks_route", lambda: False)
    state = router.navigation.NavigationState(
        page=router.navigation.PAGE_PLAYER,
        game_id="game-1",
        player_id="player-1",
    )
    monkeypatch.setattr(router.navigation, "current_state", lambda: state)

    router._pin_deep_wnba_session_route()

    assert fake_st.session_state[router.deep_route.SHELL_SPORT_SESSION_KEY] == "WNBA"
    assert fake_st.session_state[router.deep_route.SHELL_MARKET_SESSION_KEY] == "PRA"
    assert router.deep_route.SHELL_SPORT_QUERY_KEY not in fake_st.query_params
    assert router.deep_route.SHELL_MARKET_QUERY_KEY not in fake_st.query_params


def test_step7_player_callback_keeps_handoff_after_render_restores_module(monkeypatch):
    fake_st = _fake_streamlit()
    monkeypatch.setattr(router, "st", fake_st)
    monkeypatch.setattr(router.deep_route, "st", fake_st)

    calls = []

    def original_player_open(game_id, player):
        calls.append((game_id, dict(player)))

    captured = {}

    def fake_parent_render():
        captured["callback"] = router.final_transport._open_player_immediate
        return "rendered"

    monkeypatch.setattr(router.final_transport, "_open_player_immediate", original_player_open)
    monkeypatch.setattr(router.frozen_parent, "render_app", fake_parent_render)

    assert router.render_app() == "rendered"
    assert router.final_transport._open_player_immediate is original_player_open

    captured["callback"]("game-1", {"player_id": "player-1"})

    assert calls == [("game-1", {"player_id": "player-1"})]
    assert fake_st.query_params[router.deep_route.SHELL_SPORT_QUERY_KEY] == "WNBA"
    assert fake_st.query_params[router.deep_route.SHELL_MARKET_QUERY_KEY] == "PRA"
