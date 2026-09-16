"""CFB Over/Under Clean Page V39 — compact evidence renderer.

Presentation-only additive page over certified Clean Page V38. V39 replaces the
legacy lower-page Step 1-10 audit wall with compact, truthful evidence cards.
Frozen projection/probability math, schedule/runtime analysis, final model,
thresholds, ranking behavior and sportsbook projection influence are unchanged.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from time import perf_counter
from typing import Any, Mapping

import streamlit as st

import cfb_over_under_clean_page_v38 as frozen_page

MODEL_VERSION = "CFB O/U CLEAN PAGE V39 • COMPACT EVIDENCE RENDERER"
MARKET = "Over/Under"
FROZEN_PAGE = "cfb_over_under_clean_page_v38"
ACTIVE_LOGO_RESOLVER = frozen_page.ACTIVE_LOGO_RESOLVER
ACTIVE_MARKET_ADAPTER = frozen_page.ACTIVE_MARKET_ADAPTER
ACTIVE_MARKET_INTELLIGENCE = frozen_page.ACTIVE_MARKET_INTELLIGENCE
ACTIVE_SCHEDULE = frozen_page.ACTIVE_SCHEDULE
FROZEN_RUNTIME_SLATE = frozen_page.FROZEN_RUNTIME_SLATE
ACTIVE_RUNTIME_SLATE = frozen_page.ACTIVE_RUNTIME_SLATE
ACTIVE_PERFORMANCE_PROFILER = frozen_page.ACTIVE_PERFORMANCE_PROFILER
ACTIVE_ANALYSIS_PREWARM = frozen_page.ACTIVE_ANALYSIS_PREWARM
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

schedule_v6 = frozen_page.schedule_v6
market_adapter = frozen_page.market_adapter
runtime_slate = frozen_page.runtime_slate
final_model = frozen_page.final_model
profiler = frozen_page.profiler
_line_board = frozen_page._line_board
_market_caption = frozen_page._market_caption
_presentation = frozen_page._presentation

_CSS = r"""
<style>
.ou39-wrap{margin:9px 0 5px}.ou39-head{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:7px}.ou39-head b{color:#eef5fa;font-size:.58rem;letter-spacing:.07em}.ou39-head span{color:#768b9e;font-size:.34rem}
.ou39-freeze{display:flex;flex-wrap:wrap;gap:5px;margin:6px 0 8px}.ou39-chip{border:1px solid rgba(132,151,174,.18);border-radius:999px;background:#0a1621;color:#98a8b8;padding:4px 7px;font-size:.31rem;font-weight:900}.ou39-chip.good{border-color:rgba(60,207,137,.27);color:#9aecc0;background:rgba(19,74,51,.18)}.ou39-chip.purple{border-color:rgba(157,112,255,.28);color:#cab2ff;background:rgba(75,42,123,.18)}
.ou39-foundation{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}.ou39-card{border:1px solid rgba(130,151,172,.14);border-radius:11px;background:#09151f;padding:8px;min-width:0}.ou39-card small{display:block;color:#71879a;font-size:.27rem;font-weight:950;text-transform:uppercase}.ou39-card b{display:block;color:#edf4f8;font-size:.52rem;line-height:1.25;margin-top:3px}.ou39-card span{display:block;color:#8ea0ae;font-size:.31rem;line-height:1.38;margin-top:3px}.ou39-card.ready{border-color:rgba(60,207,137,.25);background:rgba(17,70,50,.15)}.ou39-card.ready b{color:#9deac0}.ou39-card.check{border-color:rgba(69,166,232,.23);background:rgba(15,58,86,.14)}.ou39-card.check b{color:#9fdcff}.ou39-card.limited{border-color:rgba(244,191,77,.23);background:rgba(89,66,17,.14)}.ou39-card.limited b{color:#f0d27a}.ou39-card.gated{border-color:rgba(255,102,111,.24);background:rgba(88,30,36,.14)}.ou39-card.gated b{color:#ffb0b5}
.ou39-teamrow{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin-top:6px}.ou39-team{border:1px solid rgba(132,151,174,.12);border-radius:9px;padding:7px;background:#0a1620}.ou39-team b{font-size:.48rem}.ou39-team span{font-size:.29rem}.ou39-steps{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}.ou39-step{border:1px solid rgba(130,151,172,.14);border-radius:10px;background:#09151f;padding:8px;min-width:0}.ou39-step .top{display:flex;justify-content:space-between;gap:6px;align-items:center}.ou39-step small{color:#71879a;font-size:.26rem;font-weight:950;text-transform:uppercase}.ou39-badge{border-radius:999px;padding:3px 6px;font-size:.24rem;font-weight:950}.ou39-step.ready{border-color:rgba(60,207,137,.24)}.ou39-step.ready .ou39-badge{background:rgba(30,116,78,.28);color:#9cecc0}.ou39-step.check{border-color:rgba(69,166,232,.23)}.ou39-step.check .ou39-badge{background:rgba(26,86,125,.30);color:#9edbff}.ou39-step.limited{border-color:rgba(244,191,77,.23)}.ou39-step.limited .ou39-badge{background:rgba(114,82,21,.27);color:#efd27b}.ou39-step.gated{border-color:rgba(255,102,111,.24)}.ou39-step.gated .ou39-badge{background:rgba(116,40,46,.28);color:#ffb1b6}.ou39-step b{display:block;color:#eef4f8;font-size:.48rem;margin-top:5px}.ou39-step span{display:block;color:#889aa8;font-size:.29rem;line-height:1.38;margin-top:3px}.ou39-note{margin-top:7px;border-left:3px solid #8d6cff;background:rgba(86,59,138,.11);padding:7px 8px;border-radius:0 8px 8px 0;color:#9eabba;font-size:.31rem;line-height:1.42}
@media(max-width:760px){.ou39-foundation{grid-template-columns:repeat(2,minmax(0,1fr))}.ou39-steps{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:430px){.ou39-foundation,.ou39-steps,.ou39-teamrow{grid-template-columns:1fr}}
</style>
"""

_STEP_TITLES = {
    4: "Pace / Expected Possessions",
    5: "Explosive Plays",
    6: "Red Zone",
    7: "Third Down",
    8: "Turnover Volatility",
    9: "Game-Day Environment",
    10: "Historical Matchup",
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _team_id(game: Mapping[str, Any], side: str) -> str:
    for key in (f"{side}_espn_id", f"{side}_team_id", f"{side}_id"):
        value = _clean(game.get(key))
        if value:
            return value
    try:
        visual = (frozen_page._resolve_visuals(frozen_page._display_game(game)).get(side) or {})
    except Exception:
        visual = {}
    for key in ("espn_id", "team_id", "id"):
        value = _clean(visual.get(key))
        if value:
            return value
    return ""


def _verified_identity(game: Mapping[str, Any]) -> bool:
    return bool(_team_id(game, "away") and _team_id(game, "home"))


def _engine_status(engine: Mapping[str, Any]) -> str:
    try:
        return _clean(_presentation._engine_ready(engine)).upper() or "CHECK"
    except Exception:
        return _clean(engine.get("status")).upper() or "CHECK"


def _metrics(engine: Mapping[str, Any], limit: int = 2) -> list[tuple[str, str]]:
    try:
        return [(str(a), str(b)) for a, b in _presentation._interesting(engine, limit=limit)]
    except Exception:
        return []


def _compact_step_state(step: int, engine: Mapping[str, Any], game: Mapping[str, Any]) -> dict[str, str]:
    model_status = _engine_status(engine)
    reason = _clean(engine.get("reason")) or "Certified engine output available."
    status = model_status
    lower_reason = reason.lower()
    false_identity_gate = (
        step in {5, 6, 7, 8}
        and model_status == "GATED"
        and _verified_identity(game)
        and "identity" in lower_reason
        and ("unavailable" in lower_reason or "missing" in lower_reason)
    )
    if false_identity_gate:
        status = "CHECK"
        reason = "Teams verified. Step-specific NCAA evidence unavailable; frozen prior preserved."
    return {"status": status, "model_status": model_status, "reason": reason}


def _tone(status: str) -> str:
    value = _clean(status).lower()
    return value if value in {"ready", "check", "limited", "gated"} else "check"


def _record(value: Any) -> str:
    return frozen_page._record(value)


def _compact_foundation_html(game: Mapping[str, Any], away: Mapping[str, Any], home: Mapping[str, Any], result: Mapping[str, Any]) -> str:
    display = frozen_page._display_game(game)
    away_name = _clean(display.get("away_team")) or "Away"
    home_name = _clean(display.get("home_team")) or "Home"
    away_id = _team_id(display, "away") or "—"
    home_id = _team_id(display, "home") or "—"
    identity_status = "READY" if away_id != "—" and home_id != "—" else "CHECK"
    pace = _compact_step_state(4, result.get("pace_engine") or {}, display)
    pace_metrics = _metrics(result.get("pace_engine") or {}, limit=2)
    pace_text = " • ".join(f"{a}: {b}" for a, b in pace_metrics) or pace["reason"]
    venue = _clean(display.get("venue")) or "Venue unavailable"
    broadcast = _clean(display.get("broadcast")) or "Broadcast unavailable"
    day = _clean(display.get("game_date")) or "Date TBD"
    matchup_engine = result.get("matchup_engine") or {}
    matchup_status = _engine_status(matchup_engine)
    matchup_metrics = _metrics(matchup_engine, limit=2)
    matchup_text = " • ".join(f"{a}: {b}" for a, b in matchup_metrics) or (_clean(matchup_engine.get("reason")) or "Matchup evidence available below.")
    return f'''<div class="ou39-wrap"><div class="ou39-head"><b>🏟️ MATCHUP FOUNDATION • STEPS 1–4</b><span>compact verified identity + matchup context</span></div><div class="ou39-freeze"><span class="ou39-chip good">FROZEN O/U MATH</span><span class="ou39-chip">MUTATION OFF</span><span class="ou39-chip purple">SPORTSBOOK 0.0%</span></div><div class="ou39-foundation"><div class="ou39-card {_tone(identity_status)}"><small>Step 1 • {escape(identity_status)}</small><b>Verified Team Identity</b><div class="ou39-teamrow"><div class="ou39-team"><b>{escape(away_name)}</b><span>Record {escape(_record(away.get("record") or display.get("away_record")))} • ESPN {escape(away_id)}</span></div><div class="ou39-team"><b>{escape(home_name)}</b><span>Record {escape(_record(home.get("record") or display.get("home_record")))} • ESPN {escape(home_id)}</span></div></div></div><div class="ou39-card check"><small>Step 2 • TEAM PROFILE</small><b>Game Context</b><span>{escape(day)} • {escape(venue)} • {escape(broadcast)}</span></div><div class="ou39-card {_tone(matchup_status)}"><small>Step 3 • {escape(matchup_status)}</small><b>Matchup Evidence</b><span>{escape(matchup_text[:180])}</span></div><div class="ou39-card {_tone(pace['status'])}"><small>Step 4 • {escape(pace['status'])}</small><b>Pace / Expected Possessions</b><span>{escape(pace_text[:180])}</span></div></div></div>'''


def _compact_steps_html(game: Mapping[str, Any], result: Mapping[str, Any]) -> str:
    engines = [
        (5, result.get("explosive_engine") or {}),
        (6, result.get("red_zone_engine") or {}),
        (7, result.get("third_down_engine") or {}),
        (8, result.get("turnover_engine") or {}),
        (9, result.get("environment_engine") or {}),
        (10, result.get("history_engine") or {}),
    ]
    cards: list[str] = []
    for step, engine in engines:
        state = _compact_step_state(step, engine, game)
        metrics = _metrics(engine, limit=2)
        metric_text = " • ".join(f"{a}: {b}" for a, b in metrics)
        body = metric_text or state["reason"]
        if metric_text and state["reason"]:
            body = f"{metric_text}<br>{state['reason']}"
        cards.append(
            f'<div class="ou39-step {_tone(state["status"])}"><div class="top"><small>Step {step}</small><span class="ou39-badge">{escape(state["status"])}</span></div><b>{escape(_STEP_TITLES[step])}</b><span>{body if "<br>" in body else escape(body[:190])}</span></div>'
        )
    return '<div class="ou39-wrap"><div class="ou39-head"><b>🧠 WHAT MOVES THE TOTAL • STEPS 5–10</b><span>truthful display states • model gates preserved</span></div><div class="ou39-freeze"><span class="ou39-chip good">FROZEN O/U MATH</span><span class="ou39-chip">MUTATION OFF</span><span class="ou39-chip purple">SPORTSBOOK 0.0%</span></div><div class="ou39-steps">' + "".join(cards) + '</div><div class="ou39-note">CHECK means the teams are verified but that specific NCAA evidence category is unavailable. A true frozen-model blocker remains GATED.</div></div>'


def _audit_payload(game: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]:
    engines = {
        4: result.get("pace_engine") or {},
        5: result.get("explosive_engine") or {},
        6: result.get("red_zone_engine") or {},
        7: result.get("third_down_engine") or {},
        8: result.get("turnover_engine") or {},
        9: result.get("environment_engine") or {},
        10: result.get("history_engine") or {},
    }
    return {
        f"step_{step}": {
            "display": _compact_step_state(step, engine, game),
            "raw_engine": dict(engine),
        }
        for step, engine in engines.items()
    }


def render_over_under_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    trace = profiler.PerfTrace()
    token = profiler.set_active_trace(trace)
    perf_slot = st.empty()
    started = perf_counter()
    try:
        st.caption("🟣 CFB O/U • CLEAN PAGE V39 ACTIVE • COMPACT EVIDENCE RENDERER • V38 HERO PRESERVED • TRUTHFUL STEP STATES • 0.0% SPORTSBOOK PROJECTION INFLUENCE")
        st.markdown(frozen_page._CSS + _CSS, unsafe_allow_html=True)
        selected = st.date_input("📅 CFB Over/Under slate date", value=datetime.now(frozen_page._EASTERN).date(), key="cfb_ou_v18_date")
        day = selected.isoformat()
        games, schedule_diag = schedule_v6.load_with_diagnostics(day)
        if not games:
            st.warning("No verified College Football games were returned for this date.")
            return
        odds_payload, market_diag = market_adapter.load_odds_for_date(day, "FanDuel")
        games, attach_diag = market_adapter.attach_market_lines(games, odds_payload)
        index = st.selectbox("🏟️ Over/Under matchup", options=list(range(len(games))), format_func=lambda i: f"{games[int(i)].get('away_team')} @ {games[int(i)].get('home_team')} • {frozen_page._kickoff_phoenix(games[int(i)])} " + (f"• O/U {frozen_page._market_line(games[int(i)]):.1f}" if frozen_page._market_line(games[int(i)]) is not None else "• O/U unavailable"), key=f"cfb_ou_v18_matchup_{day}")
        selected_game = dict(games[int(index)])
        identity = _clean(selected_game.get("identity_key") or selected_game.get("game_id") or index)
        live_line = frozen_page._market_line(selected_game)
        default_line = float(live_line) if live_line is not None else 50.5
        line = st.number_input("🎯 Analysis total line — threshold only (0.0% projection weight)", min_value=20.0, max_value=100.0, value=default_line, step=0.5, key=f"cfb_ou_v18_line_{day}_{identity}")
        if live_line is not None and abs(float(line) - float(live_line)) > 0.001:
            st.caption(f"✏️ Manual threshold override: {float(line):.1f} • live {selected_game.get('market_sportsbook') or 'market'} total {float(live_line):.1f}.")
        try:
            result = runtime_slate.analyze_game(selected_game, day, float(line))
        except Exception as exc:
            st.error(f"Current runtime analysis failed visibly: {type(exc).__name__}: {exc}")
            return
        game = dict(result.get("game") or selected_game)
        away = dict(result.get("away") or {})
        home = dict(result.get("home") or {})
        diag = result.get("team_diag") or {}
        st.markdown(frozen_page._hero_html(game, away, home, live_line, attach_diag), unsafe_allow_html=True)
        st.markdown(frozen_page._quick_read_html(result, float(line)), unsafe_allow_html=True)
        runtime_status = _clean(diag.get("runtime_status")) or "CHECK"
        issue_count = len(diag.get("runtime_issues") or [])
        market_state = _clean(market_diag.get("status")) or "CHECK"
        st.caption(f"Runtime data {runtime_status} • Market {market_state} • {int(schedule_diag.get('espn_matches') or 0)} ESPN-enriched matchups • {int(attach_diag.get('market_lines_attached') or 0)} live totals • {issue_count} runtime issue(s)")

        with st.expander("📈 Market context • sportsbook details", expanded=False):
            st.markdown(_market_caption(selected_game, market_diag), unsafe_allow_html=True)

        st.markdown(_compact_foundation_html(game, away, home, result), unsafe_allow_html=True)
        st.markdown(_compact_steps_html(game, result), unsafe_allow_html=True)

        with st.expander("🔬 Model Audit • raw technical evidence", expanded=False):
            st.caption("Raw engine evidence is preserved here for auditability. Display-only CHECK corrections never feed back into frozen model status or calculations.")
            st.json(_audit_payload(game, result), expanded=False)

        with st.expander("🧪 Steps 11–12 • current form + certification", expanded=False):
            st.markdown(_presentation._model_step(11, "CURRENT FORM + SCHEDULE STRENGTH", result.get("form_strength_engine") or {}), unsafe_allow_html=True)
            st.markdown(_presentation._cert_step(result), unsafe_allow_html=True)
            st.markdown(_presentation._final(result), unsafe_allow_html=True)

        with st.expander("📋 Full-slate scan workspace", expanded=False):
            st.caption("Every game keeps its own live FanDuel total when available. Analysis Line is editable and remains a threshold only.")
            editor = st.data_editor(_line_board(games, identity, float(line)), use_container_width=True, hide_index=True, key=f"cfb_ou_v18_board_{day}")
            try:
                records = editor.to_dict("records")
            except Exception:
                records = list(editor) if isinstance(editor, list) else []
            selected_lines: dict[str, float] = {}
            for row in records:
                if not bool(row.get("Use")):
                    continue
                row_identity = _clean(row.get("Identity"))
                try:
                    row_line = float(row.get("Analysis Line"))
                except Exception:
                    continue
                if row_identity and 20.0 <= row_line <= 100.0:
                    selected_lines[row_identity] = row_line
            if st.button(f"Run clean-page O/U scan for {len(selected_lines)} selected game(s)", key=f"cfb_ou_v18_scan_{day}", type="primary", disabled=not bool(selected_lines)):
                rows, scan_diag = runtime_slate.scan_slate(games, day, selected_lines)
                ranked = final_model.rank_slate(rows, limit=5)
                st.session_state[f"cfb_ou_v18_top5_{day}"] = ranked
                st.session_state[f"cfb_ou_v18_scan_diag_{day}"] = scan_diag
            top5 = st.session_state.get(f"cfb_ou_v18_top5_{day}") or []
            scan_diag = st.session_state.get(f"cfb_ou_v18_scan_diag_{day}") or {}
            if scan_diag:
                st.caption(f"{int(scan_diag.get('games_analyzed') or 0)} analyzed • {int(scan_diag.get('step12_certified_games') or 0)} Step-12 certified • {len(scan_diag.get('errors') or [])} errors")
            for rank, row in enumerate(top5, start=1):
                game_row = row.get("game") or {}
                final_row = row.get("final") or {}
                raw_row = row.get("raw") or {}
                st.markdown(f"**#{rank} {game_row.get('away_team')} @ {game_row.get('home_team')} — {final_row.get('selection') or raw_row.get('model_lean') or 'PASS'}** • projected total {frozen_page._num(raw_row.get('projected_total'),1)} • analysis line {frozen_page._num(row.get('analysis_line'),1)}")
    finally:
        trace.add("page.total_server_render", perf_counter() - started)
        profiler.reset_active_trace(token)
        try:
            st.session_state["cfb_ou_perf_v1_last"] = {"version": profiler.MODEL_VERSION, "active_page": MODEL_VERSION, "active_runtime_slate": ACTIVE_RUNTIME_SLATE, "active_market_adapter": ACTIVE_MARKET_ADAPTER, "active_prewarm": ACTIVE_ANALYSIS_PREWARM, "active_logo_resolver": ACTIVE_LOGO_RESOLVER, "total_ms": trace.total_ms(), "stages": trace.aggregate(), "projection_weight": 0.0, "may_modify_projection": False}
        except Exception:
            pass
        perf_slot.caption(trace.compact_caption(limit=8))


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"Clean O/U Page V39 received unsupported market: {market}")
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_ANALYSIS_PREWARM",
    "ACTIVE_LOGO_RESOLVER",
    "ACTIVE_MARKET_ADAPTER",
    "ACTIVE_MARKET_INTELLIGENCE",
    "ACTIVE_PERFORMANCE_PROFILER",
    "ACTIVE_RUNTIME_SLATE",
    "ACTIVE_SCHEDULE",
    "FROZEN_PAGE",
    "FROZEN_RUNTIME_SLATE",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_compact_foundation_html",
    "_compact_step_state",
    "_compact_steps_html",
    "render_cfb_hub",
    "render_over_under_hub",
]
