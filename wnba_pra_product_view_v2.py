"""FanDuel-qualified customer presentation for the preserved WNBA PRA engine."""
from __future__ import annotations

from html import escape
import math

import pandas as pd
import streamlit as st

import wnba_pra_advanced_diagnostics_v1 as diagnostics


PRODUCT_CSS = r"""
<style>
.fd-wrap{display:flex;flex-direction:column;gap:12px;margin:.35rem 0 1.25rem}
.fd-hero{border:1px solid rgba(56,189,248,.28);border-radius:20px;padding:16px;background:radial-gradient(circle at 92% 0,rgba(34,197,94,.10),transparent 34%),linear-gradient(145deg,#0a1727,#07111d)}
.fd-eyebrow{font-size:.63rem;font-weight:950;letter-spacing:.13em;text-transform:uppercase;color:#67ddff}.fd-title{font-size:clamp(1.8rem,6vw,2.8rem);font-weight:1000;color:#fff;letter-spacing:-.04em}.fd-sub{color:#9fb2c7;font-size:.76rem;line-height:1.5}.fd-pills{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}.fd-pill{border:1px solid #29435c;background:#091624;color:#aec2d5;border-radius:999px;padding:5px 9px;font-size:.56rem;font-weight:850}.fd-pill.live{color:#86efac;border-color:#286344;background:#082219}
.fd-board{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.fd-card{border:1px solid #29445f;border-radius:17px;background:linear-gradient(145deg,#0a1725,#07121d);padding:13px;min-width:0}.fd-person{display:flex;align-items:center;gap:9px}.fd-face{width:50px;height:50px;border-radius:50%;object-fit:cover;background:#102235}.fd-logo{width:27px;height:27px;object-fit:contain}.fd-name{color:#fff;font-size:.98rem;font-weight:950}.fd-meta{color:#849bb4;font-size:.59rem}.fd-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin-top:10px}.fd-metric{border:1px solid #20384f;border-radius:10px;background:#07131f;padding:8px;min-width:0}.fd-metric span{display:block;color:#7189a3;font-size:.43rem;font-weight:900;text-transform:uppercase}.fd-metric b{display:block;color:#fff;font-size:.8rem;margin-top:2px;overflow-wrap:anywhere}.fd-metric.primary b{color:#86efac}.fd-foot{margin-top:9px;color:#8da4bb;font-size:.58rem;line-height:1.45}.fd-detail{font-size:.74rem;color:#b8c7d8;line-height:1.55}.fd-detail strong{color:#fff}.fd-detail-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin:.45rem 0}.fd-mini{border:1px solid #263d55;border-radius:10px;padding:7px;background:#081522}.fd-mini span{display:block;color:#718aa4;font-size:.46rem;text-transform:uppercase}.fd-mini b{color:#fff;font-size:.78rem}.fd-final{border:1px solid rgba(45,212,191,.26);border-radius:18px;padding:13px;background:linear-gradient(145deg,#071b20,#07131e)}.fd-final-row{border-bottom:1px solid #1b3541;padding:9px 2px}.fd-final-row:last-child{border-bottom:0}.fd-final-row b{color:#fff}.fd-final-row span{color:#8fa8ba;font-size:.65rem}
@media(max-width:720px){.fd-board{grid-template-columns:1fr}.fd-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.fd-detail-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.fd-hero{padding:14px}.fd-title{font-size:2rem}}
</style>
"""


def _fmt(value, digits=1, suffix=""):
    try:
        number = float(value)
        if math.isnan(number):
            return "—"
        return f"{number:.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return "—"


def _pct(value):
    try:
        return f"{100.0 * float(value):.1f}%"
    except (TypeError, ValueError):
        return "—"


def _odds(value):
    try:
        number = int(value)
        return f"+{number}" if number > 0 else str(number)
    except (TypeError, ValueError):
        return "—"


def _player_card(view):
    face = (
        f'<img class="fd-face" src="{escape(view.headshot_url)}" alt="{escape(view.player)}">'
        if view.headshot_url else '<div class="fd-face"></div>'
    )
    logo = (
        f'<img class="fd-logo" src="{escape(view.team_logo_url)}" alt="team logo">'
        if view.team_logo_url else ""
    )
    line = _fmt(view.fanduel_line)
    edge = _fmt(float(view.edge) * 100.0, 1, " pp") if view.edge is not None else "—"
    prices = f"O {_odds(view.fanduel_over_odds)} • U {_odds(view.fanduel_under_odds)}"
    evidence = escape(str(view.evidence_state or "UNAVAILABLE").replace("_", " "))
    freshness = escape(str(view.market_freshness or "UNAVAILABLE").replace("_", " "))
    decision = escape(view.decision_label or "Research only")
    confidence = _fmt(view.decision_strength)
    return (
        '<div class="fd-card"><div class="fd-person">' + face + logo +
        f'<div><div class="fd-name">{escape(view.player)}</div>'
        f'<div class="fd-meta">{escape(view.team)} vs {escape(view.opponent)}</div></div></div>'
        '<div class="fd-grid">'
        f'<div class="fd-metric primary"><span>FanDuel PRA</span><b>{line}</b></div>'
        f'<div class="fd-metric"><span>Model PRA</span><b>{_fmt(view.proj_pra)}</b></div>'
        f'<div class="fd-metric"><span>Over / Under</span><b>{_pct(view.over_probability)} / {_pct(view.under_probability)}</b></div>'
        f'<div class="fd-metric"><span>Edge</span><b>{edge}</b></div>'
        f'<div class="fd-metric"><span>Decision</span><b>{decision}</b></div>'
        f'<div class="fd-metric"><span>Confidence</span><b>{confidence}</b></div>'
        f'</div><div class="fd-foot">FanDuel prices: {prices}<br>{freshness} • {evidence} • {view.book_count} comparison source(s)</div></div>'
    )


