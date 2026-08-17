"""MLB Slate V3.2 recovery wrapper — MLB ONLY.

The old global games_df bootstrap can be empty. This wrapper reloads the selected
MLB date independently before the slate UI renders. If all transports fail, it
shows provider diagnostics instead of a generic zero-games message.
"""
from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

import mlb_schedule_v32 as schedule
import slate_hub_v2091 as base

MODEL_VERSION = "MLB Slate Recovery V3.2"

CSS = r"""
<style>
.mlb32-box{border:1px solid #265476;background:linear-gradient(145deg,#09192b,#08111f);border-radius:18px;padding:14px 15px;margin:8px 0 14px}
.mlb32-title{font-size:1.05rem;font-weight:950;color:#f8fafc}.mlb32-sub{color:#91a8c2;font-size:.73rem;margin-top:3px}
.mlb32-ok{color:#68e8b1;font-weight:900}.mlb32-bad{color:#ff8c98;font-weight:900}
.mlb32-row{border-top:1px solid rgba(120,150,180,.17);padding:8px 0;font-size:.72rem;color:#a9bdd2;line-height:1.5}.mlb32-row b{color:#eaf6ff}
</style>
"""


def _diag_html(diag):
    attempts = (diag or {}).get("attempts") or []
    rows = []
    for a in attempts:
        provider = escape(str(a.get("provider") or "provider"))
        http = escape(str(a.get("http") if a.get("http") is not None else "—"))
        games = escape(str(a.get("games") or 0))
        size = escape(str(a.get("bytes") or 0))
        err = escape(str(a.get("error") or ""))
        rows.append(f'<div class="mlb32-row"><b>{provider}</b> • HTTP {http} • {games} games • {size} bytes' + (f'<br><span class="mlb32-bad">{err}</span>' if err else '') + '</div>')
    return ''.join(rows) or '<div class="mlb32-row">No provider attempts were recorded.</div>'


def render_slate_hub(games_df, section_header, status_info, team_logo, h):
    st.markdown(CSS, unsafe_allow_html=True)

    try:
        day = schedule.current_selected_date()
    except Exception:
        day = None
    if not day and games_df is not None and not games_df.empty and "game_date" in games_df.columns:
        day = str(games_df.iloc[0].get("game_date") or "")
    day = str(day or pd.Timestamp.now(tz="America/New_York").date())[:10]

    # Do not trust the global bootstrap if it is empty. V3.2 owns the MLB Slate load.
    try:
        fresh, diag = schedule.load_with_diagnostics(day)
    except Exception as exc:
        fresh = pd.DataFrame()
        diag = {"version":"V3.2","date":day,"source":"none","games":0,"attempts":[{"provider":"V3.2 loader","error":f"{type(exc).__name__}: {exc}","games":0}]}

    if fresh is not None and not fresh.empty:
        source = escape(str((diag or {}).get("source") or "MLB schedule"))
        st.markdown(
            f'<div class="mlb32-box"><div class="mlb32-title">⚾ MLB Schedule V3.2 • <span class="mlb32-ok">{len(fresh)} games loaded</span></div>'
            f'<div class="mlb32-sub">{escape(day)} • Source: {source} • MLB-only recovery path active</div></div>',
            unsafe_allow_html=True,
        )
        return base.render_slate_hub(fresh, section_header, status_info, team_logo, h)

    st.markdown(
        f'<div class="mlb32-box"><div class="mlb32-title">⚾ MLB Schedule V3.2 • <span class="mlb32-bad">provider diagnostics</span></div>'
        f'<div class="mlb32-sub">No games reached the slate for {escape(day)}. These are the actual transport/parser results:</div>{_diag_html(diag)}</div>',
        unsafe_allow_html=True,
    )
    if st.button("🔄 RETRY MLB SCHEDULE V3.2", use_container_width=True, key=f"mlb32_retry_{day}"):
        schedule.clear_schedule_cache()
        st.rerun()
