"""Kyre Sports AI — NFL Moneyline V9 fresh matchup-card presentation.

V9 is a presentation-only rebuild over frozen Moneyline V8. The complete V8
engine still owns pregame eligibility, QB/injury/game-plan verification,
calibrated probability, sportsbook/no-vig market context, Monte Carlo, edge/EV,
and final grading. V9 runs that frozen surface in a disposable Streamlit
container, clears the legacy step-first UI, and renders the already-computed
outputs as compact matchup-first cards inspired by the certified Rushing and
Receiving Yards pages.

No win probability, no-vig probability, Monte Carlo, fair-price, edge, EV, or
grading formula is reimplemented here.
"""
from __future__ import annotations

from datetime import date
from html import escape
import math
from typing import Any

import pandas as pd
import streamlit as st

import nfl_moneyline_hub_v1 as step1
import nfl_moneyline_hub_v8 as frozen

MODEL_VERSION = "NFL MONEYLINE V9 • FRESH MATCHUP CARDS"
FROZEN_ENGINE = "nfl_moneyline_hub_v8"
PRESENTATION_ONLY = True
MATCHUP_CARD_FIRST = True
SPORTSBOOK_MODEL_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False


def _safe(value: Any, default: str = "") -> str:
    try:
        text = str(value if value is not None else "").strip()
    except Exception:
        text = ""
    return text or default


def _num(value: Any) -> float:
    try:
        out = float(value)
        return out if math.isfinite(out) else math.nan
    except Exception:
        return math.nan


def _pct(value: Any, digits: int = 1) -> str:
    n = _num(value)
    return "—" if not math.isfinite(n) else f"{100.0 * n:.{digits}f}%"


def _pp(value: Any, digits: int = 1) -> str:
    n = _num(value)
    if not math.isfinite(n):
        return "—"
    sign = "+" if n > 0 else ""
    return f"{sign}{100.0 * n:.{digits}f} pp"


def _ev(value: Any, digits: int = 1) -> str:
    n = _num(value)
    if not math.isfinite(n):
        return "—"
    sign = "+" if n > 0 else ""
    return f"{sign}{100.0 * n:.{digits}f}%"


def _ml(value: Any) -> str:
    n = _num(value)
    if not math.isfinite(n):
        return "—"
    x = int(round(n))
    return f"+{x}" if x > 0 else str(x)


def _status_class(value: str) -> str:
    text = _safe(value).upper()
    if text in {"QUALIFIED", "READY", "VERIFIED", "HIGH"}:
        return "good"
    if text in {"LEAN / WATCH", "MEDIUM", "AGING"}:
        return "watch"
    if text in {"GATED", "HIGH UNCERTAINTY", "CHECK", "LOW"}:
        return "warn"
    if text in {"NO PLAY", "UNAVAILABLE", "STALE"}:
        return "bad"
    return "neutral"


def _gid(game: dict) -> str:
    return _safe(game.get("game_id")) or f"{_safe(game.get('away_abbr')).upper()}@{_safe(game.get('home_abbr')).upper()}"


def _team_logo(game: dict, side: str) -> str:
    logo = _safe(game.get(f"{side}_logo"))
    abbr = _safe(game.get(f"{side}_abbr"), "NFL")
    team = _safe(game.get(f"{side}_team"), side.title())
    return step1.foundation._team_logo(logo, abbr, team)


def _qb_snapshot(ctx: dict, gameplan: dict, regular_season: bool) -> dict:
    qbs = list((ctx or {}).get("qbs") or [])
    qb1 = qbs[0] if qbs else {}
    depth_name = _safe(qb1.get("name"), "QB not verified")
    explicit = _safe((gameplan or {}).get("starter_name")) if (gameplan or {}).get("starter_verified") else ""
    starter = explicit or depth_name
    injury = _safe(qb1.get("injury_status"), "No listed injury" if qb1 else "Availability unknown")
    depth_state = _safe((ctx or {}).get("depth_state"), "CHECK")
    injury_state = _safe((ctx or {}).get("injury_state"), "CHECK")
    if regular_season:
        plan_state = "REGULAR SEASON"
    else:
        plan_state = "VERIFIED" if (gameplan or {}).get("ready") else "CHECK"
    return {
        "starter": starter,
        "injury": injury,
        "depth_state": depth_state,
        "injury_state": injury_state,
        "plan_state": plan_state,
    }


