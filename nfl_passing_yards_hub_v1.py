"""NFL Passing Yards V1 compact foundation page.

Presentation-only foundation for the dedicated NFL Passing Yards route. Reuses
verified NFL slate/date identity from the existing NFL hub and intentionally
keeps projection, sportsbook grading, Monte Carlo, ranking, and recommendation
logic OFF until the passing-yards build steps are added.
"""
from __future__ import annotations

from datetime import datetime
from html import escape

import pandas as pd
import streamlit as st

import nfl_hub_v18 as base

MODEL_VERSION = "NFL PASSING YARDS V1 • COMPACT FOUNDATION • VERIFIED SLATE"

_CSS = r"""
<style>
/* Keep the shared shell, but stop it from consuming the first screen. */
.ks-shell{padding:10px 14px!important;margin-bottom:9px!important;border-radius:14px!important}
.ks-eyebrow{font-size:.58rem!important}.ks-title{font-size:1.55rem!important;margin-top:1px!important}
.ks-sub{font-size:.68rem!important;margin-top:2px!important}

.kpy-head{display:flex;align-items:center;justify-content:space-between;gap:12px;border:1px solid #294967;
background:linear-gradient(135deg,#0b1726,#0a1320);border-radius:14px;padding:11px 13px;margin:8px 0 10px}
.kpy-title{color:#f8fafc;font-size:1.18rem;font-weight:950;letter-spacing:-.02em}.kpy-title span{color:#7ff2c2}
.kpy-sub{color:#8197ac;font-size:.64rem;margin-top:2px}.kpy-chips{display:flex;gap:5px;flex-wrap:wrap;justify-content:flex-end}
.kpy-chip{border:1px solid #2d506b;background:#0a1a2a;border-radius:999px;padding:4px 7px;color:#9bd9f5;font-size:.52rem;font-weight:900;white-space:nowrap}
.kpy-strip{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin:5px 0 10px}
.kpy-stat{border:1px solid #263f57;background:#091522;border-radius:10px;padding:6px 9px;min-width:84px}
.kpy-stat b{display:block;color:#f6fbff;font-size:.9rem;line-height:1}.kpy-stat span{display:block;color:#72899e;font-size:.5rem;font-weight:800;text-transform:uppercase;margin-top:3px}
.kpy-note{border:1px dashed #35506c;background:#091523;border-radius:11px;padding:10px 12px;color:#8fa4bd;font-size:.68rem;line-height:1.45;margin:7px 0}
.kpy-ok{color:#7ff2c2;font-weight:900}.kpy-warn{color:#f5c76e;font-weight:900}
.kpy-section{margin:11px 0 6px;color:#f8fafc;font-size:.92rem;font-weight:900}
.kpy-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:7px}
.kpy-game{border:1px solid #263f57;background:#081522;border-radius:12px;padding:9px 10px}
.kpy-game-top{display:flex;justify-content:space-between;gap:8px;color:#7890a8;font-size:.51rem;font-weight:900;text-transform:uppercase}
.kpy-team{display:flex;align-items:center;gap:7px;margin-top:7px;color:#f4f8ff;font-size:.72rem;font-weight:850}
.kpy-logo{width:26px;height:26px;object-fit:contain;flex:0 0 26px}.kpy-rec{color:#6f879d;font-size:.5rem;font-weight:700;margin-left:auto}
.kpy-meta{border-top:1px solid #183047;margin-top:7px;padding-top:6px;color:#6f879d;font-size:.5rem;display:flex;gap:8px;flex-wrap:wrap}
@media(max-width:700px){.kpy-head{align-items:flex-start;flex-direction:column}.kpy-chips{justify-content:flex-start}.kpy-grid{grid-template-columns:1fr}.kpy-stat{min-width:72px}}
</style>
"""


def _safe(value, default="") -> str:
    text = str(value or "").strip()
    return text or default


def _logo(url: str, name: str) -> str:
    if not url:
        return ""
    return (
        f'<img class="kpy-logo" src="{escape(url, quote=True)}" '
        f'alt="{escape(name, quote=True)} logo" loading="lazy">'
    )


