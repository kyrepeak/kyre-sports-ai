"""Playoff-first customer presentation for the preserved WNBA PRA engine."""
from __future__ import annotations

from html import escape
import math
import pandas as pd
import streamlit as st

import wnba_pra_advanced_diagnostics_v1 as diagnostics

PRODUCT_CSS = r"""
<style>
.kp-wrap{display:flex;flex-direction:column;gap:14px;margin:.35rem 0 1.2rem}
.kp-hero{border:1px solid rgba(56,189,248,.30);border-radius:22px;padding:18px;background:radial-gradient(circle at 90% 0,rgba(236,72,153,.13),transparent 35%),linear-gradient(145deg,#0b1728,#07111d)}
.kp-eyebrow{font-size:.66rem;font-weight:950;letter-spacing:.13em;text-transform:uppercase;color:#62d9ff}.kp-title{font-size:clamp(1.9rem,6vw,3rem);font-weight:1000;color:#fff;letter-spacing:-.045em}.kp-sub{color:#a1b4ca;font-size:.78rem;line-height:1.5}.kp-pills{display:flex;flex-wrap:wrap;gap:7px;margin-top:12px}.kp-pill{border:1px solid #29435d;background:#091624;color:#a9bed3;border-radius:999px;padding:5px 9px;font-size:.57rem;font-weight:850}.kp-pill.good{color:#7cf0ba;border-color:#2b6e56;background:#09251d}.kp-pill.warn{color:#ffe08a;border-color:#6f5d25;background:#241e0b}
.kp-next{border:1px solid #35536f;border-radius:16px;background:#091725;padding:13px 14px}.kp-next b{color:#fff}.kp-next span{color:#9fb3ca;font-size:.72rem}.kp-board{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.kp-player{border:1px solid #29445f;border-radius:18px;background:linear-gradient(145deg,#0a1725,#07121d);padding:14px}.kp-person{display:flex;align-items:center;gap:10px}.kp-face{width:52px;height:52px;border-radius:50%;object-fit:cover;background:#102235}.kp-logo{width:28px;height:28px;object-fit:contain}.kp-name{color:#fff;font-size:1rem;font-weight:950}.kp-meta{color:#8299b2;font-size:.6rem}.kp-metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:11px}.kp-metric{border:1px solid #20384f;border-radius:11px;background:#07131f;padding:8px}.kp-metric span{display:block;color:#7189a3;font-size:.42rem;font-weight:900;text-transform:uppercase}.kp-metric b{display:block;color:#fff;font-size:.82rem;margin-top:2px}.kp-metric.hot b{color:#79efba}.kp-line{margin-top:9px;color:#8ba2ba;font-size:.6rem}.kp-final{border:1px solid rgba(45,212,191,.28);border-radius:20px;padding:14px;background:linear-gradient(145deg,#071b20,#07131e)}.kp-final-row{border-bottom:1px solid #1b3541;padding:10px 2px}.kp-final-row:last-child{border-bottom:0}.kp-final-row b{color:#fff}.kp-final-row span{color:#8fa8ba;font-size:.66rem}.kp-detail{font-size:.74rem;color:#b8c7d8;line-height:1.55}.kp-detail strong{color:#fff}.kp-grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin:.45rem 0}.kp-mini{border:1px solid #263d55;border-radius:10px;padding:7px;background:#081522}.kp-mini span{display:block;color:#718aa4;font-size:.46rem;text-transform:uppercase}.kp-mini b{color:#fff;font-size:.78rem}
@media(max-width:720px){.kp-board{grid-template-columns:1fr}.kp-metrics{grid-template-columns:repeat(2,1fr)}.kp-grid4{grid-template-columns:repeat(2,1fr)}.kp-hero{padding:15px}.kp-title{font-size:2rem}}
</style>
"""


def _fmt(value, digits=1, suffix=""):
    try:
        x=float(value)
        if math.isnan(x): return "—"
        return f"{x:.{digits}f}{suffix}"
    except (TypeError,ValueError): return "—"


def _pct(value):
    try: return f"{100*float(value):.1f}%"
    except (TypeError,ValueError): return "—"


def _game_parts(game):
    if not isinstance(game, dict): return "", "", ""
    away=game.get("away") if isinstance(game.get("away"),dict) else {}
    home=game.get("home") if isinstance(game.get("home"),dict) else {}
    away_name=str(away.get("full_name") or away.get("team_name") or game.get("away_team") or "Away")
    home_name=str(home.get("full_name") or home.get("team_name") or game.get("home_team") or "Home")
    tip=str(game.get("game_datetime_eastern") or game.get("first_tip_et") or "Tip time TBD")
    return away_name,home_name,tip


def _player_card(v):
    face=f'<img class="kp-face" src="{escape(v.headshot_url)}" alt="{escape(v.player)}">' if v.headshot_url else '<div class="kp-face"></div>'
    logo=f'<img class="kp-logo" src="{escape(v.team_logo_url)}" alt="team logo">' if v.team_logo_url else ''
    market="—" if v.market_line is None else _fmt(v.market_line)
    books=f"{v.book_count} books" if v.book_count else "market pending"
    return (
        '<div class="kp-player"><div class="kp-person">'+face+logo+
        f'<div><div class="kp-name">{escape(v.player)}</div><div class="kp-meta">{escape(v.team)} vs {escape(v.opponent)} • {escape(v.availability_label)}</div></div></div>'
        '<div class="kp-metrics">'
        f'<div class="kp-metric hot"><span>Model PRA</span><b>{_fmt(v.proj_pra)}</b></div>'
        f'<div class="kp-metric"><span>Market Line</span><b>{market}</b></div>'
        f'<div class="kp-metric"><span>Over / Under</span><b>{_pct(v.over_probability)} / {_pct(v.under_probability)}</b></div>'
        f'<div class="kp-metric"><span>Edge</span><b>{_fmt((v.edge or 0)*100,1," pp") if v.edge is not None else "—"}</b></div>'
        f'<div class="kp-metric"><span>Confidence</span><b>{_fmt(v.decision_strength)}</b></div>'
        f'<div class="kp-metric"><span>Minutes</span><b>{_fmt(v.projected_minutes)}</b></div>'
        f'</div><div class="kp-line">{escape(books)} • Evidence: {escape(v.evidence_state.replace("_"," "))}</div></div>'
    )


