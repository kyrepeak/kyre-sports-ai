"""NFL Spread V10 — visual hierarchy polish over frozen V9 consumer logic."""
from __future__ import annotations

from datetime import date, datetime
from html import escape
import math
from typing import Any

import pandas as pd
import streamlit as st

import nfl_spread_hub_v9 as prior

MODEL_VERSION = "NFL SPREAD V10 • VISUAL HIERARCHY • V9 FROZEN"
FROZEN_PRIOR = "nfl_spread_hub_v9"
PRESENTATION_ONLY = True
LINE_LAB_SETTLEMENT_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False

_CSS = r"""
<style data-nfl-spread-v10="true">
.ksp10-hero{padding:20px 21px;margin:4px 0 15px;border:1px solid #315b76;border-radius:20px;background:radial-gradient(circle at 90% 0%,rgba(92,220,255,.12),transparent 34%),linear-gradient(145deg,#0a1824,#07111a);box-shadow:0 14px 34px rgba(0,0,0,.18)}
.ksp10-kicker{color:#72dfff;font-size:.72rem;font-weight:950;letter-spacing:.13em}.ksp10-title{margin-top:5px;color:#f7fbfd;font-size:1.72rem;font-weight:950;letter-spacing:-.035em}.ksp10-title span{color:#80f2c3}.ksp10-sub{margin-top:7px;color:#a8bac8;font-size:.84rem;line-height:1.5;max-width:880px}.ksp10-chips{display:flex;flex-wrap:wrap;gap:7px;margin-top:12px}.ksp10-chip{border:1px solid #31556d;border-radius:999px;padding:6px 10px;color:#a9dced;background:#0a1b27;font-size:.64rem;font-weight:900}.ksp10-chip.good{border-color:#2d8066;color:#80f2c3}
.ksp10-match{margin:15px 0 12px;border:1px solid #274b61;border-radius:18px;background:linear-gradient(145deg,#081722,#07121b);padding:15px}.ksp10-match-top{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);gap:14px;align-items:center}.ksp10-team{display:flex;align-items:center;gap:10px;min-width:0}.ksp10-team.home{justify-content:flex-end;text-align:right}.ksp10-team-logo{width:44px;height:44px;object-fit:contain;filter:drop-shadow(0 5px 10px rgba(0,0,0,.28))}.ksp10-team-fallback{width:44px;height:44px;border-radius:50%;display:grid;place-items:center;border:1px solid #355c72;background:#0d2230;color:#d9f5ff;font-weight:950}.ksp10-team-name{color:#f4f9fc;font-size:1rem;font-weight:900;line-height:1.2}.ksp10-team-meta{color:#89a0b1;font-size:.72rem;margin-top:3px}.ksp10-vs{text-align:center;color:#6e899d;font-size:.68rem;font-weight:950;letter-spacing:.13em}.ksp10-game-meta{text-align:center;color:#9fb1bf;font-size:.76rem;line-height:1.45;margin:13px 0 0}.ksp10-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:12px 0 0}.ksp10-stat{border:1px solid #214359;border-radius:12px;background:#06111a;padding:10px}.ksp10-stat span{display:block;color:#7690a4;font-size:.64rem;font-weight:900;letter-spacing:.07em}.ksp10-stat b{display:block;color:#eff8fc;font-size:.94rem;margin-top:5px}.ksp10-stat b.good{color:#7ff2c2}
.ksp10-lab-title{margin:.8rem 0 .22rem;color:#f6fbfd;font-size:1.16rem;font-weight:950}.ksp10-lab-sub{color:#91a7b8;font-size:.76rem;line-height:1.45;margin-bottom:.35rem}.ksp10-ruler{position:relative;height:62px;margin:6px 0 2px}.ksp10-ruler-line{position:absolute;left:2%;right:2%;top:30px;height:4px;border-radius:999px;background:linear-gradient(90deg,#1f3340,#314a58)}.ksp10-ruler-marker{position:absolute;top:10px;transform:translateX(-50%);text-align:center;white-space:nowrap}.ksp10-ruler-marker i{display:block;width:10px;height:10px;border-radius:50%;margin:14px auto 0;background:#6bd8ff;box-shadow:0 0 0 3px rgba(107,216,255,.14)}.ksp10-ruler-marker.market i{background:#ffcc75}.ksp10-ruler-marker.fair i{background:#7ff2c2}.ksp10-ruler-marker.selected i{background:#ff5e67}.ksp10-ruler-marker b{font-size:.66rem;color:#eef7fb}.ksp10-ruler-marker span{display:block;font-size:.62rem;color:#88a0b2;margin-top:2px}
.ksp10-model-read{border:1px solid #2c765e;border-radius:16px;background:radial-gradient(circle at 95% 0%,rgba(89,238,185,.12),transparent 34%),linear-gradient(145deg,#092019,#08151a);padding:14px 15px;margin:10px 0 12px}.ksp10-model-read .eyebrow{color:#79efbd;font-size:.68rem;font-weight:950;letter-spacing:.12em}.ksp10-model-read .headline{color:#f4fcf8;font-size:1.24rem;font-weight:950;margin-top:5px}.ksp10-model-read .support{color:#a6beb2;font-size:.76rem;margin-top:4px}.ksp10-read-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:11px}.ksp10-read-grid div{border:1px solid #285b4a;border-radius:11px;background:#071a14;padding:9px}.ksp10-read-grid span{display:block;color:#7f9e90;font-size:.62rem;font-weight:900}.ksp10-read-grid b{display:block;color:#effaf4;font-size:.95rem;margin-top:3px}
.ksp10-prob{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin:10px 0 12px}.ksp10-prob>div{border:1px solid #21465a;border-radius:14px;background:#07141e;padding:12px}.ksp10-prob>div.leader{border-color:#2b8063;background:linear-gradient(145deg,#092019,#07141e);box-shadow:0 0 0 1px rgba(127,242,194,.05)}.ksp10-prob span{display:block;color:#8fa5b4;font-size:.72rem;font-weight:850}.ksp10-prob b{display:block;color:#f5fbfe;font-size:1.38rem;margin:3px 0 7px}.ksp10-prob .leader b{color:#7ff2c2}.ksp10-bar{height:8px;border-radius:999px;background:#122938;overflow:hidden}.ksp10-fill{height:100%;border-radius:999px;background:linear-gradient(90deg,#55c7ff,#7ff2c2)}
.ksp10-section-label{color:#dff4fb;font-size:.86rem;font-weight:950;letter-spacing:.04em;margin:13px 0 7px}.ksp10-reason-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:8px 0 13px}.ksp10-reason{border:1px solid #24485d;border-radius:13px;background:#081621;padding:11px}.ksp10-reason span{display:block;color:#7891a4;font-size:.64rem;font-weight:900;letter-spacing:.06em}.ksp10-reason b{display:block;color:#eef8fc;font-size:.92rem;margin-top:5px}.ksp10-reason p{margin:5px 0 0;color:#9bafbd;font-size:.70rem;line-height:1.4}.ksp10-history{border:1px solid #24485c;border-radius:15px;background:#07131d;padding:12px;margin:8px 0 12px}.ksp10-history-head{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:7px}.ksp10-history-head b{color:#eef8fc;font-size:.86rem}.ksp10-history-head span{color:#8da4b4;font-size:.68rem}.ksp10-history-row{display:grid;grid-template-columns:110px minmax(0,1fr) auto;gap:8px;align-items:center;border-top:1px solid #173446;padding:8px 0}.ksp10-history-date{color:#89a2b4;font-size:.68rem}.ksp10-history-score{color:#e6f1f7;font-size:.73rem;font-weight:800}.ksp10-history-badge{border:1px solid #35586a;border-radius:999px;padding:4px 7px;color:#a8c5d5;font-size:.62rem;font-weight:900}.ksp10-history-badge.good{border-color:#2c7c62;color:#7ff2c2}.ksp10-note{color:#8299aa;font-size:.68rem;line-height:1.45;margin:5px 0 13px}
@media(max-width:820px){.ksp10-summary{grid-template-columns:1fr 1fr}.ksp10-read-grid,.ksp10-reason-grid{grid-template-columns:1fr}.ksp10-match-top{grid-template-columns:1fr}.ksp10-team.home{justify-content:flex-start;text-align:left}.ksp10-vs{text-align:left}.ksp10-title{font-size:1.42rem}}
@media(max-width:520px){.ksp10-summary,.ksp10-prob{grid-template-columns:1fr}.ksp10-hero{padding:15px}.ksp10-title{font-size:1.22rem}.ksp10-history-row{grid-template-columns:1fr}.ksp10-ruler-marker b{font-size:.62rem}}
</style>
"""


