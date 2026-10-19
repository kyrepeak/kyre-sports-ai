"""NFL Spread V9 — consumer-first matchup intelligence + interactive Line Lab.

V9 changes presentation and settlement-only line exploration. Frozen Spread V8/V3/V1
continue to own schedule identity, Kyre Sports API market transport, independent fair
margin, and the deterministic 5M Monte Carlo distribution. The slider never feeds a
sportsbook or hypothetical line back into projection math.
"""
from __future__ import annotations

from datetime import date, datetime
from html import escape
import math
from typing import Any

import pandas as pd
import streamlit as st

import nfl_spread_hub_v4 as frozen_v4
import nfl_spread_hub_v8 as frozen_v8
from nfl_spread_line_lab_v1 import american_break_even, settle_line

MODEL_VERSION = "NFL SPREAD V9 • CONSUMER LINE LAB • V8/V3/V1 FROZEN"
FROZEN_PRIOR = "nfl_spread_hub_v8"
FROZEN_ANALYTICS = "nfl_spread_hub_v3"
FROZEN_TRANSPORT = "nfl_spread_hub_v1"
PRESENTATION_ONLY = True
LINE_LAB_SETTLEMENT_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False

_CSS = r"""
<style data-nfl-spread-v9="true">
.ksp9-hero{padding:18px 19px;margin:4px 0 13px;border:1px solid #315b76;border-radius:18px;background:radial-gradient(circle at 92% 0%,rgba(72,205,255,.11),transparent 34%),linear-gradient(145deg,#091724,#07111a)}
.ksp9-kicker{color:#68d6ff;font-size:.62rem;font-weight:950;letter-spacing:.12em}.ksp9-title{margin-top:5px;color:#f5f9fc;font-size:1.55rem;font-weight:950;letter-spacing:-.03em}.ksp9-title span{color:#7ff2c2}.ksp9-sub{margin-top:6px;color:#91a5b7;font-size:.72rem;line-height:1.45}.ksp9-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}.ksp9-chip{border:1px solid #2d536b;border-radius:999px;padding:5px 8px;color:#9ed7eb;background:#091b28;font-size:.49rem;font-weight:900}.ksp9-chip.good{border-color:#29785f;color:#79efbd}
.ksp9-match{margin:13px 0 8px;border:1px solid #23465c;border-radius:16px;background:#07131e;padding:13px 14px}.ksp9-match-top{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.ksp9-match h3{margin:0;color:#f3f8fc;font-size:1rem}.ksp9-match p{margin:5px 0 0;color:#71889c;font-size:.60rem}.ksp9-badge{border:1px solid #29785f;color:#79efbd;border-radius:999px;padding:5px 8px;font-size:.48rem;font-weight:900;white-space:nowrap}
.ksp9-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin:9px 0}.ksp9-stat{border:1px solid #1d3e51;border-radius:11px;background:#06111a;padding:9px}.ksp9-stat span{display:block;color:#6f879b;font-size:.45rem;font-weight:900;letter-spacing:.06em}.ksp9-stat b{display:block;color:#edf7fd;font-size:.78rem;margin-top:4px}.ksp9-stat b.good{color:#7ff2c2}
.ksp9-prob{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:8px 0 11px}.ksp9-prob>div{border:1px solid #1e4052;border-radius:12px;background:#07131d;padding:10px}.ksp9-prob span{display:block;color:#8198aa;font-size:.55rem;font-weight:850}.ksp9-prob b{display:block;color:#f4f8fb;font-size:1.15rem;margin:2px 0 6px}.ksp9-bar{height:6px;border-radius:999px;background:#132635;overflow:hidden}.ksp9-fill{height:100%;border-radius:999px;background:linear-gradient(90deg,#55c7ff,#7ff2c2)}
.ksp9-why{border:1px solid #23465b;border-radius:14px;background:#081520;padding:11px 12px;margin:9px 0}.ksp9-why h4{margin:0 0 7px;color:#eff8fd;font-size:.77rem}.ksp9-why ul{margin:0;padding-left:18px;color:#9db0bf;font-size:.61rem;line-height:1.55}.ksp9-history{margin-top:8px;color:#91a7b7;font-size:.58rem}.ksp9-history b{color:#e7f4fb}.ksp9-note{color:#71899b;font-size:.55rem;margin:4px 0 12px}.ksp9-lab-title{margin:.55rem 0 .15rem;color:#f5f9fc;font-size:1.02rem;font-weight:950}.ksp9-lab-sub{color:#8298aa;font-size:.62rem;margin-bottom:.2rem}
@media(max-width:820px){.ksp9-summary{grid-template-columns:1fr 1fr}.ksp9-match-top{flex-direction:column}.ksp9-match{padding:11px}.ksp9-title{font-size:1.28rem}}
@media(max-width:520px){.ksp9-summary,.ksp9-prob{grid-template-columns:1fr}.ksp9-hero{padding:14px}.ksp9-title{font-size:1.12rem}.ksp9-stat b{font-size:.72rem}}
</style>
"""