def _side_html(*, game: dict, side: str, edge: dict, grade: dict, ctx: dict, gp: dict, mc: dict) -> str:
    team = _safe(game.get(f"{side}_team"), side.title())
    abbr = _safe(game.get(f"{side}_abbr"), "NFL")
    record = _safe(game.get(f"{side}_record"), "—")
    qb = _qb_snapshot(ctx, gp, _safe(game.get("season_type")).lower() != "preseason")
    model_p = edge.get("model_p")
    market_p = edge.get("market_p")
    fair_ml = edge.get("fair_ml")
    best_price = edge.get("best_price")
    best_book = _safe(edge.get("best_book"), "—")
    grade_name = _safe(grade.get("grade"), "NO PLAY")
    if side == "away":
        p05 = mc.get("p05_probability")
        p95 = mc.get("p95_probability")
    else:
        away_p95 = _num(mc.get("p95_probability"))
        away_p05 = _num(mc.get("p05_probability"))
        p05 = 1.0 - away_p95 if math.isfinite(away_p95) else math.nan
        p95 = 1.0 - away_p05 if math.isfinite(away_p05) else math.nan
    interval = f"{_pct(p05)}–{_pct(p95)}"
    return f'''
      <section class="kml9-team-panel kml9-{escape(side)}">
        <div class="kml9-team-head">
          <div class="kml9-team-id">{_team_logo(game, side)}<div><b>{escape(team)}</b><span>{escape(abbr)} • {escape(record)}</span></div></div>
          <span class="kml9-grade {_status_class(grade_name)}">{escape(grade_name)}</span>
        </div>
        <div class="kml9-qb-row">
          <div><span>QB / AVAILABILITY</span><b>{escape(qb['starter'])}</b><small>{escape(qb['injury'])}</small></div>
          <div class="kml9-mini-status"><span>{escape(qb['depth_state'])}</span><span>{escape(qb['injury_state'])}</span><span>{escape(qb['plan_state'])}</span></div>
        </div>
        <div class="kml9-primary-grid">
          <div class="kml9-stat hero"><span>MODEL P(WIN)</span><b>{_pct(model_p)}</b></div>
          <div class="kml9-stat"><span>FAIR ML</span><b>{_ml(fair_ml)}</b></div>
          <div class="kml9-stat"><span>MARKET NO-VIG</span><b>{_pct(market_p)}</b></div>
          <div class="kml9-stat"><span>BEST ML</span><b>{_ml(best_price)}</b><small>{escape(best_book)}</small></div>
          <div class="kml9-stat"><span>EDGE</span><b>{_pp(edge.get('edge'))}</b></div>
          <div class="kml9-stat"><span>EV / 1U</span><b>{_ev(edge.get('ev'))}</b></div>
        </div>
        <div class="kml9-floor">
          <span>UNCERTAINTY RANGE <b>{interval}</b></span>
          <span>FLOOR EDGE <b>{_pp(edge.get('conservative_edge'))}</b></span>
          <span>FLOOR EV <b>{_ev(edge.get('conservative_ev'))}</b></span>
        </div>
      </section>
    '''