def _num(value: Any) -> float:
    return prior._num(value)


def _spread(value: Any) -> str:
    return prior._spread(value)


def _pct(value: Any) -> str:
    return prior._pct(value)


def _round_half(value: float) -> float:
    return prior._round_half(value)


def resolve_default_slate(selected: date):
    return prior.resolve_default_slate(selected)


def _active_day() -> tuple[date, dict[str, Any]]:
    return prior._active_day()


def _logo(url: Any, abbr: str) -> str:
    text = str(url or "").strip()
    if text.startswith("http://") or text.startswith("https://"):
        return f'<img class="ksp10-team-logo" src="{escape(text)}" alt="{escape(abbr)} logo">'
    return f'<div class="ksp10-team-fallback">{escape(abbr[:3])}</div>'


def _pos(value: float) -> float:
    if not math.isfinite(value):
        return 50.0
    return max(2.0, min(98.0, ((value + 30.5) / 61.0) * 100.0))


def _ruler_html(selected: float, market: float, fair: float, away_abbr: str) -> str:
    markers = []
    for css, label, value in (("market", "MARKET", market), ("fair", "MODEL FAIR", fair), ("selected", "SELECTED", selected)):
        if math.isfinite(value):
            markers.append(
                f'<div class="ksp10-ruler-marker {css}" style="left:{_pos(value):.2f}%"><b>{label}</b><span>{escape(away_abbr)} {_spread(value)}</span><i></i></div>'
            )
    return '<div class="ksp10-ruler"><div class="ksp10-ruler-line"></div>' + "".join(markers) + '</div>'


