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