def _num(value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError, OverflowError):
        return math.nan
    return out if math.isfinite(out) else math.nan


def _spread(value: Any) -> str:
    number = _num(value)
    return frozen_v4.frozen.market_api.fmt_spread(number) if math.isfinite(number) else "—"


def _pct(value: Any) -> str:
    number = _num(value)
    return f"{number * 100.0:.1f}%" if math.isfinite(number) else "—"


def _price(value: Any) -> str:
    number = _num(value)
    return frozen_v4.frozen.market_api.fmt_american(number) if math.isfinite(number) else "—"


def _coerce_day(value: Any, fallback: date) -> date:
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return fallback


def _round_half(value: float) -> float:
    return min(30.5, max(-30.5, round(float(value) * 2.0) / 2.0))


def resolve_default_slate(selected: date):
    return frozen_v8.resolve_default_slate(selected)


def _active_day() -> tuple[date, dict[str, Any]]:
    today = datetime.now(frozen_v4.frozen.base.ET).date()
    result = resolve_default_slate(today)
    selected = _coerce_day(result.get("resolved_date"), today) if isinstance(result, dict) else today
    if not isinstance(result, dict) or result.get("state") != "FOUND":
        selected = today
    st.session_state["nfl_v1_date"] = selected
    return selected, result if isinstance(result, dict) else {}


def _hero(selected: date, games: int) -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(
        '<section class="ksp9-hero">'
        '<div class="ksp9-kicker">KYRE SPORTS AI • NFL SPREAD</div>'
        '<div class="ksp9-title">🎯 Spread <span>Intelligence + Line Lab</span></div>'
        '<div class="ksp9-sub">Market vs model first • move the spread in 0.5-point increments • instantly re-grade the frozen 5M margin distribution without rerunning or changing the football model.</div>'
        '<div class="ksp9-chips"><span class="ksp9-chip good">MODEL FIREWALL 0.0%</span><span class="ksp9-chip">5M MARGIN DISTRIBUTION</span><span class="ksp9-chip">LINE LAB SETTLEMENT ONLY</span><span class="ksp9-chip">NO STAKE SIZING</span></div>'
        '</section>', unsafe_allow_html=True,
    )
    st.caption(f"Active verified NFL slate • {selected.strftime('%a, %b %d, %Y')} • {games} matchup(s)")


def _history_html(history: dict[str, Any]) -> str:
    if not isinstance(history, dict) or not history.get("ready"):
        return ""
    meetings = history.get("meetings") or []
    rows = []
    for item in meetings[:5]:
        line = item.get("spread_line")
        ats = item.get("ats_winner")
        extra = f" • verified spread {line:+.1f} • ATS {ats}" if isinstance(line, (int, float)) and ats else ""
        rows.append(f"<div>{escape(str(item.get('date') or ''))} • {escape(str(item.get('score') or ''))}{escape(extra)}</div>")
    if not rows:
        return ""
    return (
        '<div class="ksp9-history"><b>Recent matchup history</b> • '
        + escape(str(history.get("series_summary") or ""))
        + "<br>" + "".join(rows) + "</div>"
    )