def _history_html(history: dict[str, Any]) -> str:
    if not isinstance(history, dict) or not history.get("ready"):
        return ""
    meetings = history.get("meetings") or []
    rows = []
    for item in meetings[:5]:
        line = item.get("spread_line")
        ats = str(item.get("ats_winner") or "").strip()
        badge = ""
        if isinstance(line, (int, float)) and ats:
            badge = f'<span class="ksp10-history-badge good">ATS {escape(ats)} • {line:+.1f}</span>'
        rows.append(
            '<div class="ksp10-history-row">'
            f'<span class="ksp10-history-date">{escape(str(item.get("date") or ""))}</span>'
            f'<span class="ksp10-history-score">{escape(str(item.get("score") or ""))}</span>{badge}</div>'
        )
    if not rows:
        return ""
    return (
        '<section class="ksp10-history"><div class="ksp10-history-head"><b>RECENT MATCHUP HISTORY</b>'
        f'<span>{escape(str(history.get("series_summary") or ""))}</span></div>{"".join(rows)}</section>'
    )


def _why_html(away: str, home: str, lab: dict[str, Any], analytics: dict[str, Any]) -> str:
    fair = _num(lab.get("fair_away_spread"))
    line_value = _num(lab.get("line_value"))
    q = analytics.get("margin_quantiles") or {}
    p25, p75 = _num(q.get("p25")), _num(q.get("p75"))
    quality = str(analytics.get("model_quality") or "CHECK").upper()
    side = away if line_value >= 0 else home
    value_text = f"{abs(line_value):.1f} pts toward {side}" if math.isfinite(line_value) else "Unavailable"
    range_text = f"{p25:+.1f} to {p75:+.1f}" if math.isfinite(p25) and math.isfinite(p75) else "Unavailable"
    return (
        '<div class="ksp10-section-label">🧠 WHY THE MODEL SEES IT</div><div class="ksp10-reason-grid">'
        f'<div class="ksp10-reason"><span>MODEL FAIR</span><b>{escape(away)} {_spread(fair)}</b><p>Independent football projection; sportsbook weight remains 0.0%.</p></div>'
        f'<div class="ksp10-reason"><span>LINE VALUE</span><b>{escape(value_text)}</b><p>Difference between the selected spread and frozen model fair.</p></div>'
        f'<div class="ksp10-reason"><span>UNCERTAINTY</span><b>{escape(range_text)}</b><p>Middle 50% simulated away-margin range • model quality {escape(quality)}.</p></div>'
        '</div>'
    )


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

    book = prior.frozen_v4._first_book(market)
    market_ready = bool(market.get("ready")) and bool(book)
    market_away = _num(book.get("away_spread")) if market_ready else math.nan
    away_price = _num(book.get("away_price")) if market_ready else math.nan
    home_price = _num(book.get("home_price")) if market_ready else math.nan
    projected = _num(analytics.get("projected_away_margin"))
    fair_away = -projected if math.isfinite(projected) else math.nan

    default = market_away if math.isfinite(market_away) else fair_away if math.isfinite(fair_away) else 0.0
    default = _round_half(default)
    slider_key = f"nfl_spread_v9_line_lab_{event_id}"
    if slider_key not in st.session_state:
        st.session_state[slider_key] = default

    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(
        '<section class="ksp10-match"><div class="ksp10-match-top">'
        f'<div class="ksp10-team">{_logo(game.get("away_logo"), away_abbr)}<div><div class="ksp10-team-name">{escape(away)}</div><div class="ksp10-team-meta">{escape(str(game.get("away_record") or ""))}</div></div></div>'
        '<div class="ksp10-vs">VS</div>'
        f'<div class="ksp10-team home"><div><div class="ksp10-team-name">{escape(home)}</div><div class="ksp10-team-meta">{escape(str(game.get("home_record") or ""))}</div></div>{_logo(game.get("home_logo"), home_abbr)}</div>'
        '</div>'
        f'<div class="ksp10-game-meta">{escape(phase)} • 🕒 {escape(tip)} • 🏟️ {escape(venue)} • 📺 {escape(broadcast)}</div>'
        '<div class="ksp10-summary">'
        f'<div class="ksp10-stat"><span>MARKET</span><b>{escape(away_abbr)} {_spread(market_away)}</b></div>'
        f'<div class="ksp10-stat"><span>MODEL FAIR</span><b>{escape(away_abbr)} {_spread(fair_away)}</b></div>'
        f'<div class="ksp10-stat"><span>5M MODEL</span><b>{"CERTIFIED" if analytics.get("certified_run") else "CHECK"}</b></div>'
        f'<div class="ksp10-stat"><span>SPORTSBOOK → MODEL</span><b class="good">0.0%</b></div>'
        '</div></section>', unsafe_allow_html=True,
    )

    st.markdown('<div class="ksp10-lab-title">🎚️ LINE LAB</div><div class="ksp10-lab-sub">Move the away-team spread. The native slider re-grades only the frozen 5M distribution; model fair never moves.</div>', unsafe_allow_html=True)
    jump_market, jump_model, _ = st.columns([1, 1, 2])
    with jump_market:
        if st.button("Market line", key=f"ksp10_market_{event_id}", use_container_width=True, disabled=not math.isfinite(market_away)):
            st.session_state[slider_key] = _round_half(market_away)
            st.rerun()
    with jump_model:
        if st.button("Model fair", key=f"ksp10_fair_{event_id}", use_container_width=True, disabled=not math.isfinite(fair_away)):
            st.session_state[slider_key] = _round_half(fair_away)
            st.rerun()

    selected_line = st.slider(f"{away_abbr} spread", min_value=-30.5, max_value=30.5, step=0.5, key=slider_key)
    st.markdown(_ruler_html(float(selected_line), market_away, fair_away, away_abbr), unsafe_allow_html=True)

    is_market_line = math.isfinite(market_away) and abs(float(selected_line) - market_away) < 1e-9
    pricing_away = away_price if is_market_line and math.isfinite(away_price) else -110.0
    pricing_home = home_price if is_market_line and math.isfinite(home_price) else -110.0
    lab = prior.settle_line(analytics, selected_line, price=pricing_away)
    if not lab.get("ready"):
        st.warning(str(lab.get("error") or "Line Lab is unavailable for this matchup."))
        history = prior.frozen_v8.load_matchup_history(game, limit=5)
        prior._diagnostics(game, market, analytics, history, lab)
        return

    away_non_push = _num(lab.get("away_cover_probability_non_push"))
    home_non_push = _num(lab.get("home_cover_probability_non_push"))
    away_be = prior.american_break_even(pricing_away)
    home_be = prior.american_break_even(pricing_home)
    away_edge = away_non_push - away_be if math.isfinite(away_non_push) and math.isfinite(away_be) else math.nan
    home_edge = home_non_push - home_be if math.isfinite(home_non_push) and math.isfinite(home_be) else math.nan
    lean_away = away_edge >= home_edge
    lean_team = away if lean_away else home
    lean_line = float(selected_line) if lean_away else -float(selected_line)
    lean_prob = away_non_push if lean_away else home_non_push
    lean_edge = away_edge if lean_away else home_edge
    line_value = _num(lab.get("line_value"))

    st.markdown(
        '<section class="ksp10-model-read"><div class="eyebrow">MODEL READ</div>'
        f'<div class="headline">{escape(lean_team)} {_spread(lean_line)}</div>'
        f'<div class="support">{_pct(lean_prob)} non-push cover probability • {lean_edge*100:+.1f} pts vs break-even</div>'
        '<div class="ksp10-read-grid">'
        f'<div><span>SELECTED LINE</span><b>{escape(away_abbr)} {_spread(selected_line)}</b></div>'
        f'<div><span>MODEL FAIR</span><b>{escape(away_abbr)} {_spread(fair_away)}</b></div>'
        f'<div><span>LINE VALUE</span><b>{line_value:+.1f} pts</b></div>'
        '</div></section>', unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="ksp10-prob">'
        f'<div class="{"leader" if lean_away else ""}"><span>{escape(away)} {_spread(selected_line)} • non-push cover</span><b>{_pct(away_non_push)}</b><div class="ksp10-bar"><div class="ksp10-fill" style="width:{max(0.0,min(100.0,away_non_push*100.0)):.1f}%"></div></div></div>'
        f'<div class="{"leader" if not lean_away else ""}"><span>{escape(home)} {_spread(-float(selected_line))} • non-push cover</span><b>{_pct(home_non_push)}</b><div class="ksp10-bar"><div class="ksp10-fill" style="width:{max(0.0,min(100.0,home_non_push*100.0)):.1f}%"></div></div></div>'
        '</div>', unsafe_allow_html=True,
    )
    pricing_label = "current market price" if is_market_line else "-110 hypothetical pricing"
    st.caption(f"{lean_team} {_spread(lean_line)} • {_pct(lean_prob)} cover • edge {lean_edge*100:+.1f} pts • {pricing_label} • push {_pct(lab.get('push_probability'))}")

    st.markdown(_why_html(away, home, lab, analytics), unsafe_allow_html=True)

    opening = _num(book.get("opening_away_spread") or book.get("open_away_spread")) if market_ready else math.nan
    if math.isfinite(opening) and math.isfinite(market_away):
        st.markdown(f'<div class="ksp10-note"><b>Line movement:</b> {escape(away_abbr)} opened {_spread(opening)} → current {_spread(market_away)} • model fair {_spread(fair_away)}.</div>', unsafe_allow_html=True)

    history = prior.frozen_v8.load_matchup_history(game, limit=5)
    history_html = _history_html(history)
    if history_html:
        st.markdown(history_html, unsafe_allow_html=True)

    st.markdown(f'<div class="ksp10-note"><b>Readiness:</b> verified game identity • market {"ready" if market_ready else "waiting"} • model {"ready" if analytics.get("ready") else "gated"} • Monte Carlo {"certified" if analytics.get("certified_run") else "check"}. Matchup history remains display-only.</div>', unsafe_allow_html=True)
    prior._diagnostics(game, market, analytics, history, lab)


