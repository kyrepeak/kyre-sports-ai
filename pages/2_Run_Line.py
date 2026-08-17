from html import escape

import pandas as pd
import streamlit as st

from engine import ET, games_today, requests
from spread_engine import render_spread_module


st.markdown(
    """
    <style>
    :root {
        --ks-bg:#080d16;
        --ks-panel:#0f1726;
        --ks-border:rgba(148,163,184,.18);
        --ks-text:#f8fafc;
        --ks-muted:#94a3b8;
        --ks-blue:#38bdf8;
        --ks-blue2:#2563eb;
        --ks-green:#22c55e;
        --ks-red:#ef4444;
    }
    .stApp{background:radial-gradient(circle at 12% 0%,rgba(37,99,235,.14),transparent 32rem),var(--ks-bg)}
    .block-container{max-width:1180px;padding-top:1.1rem;padding-bottom:4rem}
    .ks-hero{background:linear-gradient(135deg,rgba(37,99,235,.22),rgba(15,23,38,.96) 58%,rgba(56,189,248,.08));border:1px solid var(--ks-border);border-radius:22px;padding:22px 24px;margin-bottom:18px;box-shadow:0 20px 50px rgba(0,0,0,.22)}
    .ks-eyebrow{color:var(--ks-blue);font-size:.75rem;font-weight:900;letter-spacing:.13em;text-transform:uppercase}
    .ks-title{color:var(--ks-text);font-size:clamp(2rem,5vw,3.1rem);line-height:1;font-weight:950;letter-spacing:-.045em;margin-top:5px}
    .ks-subtitle{color:var(--ks-muted);font-size:.95rem;margin:.65rem 0 0}
    .ks-pills{display:flex;flex-wrap:wrap;gap:7px;margin-top:14px}
    .ks-pill{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--ks-border);border-radius:999px;background:rgba(15,23,42,.72);color:#cbd5e1;padding:6px 9px;font-size:.74rem;font-weight:800;white-space:nowrap}
    .ks-section{margin:22px 0 10px}
    .ks-section h2{margin:0;color:var(--ks-text);font-size:1.45rem;letter-spacing:-.025em}
    .ks-kicker{color:var(--ks-muted);font-size:.82rem;margin-top:3px}
    .ks-feature{border:1px solid var(--ks-border);border-radius:19px;background:linear-gradient(135deg,rgba(37,99,235,.16),rgba(15,23,38,.96));padding:18px;margin:10px 0 14px}
    .ks-feature-name{color:var(--ks-text);font-size:1.35rem;font-weight:950;letter-spacing:-.03em}
    .ks-feature-meta{color:var(--ks-muted);margin-top:5px;font-size:.82rem;overflow-wrap:anywhere}
    .ks-feature-prob{font-size:clamp(2.7rem,8vw,4.3rem);font-weight:950;line-height:1;letter-spacing:-.06em;color:#f8fafc;margin-top:13px}
    .ks-note{border-left:3px solid var(--ks-blue);background:rgba(56,189,248,.06);padding:10px 12px;color:#cbd5e1;border-radius:0 10px 10px 0;font-size:.82rem;margin:10px 0}
    .ks-player-row{display:flex;align-items:center;gap:10px;min-width:0}
    .ks-player-copy{min-width:0}
    .ks-team-logo{width:34px;height:34px;object-fit:contain;flex:0 0 auto;filter:drop-shadow(0 4px 8px rgba(0,0,0,.2))}
    .ks-badge{display:inline-block;border-radius:999px;padding:4px 7px;font-size:.64rem;font-weight:950;letter-spacing:.04em;white-space:nowrap}
    .ks-high{background:rgba(34,197,94,.14);color:#86efac;border:1px solid rgba(34,197,94,.28)}
    .ks-medium{background:rgba(245,158,11,.14);color:#fde68a;border:1px solid rgba(245,158,11,.28)}
    .ks-low{background:rgba(239,68,68,.14);color:#fca5a5;border:1px solid rgba(239,68,68,.28)}
    div[data-testid="stMetric"]{background:rgba(15,23,38,.78);border:1px solid var(--ks-border);border-radius:13px;padding:9px 11px;min-height:88px}
    div[data-testid="stMetricLabel"]{color:var(--ks-muted)}
    div[data-testid="stMetricValue"]{color:var(--ks-text);font-size:clamp(1.12rem,3vw,1.75rem)}
    .stButton>button{border-radius:11px;font-weight:850;min-height:44px}
    .stButton>button[kind="primary"]{background:linear-gradient(135deg,var(--ks-blue2),#0284c7)!important;border:1px solid rgba(125,211,252,.55)!important;color:white!important;box-shadow:0 8px 24px rgba(37,99,235,.20)}
    div[data-testid="stExpander"]{border:1px solid var(--ks-border);border-radius:13px;background:rgba(15,23,38,.5)}
    @media(max-width:700px){.block-container{padding-left:.8rem;padding-right:.8rem}.ks-hero{padding:18px 16px;border-radius:17px}.ks-team-logo{width:29px;height:29px}}
    </style>
    """,
    unsafe_allow_html=True,
)


def h(value):
    return escape(str(value if value is not None else ""))


def section_header(title, subtitle=""):
    st.markdown(
        '<div class="ks-section">'
        f'<h2>{h(title)}</h2>'
        f'<div class="ks-kicker">{h(subtitle)}</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def status_info(status):
    text = str(status or "Unknown")
    low = text.lower()
    if any(x in low for x in ["final", "game over", "completed"]):
        return "FINAL", "ks-final"
    if any(x in low for x in ["in progress", "live", "delayed", "warmup"]):
        return "LIVE", "ks-live"
    return "PREGAME", "ks-pregame"


def team_logo(team_id):
    if team_id is None or (isinstance(team_id, float) and pd.isna(team_id)):
        return ""
    try:
        tid = int(team_id)
    except (TypeError, ValueError):
        return ""
    return f'<img class="ks-team-logo" src="https://www.mlbstatic.com/team-logos/{tid}.svg" alt="team logo">'


try:
    games_df, game_date = games_today()
except requests.RequestException:
    games_df, game_date = pd.DataFrame(), "Unavailable"

st.markdown(
    '<div class="ks-hero">'
    '<div class="ks-eyebrow">V15 Team Market Engine</div>'
    '<div class="ks-title">⚾ MLB RUN LINE AI</div>'
    '<p class="ks-subtitle">Independent projected scores, run margins, cover probabilities and Monte Carlo uncertainty.</p>'
    '<div class="ks-pills">'
    '<span class="ks-pill">🧠 KYRE SPORTS AI</span>'
    '<span class="ks-pill">📐 Spread Model V15</span>'
    f'<span class="ks-pill">📅 {h(game_date)}</span>'
    '</div></div>',
    unsafe_allow_html=True,
)

render_spread_module(games_df, section_header, status_info, team_logo, h)

st.caption("Kyre Sports AI • MLB Run Line Model V15 • Foundation build")