def _why_html(away: str, home: str, selected_line: float, lab: dict[str, Any], analytics: dict[str, Any]) -> str:
    fair = _num(lab.get("fair_away_spread"))
    line_value = _num(lab.get("line_value"))
    q = analytics.get("margin_quantiles") or {}
    p25, p75 = _num(q.get("p25")), _num(q.get("p75"))
    quality = str(analytics.get("model_quality") or "CHECK").upper()
    side = away if line_value >= 0 else home
    advantage = abs(line_value) if math.isfinite(line_value) else math.nan
    bullets = [
        f"Model fair spread: {away} {_spread(fair)} / {home} {_spread(-fair) if math.isfinite(fair) else '—'}.",
        f"At the selected line, {side} receives {advantage:.1f} points of line value versus model fair." if math.isfinite(advantage) else "Line-value comparison is unavailable.",
        f"Frozen model quality: {quality}; certified 5M Monte Carlo: {'YES' if analytics.get('certified_run') else 'CHECK'}.",
    ]
    if math.isfinite(p25) and math.isfinite(p75):
        bullets.append(f"Middle 50% of simulated away margin: {p25:+.1f} to {p75:+.1f} points — uncertainty stays visible.")
    items = "".join(f"<li>{escape(text)}</li>" for text in bullets)
    return f'<section class="ksp9-why"><h4>🧠 Why the model sees this line</h4><ul>{items}</ul></section>'


def _diagnostics(game: dict[str, Any], market: dict[str, Any], analytics: dict[str, Any], history: dict[str, Any], lab: dict[str, Any]) -> None:
    away = str(game.get("away_team") or "Away")
    home = str(game.get("home_team") or "Home")
    with st.expander(f"Advanced Diagnostics — {away} @ {home}", expanded=False):
        st.caption(
            "Frozen ownership: V1 schedule + Kyre Sports API market transport • V3 independent fair-margin model + deterministic 5M Monte Carlo • V8 display-only matchup history. Line Lab re-grades only the saved margin distribution."
        )
        st.json({
            "market_ready": bool(market.get("ready")),
            "model_ready": bool(analytics.get("ready")),
            "model_quality": analytics.get("model_quality"),
            "certified_run": bool(analytics.get("certified_run")),
            "converged": bool(analytics.get("converged")),
            "simulations": analytics.get("simulations"),
            "sportsbook_projection_influence": analytics.get("sportsbook_projection_influence", 0.0),
            "line_lab": lab,
            "history_source": history.get("source") if isinstance(history, dict) else None,
        })