def _player_detail(v):
    st.markdown(
        '<div class="kp-detail"><strong>Decision Snapshot</strong>'
        f'<div class="kp-grid4"><div class="kp-mini"><span>Projected PRA</span><b>{_fmt(v.proj_pra)}</b></div>'
        f'<div class="kp-mini"><span>Market</span><b>{_fmt(v.market_line)}</b></div>'
        f'<div class="kp-mini"><span>Over</span><b>{_pct(v.over_probability)}</b></div>'
        f'<div class="kp-mini"><span>Availability</span><b>{escape(v.availability_label)}</b></div></div>'
        '<strong>P / R / A Breakdown</strong>'
        f'<div class="kp-grid4"><div class="kp-mini"><span>Points</span><b>{_fmt(v.proj_pts)}</b></div><div class="kp-mini"><span>Rebounds</span><b>{_fmt(v.proj_reb)}</b></div><div class="kp-mini"><span>Assists</span><b>{_fmt(v.proj_ast)}</b></div><div class="kp-mini"><span>PRA</span><b>{_fmt(v.proj_pra)}</b></div></div>'
        f'<p><strong>Minutes + Role:</strong> {_fmt(v.projected_minutes)} projected minutes • {escape(v.role_label or "Role pending")}</p>'
        '<p><strong>Recent Form:</strong> Shown only when verified recent-game evidence is supplied by the preserved research stack.</p>'
        '<p><strong>Opponent Context:</strong> Preserved matchup-adjusted projection is used when available; no extra adjustment is added by this page.</p>'
        '<p><strong>Matchup History:</strong> Descriptive verified history only when available; never fabricated or promoted into model weight here.</p>'
        f'<p><strong>Market Comparison:</strong> {v.book_count} current source(s) represented • consensus presentation does not move the model projection.</p>'
        f'<p><strong>Why This Side:</strong> {escape(v.decision_label or "No final side qualified yet.")}</p>'
        f'<p><strong>Sources + Freshness:</strong> Evidence state {escape(v.evidence_state.replace("_"," "))}.</p></div>',
        unsafe_allow_html=True,
    )


def render_pra_product(snapshot, context, player_views, consensus) -> None:
    st.markdown(PRODUCT_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="kp-wrap"><div class="kp-hero">'
        '<div class="kp-eyebrow">KYRE SPORTS AI • WNBA PLAYOFFS</div><div class="kp-title">🏀 WNBA PRA</div>'
        f'<div class="kp-sub">{escape(context.competition_label)} • {escape(context.series_label or "Verified slate context")}<br>Selected {escape(context.selected_date)} • Research slate {escape(context.effective_date)}</div>'
        f'<div class="kp-pills"><div class="kp-pill good">PRA-first</div><div class="kp-pill">{escape(context.evidence_state.replace("_"," "))}</div><div class="kp-pill">{len(context.sources)} schedule sources</div></div>'
        '</div></div>', unsafe_allow_html=True,
    )
    if not context.today_has_game and context.off_day_message:
        away,home,tip=_game_parts(dict(context.next_game or {}))
        st.info("No WNBA game today. The page has moved preparation to the next verified playoff game.")
        if context.next_game:
            st.markdown(f'<div class="kp-next"><b>Next: {escape(away)} @ {escape(home)}</b><br><span>{escape(tip)}</span></div>',unsafe_allow_html=True)

    st.markdown("### PRA Player Board")
    if not player_views:
        st.info("Player PRA research is not available for the verified slate yet. No player rows are being fabricated.")
    else:
        st.markdown('<div class="kp-board">'+''.join(_player_card(v) for v in player_views)+'</div>',unsafe_allow_html=True)
        for v in player_views:
            with st.expander(f"{v.player} • Full PRA Analysis", expanded=False):
                _player_detail(v)

    if not any(v.market_line is not None for v in player_views):
        st.info("PRA market lines are not available yet. Model projections remain visible; final market decisions are paused.")
    if any(v.availability_label == "UNRESOLVED" for v in player_views):
        st.warning("Final PRA decisions are waiting for verified availability.")

    st.markdown("### 🏆 Final PRA Card")
    by_key={(v.game_id,v.player_key):v for v in player_views}
    rendered=0
    if isinstance(snapshot.final_card,pd.DataFrame) and not snapshot.final_card.empty:
        for row in snapshot.final_card.head(5).to_dict("records"):
            v=by_key.get((str(row.get("game_id") or ""),str(row.get("player_key") or "")))
            if v is None or not v.final_card_selected: continue
            rendered+=1
            st.markdown(f'<div class="kp-final-row"><b>#{rendered} {escape(v.player)} — {escape(v.decision_label or "Qualified PRA")}</b><br><span>{escape(v.team)} vs {escape(v.opponent)} • Model PRA {_fmt(v.proj_pra)} • Market {_fmt(v.market_line)} • Over {_pct(v.over_probability)}</span></div>',unsafe_allow_html=True)
    if rendered == 0:
        st.info("No final PRA selections are certified for this slate yet. The page will not force picks.")

    diagnostics.render_advanced_diagnostics(snapshot, context, consensus)


__all__=["PRODUCT_CSS","render_pra_product"]
