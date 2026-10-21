from __future__ import annotations

import sys
import types

import nba_pra_page1_ui_v2 as page1_ui


def _load_runtime():
    import importlib
    if "nba_pra_runtime_v2" in sys.modules:
        del sys.modules["nba_pra_runtime_v2"]
    return importlib.import_module("nba_pra_runtime_v2")


def test_selected_player_key_rejects_missing_and_whitespace():
    runtime = _load_runtime()
    assert runtime.selected_player_key({}) is None
    assert runtime.selected_player_key({page1_ui.SESSION_PLAYER: "   "}) is None
    assert runtime.selected_player_key({page1_ui.SESSION_PLAYER: "player-123"}) == "player-123"


def test_no_selection_renders_page1_only(monkeypatch):
    calls = []
    fake_st = types.SimpleNamespace(session_state={})
    fake_p1 = types.SimpleNamespace(render_nba_pra_page1_v2=lambda: calls.append("page1"))
    fake_p2 = types.SimpleNamespace(render_nba_pra_page2_v1=lambda: calls.append("page2"))
    monkeypatch.setitem(sys.modules, "streamlit", fake_st)
    monkeypatch.setitem(sys.modules, "nba_pra_page1_v2", fake_p1)
    monkeypatch.setitem(sys.modules, "nba_pra_page2_v1", fake_p2)
    runtime = _load_runtime()
    runtime.render_nba_pra_runtime_v2()
    assert calls == ["page1"]


def test_valid_selection_renders_page2_only(monkeypatch):
    calls = []
    fake_st = types.SimpleNamespace(session_state={page1_ui.SESSION_PLAYER: "player-123"})
    fake_p1 = types.SimpleNamespace(render_nba_pra_page1_v2=lambda: calls.append("page1"))
    fake_p2 = types.SimpleNamespace(render_nba_pra_page2_v1=lambda: calls.append("page2"))
    monkeypatch.setitem(sys.modules, "streamlit", fake_st)
    monkeypatch.setitem(sys.modules, "nba_pra_page1_v2", fake_p1)
    monkeypatch.setitem(sys.modules, "nba_pra_page2_v1", fake_p2)
    runtime = _load_runtime()
    runtime.render_nba_pra_runtime_v2()
    assert calls == ["page2"]


def test_back_clears_only_page2_state_and_preserves_route():
    runtime = _load_runtime()
    state = {
        page1_ui.SESSION_PLAYER: "player-123",
        runtime.SESSION_LINE_LAB: 31.5,
        runtime.SESSION_PAGE2_TAB: "history",
        "sport": "nba",
        "market": "pra",
        "date": "2026-10-21",
        "other": "keep",
    }
    runtime.clear_page2_state(state)
    assert page1_ui.SESSION_PLAYER not in state
    assert runtime.SESSION_LINE_LAB not in state
    assert runtime.SESSION_PAGE2_TAB not in state
    assert state["sport"] == "nba"
    assert state["market"] == "pra"
    assert state["date"] == "2026-10-21"
    assert state["other"] == "keep"

def test_page2_state_clear_includes_selected_quote():
    runtime = _load_runtime()
    state = {
        page1_ui.SESSION_PLAYER: 'player-123',
        runtime.SESSION_SELECTED_QUOTE: {'sportsbook':'FanDuel','line':36.5},
        runtime.SESSION_LINE_LAB: 36.5,
        'sport':'nba','market':'pra',
    }
    runtime.clear_page2_state(state)
    assert runtime.SESSION_SELECTED_QUOTE not in state
    assert state['sport']=='nba' and state['market']=='pra'


def test_page1_click_source_hands_off_exact_featured_quote():
    from pathlib import Path
    text = Path('nba_pra_page1_v2.py').read_text()
    assert 'SESSION_SELECTED_QUOTE' in text
    assert 'dict(item["featured_quote"])' in text or "dict(item['featured_quote'])" in text

def test_page1_selection_immediately_reruns_into_page2():
    from pathlib import Path
    text=Path('nba_pra_page1_v2.py').read_text()
    assert text.count('st.rerun()') >= 2