def _hero(selected: date, games: int) -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(
        '<section class="ksp10-hero"><div class="ksp10-kicker">KYRE SPORTS AI • NFL SPREAD</div>'
        '<div class="ksp10-title">🎯 Spread <span>Intelligence + Line Lab</span></div>'
        '<div class="ksp10-sub">Cleaner visual hierarchy for faster reading. Model Read leads the page, Line Lab shows market/fair/selected markers, and deep evidence stays collapsed.</div>'
        '<div class="ksp10-chips"><span class="ksp10-chip good">MODEL FIREWALL 0.0%</span><span class="ksp10-chip">5M MARGIN DISTRIBUTION</span><span class="ksp10-chip">LINE LAB SETTLEMENT ONLY</span><span class="ksp10-chip">NO STAKE SIZING</span></div></section>',
        unsafe_allow_html=True,
    )
    st.caption(f"Active verified NFL slate • {selected.strftime('%a, %b %d, %Y')} • {games} matchup(s)")


def render_nfl_hub(market: str = "Spread") -> None:
    if str(market or "") != "Spread":
        raise RuntimeError("NFL Spread V10 only owns the Spread route.")
    selected, _resolver = _active_day()
    day_str = selected.isoformat()
    with st.spinner("Loading verified NFL Spread matchup intelligence…"):
        games, diag = prior.frozen_v4.frozen.base.load_nfl_slate(day_str)
    if not isinstance(diag, dict) or not diag.get("request_ok"):
        st.error("Verified NFL schedule is unavailable. Spread remains fail-closed; no synthetic matchup or line is created.")
        return
    _hero(selected, 0 if games is None or games.empty else len(games))
    if games is None or games.empty:
        st.info("No verified NFL game is available on the resolved slate.")
        return
    with st.spinner("Loading certified Spread markets…"):
        markets = prior.frozen_v4.frozen._fetch_markets(games)
    for _, row in games.iterrows():
        game = row.to_dict()
        event_id = str(game.get("game_id") or "")
        market_state = markets.get(event_id) or {"ready": False, "reason": "Certified pregame Spread market is unavailable.", "books": [], "projection_weight": 0.0}
        analytics = prior.frozen_v4.prior._analytics_for_game(game, market_state, day_str)
        _render_matchup(game, market_state, analytics)
    st.caption("NFL Spread V10 • presentation-only visual hierarchy over frozen V9 • settlement-only Line Lab • sportsbook projection influence 0.0% • wager actions OFF")


__all__ = ["MODEL_VERSION", "FROZEN_PRIOR", "PRESENTATION_ONLY", "LINE_LAB_SETTLEMENT_ONLY", "SPORTSBOOK_PROJECTION_INFLUENCE", "STAKE_SIZING_ENABLED", "WAGER_ACTIONS_ENABLED", "render_nfl_hub", "resolve_default_slate"]