def _game_card(row) -> str:
    away = _safe(row.get("away_team"), "Away")
    home = _safe(row.get("home_team"), "Home")
    return f'''
    <article class="kpy-game">
      <div class="kpy-game-top"><span>{escape(_safe(row.get('season_type'), 'NFL'))}</span><span>{escape(_safe(row.get('status'), 'Scheduled'))}</span></div>
      <div class="kpy-team">{_logo(_safe(row.get('away_logo')), away)}<span>{escape(away)}</span><span class="kpy-rec">{escape(_safe(row.get('away_record'), '—'))}</span></div>
      <div class="kpy-team">{_logo(_safe(row.get('home_logo')), home)}<span>{escape(home)}</span><span class="kpy-rec">{escape(_safe(row.get('home_record'), '—'))}</span></div>
      <div class="kpy-meta"><span>🕒 {escape(_safe(row.get('tip_et'), 'TBD'))}</span><span>🏟️ {escape(_safe(row.get('venue'), 'Venue TBD'))}</span><span>📺 {escape(_safe(row.get('broadcast'), '—'))}</span></div>
    </article>
    '''


def render_nfl_passing_yards_hub() -> None:
    """Render the compact Passing Yards foundation without enabling model math."""
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="kpy-head">'
        '<div><div class="kpy-title">🏈 NFL <span>Passing Yards</span></div>'
        '<div class="kpy-sub">Compact workspace • verified NFL slate foundation • passing model still protected/off</div></div>'
        '<div class="kpy-chips">'
        '<span class="kpy-chip">PASS YARDS</span><span class="kpy-chip">VERIFIED SLATE</span><span class="kpy-chip">MODEL OFF</span>'
        '</div></div>',
        unsafe_allow_html=True,
    )

    key = "nfl_passing_yards_v1_date"
    if key not in st.session_state:
        st.session_state[key] = datetime.now(base.ET).date()

    c_date, c_space = st.columns([1.1, 2.9])
    with c_date:
        st.caption("📅 Slate date")
        day = st.date_input(
            "NFL Passing Yards slate date",
            value=st.session_state[key],
            key="nfl_passing_yards_v1_date_input",
            label_visibility="collapsed",
        )
    st.session_state[key] = day
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")

    with st.spinner("Verifying NFL slate…"):
        games, diag = base.load_nfl_slate(day_str)

    live = int((games.get("state", pd.Series(dtype=str)).astype(str) == "in").sum()) if not games.empty else 0
    final = int((games.get("state", pd.Series(dtype=str)).astype(str) == "post").sum()) if not games.empty else 0
    upcoming = int((games.get("state", pd.Series(dtype=str)).astype(str) == "pre").sum()) if not games.empty else 0

    st.markdown(
        '<div class="kpy-strip">'
        f'<div class="kpy-stat"><b>{len(games)}</b><span>Games</span></div>'
        f'<div class="kpy-stat"><b>{upcoming}</b><span>Upcoming</span></div>'
        f'<div class="kpy-stat"><b>{live}</b><span>Live</span></div>'
        f'<div class="kpy-stat"><b>{final}</b><span>Final</span></div>'
        f'<div class="kpy-stat"><b>{escape(day_str)}</b><span>ET Slate</span></div>'
        '</div>',
        unsafe_allow_html=True,
    )

    if not diag.get("request_ok"):
        st.markdown(
            '<div class="kpy-note"><span class="kpy-warn">Schedule unavailable.</span> '
            f"Provider: {escape(_safe(diag.get('provider'), 'ESPN NFL scoreboard'))} • "
            f"HTTP: {escape(_safe(diag.get('http'), '—'))}. No fake games are created.</div>",
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        '<div class="kpy-note"><span class="kpy-ok">✓ Verified NFL schedule</span> • '
        f"{len(games)} game(s) • ESPN NFL scoreboard • ET date guard active • "
        "no projection or sportsbook influence enabled.</div>",
        unsafe_allow_html=True,
    )

    if games.empty:
        st.markdown(
            '<div class="kpy-note">No NFL games on this ET calendar date. Choose another date above. '
            'This is treated as an empty verified slate—not a prediction.</div>',
            unsafe_allow_html=True,
        )
        return

    st.markdown('<div class="kpy-section">Verified matchups</div>', unsafe_allow_html=True)
    cards = "".join(_game_card(row) for _, row in games.iterrows())
    st.markdown(f'<div class="kpy-grid">{cards}</div>', unsafe_allow_html=True)

    st.caption(
        f"{MODEL_VERSION} • UI foundation only. QB starter identity, passing data, matchup engines, projections, probabilities, and rankings are not active yet."
    )


__all__ = ["MODEL_VERSION", "render_nfl_passing_yards_hub"]
