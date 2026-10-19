"""NBA Spread Page V8 — professional decision board + exact selected-game seam.

Additive presentation successor over V7. Frozen Step-9/Step-10 retain all model,
projection, probability, decision, and ranking ownership. V8 adds truthful V2
market presentation, exact team identity, and a minimal selected-game consumer.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from collections.abc import Mapping, Sequence
from typing import Any

import streamlit as st

import nba_spread_page_v2 as step7_page
import nba_spread_page_v7 as frozen_v7
import nba_spread_live_data_repair_v2 as live_v2
from nba_spread_decision_board_data_v1 import build_decision_board_state
from nba_spread_team_identity_v1 import resolve_nba_team_logo
from nba_spread_page1_handoff_v1 import apply_analysis_handoff
from nba_spread_selected_game_consumer_v1 import build_back_query, build_selected_game_state
from nba_spread_page2_selected_game_v1 import render_selected_game

MODEL_VERSION = "NBA_SPREAD_PAGE_V8_PROFESSIONAL_DECISION_BOARD_V1"
FROZEN_PARENT_PAGE = "nba_spread_page_v7"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_PAGE2 = False

_CSS = r"""
<style>
.nba8-hero{border:1px solid rgba(56,189,248,.30);border-radius:22px;padding:17px 18px;background:linear-gradient(135deg,rgba(7,17,29,.99),rgba(11,39,61,.97));margin:8px 0 10px}.nba8-kicker{font-size:.7rem;font-weight:950;letter-spacing:.12em;color:#67d8ff}.nba8-title{font-size:clamp(1.8rem,5vw,2.45rem);font-weight:950;color:#f8fafc;letter-spacing:-.04em;margin-top:3px}.nba8-sub{font-size:.85rem;color:#9bb0c0;margin-top:5px}.nba8-slate{display:flex;justify-content:space-between;gap:12px;align-items:center;border:1px solid rgba(148,163,184,.14);border-radius:14px;padding:10px 12px;background:#09131f;margin-bottom:7px}.nba8-slate b{font-size:.91rem;color:#f4f8fb}.nba8-slate span{font-size:.74rem;color:#8299ab}.nba8-fresh{font-size:.68rem;color:#738b9f;margin:0 2px 13px}.nba8-section{font-size:.75rem;font-weight:950;letter-spacing:.09em;color:#cbd5e1;margin:16px 0 8px;text-transform:uppercase}.nba8-opps{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-bottom:13px}.nba8-opp{border:1px solid rgba(55,205,126,.24);border-radius:14px;background:linear-gradient(145deg,#091823,#0b2930);padding:11px}.nba8-opp small{color:#9ee6bc;font-size:.62rem;font-weight:950}.nba8-opp b{display:block;color:#fff;font-size:.91rem;margin-top:4px}.nba8-opp span{display:block;color:#8fa7b7;font-size:.69rem;margin-top:3px}.nba8-card{border:1px solid rgba(103,216,255,.20);border-radius:19px;background:linear-gradient(145deg,#081522,#0d2032);padding:14px 15px;margin:0 0 7px}.nba8-head{display:flex;justify-content:space-between;gap:12px;align-items:center}.nba8-teams{display:flex;align-items:center;gap:10px;min-width:0}.nba8-logo{width:42px;height:42px;border-radius:50%;object-fit:contain;background:rgba(255,255,255,.05);padding:3px}.nba8-mono{width:42px;height:42px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:#0d2b42;color:#dff4ff;font-size:.66rem;font-weight:950}.nba8-matchup{font-size:1.08rem;font-weight:950;color:#f8fafc}.nba8-names{font-size:.71rem;color:#8198aa;margin-top:3px}.nba8-time{text-align:right;white-space:nowrap;font-size:.82rem;font-weight:900;color:#f4f8fb}.nba8-date{font-size:.65rem;color:#758da0;margin-top:3px}.nba8-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin-top:11px}.nba8-metric{border:1px solid rgba(148,163,184,.12);border-radius:11px;background:rgba(4,12,20,.45);padding:9px}.nba8-metric small{display:block;color:#71889c;font-size:.6rem;font-weight:950;text-transform:uppercase}.nba8-metric b{display:block;color:#edf5fa;font-size:.8rem;margin-top:4px;line-height:1.34}.nba8-inj{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:7px}.nba8-inj div{border:1px solid rgba(148,163,184,.09);border-radius:9px;padding:7px 8px;color:#92a9ba;font-size:.68rem}.nba8-decision{display:flex;justify-content:space-between;gap:10px;align-items:center;border-radius:11px;padding:9px 10px;margin-top:8px;background:rgba(21,49,69,.48);border:1px solid rgba(103,216,255,.15)}.nba8-decision.play{border-color:rgba(55,205,126,.26);background:rgba(17,69,48,.23)}.nba8-decision strong{font-size:.79rem;color:#f8fafc}.nba8-decision.play strong{color:#a9ebc4}.nba8-decision span{font-size:.67rem;color:#8ca4b7;text-align:right}.nba8-move{font-size:.66rem;color:#7f98ab;margin-top:7px}.nba8-action{font-size:.7rem;font-weight:950;color:#67d8ff;margin-top:9px}.nba8-empty{border:1px dashed rgba(148,163,184,.18);border-radius:14px;padding:14px;color:#8399aa;font-size:.78rem}.nba8-diag{font-size:.75rem;color:#8da2b2;line-height:1.65}.nba8-diag b{color:#e1ebf1}
@media(max-width:800px){.nba8-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.nba8-opps{grid-template-columns:1fr}.nba8-head{align-items:flex-start}}
@media(max-width:600px){.nba8-grid{grid-template-columns:1fr 1fr}.nba8-inj{grid-template-columns:1fr}.nba8-decision{align-items:flex-start;flex-direction:column}.nba8-decision span{text-align:left}.nba8-slate{align-items:flex-start;flex-direction:column}.nba8-logo,.nba8-mono{width:38px;height:38px}}
</style>
"""


def _clean(value: object) -> str:
    return str(value or "").strip()


def _line(value: object) -> str:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{parsed:+g}" if parsed != 0 else "PK"


def _pct(value: object) -> str:
    try:
        return f"{100.0 * float(value):.1f}%"
    except (TypeError, ValueError):
        return "—"


def _human_slate_label(value: object) -> str:
    text = _clean(value)
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return "NEXT NBA SLATE"
    return f"NEXT NBA SLATE • {parsed.strftime('%a %b %d').upper()}"


def _logo_html(code: str, url: str | None) -> str:
    if url:
        return f'<img class="nba8-logo" alt="{escape(code)} logo" src="{escape(url)}">'
    return f'<div class="nba8-mono">{escape(code)}</div>'


def _market_text(record: Mapping[str, Any]) -> str:
    market = dict(record.get("market") or {})
    away = _clean(record.get("away_tricode"))
    home = _clean(record.get("home_tricode"))
    if market.get("verification") != "VERIFIED":
        return _clean(market.get("label")) or "Market verification pending"
    text = f"{away} {_line(market.get('away_spread'))} • {home} {_line(market.get('home_spread'))}"
    label = _clean(market.get("label"))
    return f"{text} • {label}" if label else text


def _fair_text(record: Mapping[str, Any]) -> str:
    fair = dict(record.get("fair") or {})
    away = _clean(record.get("away_tricode"))
    home = _clean(record.get("home_tricode"))
    if fair.get("verification") != "VERIFIED":
        return _clean(fair.get("reason")) or "Model verification pending"
    return f"{away} {_line(fair.get('away_spread'))} • {home} {_line(fair.get('home_spread'))}"


def _cover_text(record: Mapping[str, Any]) -> str:
    cover = dict(record.get("cover") or {})
    away = _clean(record.get("away_tricode"))
    home = _clean(record.get("home_tricode"))
    if cover.get("verification") != "VERIFIED":
        return _clean(cover.get("reason")) or "Market threshold pending"
    return f"{away} {_pct(cover.get('away_probability'))} • {home} {_pct(cover.get('home_probability'))}"


def _edge_text(record: Mapping[str, Any]) -> str:
    value = record.get("edge_points")
    try:
        return f"{float(value):.1f} pts"
    except (TypeError, ValueError):
        return "Verification pending"


def _decision_text(record: Mapping[str, Any]) -> tuple[str, str, bool]:
    decision = dict(record.get("decision") or {})
    if decision.get("verification") == "VERIFIED" and decision.get("decision_state") == "PLAY":
        title = _clean(decision.get("pick_text")) or "VERIFIED PLAY"
        detail = " • ".join(item for item in (_clean(decision.get("pick_strength")), _clean(decision.get("production_grade"))) if item) or "Verified Step-10 play"
        return title, detail, True
    return "NO PLAY", _clean(decision.get("consumer_reason")) or "Verification / edge threshold pending", False


def _decision_card_html(record: Mapping[str, Any]) -> str:
    away = _clean(record.get("away_tricode")) or "AWAY"
    home = _clean(record.get("home_tricode")) or "HOME"
    away_name = _clean(record.get("away_name")) or away
    home_name = _clean(record.get("home_name")) or home
    away_logo = record.get("away_logo") or resolve_nba_team_logo(away)
    home_logo = record.get("home_logo") or resolve_nba_team_logo(home)
    tip = _clean(record.get("tip_phoenix")) or "Time pending"
    date = _clean(record.get("date") or record.get("game_date_phoenix")) or "Date pending"
    venue = _clean(record.get("venue"))
    injuries = dict(record.get("injuries") or {})
    away_inj = _clean(injuries.get("away_summary")) or f"{away}: status pending"
    home_inj = _clean(injuries.get("home_summary")) or f"{home}: status pending"
    decision_title, decision_detail, is_play = _decision_text(record)
    movement = dict(record.get("line_movement") or {}) if isinstance(record.get("line_movement"), Mapping) else {}
    movement_html = f'<div class="nba8-move">{escape(_clean(movement.get("label")))}</div>' if _clean(movement.get("label")) else ""
    venue_bit = f" • {escape(venue)}" if venue else ""
    return f'''<div class="nba8-card" data-testid="nba-spread-v8-game-card">
      <div class="nba8-head">
        <div class="nba8-teams">{_logo_html(away, away_logo)}{_logo_html(home, home_logo)}<div><div class="nba8-matchup">{escape(away)} @ {escape(home)}</div><div class="nba8-names">{escape(away_name)} at {escape(home_name)}{venue_bit}</div></div></div>
        <div class="nba8-time">{escape(tip)}<div class="nba8-date">{escape(date)} • Phoenix</div></div>
      </div>
      <div class="nba8-grid">
        <div class="nba8-metric"><small>Market</small><b>{escape(_market_text(record))}</b></div>
        <div class="nba8-metric"><small>Kyre Fair Spread</small><b>{escape(_fair_text(record))}</b></div>
        <div class="nba8-metric"><small>Cover Probability</small><b>{escape(_cover_text(record))}</b></div>
        <div class="nba8-metric"><small>Edge</small><b>{escape(_edge_text(record))}</b></div>
      </div>
      <div class="nba8-inj"><div>{escape(away_inj)}</div><div>{escape(home_inj)}</div></div>
      <div class="nba8-decision{' play' if is_play else ''}"><strong>{escape(decision_title)}</strong><span>{escape(decision_detail)}</span></div>
      {movement_html}<div class="nba8-action">View Analysis →</div>
    </div>'''


def _load_schedule_and_market_once() -> tuple[dict, dict | None]:
    """Run the frozen V7 schedule/model chain with the verified V2 market seam.

    V7 already owns the Step-9 market-threshold injection point. V8 swaps only
    that transport dependency, captures its result, and restores the frozen
    binding immediately. The captured payload is then reused by Page 1 so the
    market provider is not fetched again for the same render.
    """
    captured: dict[str, dict] = {}
    original_market_loader = frozen_v7.live_repair_page._load_verified_market_payload

    def _market_once(games: list[dict]) -> dict:
        if "payload" not in captured:
            captured["payload"] = dict(live_v2.load_market_payload_v2(games) or {})
        return captured["payload"]

    frozen_v7.live_repair_page._load_verified_market_payload = _market_once
    try:
        schedule = frozen_v7._load_launch_schedule()
    finally:
        frozen_v7.live_repair_page._load_verified_market_payload = original_market_loader
    return dict(schedule or {}), captured.get("payload")


@st.cache_data(ttl=90, show_spinner=False)
def _load_market_once(games: list[dict]) -> dict:
    return live_v2.load_market_payload_v2(games)


@st.cache_data(ttl=180, show_spinner=False)
def _load_injuries_once(games: list[dict]) -> dict:
    try:
        return step7_page._load_injury_availability(games)
    except Exception as exc:
        return {"verification": "UNAVAILABLE", "diagnostic_state": f"INJURY_TRANSPORT_ERROR:{type(exc).__name__}", "features": []}


@st.cache_data(ttl=180, show_spinner=False)
def _load_public_once(games: list[dict]) -> dict:
    return live_v2.load_public_betting_payload(games)


def _query_value(name: str) -> str:
    try:
        value = st.query_params.get(name, "")
    except Exception:
        return ""
    if isinstance(value, (list, tuple)):
        value = value[-1] if value else ""
    return _clean(value)


def _market_history(payload: Mapping[str, Any]) -> dict[str, list[dict]]:
    key = "nba_spread_v8_market_history"
    history = st.session_state.get(key)
    if not isinstance(history, dict):
        history = {}
    for row in payload.get("observations") or []:
        if not isinstance(row, Mapping):
            continue
        game_key = _clean(row.get("game_key"))
        stamp = _clean(row.get("observed_at_utc") or row.get("retrieved_at_utc"))
        if not game_key or not stamp:
            continue
        series = [dict(item) for item in history.get(game_key, []) if isinstance(item, Mapping)]
        snapshot = {
            "verification": "VERIFIED",
            "away_spread": row.get("away_spread"),
            "home_spread": row.get("home_spread"),
            "observed_at_utc": stamp,
        }
        if not any(_clean(item.get("observed_at_utc")) == stamp and item.get("away_spread") == snapshot["away_spread"] for item in series):
            series.append(snapshot)
        series.sort(key=lambda item: _clean(item.get("observed_at_utc")))
        history[game_key] = series[-8:]
    st.session_state[key] = history
    return history


def _best_opportunities_html(rows: Sequence[Mapping[str, Any]]) -> str:
    cards: list[str] = []
    for index, row in enumerate(list(rows)[:3], start=1):
        pick = _clean(row.get("pick_text")) or "VERIFIED PLAY"
        strength = _clean(row.get("pick_strength")) or "Verified"
        grade = _clean(row.get("production_grade"))
        detail = " • ".join(item for item in (strength, grade) if item)
        cards.append(f'<div class="nba8-opp"><small>#{index} VERIFIED OPPORTUNITY</small><b>{escape(pick)}</b><span>{escape(detail)}</span></div>')
    return '<div class="nba8-opps">' + "".join(cards) + '</div>' if cards else ""


def _render_selected(schedule: Mapping[str, Any], *, date: str, game_id: str) -> bool:
    games = [dict(game) for game in schedule.get("games") or [] if isinstance(game, Mapping)]
    state = build_selected_game_state(games, date=date, game_id=game_id)
    if state.get("verification") != "VERIFIED":
        st.markdown('<div class="nba8-empty">The selected NBA Spread game could not be verified. Return to the slate and choose the matchup again.</div>', unsafe_allow_html=True)
        return True
    game = dict(state["game"])
    selected_games = [game]
    market_payload = _load_market_once(selected_games)
    injury_payload = _load_injuries_once(selected_games)
    board = build_decision_board_state(selected_games, market_payload, injury_payload, {"verification": "UNAVAILABLE", "observations": []}, now_utc=datetime.now(timezone.utc))
    card = dict((board.get("games") or [{}])[0]) if board.get("games") else {}

    if st.button("← Back to NBA Spread slate", key="nba_spread_v8_back", use_container_width=True):
        current = dict(st.query_params)
        back = build_back_query(current)
        st.session_state.pop("game_id", None)
        st.session_state.pop("date", None)
        st.query_params.clear()
        st.query_params.update(back)
        st.rerun()
    render_selected_game(state, market=dict(card.get("market") or {}), injuries=dict(card.get("injuries") or {}))
    with st.expander("Sources & Diagnostics", expanded=False):
        st.write({
            "selected_game": state.get("verification"),
            "market": market_payload.get("verification"),
            "injuries": injury_payload.get("verification"),
            "model_boundary": "Frozen Step-9 / Step-10; sportsbook projection influence 0.0%",
        })
    return True


def render_nba_spread_page() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown('<div data-testid="nba-spread-v8-decision-board-active" style="display:none!important"></div>', unsafe_allow_html=True)
    st.markdown('<div class="nba8-hero"><div class="nba8-kicker">KYRE SPORTS AI • NBA</div><div class="nba8-title">🏀 NBA Spread Decision Board</div><div class="nba8-sub">Verified market context • Kyre fair line • exact-game analysis handoff</div></div>', unsafe_allow_html=True)

    schedule, captured_market = _load_schedule_and_market_once()
    if schedule.get("verification") != "VERIFIED":
        st.markdown('<div class="nba8-empty">Verified NBA schedule is temporarily unavailable. No matchup will be invented.</div>', unsafe_allow_html=True)
        with st.expander("Sources & Diagnostics", expanded=False):
            st.write({"schedule": schedule.get("diagnostic_state") or "UNAVAILABLE"})
        return

    selected_id = _query_value("game_id")
    selected_date = _query_value("date")
    if selected_id:
        _render_selected(schedule, date=selected_date, game_id=selected_id)
        return

    slate_date, games = frozen_v7._next_active_slate_games(list(schedule.get("games") or []))
    if not games:
        st.markdown('<div class="nba8-empty">No verified upcoming NBA games are available in the current rolling window.</div>', unsafe_allow_html=True)
        return

    market_payload = captured_market if isinstance(captured_market, Mapping) else _load_market_once(games)
    injury_payload = _load_injuries_once(games)
    public_payload = _load_public_once(games)
    history = _market_history(market_payload)
    board = build_decision_board_state(
        games,
        market_payload,
        injury_payload,
        public_payload,
        now_utc=datetime.now(timezone.utc),
        market_history=history,
    )

    public_verified = _clean(public_payload.get("verification")).upper() == "VERIFIED"
    freshness_parts = [
        f"Market: {_clean(market_payload.get('verification')) or 'UNAVAILABLE'}",
        f"Injuries: {_clean(injury_payload.get('verification')) or 'CHECK'}",
    ]
    if public_verified:
        freshness_parts.append("Public betting: VERIFIED")
    st.markdown(f'<div class="nba8-slate"><b>{escape(_human_slate_label(slate_date))}</b><span>{len(games)} game{"s" if len(games) != 1 else ""} • Phoenix time</span></div><div class="nba8-fresh">{escape(" • ".join(freshness_parts))}</div>', unsafe_allow_html=True)

    opportunities = _best_opportunities_html(board.get("best_opportunities") or [])
    if opportunities:
        st.markdown('<div class="nba8-section">BEST OPPORTUNITIES</div>' + opportunities, unsafe_allow_html=True)

    st.markdown('<div class="nba8-section">NEXT SLATE</div>', unsafe_allow_html=True)
    game_by_key = {_clean(game.get("game_key")): game for game in games}
    for record in board.get("games") or []:
        if not isinstance(record, Mapping):
            continue
        row = dict(record)
        row["away_logo"] = resolve_nba_team_logo(_clean(row.get("away_tricode")))
        row["home_logo"] = resolve_nba_team_logo(_clean(row.get("home_tricode")))
        st.markdown(_decision_card_html(row), unsafe_allow_html=True)
        game = game_by_key.get(_clean(row.get("game_key")))
        if game and st.button("View Analysis →", key=f"nba_spread_v8_open_{_clean(row.get('game_key'))}", use_container_width=True):
            query = dict(st.query_params)
            patch = apply_analysis_handoff(st.session_state, query, game)
            if patch:
                st.query_params.clear()
                st.query_params.update(query)
                st.rerun()

    with st.expander("Sources & Diagnostics", expanded=False):
        st.markdown(
            f'<div class="nba8-diag"><b>Schedule:</b> {escape(_clean(schedule.get("verification")) or "UNAVAILABLE")} • NBA Official + ESPN NBA<br>'
            f'<b>Market transport:</b> {escape(_clean(market_payload.get("verification")) or "UNAVAILABLE")}<br>'
            f'<b>Injuries:</b> {escape(_clean(injury_payload.get("verification")) or "CHECK")}<br>'
            f'<b>Public betting:</b> {escape(_clean(public_payload.get("verification")) or "UNAVAILABLE")}<br>'
            f'<b>Model boundary:</b> frozen Step-9 / Step-10 • sportsbook projection influence 0.0%</div>',
            unsafe_allow_html=True,
        )


__all__ = [
    "FROZEN_PARENT_PAGE",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PAGE2",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RANKING",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_decision_card_html",
    "_human_slate_label",
    "render_nba_spread_page",
]
