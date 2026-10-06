from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness.py"


class CountingQueryParams(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.write_count = 0

    def __setitem__(self, key, value):
        self.write_count += 1
        return super().__setitem__(key, value)


def _load_overlay(monkeypatch, initial_query=None):
    fake_st = ModuleType("streamlit")
    fake_st.session_state = {}
    fake_st.query_params = CountingQueryParams(initial_query or {})
    fake_st.cache_data = lambda *args, **kwargs: (lambda fn: fn)
    fake_st.markdown = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "streamlit", fake_st)

    nav = ModuleType("wnba_pra_navigation_v2_step1")
    nav.PAGE_SLATE = "slate"
    nav.PAGE_GAME = "game"
    nav.PAGE_PLAYER = "player"
    nav.current_state = lambda: SimpleNamespace(page=nav.PAGE_GAME)
    nav._write_query = lambda state: None
    monkeypatch.setitem(sys.modules, "wnba_pra_navigation_v2_step1", nav)

    for name in (
        "streamlit_memory_lazy_router_wnba_pra_repair_v1_step2_team_identity",
        "wnba_pra_game_center_v2_step3",
        "wnba_pra_player_intelligence_v2_step4",
        "wnba_pra_performance_v2_step5",
        "wnba_pra_repair_v1_step3_data",
        "wnba_pra_slate_v2_step2",
    ):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))

    spec = importlib.util.spec_from_file_location("wnba_pushstate_step2_overlay", OVERLAY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, fake_st, nav


def test_step2_deep_shell_pin_is_idempotent_when_route_is_already_correct(monkeypatch):
    overlay, fake_st, nav = _load_overlay(
        monkeypatch,
        {
            "ks_jump_sport": "WNBA",
            "ks_jump_market": "PRA",
        },
    )
    state = SimpleNamespace(page=nav.PAGE_GAME)

    for _ in range(150):
        assert overlay._pin_deep_wnba_shell_route(state) is state

    assert fake_st.query_params.write_count == 0
    assert fake_st.session_state["ks_sport_touch"] == "WNBA"
    assert fake_st.session_state["ks_wnba_market_touch"] == "PRA"


def test_step2_deep_shell_pin_writes_missing_route_once_then_stays_quiet(monkeypatch):
    overlay, fake_st, nav = _load_overlay(monkeypatch)
    state = SimpleNamespace(page=nav.PAGE_PLAYER)

    assert overlay._pin_deep_wnba_shell_route(state) is state
    assert fake_st.query_params.write_count == 2
    assert fake_st.query_params["ks_jump_sport"] == "WNBA"
    assert fake_st.query_params["ks_jump_market"] == "PRA"

    assert overlay._pin_deep_wnba_shell_route(state) is state
    assert fake_st.query_params.write_count == 2
