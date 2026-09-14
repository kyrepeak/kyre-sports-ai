"""NFL Spread V4 — visual-parity matchup lab over certified Spread V3.

V4 is presentation/composition only. Certified Spread V3 continues to own the
independent fair-margin model + deterministic 5,000,000-simulation Monte Carlo
analytics, while frozen Spread V1 continues to own verified NFL slate identity
and certified sportsbook transport.

The visible page follows the established Receiving Yards / Rushing Yards /
Moneyline family: compact hero + chips, summary tiles, matchup-first cards,
logo-first team panels, dense metric grids, evidence readouts, support/concern
context, and a final model readout. Sportsbook values are display/settlement
context only. They never enter projection math or simulated-margin generation.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
import math
from typing import Any

import pandas as pd
import streamlit as st

import nfl_spread_hub_v1 as frozen
import nfl_spread_hub_v3 as prior


MODEL_VERSION = "NFL SPREAD V4 • VISUAL PARITY MATCHUP LAB • V3 MODEL + 5M MC FROZEN"
FROZEN_ANALYTICS = "nfl_spread_hub_v3"
FROZEN_MODEL = "nfl_spread_model_v1"
FROZEN_MONTE_CARLO = "nfl_spread_mc_v1"
FROZEN_TRANSPORT = "nfl_spread_hub_v1"
PRESENTATION_ONLY = True
MATCHUP_CARD_FIRST = True
PROJECTION_MODEL_ENABLED = True
MONTE_CARLO_ENABLED = True
CERTIFIED_SIMULATIONS = prior.CERTIFIED_SIMULATIONS
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MARKET_LINE_ROLE = "settlement_only"
RANKINGS_ENABLED = False
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False


def _safe(value: Any, default: str = "") -> str:
    return prior._safe(value, default)


def _num(value: Any) -> float:
    try:
        out = float(value)
        return out if math.isfinite(out) else math.nan
    except (TypeError, ValueError):
        return math.nan


def _pct(value: Any, digits: int = 1) -> str:
    number = _num(value)
    return f"{100.0 * number:.{digits}f}%" if math.isfinite(number) else "—"


def _spread(value: Any) -> str:
    number = _num(value)
    return frozen.market_api.fmt_spread(number) if math.isfinite(number) else "—"


def _price(value: Any) -> str:
    number = _num(value)
    return frozen.market_api.fmt_american(number) if math.isfinite(number) else "—"


def _margin(value: Any) -> str:
    number = _num(value)
    return f"{number:+.1f}" if math.isfinite(number) else "—"


def _status_class(value: Any) -> str:
    text = _safe(value).upper()
    if text in {"READY", "VERIFIED", "HIGH", "5M CERTIFIED", "CONVERGED"}:
        return "good"
    if text in {"MEDIUM", "CHECK", "AGING", "MC CONVERGED"}:
        return "watch"
    if text in {"LOW", "UNAVAILABLE", "STALE", "GATED"}:
        return "bad"
    return "neutral"


def _market_role(value: Any) -> str:
    number = _num(value)
    if not math.isfinite(number):
        return "LINE UNAVAILABLE"
    if number < 0:
        return "MARKET FAVORITE"
    if number > 0:
        return "UNDERDOG"
    return "PICK'EM"


def _role_class(value: Any) -> str:
    role = _market_role(value)
    if role == "MARKET FAVORITE":
        return "favorite"
    if role == "UNDERDOG":
        return "underdog"
    if role == "PICK'EM":
        return "pickem"
    return "off"


def _first_book(market: dict[str, Any]) -> dict[str, Any]:
    return prior._first_book(market)


def _fair_spreads(analytics: dict[str, Any]) -> tuple[float, float]:
    away_margin = _num(analytics.get("projected_away_margin"))
    if not math.isfinite(away_margin):
        return math.nan, math.nan
    return -away_margin, away_margin


def _side_win_probability(analytics: dict[str, Any], side: str) -> float:
    away = _num(analytics.get("away_win_probability"))
    if not math.isfinite(away):
        return math.nan
    return away if side == "away" else 1.0 - away


def _side_cover_probability(
    analytics: dict[str, Any], side: str, market_ready: bool
) -> float:
    if not market_ready:
        return math.nan
    return _num(
        analytics.get("away_cover_probability")
        if side == "away"
        else analytics.get("home_cover_probability")
    )


def _side_simulated_margin(analytics: dict[str, Any], side: str) -> float:
    away = _num(analytics.get("simulated_away_margin_median"))
    if not math.isfinite(away):
        return math.nan
    return away if side == "away" else -away


def _team_panel(
    game: dict[str, Any],
    side: str,
    market: dict[str, Any],
    analytics: dict[str, Any],
) -> str:
    team = _safe(game.get(f"{side}_team"), side.title())
    abbr = _safe(game.get(f"{side}_abbr"), "NFL").upper()
    record = _safe(game.get(f"{side}_record"), "—")
    market_ready = bool(market.get("ready")) and bool(_first_book(market))
    book = _first_book(market)
    line_value = book.get(f"{side}_spread") if market_ready else None
    price_value = book.get(f"{side}_price") if market_ready else None
    sportsbook = _safe(book.get("sportsbook"), "FanDuel") if market_ready else "—"
    fair_away, fair_home = _fair_spreads(analytics)
    fair = fair_away if side == "away" else fair_home
    cover = _side_cover_probability(analytics, side, market_ready)
    win = _side_win_probability(analytics, side)
    sim_margin = _side_simulated_margin(analytics, side)
    role = _market_role(line_value) if market_ready else "LINE UNAVAILABLE"
    role_class = _role_class(line_value) if market_ready else "off"
    logo = frozen._logo(game.get(f"{side}_logo"), abbr, team)

    return f'''
    <section class="ksp4-team-panel ksp4-{escape(side)}">
      <div class="ksp4-team-head">
        <div class="ksp4-team-id">
          {logo}
          <div><b>{escape(team)}</b><span>{escape(abbr)} • {escape(record)}</span></div>
        </div>
        <span class="ksp4-role {role_class}">{escape(role.replace('MARKET ', ''))}</span>
      </div>
      <div class="ksp4-line-row">
        <div class="ksp4-line-hero"><span>FANDUEL SPREAD</span><b>{escape(_spread(line_value))}</b><small>{escape(_price(price_value))} • {escape(sportsbook)}</small></div>
        <div class="ksp4-line-hero fair"><span>MODEL FAIR SPREAD</span><b>{escape(_spread(fair))}</b><small>football-only</small></div>
      </div>
      <div class="ksp4-primary-grid">
        <div class="ksp4-stat hero"><span>5M COVER</span><b>{escape(_pct(cover))}</b></div>
        <div class="ksp4-stat"><span>WIN PROB.</span><b>{escape(_pct(win))}</b></div>
        <div class="ksp4-stat"><span>SIM MEDIAN MARGIN</span><b>{escape(_margin(sim_margin))}</b></div>
        <div class="ksp4-stat"><span>MARKET ROLE</span><b>{escape(role.replace('MARKET ', ''))}</b></div>
      </div>
    </section>
    '''


def _support_concern_rows(
    analytics: dict[str, Any], market: dict[str, Any]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    supports: list[str] = []
    concerns: list[str] = []

    if analytics.get("certified_run"):
        supports.append(
            f"Monte Carlo certification: {int(analytics.get('simulations') or 0):,} deterministic simulations completed."
        )
    else:
        concerns.append("The Monte Carlo result is not marked as a full certified 5M run.")

    if analytics.get("converged"):
        supports.append("Simulation stability: batch convergence checks passed.")
    else:
        concerns.append("Simulation stability remains in CHECK state.")

    quality = _safe(analytics.get("model_quality"), "CHECK").upper()
    if quality in {"HIGH", "MEDIUM"}:
        supports.append(f"Independent football model quality: {quality}.")
    else:
        concerns.append(f"Independent football model quality: {quality}.")

    parameter_se = _num(analytics.get("parameter_se"))
    residual_sd = _num(analytics.get("residual_sd"))
    if math.isfinite(parameter_se):
        supports.append(f"Parameter uncertainty is explicitly modeled (SE {parameter_se:.2f} points).")
    if math.isfinite(residual_sd):
        concerns.append(f"Game-to-game residual uncertainty remains {residual_sd:.2f} points SD.")

    if bool(market.get("ready")) and bool(_first_book(market)):
        supports.append("Certified FanDuel spread is attached only after the football projection for settlement/comparison.")
    else:
        concerns.append("Certified pregame FanDuel spread is unavailable; cover probability remains gated.")

    if not supports:
        supports.append("No additional positive evidence marker is exposed by the certified V3 output.")
    if not concerns:
        concerns.append("No additional concern marker is exposed by the certified V3 output.")
    return tuple(supports[:4]), tuple(concerns[:4])


def _support_concerns_html(
    analytics: dict[str, Any], market: dict[str, Any]
) -> str:
    if not analytics.get("ready"):
        reason = _safe(analytics.get("error"), "Independent analytics unavailable.")
        return (
            '<section class="ksp4-evidence bad">'
            '<div class="ksp4-evidence-head"><div><span>MATCHUP INTELLIGENCE</span>'
            '<b>Support vs Concern • Model Readout</b></div><em>GATED</em></div>'
            f'<div class="ksp4-gated">{escape(reason)}</div></section>'
        )

    supports, concerns = _support_concern_rows(analytics, market)
    support_html = "".join(
        f'<div class="ksp4-evidence-item">{escape(text)}</div>' for text in supports
    )
    concern_html = "".join(
        f'<div class="ksp4-evidence-item">{escape(text)}</div>' for text in concerns
    )
    return f'''
    <section class="ksp4-evidence">
      <div class="ksp4-evidence-head">
        <div><span>MATCHUP INTELLIGENCE</span><b>Support vs Concern • Model Readout</b></div>
        <em>DESCRIPTIVE ONLY</em>
      </div>
      <div class="ksp4-evidence-grid">
        <div class="ksp4-evidence-col support"><h4>Supports</h4>{support_html}</div>
        <div class="ksp4-evidence-col concern"><h4>Concerns / Counterweights</h4>{concern_html}</div>
      </div>
    </section>
    '''


def _final_readout(
    game: dict[str, Any], market: dict[str, Any], analytics: dict[str, Any]
) -> str:
    if not analytics.get("ready"):
        reason = _safe(analytics.get("error"), "Independent spread analytics unavailable.")
        return f'''
        <div class="ksp4-verdict bad">
          <div><span>FINAL SPREAD READOUT</span><b>GATED</b></div>
          <p>{escape(reason)}</p>
          <small>No synthetic line, projection, or recommendation is created.</small>
        </div>
        '''

    away = _safe(game.get("away_team"), "Away")
    home = _safe(game.get("home_team"), "Home")
    fair_away, fair_home = _fair_spreads(analytics)
    book = _first_book(market)
    market_ready = bool(market.get("ready")) and bool(book)
    market_away = book.get("away_spread") if market_ready else None
    market_home = book.get("home_spread") if market_ready else None
    sims = int(analytics.get("simulations") or 0)
    certified = bool(analytics.get("certified_run"))
    converged = bool(analytics.get("converged"))
    status = "5M CERTIFIED" if certified else ("MC CONVERGED" if converged else "CHECK")
    klass = _status_class(status)
    q = analytics.get("margin_quantiles") or {}
    p25 = _margin(q.get("p25"))
    p75 = _margin(q.get("p75"))
    push = _pct(analytics.get("push_probability") if market_ready else math.nan)

    market_copy = (
        f"FanDuel {away} {_spread(market_away)} / {home} {_spread(market_home)}"
        if market_ready
        else "FanDuel spread unavailable"
    )
    return f'''
    <div class="ksp4-verdict {klass}">
      <div><span>FINAL SPREAD READOUT</span><b>{escape(status)}</b></div>
      <p>Model fair line: {escape(away)} {escape(_spread(fair_away))} / {escape(home)} {escape(_spread(fair_home))} • {escape(market_copy)}.</p>
      <small>{sims:,} simulations • middle 50% away-margin {escape(p25)} to {escape(p75)} • push {escape(push)} • market is settlement/comparison only • sportsbook influence on projection math 0.0%</small>
    </div>
    '''


def _matchup_card(
    game: dict[str, Any], market: dict[str, Any], analytics: dict[str, Any]
) -> str:
    event_id = _safe(game.get("game_id"))
    state = _safe(game.get("state"), "pre").lower()
    away = _safe(game.get("away_team"), "Away")
    home = _safe(game.get("home_team"), "Home")
    phase = _safe(game.get("season_type"), "NFL")
    tip = _safe(game.get("tip_et"), "TBD")
    venue = _safe(game.get("venue"), "Venue TBD")
    broadcast = _safe(game.get("broadcast"), "—")
    market_ready = state == "pre" and bool(market.get("ready")) and bool(_first_book(market))
    quality = _safe(analytics.get("model_quality"), "CHECK").upper() if analytics.get("ready") else "GATED"
    mc_state = "5M CERTIFIED" if analytics.get("certified_run") else ("CONVERGED" if analytics.get("converged") else "CHECK")
    market_state = "READY" if market_ready else ("PREGAME ONLY" if state != "pre" else "UNAVAILABLE")

    return f'''
    <article class="ksp4-matchup-card" data-spread-v4="true" data-event-id="{escape(event_id, quote=True)}">
      <div class="ksp4-matchup-top">
        <div class="ksp4-matchup-copy">
          <span class="ksp4-phase">{escape(phase)}</span>
          <b>{escape(away)} <em>@</em> {escape(home)}</b>
          <small>🕒 {escape(tip)} &nbsp; • &nbsp; 🏟️ {escape(venue)} &nbsp; • &nbsp; 📺 {escape(broadcast)}</small>
        </div>
        <div class="ksp4-health">
          <span class="{_status_class(market_state)}">MARKET {escape(market_state)}</span>
          <span class="{_status_class(quality)}">MODEL {escape(quality)}</span>
          <span class="{_status_class(mc_state)}">MC {escape(mc_state)}</span>
          <span class="good">EXACT ID</span>
        </div>
      </div>
      <div class="ksp4-team-grid">
        {_team_panel(game, 'away', market, analytics)}
        <div class="ksp4-vs">VS</div>
        {_team_panel(game, 'home', market, analytics)}
      </div>
      {_support_concerns_html(analytics, market)}
      {_final_readout(game, market, analytics)}
    </article>
    '''


def _summary_html(
    *, games: int, upcoming: int, market_ready: int, model_ready: int, mc_certified: int
) -> str:
    return f'''
    <div class="ksp4-summary">
      <div><span>PREGAME GAMES</span><b>{upcoming}</b><small>{games} verified total</small></div>
      <div><span>MARKET</span><b>{market_ready}/{upcoming}</b><small>FanDuel certified</small></div>
      <div><span>MODEL</span><b>{model_ready}/{upcoming}</b><small>independent fair line</small></div>
      <div><span>MODEL + 5M MC</span><b>{mc_certified}/{upcoming}</b><small>0.0% market → model</small></div>
    </div>
    '''


_CSS = r'''
<style>
.ksp4-page{max-width:1180px;margin:0 auto}.ksp4-hero{position:relative;overflow:hidden;border:1px solid #294e6d;border-radius:20px;background:radial-gradient(circle at 88% 12%,rgba(45,212,191,.12),transparent 32%),linear-gradient(145deg,#0c1725,#08111c 64%);padding:17px 18px;margin:7px 0 14px;box-shadow:0 12px 34px rgba(0,0,0,.14)}.ksp4-kicker{font-size:.57rem;font-weight:950;letter-spacing:.12em;color:#7dd3fc;text-transform:uppercase}.ksp4-title{font-size:1.42rem;font-weight:950;color:#f8fafc;letter-spacing:-.02em;margin-top:3px}.ksp4-title span{color:#7ff2c2}.ksp4-sub{font-size:.72rem;line-height:1.5;color:#91a6ba;margin-top:5px;max-width:900px}.ksp4-chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}.ksp4-chip,.ksp4-health span,.ksp4-role{border:1px solid #284c67;background:#091a29;color:#9ddcf6;border-radius:999px;padding:4px 7px;font-size:.51rem;font-weight:900;white-space:nowrap}.ksp4-chip.green{border-color:#397d68;color:#79efbd}.ksp4-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:10px 0 13px}.ksp4-summary>div{border:1px solid #203c52;border-radius:12px;background:linear-gradient(180deg,#0a1724,#08131e);padding:10px 11px;min-width:0}.ksp4-summary span,.ksp4-line-hero span,.ksp4-stat span,.ksp4-verdict span,.ksp4-evidence-head span{display:block;color:#7089a0;font-size:.49rem;font-weight:950;letter-spacing:.07em}.ksp4-summary b{display:block;color:#f5f9fd;font-size:.92rem;margin-top:3px}.ksp4-summary small{display:block;color:#61798f;font-size:.52rem;margin-top:2px}.ksp4-matchup-card{border:1px solid #2c5575;border-radius:18px;background:linear-gradient(180deg,#081522,#07111c);padding:13px;margin:12px 0;box-shadow:0 8px 26px rgba(0,0,0,.16);overflow:hidden}.ksp4-matchup-top{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;border-bottom:1px solid #17314a;padding-bottom:10px}.ksp4-matchup-copy{display:flex;flex-direction:column;min-width:0}.ksp4-phase{color:#7ff2c2;font-size:.51rem;font-weight:950;text-transform:uppercase}.ksp4-matchup-copy>b{color:#f6f9fc;font-size:1rem;margin-top:3px}.ksp4-matchup-copy em{font-style:normal;color:#66839d;font-size:.68rem}.ksp4-matchup-copy small{color:#728ba2;font-size:.53rem;margin-top:4px;white-space:normal}.ksp4-health{display:flex;gap:5px;flex-wrap:wrap;justify-content:flex-end}.ksp4-health span.good,.ksp4-verdict.good{border-color:#287b61;color:#79efbd}.ksp4-health span.watch,.ksp4-verdict.watch{border-color:#806d2e;color:#f2d77b}.ksp4-health span.bad,.ksp4-verdict.bad{border-color:#7e3741;color:#f199a6}.ksp4-health span.neutral{color:#9fb3c6}.ksp4-team-grid{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);gap:9px;align-items:stretch;margin-top:10px}.ksp4-team-panel{border:1px solid #203f59;border-radius:14px;background:#091725;padding:11px;min-width:0}.ksp4-team-head{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}.ksp4-team-id{display:flex;align-items:center;gap:8px;min-width:0}.ksp4-team-id .kspread-logo,.ksp4-team-id .kspread-logo-fallback{width:42px;height:42px;flex:0 0 42px}.ksp4-team-id>div{display:flex;flex-direction:column;min-width:0}.ksp4-team-id b{color:#f3f8fd;font-size:.78rem;line-height:1.15;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ksp4-team-id span{color:#6f879d;font-size:.51rem;margin-top:2px}.ksp4-role{align-self:flex-start}.ksp4-role.favorite{border-color:#397d68;color:#79efbd}.ksp4-role.underdog{border-color:#806d2e;color:#f2d77b}.ksp4-role.pickem{border-color:#365d7a;color:#9ddcf6}.ksp4-role.off{border-color:#5b4650;color:#c9a3ad}.ksp4-line-row{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;margin-top:9px}.ksp4-line-hero{border:1px solid #274b65;border-radius:10px;background:#07121d;padding:8px;min-width:0}.ksp4-line-hero.fair{border-color:#2b6e61;background:#081b1b}.ksp4-line-hero b{display:block;color:#7dd3fc;font-size:1.08rem;line-height:1;margin-top:4px}.ksp4-line-hero.fair b{color:#7ff2c2}.ksp4-line-hero small{display:block;color:#70869a;font-size:.44rem;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ksp4-primary-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;margin-top:7px}.ksp4-stat{border:1px solid #18334b;border-radius:9px;background:#07121d;padding:7px;min-width:0}.ksp4-stat.hero{border-color:#2b6e61;background:#081b1b}.ksp4-stat b{display:block;color:#f4f8fc;font-size:.72rem;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ksp4-stat.hero b{color:#7ff2c2;font-size:.88rem}.ksp4-vs{align-self:center;color:#5f7b94;border:1px solid #29455c;background:#07131e;border-radius:999px;width:34px;height:34px;display:flex;align-items:center;justify-content:center;font-size:.52rem;font-weight:950}.ksp4-evidence{border:1px solid #304957;border-radius:11px;background:#09131a;padding:9px;margin-top:9px}.ksp4-evidence.bad{border-color:#6c3e3e;background:#1b1013}.ksp4-evidence-head{display:flex;justify-content:space-between;align-items:flex-start;gap:8px;margin-bottom:7px}.ksp4-evidence-head b{display:block;color:#e8f1f7;font-size:.58rem;font-weight:950;margin-top:2px}.ksp4-evidence-head em{font-style:normal;border:1px solid #3b5968;border-radius:999px;background:#0d2029;color:#9fc9da;padding:3px 7px;font-size:.37rem;font-weight:950;white-space:nowrap}.ksp4-evidence-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.ksp4-evidence-col{border:1px solid #20323b;border-radius:9px;background:#081117;padding:7px;min-width:0}.ksp4-evidence-col h4{margin:0 0 5px;font-size:.46rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase}.ksp4-evidence-col.support h4{color:#93daa9}.ksp4-evidence-col.concern h4{color:#dfbd75}.ksp4-evidence-item{border-top:1px solid #1a2931;padding:5px 1px;color:#dce8ed;font-size:.47rem;font-weight:800;line-height:1.38}.ksp4-evidence-item:first-of-type{border-top:0}.ksp4-gated{color:#c9969f;font-size:.51rem;line-height:1.4}.ksp4-verdict{display:grid;grid-template-columns:auto minmax(0,1fr);column-gap:15px;row-gap:4px;align-items:center;border:1px solid #30495d;border-radius:12px;background:#09131e;padding:10px 11px;margin-top:9px}.ksp4-verdict b{display:block;color:#f5f9fc;font-size:.92rem;margin-top:2px}.ksp4-verdict p{margin:0;color:#b9c8d4;font-size:.61rem;line-height:1.4}.ksp4-verdict small{grid-column:1/-1;color:#6e8498;font-size:.48rem}.ksp4-empty{border:1px dashed #36536f;border-radius:13px;background:#091522;color:#8ea4ba;padding:16px;margin-top:12px}
@media(max-width:820px){.ksp4-team-grid{grid-template-columns:1fr}.ksp4-vs{margin:0 auto}.ksp4-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.ksp4-matchup-top{flex-direction:column}.ksp4-health{justify-content:flex-start}.ksp4-verdict{grid-template-columns:1fr}.ksp4-verdict small{grid-column:auto}}
@media(max-width:520px){.ksp4-line-row,.ksp4-primary-grid,.ksp4-evidence-grid{grid-template-columns:1fr}.ksp4-evidence-head{flex-direction:column;gap:3px}.ksp4-hero,.ksp4-matchup-card{padding:11px}.ksp4-title{font-size:1.18rem}}
</style>
'''


def render_nfl_hub(market: str = "Spread") -> None:
    if str(market or "") != "Spread":
        raise RuntimeError("NFL Spread V4 only owns the Spread route.")

    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="ksp4-page"><section class="ksp4-hero">'
        '<div class="ksp4-kicker">NFL SPREAD • MONSTER MATCHUP LAB</div>'
        '<div class="ksp4-title">🎯 NFL Spread <span>Matchup Board</span></div>'
        '<div class="ksp4-sub">Receiving / Rushing / Moneyline visual parity • verified team identity • FanDuel spread context • independent football fair line • deterministic 5,000,000-simulation margin engine.</div>'
        '<div class="ksp4-chips">'
        '<span class="ksp4-chip">PREGAME ONLY</span>'
        '<span class="ksp4-chip">EXACT ESPN IDS</span>'
        '<span class="ksp4-chip">FANDUEL CONTEXT</span>'
        '<span class="ksp4-chip green">MODEL + 5M MC</span>'
        '<span class="ksp4-chip green">0.0% MARKET → MODEL</span>'
        '</div></section></div>',
        unsafe_allow_html=True,
    )

    if "nfl_v1_date" not in st.session_state:
        st.session_state["nfl_v1_date"] = datetime.now(frozen.base.ET).date()
    selected = st.date_input(
        "📅 NFL Spread slate date",
        value=st.session_state["nfl_v1_date"],
        key="nfl_spread_v4_date_input",
    )
    st.session_state["nfl_v1_date"] = selected
    day_str = pd.to_datetime(selected).strftime("%Y-%m-%d")

    with st.spinner("🏈 Building verified Spread matchup cards…"):
        games, diag = frozen.base.load_nfl_slate(day_str)

    if not diag.get("request_ok"):
        st.error(
            "NFL schedule provider did not return a usable slate. Spread stays fail-closed and no fake games, lines, or projections are created. "
            f"Provider: {diag.get('provider')} • HTTP: {diag.get('http') or '—'}"
        )
        return

    with st.spinner("🔌 Loading certified FanDuel Spread context…"):
        markets = frozen._fetch_markets(games)

    analytics_by_event: dict[str, dict[str, Any]] = {}
    if not games.empty:
        with st.spinner("🧠 Running frozen independent model + certified 5M Monte Carlo…"):
            for _, row in games.iterrows():
                game = row.to_dict()
                event_id = _safe(game.get("game_id"))
                market_state = markets.get(event_id) or {
                    "ready": False,
                    "reason": "Pregame Spread market was not requested for this game state.",
                    "books": [],
                    "projection_weight": 0.0,
                }
                analytics_by_event[event_id] = prior._analytics_for_game(
                    game, market_state, day_str
                )

    pregame_ids: set[str] = set()
    if not games.empty and "state" in games.columns and "game_id" in games.columns:
        pregame_ids = set(
            games.loc[games["state"].astype(str) == "pre", "game_id"].astype(str)
        )
    upcoming = len(pregame_ids)
    market_ready = sum(
        1
        for event_id, item in markets.items()
        if str(event_id) in pregame_ids and item.get("ready")
    )
    model_ready = sum(
        1
        for event_id in pregame_ids
        if (analytics_by_event.get(str(event_id)) or {}).get("ready")
    )
    mc_certified = sum(
        1
        for event_id in pregame_ids
        if (analytics_by_event.get(str(event_id)) or {}).get("certified_run")
    )

    st.markdown(
        '<div class="ksp4-page">'
        + _summary_html(
            games=int(len(games)),
            upcoming=upcoming,
            market_ready=market_ready,
            model_ready=model_ready,
            mc_certified=mc_certified,
        )
        + '</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        f"✅ Verified NFL schedule • {day_str} • {diag.get('provider')} • {len(games)} game(s) • "
        f"{market_ready}/{upcoming} market(s) • {model_ready}/{upcoming} independent model(s) • "
        f"{mc_certified}/{upcoming} certified 5M simulation(s) • sportsbook projection influence 0.0%"
    )

    try:
        st.session_state["nfl_spread_v4_last"] = {
            "version": MODEL_VERSION,
            "date": day_str,
            "games": int(len(games)),
            "pregame_games": upcoming,
            "market_ready": market_ready,
            "model_ready": model_ready,
            "mc_certified": mc_certified,
            "frozen_analytics": FROZEN_ANALYTICS,
            "frozen_model": FROZEN_MODEL,
            "frozen_monte_carlo": FROZEN_MONTE_CARLO,
            "frozen_transport": FROZEN_TRANSPORT,
            "presentation_only": True,
            "matchup_card_first": True,
            "certified_simulations": CERTIFIED_SIMULATIONS,
            "sportsbook_projection_influence": 0.0,
            "market_line_role": MARKET_LINE_ROLE,
            "rankings_enabled": False,
            "stake_sizing_enabled": False,
            "wager_actions_enabled": False,
        }
    except Exception:
        pass

    if games.empty:
        st.markdown(
            '<div class="ksp4-page"><div class="ksp4-empty">No verified NFL games were returned for this date.</div></div>',
            unsafe_allow_html=True,
        )
        return

    for _, row in games.iterrows():
        game = row.to_dict()
        event_id = _safe(game.get("game_id"))
        market_state = markets.get(event_id) or {
            "ready": False,
            "reason": "Pregame Spread market was not requested for this game state.",
            "books": [],
            "projection_weight": 0.0,
        }
        analytics = analytics_by_event.get(event_id) or {
            "ready": False,
            "error": "Independent analytics were not produced for this game.",
            "sportsbook_projection_influence": 0.0,
        }
        st.markdown(
            '<div class="ksp4-page">' + _matchup_card(game, market_state, analytics) + '</div>',
            unsafe_allow_html=True,
        )

    with st.expander("🔒 Spread V4 visual-parity contract", expanded=False):
        st.write(
            {
                "page_version": MODEL_VERSION,
                "presentation_only": True,
                "frozen_analytics": FROZEN_ANALYTICS,
                "frozen_model": FROZEN_MODEL,
                "frozen_monte_carlo": FROZEN_MONTE_CARLO,
                "frozen_transport": FROZEN_TRANSPORT,
                "official_event_identity": "ESPN game_id only",
                "projection_model": "ON — frozen V3 independent football fair margin",
                "monte_carlo": f"ON — frozen V3 deterministic {CERTIFIED_SIMULATIONS:,}",
                "market_line_role": MARKET_LINE_ROLE,
                "sportsbook_projection_influence": 0.0,
                "rankings_recommendations": "OFF",
                "stake_sizing": "OFF",
                "wager_actions": "OFF",
            }
        )


__all__ = [
    "CERTIFIED_SIMULATIONS",
    "FROZEN_ANALYTICS",
    "FROZEN_MODEL",
    "FROZEN_MONTE_CARLO",
    "FROZEN_TRANSPORT",
    "MARKET_LINE_ROLE",
    "MATCHUP_CARD_FIRST",
    "MODEL_VERSION",
    "MONTE_CARLO_ENABLED",
    "PRESENTATION_ONLY",
    "PROJECTION_MODEL_ENABLED",
    "RANKINGS_ENABLED",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "WAGER_ACTIONS_ENABLED",
    "_final_readout",
    "_first_book",
    "_matchup_card",
    "_summary_html",
    "_support_concern_rows",
    "_support_concerns_html",
    "_team_panel",
    "render_nfl_hub",
]
