"""MLB Daily Game Picks V1.5 — non-blocking Step 4A hit connector.

Preserves V1.4 production math, but never launches a full-slate 1+ Hit scan merely
because Streamlit rerendered the page. The user explicitly builds/refreshes the
connector once; results are then cached by slate date.
"""
from __future__ import annotations
import streamlit as st
import mlb_daily_game_picks_v14 as base

VERSION="MLB Daily Game Picks V1.5 • STEP 4A NON-BLOCKING"
_ACTIVE_GAMES=None

def _day(games):
    if games is None or games.empty:return ""
    return str(games.iloc[0].get("game_date") or "")[:10]

def _key(games):return f"dgp_prod_1hit_v15::{_day(games)}"

def _hit_rows_nonblocking():
    games=_ACTIVE_GAMES
    if games is None or games.empty:return {"rows":[],"diag":{"status":"NOT_BUILT"}}
    return st.session_state.get(_key(games),{"rows":[],"diag":{"status":"NOT_BUILT"}})

# V1.4 candidate lookup resolves this global at runtime.
base._hit_rows=_hit_rows_nonblocking

def render_daily_game_picks(games_df,section_header=None,status_info=None,team_logo=None,h=None):
    global _ACTIVE_GAMES
    _ACTIVE_GAMES=games_df
    # V1.4 owns its own active-game global too.
    base._ACTIVE_GAMES=games_df
    day=_day(games_df)
    key=_key(games_df)
    pack=st.session_state.get(key)
    c1,c2=st.columns([4,1])
    with c1:
        if pack and pack.get("rows"):
            st.success(f"⚡ 1+ Hit production connector ready • {len(pack['rows'])} verified hitter outputs cached • {day}")
        else:
            st.info("⚡ 1+ Hit connector is ready to build. It will not auto-run during page rendering.")
    with c2:
        label="↻ REFRESH 1+ HIT" if pack and pack.get("rows") else "⚡ CONNECT 1+ HIT"
        if st.button(label,use_container_width=True,key=f"dgp_hit_connect_v15::{day}"):
            with st.spinner("Building the production 1+ Hit fast board once for the slate..."):
                try:
                    rows,diag=base.hitprod.fast_scan(games_df,"1+ Hit",20_000,True)
                    st.session_state[key]={"rows":[dict(r) for r in (rows or [])],"diag":dict(diag or {})}
                except Exception as exc:
                    st.session_state[key]={"rows":[],"diag":{"error":f"{type(exc).__name__}: {exc}"}}
            st.rerun()
    # Reuse V1.4 bridge, but its hit lookup has been replaced with cached-only lookup.
    return base.render_daily_game_picks(games_df,section_header,status_info,team_logo,h)
