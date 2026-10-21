'''NBA PRA Page 1/Page 2 exclusive runtime selector.'''
from __future__ import annotations

from copy import deepcopy
from html import escape
from time import sleep
from typing import Any, MutableMapping, Mapping

from nba_pra_page1_ui_v2 import SESSION_PLAYER

MODEL_VERSION = "NBA PRA RUNTIME V3 • PAGE 1/2 EXACT HANDOFF"
SESSION_SELECTED_QUOTE = "ks_nba_pra_page2_selected_quote"
SESSION_LINE_LAB = "ks_nba_pra_page2_line_lab"
SESSION_PAGE2_TAB = "ks_nba_pra_page2_tab"
SESSION_ANALYSIS_HANDOFF = "ks_nba_pra_analysis_handoff_v1"
SESSION_NAV_PHASE = "ks_nba_pra_nav_phase_v1"
PAGE2_LOCAL_KEYS = (
    SESSION_PLAYER,
    SESSION_SELECTED_QUOTE,
    SESSION_LINE_LAB,
    SESSION_PAGE2_TAB,
    SESSION_ANALYSIS_HANDOFF,
    SESSION_NAV_PHASE,
)


def selected_player_key(session_state: Mapping[str, Any]) -> str | None:
    value = str(session_state.get(SESSION_PLAYER) or "").strip()
    return value or None


def select_player_for_analysis(session_state: MutableMapping[str, Any], item: Mapping[str, Any]) -> None:
    '''Atomically hand Page 2 the exact analysis shown on Page 1.'''
    player_key = str(item.get("key") or "").strip()
    quote = dict(item.get("featured_quote") or {})
    if not player_key:
        raise ValueError("NBA_PRA_PLAYER_KEY_REQUIRED")
    session_state[SESSION_PLAYER] = player_key
    session_state[SESSION_SELECTED_QUOTE] = deepcopy(quote)
    session_state[SESSION_ANALYSIS_HANDOFF] = {
        "schema_version": "NBA_PRA_ANALYSIS_HANDOFF_V1",
        "player_key": player_key,
        "player_name": str(item.get("player_name") or "Player"),
        "team": str(item.get("team") or ""),
        "position": str(item.get("position") or ""),
        "quote": deepcopy(quote),
        "model": deepcopy(dict(item.get("model") or {})),
        "grade": deepcopy(dict(item.get("grade") or {})),
        "snapshot_at_utc": str(quote.get("observed_at_utc") or ""),
        "sportsbook_projection_influence": 0.0,
    }
    session_state[SESSION_NAV_PHASE] = "loading_page2"


def clear_page2_state(session_state: MutableMapping[str, Any]) -> None:
    for key in PAGE2_LOCAL_KEYS:
        session_state.pop(key, None)


def render_page2_loading_screen(player_name: str) -> str:
    name = escape(str(player_name or "player"))
    return f'''<style>
    .ks-pra-loading{{position:fixed;inset:0;z-index:999999;background:#050b13;display:grid;place-items:center;color:#eefaff}}
    .ks-pra-loading-card{{width:min(560px,88vw);border:1px solid rgba(91,211,255,.28);border-radius:22px;padding:30px;background:linear-gradient(145deg,#071525,#06101d);box-shadow:0 24px 70px rgba(0,0,0,.5);text-align:center}}
    .ks-pra-loading-kicker{{font-size:11px;letter-spacing:.18em;color:#6fe1ff;font-weight:900}}
    .ks-pra-loading-card h2{{margin:10px 0 8px;font-size:28px}}
    .ks-pra-loading-card p{{margin:0;color:#9ab0c1}}
    .ks-pra-loading-bar{{height:4px;border-radius:999px;background:#0c2638;overflow:hidden;margin:22px 0 0}}
    .ks-pra-loading-bar span{{display:block;width:58%;height:100%;background:#76e6ff;animation:ksload .72s ease-in-out infinite alternate}}
    @keyframes ksload{{from{{transform:translateX(-55%)}}to{{transform:translateX(120%)}}}}
    </style><div class="ks-pra-loading"><div class="ks-pra-loading-card"><div class="ks-pra-loading-kicker">KYRE SPORTS AI • PLAYER ANALYSIS</div><h2>Analyzing {name}…</h2><p>Loading projection • matchup • market • usage</p><div class="ks-pra-loading-bar"><span></span></div></div></div>'''


def render_nba_pra_runtime_v2() -> None:
    import streamlit as st

    nav_phase = str(st.session_state.get(SESSION_NAV_PHASE) or "").strip()
    if nav_phase == "loading_page2":
        handoff = st.session_state.get(SESSION_ANALYSIS_HANDOFF) or {}
        st.markdown(render_page2_loading_screen(str(handoff.get("player_name") or "player")), unsafe_allow_html=True)
        st.session_state[SESSION_NAV_PHASE] = "page2"
        sleep(0.08)
        st.rerun()
        return

    player_key = selected_player_key(st.session_state)
    if player_key is None:
        from nba_pra_page1_v2 import render_nba_pra_page1_v2
        render_nba_pra_page1_v2()
        return

    from nba_pra_page2_sync_v1 import render_nba_pra_page2_sync_v1
    render_nba_pra_page2_sync_v1()