def _matchup_html(game: dict, final: dict, edge_out: dict, mc_out: dict, snap: dict, contexts: dict, gameplans: dict) -> str:
    away = _safe(game.get("away_team"), "Away")
    home = _safe(game.get("home_team"), "Home")
    away_abbr = _safe(game.get("away_abbr")).upper()
    home_abbr = _safe(game.get("home_abbr")).upper()
    state = _safe(final.get("state"), "GATED")
    leader_side = _safe(final.get("leader_side"), "away")
    leader = away if leader_side == "away" else home
    prereq = final.get("prerequisites") or {}
    tip = _safe(game.get("tip_et"), "TBD")
    venue = _safe(game.get("venue"), "Venue TBD")
    broadcast = _safe(game.get("broadcast"), "—")
    phase = _safe(game.get("season_type"), "NFL")
    mc_state = "CONVERGED" if (mc_out or {}).get("converged") else "CHECK"
    sims = int((mc_out or {}).get("simulations") or 0)
    market_quality = _safe((snap or {}).get("quality"), prereq.get("market_quality") or "CHECK")
    calibration = _safe(prereq.get("calibration_quality"), "CHECK")
    reasons = prereq.get("reasons") or []
    reason_text = " • ".join(_safe(x) for x in reasons if _safe(x))
    verdict_copy = {
        "QUALIFIED": f"{leader} clears the frozen production thresholds.",
        "LEAN / WATCH": f"{leader} owns the stronger positive profile, but remains below full qualification.",
        "HIGH UNCERTAINTY": f"{leader} leads the headline profile, but the uncertainty floor weakens the case.",
        "NO PLAY": "Neither side clears the frozen production thresholds.",
        "GATED": reason_text or "Required production inputs are unresolved; downstream math stays diagnostic.",
    }.get(state, reason_text or "Frozen V8 final state.")
    return f'''
    <article class="kml9-matchup-card" data-game-id="{escape(_gid(game))}">
      <div class="kml9-matchup-top">
        <div><span class="kml9-phase">{escape(phase)}</span><b>{escape(away)} <em>@</em> {escape(home)}</b><small>🕒 {escape(tip)} &nbsp; • &nbsp; 🏟️ {escape(venue)} &nbsp; • &nbsp; 📺 {escape(broadcast)}</small></div>
        <div class="kml9-health"><span class="{_status_class(calibration)}">CAL {escape(calibration)}</span><span class="{_status_class(market_quality)}">MARKET {escape(market_quality)}</span><span class="{_status_class(mc_state)}">MC {escape(mc_state)}</span></div>
      </div>
      <div class="kml9-team-grid">
        {_side_html(game=game, side='away', edge=(edge_out or {}).get('away') or {}, grade=final.get('away_grade') or {}, ctx=contexts.get(away_abbr) or {}, gp=gameplans.get(away_abbr) or {}, mc=mc_out or {})}
        {_side_html(game=game, side='home', edge=(edge_out or {}).get('home') or {}, grade=final.get('home_grade') or {}, ctx=contexts.get(home_abbr) or {}, gp=gameplans.get(home_abbr) or {}, mc=mc_out or {})}
      </div>
      <div class="kml9-verdict {_status_class(state)}">
        <div><span>FINAL MONEYLINE STATE</span><b>{escape(state)}</b></div>
        <p>{escape(verdict_copy)}</p>
        <small>{'5M' if sims >= 5_000_000 else (f'{sims:,}' if sims else '—')} simulations • market is comparison-only • sportsbook influence on model P(win): 0.0%</small>
      </div>
    </article>
    '''