def _player_detail(view):
    st.markdown(
        '<div class="fd-detail"><strong>Decision Snapshot</strong>'
        f'<div class="fd-detail-grid"><div class="fd-mini"><span>FanDuel PRA</span><b>{_fmt(view.fanduel_line)}</b></div>'
        f'<div class="fd-mini"><span>Model PRA</span><b>{_fmt(view.proj_pra)}</b></div>'
        f'<div class="fd-mini"><span>Over</span><b>{_pct(view.over_probability)}</b></div>'
        f'<div class="fd-mini"><span>Under</span><b>{_pct(view.under_probability)}</b></div></div>'
        '<strong>P / R / A Breakdown</strong>'
        f'<div class="fd-detail-grid"><div class="fd-mini"><span>Points</span><b>{_fmt(view.proj_pts)}</b></div>'
        f'<div class="fd-mini"><span>Rebounds</span><b>{_fmt(view.proj_reb)}</b></div>'
        f'<div class="fd-mini"><span>Assists</span><b>{_fmt(view.proj_ast)}</b></div>'
        f'<div class="fd-mini"><span>PRA</span><b>{_fmt(view.proj_pra)}</b></div></div>'
        f'<p><strong>Minutes + Role:</strong> {_fmt(view.projected_minutes)} projected minutes • {escape(view.role_label or "Role pending")}</p>'
        '<p><strong>Recent Form:</strong> Verified recent-game evidence from the preserved research stack is used when available; no result is invented when unavailable.</p>'
        '<p><strong>Opponent Context:</strong> Preserved matchup-adjusted model output is used when available; the page adds no extra coefficient.</p>'
        '<p><strong>Matchup History:</strong> Verified descriptive player-vs-opponent history is shown only when the preserved research stack supplies it.</p>'
        f'<p><strong>Sources + Freshness:</strong> FanDuel eligibility is {escape(view.market_freshness)} • evidence {escape(view.evidence_state.replace("_", " "))} • other books are comparison only.</p>'
        '</div>',
        unsafe_allow_html=True,
    )


def render_pra_product(snapshot, context, player_views, consensus) -> None:
    st.markdown(PRODUCT_CSS, unsafe_allow_html=True)
    eligible = tuple(
        view for view in player_views
        if bool(getattr(view, "fanduel_eligible", False)) and getattr(view, "fanduel_line", None) is not None
    )

    st.markdown(
        '<div class="fd-wrap"><div class="fd-hero">'
        '<div class="fd-eyebrow">KYRE SPORTS AI • WNBA</div><div class="fd-title">🏀 WNBA PRA</div>'
        f'<div class="fd-sub">{escape(context.competition_label)} • {escape(context.series_label or "Verified slate context")}<br>'
        'Only current exact FanDuel PRA players appear on the primary board.</div>'
        f'<div class="fd-pills"><div class="fd-pill live">FanDuel-qualified</div><div class="fd-pill">Kyre model</div><div class="fd-pill">{escape(context.evidence_state.replace("_", " "))}</div></div>'
        '</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown("### PRA Player Board")
    if not eligible:
        st.info(
            "FanDuel PRA markets are pending or no current exact FanDuel player market is available for this verified slate. "
            "The page will not substitute another sportsbook or a stale line."
        )
    else:
        st.markdown('<div class="fd-board">' + ''.join(_player_card(view) for view in eligible) + '</div>', unsafe_allow_html=True)
        for view in eligible:
            with st.expander(f"{view.player} • Full PRA Analysis", expanded=False):
                _player_detail(view)

    if any(view.availability_label == "UNRESOLVED" for view in eligible):
        st.warning("One or more FanDuel-listed players still have unresolved availability; Final Card certification remains blocked for those players.")

    st.markdown("### 🏆 Final PRA Card")
    selected = [view for view in eligible if view.final_card_selected]
    if not selected:
        st.info("No FanDuel-qualified PRA selection is certified for this slate yet. No pick is being forced.")
    else:
        rows = []
        for index, view in enumerate(selected[:5], 1):
            rows.append(
                f'<div class="fd-final-row"><b>#{index} {escape(view.player)} — {escape(view.decision_label or "Qualified PRA")}</b><br>'
                f'<span>{escape(view.team)} vs {escape(view.opponent)} • FanDuel PRA {_fmt(view.fanduel_line)} • Model PRA {_fmt(view.proj_pra)} • Over {_pct(view.over_probability)}</span></div>'
            )
        st.markdown('<div class="fd-final">' + ''.join(rows) + '</div>', unsafe_allow_html=True)

    diagnostics.render_advanced_diagnostics(snapshot, context, consensus)


__all__ = ["PRODUCT_CSS", "render_pra_product"]