def _render_matchup(game: dict[str, Any], market: dict[str, Any], analytics: dict[str, Any]) -> None:
    event_id = str(game.get("game_id") or "unknown")
    away = str(game.get("away_team") or "Away")
    home = str(game.get("home_team") or "Home")
    away_abbr = str(game.get("away_abbr") or "NFL")
    home_abbr = str(game.get("home_abbr") or "NFL")
    tip = str(game.get("tip_et") or "TBD")
    venue = str(game.get("venue") or "Venue TBD")
    broadcast = str(game.get("broadcast") or "—")
    phase = str(game.get("season_type") or "NFL")

    book = frozen_v4._first_book(market)
    market_ready = bool(market.get("ready")) and bool(book)
    market_away = _num(book.get("away_spread")) if market_ready else math.nan
    market_home = _num(book.get("home_spread")) if market_ready else math.nan
    away_price = _num(book.get("away_price")) if market_ready else math.nan
    home_price = _num(book.get("home_price")) if market_ready else math.nan
    projected = _num(analytics.get("projected_away_margin"))
    fair_away = -projected if math.isfinite(projected) else math.nan

    default = market_away if math.isfinite(market_away) else fair_away if math.isfinite(fair_away) else 0.0
    default = _round_half(default)
    slider_key = f"nfl_spread_v9_line_lab_{event_id}"
    if slider_key not in st.session_state:
        st.session_state[slider_key] = default

    market_status = "MARKET READY" if market_ready else "MARKET WAITING"
    st.markdown(
        '<section class="ksp9-match"><div class="ksp9-match-top"><div>'
        f'<span class="ksp9-kicker">{escape(phase.upper())}</span><h3>{escape(away)} @ {escape(home)}</h3>'
        f'<p>🕒 {escape(tip)} • 🏟️ {escape(venue)} • 📺 {escape(broadcast)}</p></div>'
        f'<span class="ksp9-badge">{escape(market_status)}</span></div>'
        '<div class="ksp9-summary">'
        f'<div class="ksp9-stat"><span>MARKET</span><b>{escape(away_abbr)} {_spread(market_away)}</b></div>'
        f'<div class="ksp9-stat"><span>MODEL FAIR</span><b>{escape(away_abbr)} {_spread(fair_away)}</b></div>'
        f'<div class="ksp9-stat"><span>5M MODEL</span><b>{"CERTIFIED" if analytics.get("certified_run") else "CHECK"}</b></div>'
        f'<div class="ksp9-stat"><span>SPORTSBOOK → MODEL</span><b class="good">0.0%</b></div>'
        '</div></section>', unsafe_allow_html=True,
    )

    st.markdown('<div class="ksp9-lab-title">🎚️ Line Lab</div><div class="ksp9-lab-sub">Move the away-team spread. Cover probabilities update from the frozen 5M distribution; the model fair spread never moves.</div>', unsafe_allow_html=True)
    jump_market, jump_model, _ = st.columns([1, 1, 2])
    with jump_market:
        if st.button("Market line", key=f"ksp9_market_{event_id}", use_container_width=True, disabled=not math.isfinite(market_away)):
            st.session_state[slider_key] = _round_half(market_away)
            st.rerun()
    with jump_model:
        if st.button("Model fair", key=f"ksp9_fair_{event_id}", use_container_width=True, disabled=not math.isfinite(fair_away)):
            st.session_state[slider_key] = _round_half(fair_away)
            st.rerun()

    selected_line = st.slider(
        f"{away_abbr} spread",
        min_value=-30.5,
        max_value=30.5,
        step=0.5,
        key=slider_key,
    )
    is_market_line = math.isfinite(market_away) and abs(float(selected_line) - market_away) < 1e-9
    pricing_away = away_price if is_market_line and math.isfinite(away_price) else -110.0
    pricing_home = home_price if is_market_line and math.isfinite(home_price) else -110.0
    lab = settle_line(analytics, selected_line, price=pricing_away)
    if not lab.get("ready"):
        st.warning(str(lab.get("error") or "Line Lab is unavailable for this matchup."))
        history = frozen_v8.load_matchup_history(game, limit=5)
        _diagnostics(game, market, analytics, history, lab)
        return

    away_non_push = _num(lab.get("away_cover_probability_non_push"))
    home_non_push = _num(lab.get("home_cover_probability_non_push"))
    away_be = american_break_even(pricing_away)
    home_be = american_break_even(pricing_home)
    away_edge = away_non_push - away_be if math.isfinite(away_non_push) and math.isfinite(away_be) else math.nan
    home_edge = home_non_push - home_be if math.isfinite(home_non_push) and math.isfinite(home_be) else math.nan
    lean_away = away_edge >= home_edge
    lean_team = away if lean_away else home
    lean_line = float(selected_line) if lean_away else -float(selected_line)
    lean_prob = away_non_push if lean_away else home_non_push
    lean_edge = away_edge if lean_away else home_edge
    line_value = _num(lab.get("line_value"))

    st.markdown(
        '<div class="ksp9-summary">'
        f'<div class="ksp9-stat"><span>SELECTED</span><b>{escape(away_abbr)} {_spread(selected_line)}</b></div>'
        f'<div class="ksp9-stat"><span>MODEL FAIR</span><b>{escape(away_abbr)} {_spread(fair_away)}</b></div>'
        f'<div class="ksp9-stat"><span>LINE VALUE</span><b>{line_value:+.1f} pts</b></div>'
        f'<div class="ksp9-stat"><span>MODEL LEAN</span><b class="good">{escape(lean_team)} {_spread(lean_line)}</b></div>'
        '</div>', unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="ksp9-prob">'
        f'<div><span>{escape(away)} {_spread(selected_line)} • non-push cover</span><b>{_pct(away_non_push)}</b><div class="ksp9-bar"><div class="ksp9-fill" style="width:{max(0.0,min(100.0,away_non_push*100.0)):.1f}%"></div></div></div>'
        f'<div><span>{escape(home)} {_spread(-float(selected_line))} • non-push cover</span><b>{_pct(home_non_push)}</b><div class="ksp9-bar"><div class="ksp9-fill" style="width:{max(0.0,min(100.0,home_non_push*100.0)):.1f}%"></div></div></div>'
        '</div>', unsafe_allow_html=True,
    )
    pricing_label = "current market price" if is_market_line else "-110 hypothetical pricing"
    st.caption(
        f"{lean_team} {_spread(lean_line)} • {_pct(lean_prob)} non-push cover • probability edge {lean_edge*100:+.1f} pts vs break-even • {pricing_label} • push {_pct(lab.get('push_probability'))}"
    )

    st.markdown(_why_html(away, home, float(selected_line), lab, analytics), unsafe_allow_html=True)

    opening = _num(book.get("opening_away_spread") or book.get("open_away_spread")) if market_ready else math.nan
    if math.isfinite(opening) and math.isfinite(market_away):
        st.markdown(
            f'<div class="ksp9-note"><b>Line movement:</b> {escape(away_abbr)} opened {_spread(opening)} → current {_spread(market_away)} • model fair {_spread(fair_away)}.</div>',
            unsafe_allow_html=True,
        )

    history = frozen_v8.load_matchup_history(game, limit=5)
    history_html = _history_html(history)
    if history_html:
        st.markdown(history_html, unsafe_allow_html=True)

    st.markdown(
        f'<div class="ksp9-note"><b>Readiness:</b> verified game identity • market {"ready" if market_ready else "waiting"} • model {"ready" if analytics.get("ready") else "gated"} • Monte Carlo {"certified" if analytics.get("certified_run") else "check"}. Matchup history is display-only and carries 0.0% model influence.</div>',
        unsafe_allow_html=True,
    )
    _diagnostics(game, market, analytics, history, lab)


