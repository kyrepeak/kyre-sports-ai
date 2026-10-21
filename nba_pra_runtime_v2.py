'''NBA PRA Page 1/Page 2 exclusive runtime selector.'''
from __future__ import annotations

from typing import Any, MutableMapping, Mapping

from nba_pra_page1_ui_v2 import SESSION_PLAYER

MODEL_VERSION = "NBA PRA RUNTIME V2 • PAGE 1/2 EXCLUSIVE"
SESSION_SELECTED_QUOTE = "ks_nba_pra_page2_selected_quote"
SESSION_LINE_LAB = "ks_nba_pra_page2_line_lab"
SESSION_PAGE2_TAB = "ks_nba_pra_page2_tab"
PAGE2_LOCAL_KEYS = (SESSION_PLAYER, SESSION_SELECTED_QUOTE, SESSION_LINE_LAB, SESSION_PAGE2_TAB)


def selected_player_key(session_state: Mapping[str, Any]) -> str | None:
    value = str(session_state.get(SESSION_PLAYER) or "").strip()
    return value or None


def clear_page2_state(session_state: MutableMapping[str, Any]) -> None:
    for key in PAGE2_LOCAL_KEYS:
        session_state.pop(key, None)


def render_nba_pra_runtime_v2() -> None:
    import streamlit as st

    player_key = selected_player_key(st.session_state)
    if player_key is None:
        from nba_pra_page1_v2 import render_nba_pra_page1_v2
        render_nba_pra_page1_v2()
        return

    from nba_pra_page2_v1 import render_nba_pra_page2_v1
    render_nba_pra_page2_v1()