_CSS = r'''
<style>
.kml9-page{max-width:1180px;margin:0 auto}.kml9-hero{border:1px solid #294e6d;border-radius:19px;background:linear-gradient(180deg,#0c1725,#08111c);padding:16px 18px;margin:6px 0 13px;overflow:hidden}.kml9-title{font-size:1.35rem;font-weight:950;color:#f7fbff;letter-spacing:-.02em}.kml9-title span{color:#7ff2c2}.kml9-sub{font-size:.72rem;line-height:1.45;color:#89a0b7;margin-top:4px}.kml9-chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}.kml9-chip,.kml9-health span,.kml9-mini-status span{border:1px solid #2a506d;background:#091a29;color:#9ddcf6;border-radius:999px;padding:4px 7px;font-size:.52rem;font-weight:900;white-space:nowrap}.kml9-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:10px 0 12px}.kml9-summary>div{border:1px solid #203b52;border-radius:11px;background:#08131f;padding:9px 10px;min-width:0}.kml9-summary span,.kml9-stat span,.kml9-qb-row span,.kml9-verdict span{display:block;color:#718aa1;font-size:.49rem;font-weight:900;letter-spacing:.06em}.kml9-summary b{display:block;color:#f4f8fc;font-size:.9rem;margin-top:3px}.kml9-matchup-card{border:1px solid #2c5575;border-radius:18px;background:linear-gradient(180deg,#081522,#07111c);padding:13px;margin:12px 0;box-shadow:0 8px 26px rgba(0,0,0,.16);overflow:hidden}.kml9-matchup-top{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;border-bottom:1px solid #17314a;padding-bottom:10px}.kml9-matchup-top>div:first-child{display:flex;flex-direction:column;min-width:0}.kml9-phase{color:#7ff2c2;font-size:.51rem;font-weight:950;text-transform:uppercase}.kml9-matchup-top b{color:#f6f9fc;font-size:1rem;margin-top:3px}.kml9-matchup-top em{font-style:normal;color:#66839d;font-size:.68rem}.kml9-matchup-top small{color:#728ba2;font-size:.53rem;margin-top:4px;white-space:normal}.kml9-health{display:flex;gap:5px;flex-wrap:wrap;justify-content:flex-end}.kml9-health span.good,.kml9-grade.good,.kml9-verdict.good{border-color:#287b61;color:#79efbd}.kml9-health span.watch,.kml9-grade.watch,.kml9-verdict.watch{border-color:#806d2e;color:#f2d77b}.kml9-health span.warn,.kml9-grade.warn,.kml9-verdict.warn{border-color:#8b6032;color:#f1b56f}.kml9-health span.bad,.kml9-grade.bad,.kml9-verdict.bad{border-color:#7e3741;color:#f199a6}.kml9-team-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:10px}.kml9-team-panel{border:1px solid #203f59;border-radius:14px;background:#091725;padding:11px;min-width:0}.kml9-team-head{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}.kml9-team-id{display:flex;align-items:center;gap:8px;min-width:0}.kml9-team-id img{width:34px!important;height:34px!important;object-fit:contain}.kml9-team-id>div{display:flex;flex-direction:column;min-width:0}.kml9-team-id b{color:#f3f8fd;font-size:.78rem;line-height:1.15}.kml9-team-id span{color:#6f879d;font-size:.51rem;margin-top:2px}.kml9-grade{border:1px solid #35536a;border-radius:999px;padding:4px 6px;color:#aac0d2;font-size:.48rem;font-weight:950;white-space:nowrap}.kml9-qb-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;border-top:1px solid #173149;border-bottom:1px solid #173149;margin-top:9px;padding:8px 0;align-items:center}.kml9-qb-row>div:first-child{min-width:0}.kml9-qb-row b{display:block;color:#eaf1f8;font-size:.68rem;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kml9-qb-row small{display:block;color:#778da1;font-size:.49rem;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kml9-mini-status{display:flex;gap:3px;flex-wrap:wrap;justify-content:flex-end}.kml9-mini-status span{font-size:.43rem;padding:3px 5px}.kml9-primary-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin-top:8px}.kml9-stat{border:1px solid #18334b;border-radius:9px;background:#07121d;padding:7px;min-width:0}.kml9-stat.hero{border-color:#2b6e61;background:#081b1b}.kml9-stat b{display:block;color:#f4f8fc;font-size:.78rem;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kml9-stat.hero b{color:#7ff2c2;font-size:.95rem}.kml9-stat small{display:block;color:#70869a;font-size:.44rem;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kml9-floor{display:flex;gap:8px;flex-wrap:wrap;margin-top:7px;color:#71899f;font-size:.48rem}.kml9-floor b{color:#b7c7d4;font-weight:900}.kml9-verdict{display:grid;grid-template-columns:auto minmax(0,1fr);column-gap:15px;row-gap:4px;align-items:center;border:1px solid #30495d;border-radius:12px;background:#09131e;padding:10px 11px;margin-top:10px}.kml9-verdict b{display:block;color:#f5f9fc;font-size:.92rem;margin-top:2px}.kml9-verdict p{margin:0;color:#b9c8d4;font-size:.61rem;line-height:1.4}.kml9-verdict small{grid-column:1/-1;color:#6e8498;font-size:.48rem}.kml9-empty{border:1px dashed #36536f;border-radius:13px;background:#091522;color:#8ea4ba;padding:16px;margin-top:12px}
@media(max-width:820px){.kml9-team-grid{grid-template-columns:1fr}.kml9-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.kml9-matchup-top{flex-direction:column}.kml9-health{justify-content:flex-start}.kml9-verdict{grid-template-columns:1fr}.kml9-verdict small{grid-column:auto}}
@media(max-width:520px){.kml9-primary-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.kml9-qb-row{grid-template-columns:1fr}.kml9-mini-status{justify-content:flex-start}.kml9-hero,.kml9-matchup-card{padding:11px}.kml9-title{font-size:1.18rem}}
</style>
'''