def render_nfl_hub(market: str = "Spread") -> None:
    if str(market or "") != "Spread":
        raise RuntimeError("NFL Spread V9 only owns the Spread route.")

    selected, resolver = _active_day()
    day_str = selected.isoformat()
    with st.spinner("Loading verified NFL Spread matchup intelligence…"):
        games, diag = frozen_v4.frozen.base.load_nfl_slate(day_str)
    if not isinstance(diag, dict) or not diag.get("request_ok"):
        st.error("Verified NFL schedule is unavailable. Spread remains fail-closed; no synthetic matchup or line is created.")
        return
    _hero(selected, 0 if games is None or games.empty else len(games))
    if games is None or games.empty:
        st.info("No verified NFL game is available on the resolved slate.")
        return

    with st.spinner("Loading certified Spread markets…"):
        markets = frozen_v4.frozen._fetch_markets(games)

    for _, row in games.iterrows():
        game = row.to_dict()
        event_id = str(game.get("game_id") or "")
        market_state = markets.get(event_id) or {
            "ready": False,
            "reason": "Certified pregame Spread market is unavailable.",
            "books": [],
            "projection_weight": 0.0,
        }
        analytics = frozen_v4.prior._analytics_for_game(game, market_state, day_str)
        _render_matchup(game, market_state, analytics)

    st.caption(
        "NFL Spread V9 • presentation + settlement-only Line Lab • frozen football projection and 5M distribution • sportsbook projection influence 0.0% • wager actions OFF"
    )


__all__ = [
    "FROZEN_ANALYTICS", "FROZEN_PRIOR", "FROZEN_TRANSPORT", "LINE_LAB_SETTLEMENT_ONLY",
    "MODEL_VERSION", "PRESENTATION_ONLY", "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED", "WAGER_ACTIONS_ENABLED", "render_nfl_hub", "resolve_default_slate",
]
