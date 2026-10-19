"""NBA Spread Page V7 — launch-ready Page 1 presentation.

Additive presentation successor over the frozen Step-10 decision stack and V6
live-data repair. It keeps all model/projection/probability/ranking ownership in
those frozen parents, but turns Page 1 into a compact next-slate scanner.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping, Sequence

import streamlit as st

import nba_spread_page_v1 as base_page
import nba_spread_page_v2 as step7_page
import nba_spread_page_v4 as step9_page
import nba_spread_page_v5 as step10_page
import nba_spread_page_v6 as live_repair_page
from nba_spread_market_lines_v1 import build_spread_market_context

MODEL_VERSION = "NBA_SPREAD_PAGE_V7_LAUNCH_READY_PAGE1"
FROZEN_PARENT_PAGE = "nba_spread_page_v6"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_PAGE2 = False

_CSS = r"""
<style>
.nba7-hero{border:1px solid rgba(56,189,248,.28);border-radius:20px;padding:16px 18px;background:linear-gradient(135deg,rgba(8,18,31,.98),rgba(12,38,60,.96));margin:8px 0 10px}.nba7-kicker{font-size:.72rem;font-weight:950;letter-spacing:.12em;color:#67d8ff}.nba7-title{font-size:clamp(1.7rem,5vw,2.35rem);font-weight:950;color:#f8fafc;letter-spacing:-.035em;margin-top:3px}.nba7-sub{font-size:.86rem;color:#9fb1c2;margin-top:5px}.nba7-slate{display:flex;justify-content:space-between;gap:12px;align-items:center;border:1px solid rgba(148,163,184,.14);border-radius:14px;padding:10px 12px;background:#09131f;margin:0 0 10px}.nba7-slate b{color:#f4f8fb;font-size:.9rem}.nba7-slate span{color:#86a0b5;font-size:.76rem}.nba7-status{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin:8px 0 14px}.nba7-chip{border:1px solid rgba(148,163,184,.14);border-radius:12px;padding:9px 10px;background:#08131f}.nba7-chip small{display:block;color:#8197aa;font-size:.65rem;font-weight:900;letter-spacing:.04em}.nba7-chip b{display:block;color:#e7f0f6;font-size:.82rem;margin-top:3px}.nba7-chip .ok{color:#83e1af}.nba7-chip .wait{color:#f6d28b}.nba7-section{font-size:.76rem;font-weight:950;letter-spacing:.08em;color:#cbd5e1;margin:16px 0 8px;text-transform:uppercase}.nba7-opps{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-bottom:12px}.nba7-opp{border:1px solid rgba(103,216,255,.26);border-radius:14px;background:linear-gradient(145deg,#091622,#0d2538);padding:11px}.nba7-opp small{color:#7edaff;font-size:.63rem;font-weight:950}.nba7-opp b{display:block;color:#fff;font-size:.94rem;margin-top:4px}.nba7-opp span{display:block;color:#8ea4b6;font-size:.7rem;margin-top:3px}.nba7-card{border:1px solid rgba(103,216,255,.20);border-radius:18px;background:linear-gradient(145deg,#091522,#0d2032);padding:14px 15px;margin:0 0 10px}.nba7-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.nba7-matchup{font-size:1.08rem;font-weight:950;color:#f8fafc}.nba7-names{color:#8499ab;font-size:.72rem;margin-top:3px}.nba7-time{text-align:right;color:#f3f7fa;font-size:.82rem;font-weight:900;white-space:nowrap}.nba7-date{font-size:.67rem;color:#7890a5;margin-top:3px}.nba7-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin-top:11px}.nba7-metric{border:1px solid rgba(148,163,184,.12);border-radius:11px;background:rgba(4,12,20,.45);padding:9px}.nba7-metric small{display:block;color:#71889c;font-size:.6rem;font-weight:950;text-transform:uppercase}.nba7-metric b{display:block;color:#edf5fa;font-size:.78rem;margin-top:4px;line-height:1.35}.nba7-decision{display:flex;justify-content:space-between;gap:10px;align-items:center;border-radius:11px;padding:9px 10px;margin-top:9px;background:rgba(21,49,69,.48);border:1px solid rgba(103,216,255,.16)}.nba7-decision strong{font-size:.8rem;color:#f8fafc}.nba7-decision span{font-size:.68rem;color:#8ca4b7;text-align:right}.nba7-decision.play{border-color:rgba(55,205,126,.28);background:rgba(17,69,48,.24)}.nba7-decision.play strong{color:#a9ebc4}.nba7-footer{font-size:.65rem;color:#637d91;margin-top:8px}.nba7-empty{border:1px dashed rgba(148,163,184,.18);border-radius:14px;padding:14px;color:#8399aa;font-size:.78rem}.nba7-diag{font-size:.76rem;color:#8da2b2;line-height:1.65}.nba7-diag b{color:#e1ebf1}
@media(max-width:800px){.nba7-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.nba7-opps{grid-template-columns:1fr}.nba7-status{grid-template-columns:1fr 1fr 1fr}}
@media(max-width:540px){.nba7-status{grid-template-columns:1fr}.nba7-head{align-items:flex-start}.nba7-grid{grid-template-columns:1fr 1fr}.nba7-decision{align-items:flex-start;flex-direction:column}.nba7-decision span{text-align:left}}
</style>
"""


def _clean(value: object) -> str:
    return str(value or "").strip()


def _line(value: object) -> str:
    try:
        return f"{float(value):+g}"
    except (TypeError, ValueError):
        return "—"


def _pct(value: object) -> str:
    try:
        return f"{100.0 * float(value):.1f}%"
    except (TypeError, ValueError):
        return "—"


def _pair(game: Mapping[str, Any]) -> tuple[str, str]:
    return (_clean(game.get("away_tricode")).upper(), _clean(game.get("home_tricode")).upper())


def _next_active_slate_games(games: Sequence[Mapping[str, Any]]) -> tuple[str | None, list[dict]]:
    eligible = [
        dict(game)
        for game in games
        if _clean(game.get("status")).upper() in {"UPCOMING", "DELAYED"}
        and _clean(game.get("game_date_phoenix"))
    ]
    if not eligible:
        return None, []
    dates = sorted({_clean(game.get("game_date_phoenix")) for game in eligible})
    target = dates[0]
    slate = [game for game in eligible if _clean(game.get("game_date_phoenix")) == target]
    slate.sort(key=lambda game: (_clean(game.get("tip_phoenix")), _clean(game.get("away_tricode")), _clean(game.get("home_tricode"))))
    return target, slate


def _market_by_game(games: Sequence[Mapping[str, Any]], payload: Mapping[str, Any]) -> dict[tuple[str, str], dict]:
    observations = payload.get("observations") or []
    rows = [dict(row) for row in observations if isinstance(row, Mapping)] if isinstance(observations, Sequence) and not isinstance(observations, (str, bytes)) else []
    out: dict[tuple[str, str], dict] = {}
    for game in games:
        pair = _pair(game)
        pair_rows = [row for row in rows if (_clean(row.get("away_tricode")).upper(), _clean(row.get("home_tricode")).upper()) == pair]
        if _clean(payload.get("verification")).upper() != "VERIFIED":
            out[pair] = {"verification": "UNAVAILABLE", "diagnostic_state": _clean(payload.get("diagnostic_state")) or "SPORTSBOOK_OBSERVATIONS_NOT_VERIFIED"}
            continue
        context = build_spread_market_context(pair_rows, [game])
        if context.get("verification") != "VERIFIED" and not context.get("diagnostic_state"):
            context["diagnostic_state"] = "CONSENSUS_QUORUM_NOT_MET"
        out[pair] = context
    return out


def _injury_map(games: Sequence[Mapping[str, Any]]) -> tuple[dict[tuple[str, str], dict], dict]:
    if not games:
        return {}, {"verification": "UNAVAILABLE", "diagnostic_state": "NO_UPCOMING_GAMES", "features": []}
    try:
        payload = step7_page._load_injury_availability(list(games))
    except Exception as exc:
        payload = {"verification": "UNAVAILABLE", "diagnostic_state": f"INJURY_TRANSPORT_ERROR:{type(exc).__name__}", "features": []}
    out: dict[tuple[str, str], dict] = {}
    for feature in payload.get("features") or []:
        if not isinstance(feature, Mapping):
            continue
        out[(_clean(feature.get("away_tricode")).upper(), _clean(feature.get("home_tricode")).upper())] = dict(feature)
    return out, dict(payload)


def _injury_summary(feature: Mapping[str, Any] | None) -> tuple[str, str]:
    if not feature or not _clean(feature.get("verification")).upper().startswith("VERIFIED"):
        return "Injury status pending", "pending"
    away = dict(feature.get("away") or {})
    home = dict(feature.get("home") or {})
    counts: dict[str, int] = {}
    for side in (away, home):
        for label, value in dict(side.get("counts") or {}).items():
            try:
                counts[str(label).upper()] = counts.get(str(label).upper(), 0) + int(value or 0)
            except (TypeError, ValueError):
                continue
    pieces = []
    for label in ("OUT", "DOUBTFUL", "QUESTIONABLE", "PROBABLE"):
        count = counts.get(label, 0)
        if count:
            pieces.append(f"{count} {label.lower()}")
    if not pieces:
        return "No major limitations", "clear"
    state = "alert" if counts.get("OUT", 0) or counts.get("DOUBTFUL", 0) else "watch"
    return " • ".join(pieces), state


def _fair_model(game: Mapping[str, Any]) -> dict:
    record = dict(game.get("step9_fair_spread") or {})
    if record.get("verification") != "VERIFIED":
        return {}
    model = dict(record.get("pregame_model") or {})
    return model if model else {}


def _decision(game: Mapping[str, Any]) -> dict:
    record = dict(game.get("step10_decision") or {})
    return record if record else {}


def _market_text(game: Mapping[str, Any], market: Mapping[str, Any]) -> str:
    away, home = _pair(game)
    if market.get("verification") != "VERIFIED":
        return "Pending verification"
    return f"{away} {_line(market.get('consensus_away_spread'))} • {home} {_line(market.get('consensus_home_spread'))}"


def _fair_text(game: Mapping[str, Any]) -> str:
    away, home = _pair(game)
    model = _fair_model(game)
    if not model:
        return "Model verification pending"
    return f"{away} {_line(model.get('fair_away_spread'))} • {home} {_line(model.get('fair_home_spread'))}"


def _cover_text(game: Mapping[str, Any]) -> str:
    away, home = _pair(game)
    model = _fair_model(game)
    if not model or model.get("cover_verification") != "VERIFIED":
        return "Market threshold pending"
    return f"{away} {_pct(model.get('away_cover_probability'))} • {home} {_pct(model.get('home_cover_probability'))}"


def _decision_text(game: Mapping[str, Any]) -> tuple[str, str, bool]:
    decision = _decision(game)
    if decision.get("verification") == "VERIFIED" and decision.get("decision_state") == "PLAY":
        pick = _clean(decision.get("pick_text")) or "PLAY"
        strength = _clean(decision.get("pick_strength")) or "Verified"
        grade = _clean(decision.get("production_grade")) or ""
        detail = " • ".join(item for item in (strength, grade) if item)
        return f"MODEL LEAN • {pick}", detail, True
    return "MODEL STATUS • NO PLAY", "Verification / edge threshold pending", False


def _compact_game_card(game: Mapping[str, Any], market: Mapping[str, Any], injury: Mapping[str, Any] | None) -> str:
    away, home = _pair(game)
    away_name = escape(_clean(game.get("away_name")) or away)
    home_name = escape(_clean(game.get("home_name")) or home)
    tip = escape(_clean(game.get("tip_phoenix")) or "Time pending")
    date = escape(_clean(game.get("game_date_phoenix")) or "Date pending")
    venue = escape(_clean(game.get("venue")))
    injury_text, _ = _injury_summary(injury)
    decision_label, decision_detail, is_play = _decision_text(game)
    venue_html = f'<div class="nba7-footer">{venue} • Verified schedule: NBA Official + ESPN NBA</div>' if venue else '<div class="nba7-footer">Verified schedule: NBA Official + ESPN NBA</div>'
    return f'''<div class="nba7-card" data-testid="nba-spread-v7-game-card">
      <div class="nba7-head"><div><div class="nba7-matchup">{escape(away)} @ {escape(home)}</div><div class="nba7-names">{away_name} at {home_name}</div></div><div class="nba7-time">{tip}<div class="nba7-date">{date} • Phoenix</div></div></div>
      <div class="nba7-grid">
        <div class="nba7-metric"><small>Market</small><b>{escape(_market_text(game, market))}</b></div>
        <div class="nba7-metric"><small>Kyre Fair Spread</small><b>{escape(_fair_text(game))}</b></div>
        <div class="nba7-metric"><small>Cover Probability</small><b>{escape(_cover_text(game))}</b></div>
        <div class="nba7-metric"><small>Injury Status</small><b>{escape(injury_text)}</b></div>
      </div>
      <div class="nba7-decision{' play' if is_play else ''}"><strong>{escape(decision_label)}</strong><span>{escape(decision_detail)}</span></div>
      {venue_html}
    </div>'''


def _load_launch_schedule() -> dict:
    original_market = step9_page._load_sportsbook_observations
    step9_page._load_sportsbook_observations = live_repair_page._load_verified_market_payload
    try:
        return step10_page._load_schedule_with_step10()
    finally:
        step9_page._load_sportsbook_observations = original_market


def _status_chip(label: str, verified: bool) -> str:
    state = "Verified" if verified else "Pending"
    css = "ok" if verified else "wait"
    return f'<div class="nba7-chip"><small>{escape(label)}</small><b class="{css}">● {state}</b></div>'


def _best_opportunities(games: Sequence[Mapping[str, Any]]) -> list[dict]:
    plays: list[dict] = []
    for game in games:
        decision = _decision(game)
        if decision.get("verification") != "VERIFIED" or decision.get("decision_state") != "PLAY":
            continue
        row = dict(game)
        row["_decision"] = decision
        plays.append(row)
    def key(game: Mapping[str, Any]) -> tuple[int, float]:
        decision = dict(game.get("_decision") or {})
        rank = decision.get("slate_rank")
        rank_value = int(rank) if isinstance(rank, int) and rank > 0 else 999
        try:
            edge = float(decision.get("cover_edge_pp") or 0.0)
        except (TypeError, ValueError):
            edge = 0.0
        return (rank_value, -edge)
    return sorted(plays, key=key)[:3]


def _opportunity_html(games: Sequence[Mapping[str, Any]]) -> str:
    cards = []
    for index, game in enumerate(_best_opportunities(games), start=1):
        decision = dict(game.get("_decision") or {})
        away, home = _pair(game)
        pick = _clean(decision.get("pick_text")) or "PLAY"
        strength = _clean(decision.get("pick_strength")) or "Verified"
        cards.append(f'<div class="nba7-opp"><small>#{index} VERIFIED EDGE</small><b>{escape(away)} @ {escape(home)} • {escape(pick)}</b><span>{escape(strength)} • {_pct(decision.get("selected_cover_probability_no_push"))} no-push cover</span></div>')
    return '<div class="nba7-opps">' + "".join(cards) + "</div>" if cards else ""


def render_nba_spread_page() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown('<div data-testid="nba-spread-v7-launch-ready-active" style="display:none!important"></div>', unsafe_allow_html=True)
    st.markdown('''<div class="nba7-hero"><div class="nba7-kicker">KYRE SPORTS AI • NBA</div><div class="nba7-title">🏀 NBA Spread</div><div class="nba7-sub">Next active slate • Phoenix time • verified schedule and decision context</div></div>''', unsafe_allow_html=True)

    schedule = _load_launch_schedule()
    if schedule.get("verification") != "VERIFIED":
        st.markdown('<div class="nba7-empty">Verified NBA schedule is temporarily unavailable. The page will not invent matchups.</div>', unsafe_allow_html=True)
        with st.expander("Sources & Diagnostics", expanded=False):
            st.write({"schedule": schedule.get("diagnostic_state") or "UNAVAILABLE"})
        return

    slate_date, games = _next_active_slate_games(list(schedule.get("games") or []))
    if not games:
        st.markdown('<div class="nba7-empty">No verified upcoming NBA games are available in the current rolling window.</div>', unsafe_allow_html=True)
        return

    market_payload = live_repair_page._load_verified_market_payload(games)
    market_map = _market_by_game(games, market_payload)
    public_bundle = live_repair_page._load_public_bundle(games)
    injuries, injury_payload = _injury_map(games)

    st.markdown(f'<div class="nba7-slate"><b>NEXT NBA SLATE • {escape(str(slate_date))}</b><span>{len(games)} game{"s" if len(games) != 1 else ""} • auto-updating</span></div>', unsafe_allow_html=True)
    market_verified = any(feature.get("verification") == "VERIFIED" for feature in market_map.values())
    betting_verified = public_bundle.get("verification") == "VERIFIED"
    injury_verified = bool(injuries) and all(_clean(feature.get("verification")).upper().startswith("VERIFIED") for feature in injuries.values())
    st.markdown('<div class="nba7-section">MARKET DATA STATUS</div><div class="nba7-status">' + _status_chip("Market Odds", market_verified) + _status_chip("Betting Splits", betting_verified) + _status_chip("Injuries", injury_verified) + '</div>', unsafe_allow_html=True)

    opportunities = _opportunity_html(games)
    if opportunities:
        st.markdown('<div class="nba7-section">BEST OPPORTUNITIES</div>' + opportunities, unsafe_allow_html=True)

    st.markdown('<div class="nba7-section">NEXT SLATE</div>', unsafe_allow_html=True)
    for game in games:
        pair = _pair(game)
        st.markdown(_compact_game_card(game, market_map.get(pair) or {}, injuries.get(pair)), unsafe_allow_html=True)

    with st.expander("Sources & Diagnostics", expanded=False):
        market_diags = sorted({_clean(item.get("diagnostic_state")) for item in market_map.values() if item.get("verification") != "VERIFIED" and _clean(item.get("diagnostic_state"))})
        st.markdown(
            f'<div class="nba7-diag"><b>Schedule:</b> {_clean(schedule.get("verification"))} • NBA Official + ESPN NBA<br>'
            f'<b>Market transport:</b> {_clean(market_payload.get("verification")) or "UNAVAILABLE"} • {escape(_clean(market_payload.get("diagnostic_state")) or "OK")}<br>'
            f'<b>Per-game market diagnostics:</b> {escape(", ".join(market_diags) or "OK")}<br>'
            f'<b>Public betting:</b> {escape(_clean(public_bundle.get("verification")) or "UNAVAILABLE")} • {escape(_clean(public_bundle.get("diagnostic_state")) or "OK")}<br>'
            f'<b>Injuries:</b> {escape(_clean(injury_payload.get("verification")) or "CHECK")} • {escape(_clean(injury_payload.get("diagnostic_state")) or "OK")}<br>'
            f'<b>Model boundary:</b> frozen Step-10 model/decision ownership • sportsbook projection influence 0.0%</div>',
            unsafe_allow_html=True,
        )


__all__ = [
    "FROZEN_PARENT_PAGE", "MAY_MODIFY_MODEL", "MAY_MODIFY_PAGE2", "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION", "MAY_MODIFY_RANKING", "MODEL_VERSION", "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_compact_game_card", "_injury_summary", "_market_by_game", "_next_active_slate_games", "render_nba_spread_page",
]