def _sync_frozen_date(selected) -> None:
    st.session_state["nfl_v1_date"] = selected
    # The historical chain owns its own widget keys. Keep any existing widget
    # state aligned so a previous visit cannot override the new V9 selector.
    for key in list(st.session_state.keys()):
        if str(key).startswith("nfl_moneyline_v") and str(key).endswith("_date_input"):
            st.session_state[key] = selected
    st.session_state["nfl_moneyline_v1_date_input"] = selected
    st.session_state["nfl_moneyline_v2_date_input"] = selected
    st.session_state["nfl_moneyline_v3_date_input"] = selected


def _run_frozen_engine() -> None:
    legacy = st.empty()
    with legacy.container():
        frozen.render_nfl_moneyline_hub()
    legacy.empty()


def render_nfl_moneyline_hub() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="kml9-page"><div class="kml9-hero">'
        '<div class="kml9-title">💰 NFL Moneyline <span>Matchup Board</span></div>'
        '<div class="kml9-sub">Pregame team cards • verified QB availability • calibrated model probability • live market comparison • 5M Monte Carlo • edge/EV • frozen final grading.</div>'
        '<div class="kml9-chips"><span class="kml9-chip">PREGAME ONLY</span><span class="kml9-chip">MODEL / MARKET FIREWALL</span><span class="kml9-chip">V8 ENGINE FROZEN</span><span class="kml9-chip">STAKE SIZING OFF</span></div>'
        '</div></div>',
        unsafe_allow_html=True,
    )

    default_date = st.session_state.get("nfl_v1_date", date.today())
    selected = st.date_input("📅 Moneyline slate date", value=default_date, key="nfl_moneyline_v9_date_input")
    _sync_frozen_date(selected)

    with st.spinner("💰 Building verified Moneyline matchup cards…"):
        _run_frozen_engine()

    pregame = list(st.session_state.get("nfl_moneyline_v3_pregame") or st.session_state.get("nfl_moneyline_v1_pregame") or [])
    contexts = st.session_state.get("nfl_moneyline_v3_team_context") or st.session_state.get("nfl_moneyline_v2_team_context") or {}
    gameplans = st.session_state.get("nfl_moneyline_v3_gameplan_context") or {}
    edges = st.session_state.get("nfl_moneyline_v7_edge_outputs") or {}
    mc_outputs = st.session_state.get("nfl_moneyline_v6_mc_outputs") or {}
    snapshots = st.session_state.get("nfl_moneyline_v5_market_snapshots") or {}
    profiles = st.session_state.get("nfl_moneyline_v4_strength_profiles") or {}

    depth_ready = bool(st.session_state.get("nfl_moneyline_v3_depth_ready") or st.session_state.get("nfl_moneyline_v2_depth_ready"))
    injury_ready = bool(st.session_state.get("nfl_moneyline_v3_injuries_ready") or st.session_state.get("nfl_moneyline_v2_injuries_ready"))
    market_ready = bool(st.session_state.get("nfl_moneyline_v5_market_ready"))
    mc_ready = bool(st.session_state.get("nfl_moneyline_v6_mc_ready"))
    edge_ready = bool(st.session_state.get("nfl_moneyline_v7_edge_ready"))

    summary = (
        '<div class="kml9-page"><div class="kml9-summary">'
        f'<div><span>PREGAME GAMES</span><b>{len(pregame)}</b></div>'
        f'<div><span>QB / INJURY</span><b>{"READY" if depth_ready and injury_ready else "CHECK"}</b></div>'
        f'<div><span>MARKET</span><b>{"READY" if market_ready else "CHECK"}</b></div>'
        f'<div><span>MODEL + MC</span><b>{"READY" if mc_ready and edge_ready else "CHECK"}</b></div>'
        '</div></div>'
    )
    st.markdown(summary, unsafe_allow_html=True)

    if not pregame:
        st.markdown('<div class="kml9-page"><div class="kml9-empty">No verified pregame NFL matchup is available for this date. Live, final, passed-kickoff, and unknown-time games remain fail-closed.</div></div>', unsafe_allow_html=True)
        return

    calibration = frozen.v431.v43._fit_calibration_model()
    for game in pregame:
        gid = _gid(game)
        edge_out = edges.get(gid, {})
        mc_out = mc_outputs.get(gid, {})
        snap = snapshots.get(gid, {})
        final = frozen._build_final(game, gid, edge_out, mc_out, snap, profiles, calibration)
        st.markdown('<div class="kml9-page">' + _matchup_html(game, final, edge_out, mc_out, snap, contexts, gameplans) + '</div>', unsafe_allow_html=True)

        away = _safe(game.get("away_team"), "Away")
        home = _safe(game.get("home_team"), "Home")
        with st.expander(f"Model details & guardrails — {away} @ {home}", expanded=False):
            prereq = final.get("prerequisites") or {}
            if prereq.get("reasons"):
                st.caption("Hard-gate status: " + " • ".join(_safe(x) for x in prereq.get("reasons") or []))
            st.caption(
                "Frozen ownership: V8 final grading • V7 edge/EV • V6 Monte Carlo • V5 market/no-vig • V4.x calibrated P(win) • V3/V2 availability. "
                "Sportsbook prices are comparison-only and never alter model P(win). Stake sizing remains OFF."
            )
            if snap.get("rows"):
                rows = []
                for row in snap.get("rows") or []:
                    rows.append({
                        "Book": row.get("book") or "—",
                        "Away ML": _ml(row.get("away_ml")),
                        "Home ML": _ml(row.get("home_ml")),
                        "Freshness": row.get("freshness") or "UNKNOWN",
                        "Provider": row.get("provider") or "—",
                    })
                st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    st.caption("Model probabilities are estimates — not guarantees. Moneyline V9 changes presentation only; frozen V8 analytical ownership remains authoritative.")


# Router compatibility with NFL hubs that call render_nfl_hub(market).
def render_nfl_hub(market: str = "Moneyline") -> None:
    if _safe(market, "Moneyline") != "Moneyline":
        raise RuntimeError("NFL Moneyline V9 handles Moneyline only.")
    return render_nfl_moneyline_hub()


__all__ = [
    "FROZEN_ENGINE",
    "MATCHUP_CARD_FIRST",
    "MODEL_VERSION",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_MODEL_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "render_nfl_hub",
    "render_nfl_moneyline_hub",
]
