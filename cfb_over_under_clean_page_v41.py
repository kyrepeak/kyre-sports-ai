"""CFB Over/Under Clean Page V41 — Slider + Readability V3.

Presentation-only additive successor over frozen Premium Dashboard V40. Schedule,
market, runtime analysis, team evidence, frozen projection math, selection
probabilities, full-slate ranking, and sportsbook influence stay owned by the
certified stack.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from time import perf_counter
from typing import Any, Mapping

import streamlit as st

import cfb_over_under_clean_page_v40 as frozen_page

MODEL_VERSION = "CFB O/U CLEAN PAGE V41 • SLIDER + READABILITY V3"
MARKET = frozen_page.MARKET
FROZEN_PRESENTATION = "cfb_over_under_clean_page_v40"
FROZEN_PAGE = frozen_page.FROZEN_PAGE
FROZEN_RUNTIME_SLATE = frozen_page.FROZEN_RUNTIME_SLATE
ACTIVE_LOGO_RESOLVER = frozen_page.ACTIVE_LOGO_RESOLVER
ACTIVE_MARKET_ADAPTER = frozen_page.ACTIVE_MARKET_ADAPTER
ACTIVE_MARKET_INTELLIGENCE = frozen_page.ACTIVE_MARKET_INTELLIGENCE
ACTIVE_SCHEDULE = frozen_page.ACTIVE_SCHEDULE
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
_clean = frozen_page._clean
_num = frozen_page._num
_market_line = frozen_page._market_line
_kickoff_phoenix = frozen_page._kickoff_phoenix
_display_game = frozen_page._display_game
_resolve_visuals = frozen_page._resolve_visuals
_float = frozen_page._float
_pct = frozen_page._pct
_decision_state = frozen_page._decision_state
_record = frozen_page._record
_metric = frozen_page._metric
_EASTERN = frozen_page._EASTERN
_presentation = frozen_page._presentation

_CSS = r"""
<style>
.ou41-section{margin:22px 0 10px}.ou41-kicker{color:#81dcff;font-size:.76rem;font-weight:950;letter-spacing:.09em;text-transform:uppercase}.ou41-heading{color:#f4f8fb;font-size:1.28rem;font-weight:950;margin-top:3px;line-height:1.18}.ou41-sub{color:#a8bac7;font-size:.92rem;line-height:1.55;margin-top:4px}
.ou41-matchup{margin:12px 0 14px;border:1px solid rgba(116,153,182,.22);border-radius:18px;background:linear-gradient(145deg,rgba(9,26,39,.98),rgba(8,19,29,.98));padding:15px}.ou41-matchup-main{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);gap:14px;align-items:center}.ou41-team-side{display:flex;align-items:center;gap:12px;min-width:0}.ou41-team-side.home{justify-content:flex-end;text-align:right}.ou41-matchup-logo{width:72px;height:72px;display:flex;align-items:center;justify-content:center;flex:0 0 72px;border-radius:16px;background:#0b1b28;border:1px solid rgba(124,160,190,.18);overflow:hidden}.ou41-matchup-logo img{width:72px;height:72px;object-fit:contain;padding:6px}.ou41-matchup-logo span{font-size:1.28rem;font-weight:950;color:#eff7fb}.ou41-team-name{color:#f4f8fb;font-size:1.08rem;font-weight:950;line-height:1.2}.ou41-team-meta{color:#9eb2c1;font-size:.86rem;margin-top:4px}.ou41-vs{color:#7f95a8;font-size:.78rem;font-weight:950;letter-spacing:.08em}.ou41-game-meta{display:flex;flex-wrap:wrap;gap:8px 14px;margin-top:13px;padding-top:12px;border-top:1px solid rgba(120,151,177,.13);color:#b2c2cd;font-size:.9rem}.ou41-game-meta b{color:#f0f6fa}
.ou41-decision{margin:12px 0 14px;border:1px solid rgba(127,99,255,.42);border-radius:20px;background:linear-gradient(145deg,rgba(42,31,96,.95),rgba(7,24,35,.98));padding:16px}.ou41-grid{display:grid;grid-template-columns:1.45fr repeat(4,minmax(0,1fr));gap:9px}.ou41-pick,.ou41-stat{border:1px solid rgba(125,151,176,.18);border-radius:14px;background:#091925;padding:13px}.ou41-pick{border-color:rgba(154,121,255,.45);background:linear-gradient(145deg,rgba(77,50,154,.38),rgba(8,20,32,.86))}.ou41-label{font-size:.72rem;color:#c0b5ff;font-weight:950;letter-spacing:.08em}.ou41-pick strong{display:block;color:#fff;font-size:2rem;font-weight:950;line-height:1.05;margin-top:6px}.ou41-pick span,.ou41-stat span{display:block;color:#9fb0bd;font-size:.84rem;line-height:1.4;margin-top:5px}.ou41-stat small{display:block;color:#8ca2b4;font-size:.72rem;font-weight:950}.ou41-stat b{display:block;color:#f1f7fa;font-size:1.18rem;margin-top:6px}
.ou41-slider-head{display:flex;align-items:end;justify-content:space-between;gap:12px;margin:4px 0 8px}.ou41-slider-value small{display:block;color:#8ca2b4;font-size:.76rem;font-weight:900}.ou41-slider-value b{display:block;color:#f5f9fb;font-size:1.9rem;line-height:1}.ou41-market-chip{border:1px solid rgba(92,184,235,.22);border-radius:999px;background:rgba(21,72,101,.18);padding:7px 11px;color:#c0d8e7;font-size:.82rem;font-weight:850}.ou41-marker{position:relative;height:28px;margin:0 0 8px}.ou41-marker-track{position:absolute;left:0;right:0;top:12px;height:3px;border-radius:3px;background:rgba(120,151,177,.24)}.ou41-marker-pin{position:absolute;top:4px;transform:translateX(-50%);display:flex;flex-direction:column;align-items:center;gap:2px}.ou41-marker-pin i{display:block;width:2px;height:16px;background:#73c9f7}.ou41-marker-pin em{font-style:normal;color:#9ec6dc;font-size:.7rem;white-space:nowrap}.ou41-lab{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:9px}.ou41-lab div,.ou41-market div{border:1px solid rgba(111,151,183,.18);border-radius:12px;background:#091722;padding:10px}.ou41-lab small,.ou41-market small{display:block;color:#8da4b5;font-size:.74rem;font-weight:950}.ou41-lab b,.ou41-market b{display:block;color:#eef5f9;font-size:1.06rem;margin-top:5px}.ou41-note{margin-top:8px;border-left:3px solid #69bfff;border-radius:0 9px 9px 0;background:rgba(27,77,109,.16);padding:9px 11px;color:#a9bdca;font-size:.86rem;line-height:1.5}
.ou41-reasons,.ou41-drivers{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}.ou41-card{border:1px solid rgba(124,150,175,.18);border-radius:14px;background:#091722;padding:12px}.ou41-card.primary{border-color:rgba(126,99,255,.38);background:rgba(63,45,127,.2)}.ou41-card.ready{border-color:rgba(44,194,124,.3);background:rgba(16,72,51,.19)}.ou41-card.gated{border-color:rgba(255,108,115,.28);background:rgba(85,30,35,.18)}.ou41-card small{display:block;color:#8da4b5;font-size:.73rem;font-weight:950;letter-spacing:.03em}.ou41-card b{display:block;color:#eef5f8;font-size:1.02rem;margin-top:5px}.ou41-card strong{display:block;color:#fff;font-size:1.28rem;line-height:1.15;margin-top:8px}.ou41-card span{display:block;color:#a6b8c4;font-size:.86rem;line-height:1.5;margin-top:5px}.ou41-signal{display:inline-flex;align-items:center;margin-top:8px;border-radius:999px;padding:5px 8px;border:1px solid rgba(123,152,177,.18);color:#c7d5de;font-size:.77rem;font-weight:900}.ou41-signal.over{border-color:rgba(57,197,121,.28);color:#9be2b8}.ou41-signal.under{border-color:rgba(255,122,130,.28);color:#ffb1b6}.ou41-signal.neutral,.ou41-signal.context{color:#b6c5cf}
.ou41-team{border:1px solid rgba(120,150,176,.18);border-radius:15px;background:#081621;overflow:hidden}.ou41-teamhead,.ou41-row{display:grid;grid-template-columns:minmax(0,1fr) 1.1fr minmax(0,1fr);align-items:center;padding:10px 11px}.ou41-teamhead{background:rgba(21,47,66,.58)}.ou41-row{border-top:1px solid rgba(120,150,176,.11)}.ou41-teamhead b,.ou41-row strong{color:#eef5f9;font-size:.94rem}.ou41-teamhead b:last-child,.ou41-row strong:last-child{text-align:right}.ou41-teamhead span,.ou41-row span{text-align:center;color:#8da2b3;font-size:.78rem;font-weight:900}
.ou41-market{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px}.ou41-market span{display:block;color:#a4b6c3;font-size:.82rem;margin-top:4px}.ou41-rule{margin-top:8px;border:1px solid rgba(80,194,255,.2);border-radius:10px;background:rgba(21,70,99,.15);padding:9px 11px;color:#a7c2d2;font-size:.86rem;line-height:1.5}.ou41-diag{color:#9cb0bd;font-size:.85rem;line-height:1.6}.ou41-diag b{color:#dce7ee}
@media(max-width:900px){.ou41-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.ou41-pick{grid-column:1/-1}.ou41-reasons,.ou41-drivers,.ou41-market{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:620px){.ou41-matchup-main{grid-template-columns:1fr auto 1fr;gap:8px}.ou41-team-side{flex-direction:column;text-align:center}.ou41-team-side.home{flex-direction:column-reverse;text-align:center}.ou41-matchup-logo,.ou41-matchup-logo img{width:56px;height:56px;flex-basis:56px}.ou41-team-name{font-size:.94rem}.ou41-game-meta{font-size:.82rem}.ou41-lab,.ou41-reasons,.ou41-drivers,.ou41-market{grid-template-columns:1fr}.ou41-teamhead,.ou41-row{grid-template-columns:.8fr 1fr .8fr}.ou41-slider-head{align-items:flex-start;flex-direction:column}.ou41-market-chip{align-self:flex-start}}
</style>
"""


def _section(kicker: str, title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="ou41-section"><div class="ou41-kicker">{escape(kicker)}</div><div class="ou41-heading">{escape(title)}</div><div class="ou41-sub">{escape(subtitle)}</div></div>',
        unsafe_allow_html=True,
    )


def _clamp_line(value: Any) -> float:
    number = _float(value)
    if number is None:
        number = 50.5
    number = max(20.0, min(100.0, float(number)))
    return round(number * 2.0) / 2.0


def _nudge_line(key: str, delta: float) -> None:
    st.session_state[key] = _clamp_line((_float(st.session_state.get(key)) or 50.5) + float(delta))


def _monogram(name: str) -> str:
    tokens = [token for token in _clean(name).replace("&", " ").split() if token]
    return "".join(token[0].upper() for token in tokens[:2]) or "CFB"


def _logo_html(name: str, visual: Mapping[str, Any]) -> str:
    url = _clean(visual.get("logo") or visual.get("logo_url") or visual.get("image"))
    if url:
        return f'<div class="ou41-matchup-logo"><img src="{escape(url, quote=True)}" alt="{escape(name)} logo"></div>'
    return f'<div class="ou41-matchup-logo"><span>{escape(_monogram(name))}</span></div>'


def _compact_matchup_html(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    live_line: float | None,
) -> str:
    display = _display_game(game)
    visuals = _resolve_visuals(display)
    away_name = _clean(display.get("away_team")) or _clean(away.get("team")) or "Away"
    home_name = _clean(display.get("home_team")) or _clean(home.get("team")) or "Home"
    venue = _clean(display.get("venue") or display.get("venue_name")) or "Venue unavailable"
    broadcast = _clean(display.get("broadcast") or display.get("network") or display.get("tv")) or "Broadcast unavailable"
    date_text = _clean(display.get("date") or display.get("game_date") or display.get("start_date")) or "Date unavailable"
    sportsbook = _clean(game.get("market_sportsbook")) or "Market"
    market_text = f"{sportsbook} O/U {float(live_line):.1f}" if live_line is not None else f"{sportsbook} O/U unavailable"
    return f'''<div class="ou41-matchup">
      <div class="ou41-matchup-main">
        <div class="ou41-team-side">{_logo_html(away_name, visuals.get("away") or {})}<div><div class="ou41-team-name">{escape(away_name)}</div><div class="ou41-team-meta">Record {escape(_record(away))}</div></div></div>
        <div class="ou41-vs">VS</div>
        <div class="ou41-team-side home"><div><div class="ou41-team-name">{escape(home_name)}</div><div class="ou41-team-meta">Record {escape(_record(home))}</div></div>{_logo_html(home_name, visuals.get("home") or {})}</div>
      </div>
      <div class="ou41-game-meta"><span><b>{escape(date_text)}</b></span><span>{escape(_kickoff_phoenix(display))}</span><span>{escape(venue)}</span><span>{escape(broadcast)}</span><span>{escape(market_text)}</span></div>
    </div>'''


def _decision_html(state: Mapping[str, Any]) -> str:
    selection = _clean(state.get("selection")) or "PASS"
    line = _num(state.get("analysis_line"), 1)
    projected = _num(state.get("projected_total"), 1)
    edge = _num(state.get("edge_points"), 1)
    probability = _pct(state.get("selection_probability"))
    return f'''<div class="ou41-decision"><div class="ou41-grid">
      <div class="ou41-pick"><div class="ou41-label">MODEL PICK</div><strong>{escape(selection)} {escape(line)}</strong><span>Current certified decision at your selected threshold.</span></div>
      <div class="ou41-stat"><small>PROBABILITY</small><b>{escape(probability)}</b><span>Selection probability</span></div>
      <div class="ou41-stat"><small>PROJECTED TOTAL</small><b>{escape(projected)}</b><span>Frozen projection</span></div>
      <div class="ou41-stat"><small>YOUR LINE</small><b>{escape(line)}</b><span>Slider threshold</span></div>
      <div class="ou41-stat"><small>MODEL EDGE</small><b>{escape(edge)} pts</b><span>Projection-to-line gap</span></div>
    </div></div>'''


def _slider_marker_html(line: float, live_line: float | None) -> str:
    live = f"{float(live_line):.1f}" if live_line is not None else "Unavailable"
    head = f'''<div class="ou41-slider-head"><div class="ou41-slider-value"><small>SELECTED LINE</small><b>{float(line):.1f}</b></div><div class="ou41-market-chip">Market line: {escape(live)}</div></div>'''
    if live_line is None:
        return head
    pct = max(0.0, min(100.0, (float(live_line) - 20.0) / 80.0 * 100.0))
    return head + f'''<div class="ou41-marker"><div class="ou41-marker-track"></div><div class="ou41-marker-pin" style="left:{pct:.2f}%"><i></i><em>Market {float(live_line):.1f}</em></div></div>'''


def _line_lab_html(state: Mapping[str, Any], live_line: float | None) -> str:
    live = f"{float(live_line):.1f}" if live_line is not None else "Unavailable"
    return f'''<div class="ou41-lab">
      <div><small>UNDER PROBABILITY</small><b>{escape(_pct(state.get("under_probability")))}</b></div>
      <div><small>OVER PROBABILITY</small><b>{escape(_pct(state.get("over_probability")))}</b></div>
      <div><small>PROJECTED TOTAL</small><b>{escape(_num(state.get("projected_total"),1))}</b></div>
      <div><small>VERIFIED MARKET</small><b>{escape(live)}</b></div>
    </div><div class="ou41-note">Drag the slider left or right in 0.5-point increments. The certified runtime evaluates that threshold; sportsbook data remains comparison-only with 0.0% model influence.</div>'''


def _engine_ready(engine: Mapping[str, Any]) -> bool:
    status = _clean(engine.get("status") or ("READY" if engine.get("ready") else "CHECK")).upper()
    return status in {"READY", "GREEN", "PASS", "OK"}


def _why_html(result: Mapping[str, Any], state: Mapping[str, Any]) -> str:
    projected = _float(state.get("projected_total"))
    line = _float(state.get("analysis_line"))
    edge = _float(state.get("edge_points")) or 0.0
    selection = _clean(state.get("selection")) or "PASS"
    if projected is None or line is None:
        gap_value = "Unavailable"
        gap_note = "Certified decision preserved without inventing a projection gap."
    elif selection == "UNDER":
        gap_value = f"{edge:.1f} pts below"
        gap_note = f"Projection {projected:.1f} vs line {line:.1f}."
    elif selection == "OVER":
        gap_value = f"{edge:.1f} pts above"
        gap_note = f"Projection {projected:.1f} vs line {line:.1f}."
    else:
        gap_value = f"{edge:.1f} pts"
        gap_note = f"Projection {projected:.1f} vs line {line:.1f}; no certified side cleared."
    engines = [result.get(k) or {} for k in ("explosive_engine", "red_zone_engine", "third_down_engine", "turnover_engine", "environment_engine", "history_engine")]
    ready = sum(1 for engine in engines if _engine_ready(engine))
    probability = _pct(state.get("selection_probability"))
    return f'''<div class="ou41-reasons">
      <div class="ou41-card primary"><small>PROJECTION GAP</small><strong>{escape(gap_value)}</strong><span>{escape(gap_note)}</span></div>
      <div class="ou41-card ready"><small>PROBABILITY SIGNAL</small><strong>{escape(probability)} {escape(selection)}</strong><span>Certified selection probability at this threshold.</span></div>
      <div class="ou41-card"><small>EVIDENCE READY</small><strong>{ready} / 6</strong><span>Deep evidence engines currently reporting a ready state.</span></div>
    </div>'''


def _driver_signal(engine: Mapping[str, Any]) -> tuple[str, str]:
    raw = _clean(
        engine.get("direction")
        or engine.get("lean")
        or engine.get("impact_direction")
        or engine.get("signal")
        or engine.get("model_lean")
    ).upper()
    if "OVER" in raw:
        return "↑ OVER", "over"
    if "UNDER" in raw:
        return "↓ UNDER", "under"
    if raw in {"NEUTRAL", "EVEN", "FLAT", "MIXED", "NONE"}:
        return "→ NEUTRAL", "neutral"
    return "→ CONTEXT", "context"


def _drivers_html(result: Mapping[str, Any]) -> str:
    factors = [
        ("Explosive Plays", result.get("explosive_engine") or {}),
        ("Red Zone", result.get("red_zone_engine") or {}),
        ("Third Down", result.get("third_down_engine") or {}),
        ("Turnover Volatility", result.get("turnover_engine") or {}),
        ("Game-Day Environment", result.get("environment_engine") or {}),
        ("Historical Matchup", result.get("history_engine") or {}),
    ]
    cards: list[str] = []
    for title, engine in factors:
        status = _clean(engine.get("status") or ("READY" if engine.get("ready") else "CHECK")).upper() or "CHECK"
        css = "ready" if status in {"READY", "GREEN", "PASS", "OK"} else "gated" if status in {"GATED", "FAIL", "BLOCKED"} else ""
        metrics = frozen_page.frozen_page._scalar_metrics(engine)
        detail = " • ".join(f"{name}: {value}" for name, value in metrics[:2]) or _clean(engine.get("reason")) or "Certified engine state preserved."
        signal, signal_css = _driver_signal(engine)
        cards.append(f'<div class="ou41-card {css}"><small>{escape(status)}</small><b>{escape(title)}</b><div class="ou41-signal {signal_css}">{escape(signal)}</div><span>{escape(detail)}</span></div>')
    return '<div class="ou41-drivers">' + "".join(cards) + "</div>"


def _team_html(game: Mapping[str, Any], away: Mapping[str, Any], home: Mapping[str, Any]) -> str:
    display = _display_game(game)
    away_name = _clean(display.get("away_team")) or "Away"
    home_name = _clean(display.get("home_team")) or "Home"
    rows = [
        ("Record", _record(away), _record(home)),
        ("Points / game", _metric(away, "ppg", "points_per_game"), _metric(home, "ppg", "points_per_game")),
        ("Allowed / game", _metric(away, "points_allowed_pg"), _metric(home, "points_allowed_pg")),
        ("Point diff / game", _metric(away, "point_diff_pg"), _metric(home, "point_diff_pg")),
        ("Recent form", _clean(away.get("recent_form")) or "—", _clean(home.get("recent_form")) or "—"),
    ]
    body = "".join(f'<div class="ou41-row"><strong>{escape(a)}</strong><span>{escape(label)}</span><strong>{escape(h)}</strong></div>' for label, a, h in rows)
    return f'<div class="ou41-team"><div class="ou41-teamhead"><b>{escape(away_name)}</b><span>TEAM MATCHUP</span><b>{escape(home_name)}</b></div>{body}</div>'


def _market_html(game: Mapping[str, Any], live_line: float | None, line: float, market_diag: Mapping[str, Any], attach_diag: Mapping[str, Any]) -> str:
    sportsbook = _clean(game.get("market_sportsbook")) or "Verified market"
    live = f"{float(live_line):.1f}" if live_line is not None else "Unavailable"
    status = _clean(market_diag.get("status")) or "CHECK"
    attached = int(attach_diag.get("market_lines_attached") or 0)
    return f'''<div class="ou41-market">
      <div><small>CURRENT TOTAL</small><b>{escape(live)}</b><span>{escape(sportsbook)}</span></div>
      <div><small>YOUR LINE</small><b>{float(line):.1f}</b><span>Slider threshold</span></div>
      <div><small>MARKET STATUS</small><b>{escape(status)}</b><span>{attached} verified total(s)</span></div>
      <div><small>MODEL INFLUENCE</small><b>0.0%</b><span>Comparison only</span></div>
    </div><div class="ou41-rule">Sportsbook pricing stays separate from projection math. The model projection is not fitted to the book.</div>'''


def render_over_under_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    trace = profiler.PerfTrace()
    token = profiler.set_active_trace(trace)
    started = perf_counter()
    try:
        st.markdown(frozen_page._CSS + _CSS, unsafe_allow_html=True)
        selected = st.date_input("📅 CFB Over/Under slate date", value=datetime.now(_EASTERN).date(), key="cfb_ou_v41_date")
        day = selected.isoformat()
        games, schedule_diag = schedule_v6.load_with_diagnostics(day)
        if not games:
            st.warning("No verified College Football games were returned for this date.")
            return
        odds_payload, market_diag = market_adapter.load_odds_for_date(day, "FanDuel")
        games, attach_diag = market_adapter.attach_market_lines(games, odds_payload)
        index = st.selectbox(
            "🏟️ Over/Under matchup",
            options=list(range(len(games))),
            format_func=lambda i: f"{games[int(i)].get('away_team')} @ {games[int(i)].get('home_team')} • {_kickoff_phoenix(games[int(i)])}" + (f" • O/U {_market_line(games[int(i)]):.1f}" if _market_line(games[int(i)]) is not None else " • O/U unavailable"),
            key=f"cfb_ou_v41_matchup_{day}",
        )
        selected_game = dict(games[int(index)])
        game_identity = _clean(selected_game.get("identity_key") or selected_game.get("game_id") or index)
        live_line = _market_line(selected_game)
        default_line = _clamp_line(live_line if live_line is not None else 50.5)
        line_key = f"cfb_ou_v41_line_{day}_{game_identity}"
        if line_key not in st.session_state:
            st.session_state[line_key] = default_line

        hero_slot = st.empty()
        decision_slot = st.empty()
        _section("INTERACTIVE THRESHOLD", "LINE LAB", "Drag left or right to test any half-point threshold without changing the frozen projection.")
        st.markdown(_slider_marker_html(float(st.session_state[line_key]), live_line), unsafe_allow_html=True)
        minus_col, slider_col, plus_col = st.columns([1.15, 7.7, 1.15])
        with minus_col:
            st.button("−0.5", key=f"{line_key}_minus", on_click=_nudge_line, args=(line_key, -0.5), use_container_width=True)
        with slider_col:
            line = st.slider(
                "🎚️ Line Lab total",
                min_value=20.0,
                max_value=100.0,
                step=0.5,
                key=line_key,
            )
        with plus_col:
            st.button("+0.5", key=f"{line_key}_plus", on_click=_nudge_line, args=(line_key, 0.5), use_container_width=True)
        lab_slot = st.empty()

        try:
            result = runtime_slate.analyze_game(selected_game, day, float(line))
        except Exception as exc:
            st.error(f"Current runtime analysis failed visibly: {type(exc).__name__}: {exc}")
            return
        game = dict(result.get("game") or selected_game)
        away = dict(result.get("away") or {})
        home = dict(result.get("home") or {})
        state = _decision_state(result, float(line))
        hero_slot.markdown(_compact_matchup_html(game, away, home, live_line), unsafe_allow_html=True)
        decision_slot.markdown(_decision_html(state), unsafe_allow_html=True)
        lab_slot.markdown(_line_lab_html(state, live_line), unsafe_allow_html=True)

        _section("PLAIN-ENGLISH READ", "WHY THE MODEL LIKES IT", "Three fast signals explain the current certified decision.")
        st.markdown(_why_html(result, state), unsafe_allow_html=True)
        _section("EVIDENCE DRIVERS", "WHAT MOVES THE TOTAL", "Directional labels appear only when the certified engine explicitly supplies one; otherwise the card stays context-only.")
        st.markdown(_drivers_html(result), unsafe_allow_html=True)
        _section("SIDE-BY-SIDE", "TEAM MATCHUP", "Verified runtime snapshot only; unavailable fields stay blank instead of being guessed.")
        st.markdown(_team_html(game, away, home), unsafe_allow_html=True)
        _section("PRICE CONTEXT", "MARKET INTELLIGENCE", "Market information stays separate from the frozen projection.")
        st.markdown(_market_html(selected_game, live_line, float(line), market_diag, attach_diag), unsafe_allow_html=True)

        identity = frozen_page.frozen_page._identity_state(game, away, home)
        with st.expander("🧠 ADVANCED ANALYTICS", expanded=False):
            for step, title, key in ((5, "Explosive Plays", "explosive_engine"), (6, "Red Zone", "red_zone_engine"), (7, "Third Down", "third_down_engine"), (8, "Turnover Volatility", "turnover_engine"), (9, "Game-Day Environment", "environment_engine"), (10, "Historical Matchup", "history_engine")):
                state_row = frozen_page.frozen_page._step_evidence_state(step, title, result.get(key) or {}, identity)
                metrics = " • ".join(f"{name}: {value}" for name, value in (state_row.get("metrics") or [])[:3])
                st.markdown(f"**{title} — {_clean(state_row.get('display_status'))}**  \\n{metrics or _clean(state_row.get('display_reason'))}")
            st.caption("Full-slate scan remains available without changing the single-game model.")
            if st.checkbox("Open full-slate scan workspace", key=f"cfb_ou_v41_scan_open_{day}"):
                editor = st.data_editor(_line_board(games, game_identity, float(line)), use_container_width=True, hide_index=True, key=f"cfb_ou_v41_board_{day}")
                try:
                    records = editor.to_dict("records")
                except Exception:
                    records = list(editor) if isinstance(editor, list) else []
                selected_lines = {}
                for row in records:
                    if bool(row.get("Use")) and _clean(row.get("Identity")) and _float(row.get("Analysis Line")) is not None:
                        selected_lines[_clean(row.get("Identity"))] = float(row.get("Analysis Line"))
                if st.button(f"Run O/U scan for {len(selected_lines)} selected game(s)", key=f"cfb_ou_v41_scan_{day}", type="primary", disabled=not bool(selected_lines)):
                    rows, scan_diag = runtime_slate.scan_slate(games, day, selected_lines)
                    st.session_state[f"cfb_ou_v41_top5_{day}"] = final_model.rank_slate(rows, limit=5)
                    st.session_state[f"cfb_ou_v41_scan_diag_{day}"] = scan_diag
                for rank, row in enumerate(st.session_state.get(f"cfb_ou_v41_top5_{day}") or [], start=1):
                    g = row.get("game") or {}
                    f = row.get("final") or {}
                    r = row.get("raw") or {}
                    st.markdown(f"**#{rank} {g.get('away_team')} @ {g.get('home_team')} — {f.get('selection') or r.get('model_lean') or 'PASS'}** • projected {_num(r.get('projected_total'),1)} • line {_num(row.get('analysis_line'),1)}")

        with st.expander("📚 SOURCE & DATA QUALITY", expanded=False):
            team_diag = result.get("team_diag") or {}
            st.markdown(f"Schedule: **{_clean(schedule_diag.get('status')) or 'CHECK'}** • ESPN-enriched matchups: **{int(schedule_diag.get('espn_matches') or 0)}**  \\nMarket: **{_clean(market_diag.get('status')) or 'CHECK'}** • verified totals attached: **{int(attach_diag.get('market_lines_attached') or 0)}**  \\nRuntime team data: **{_clean(team_diag.get('runtime_status')) or 'CHECK'}** • issues: **{len(team_diag.get('runtime_issues') or [])}**")
            st.markdown(_market_caption(selected_game, market_diag), unsafe_allow_html=True)

        with st.expander("🧪 MODEL TRANSPARENCY", expanded=False):
            st.markdown("Sportsbook projection influence: **0.0%**. The Line Lab changes the threshold only; frozen projection/probability ownership is unchanged.")
            st.markdown(_presentation._model_step(11, "CURRENT FORM + SCHEDULE STRENGTH", result.get("form_strength_engine") or {}), unsafe_allow_html=True)
            st.markdown(_presentation._cert_step(result), unsafe_allow_html=True)
            st.markdown(_presentation._final(result), unsafe_allow_html=True)

        with st.expander("🛠 DIAGNOSTICS", expanded=False):
            previous = st.session_state.get("cfb_ou_perf_v1_last") or {}
            st.markdown(f'<div class="ou41-diag"><b>Presentation:</b> {escape(MODEL_VERSION)}<br><b>Runtime slate:</b> {escape(_clean(ACTIVE_RUNTIME_SLATE))}<br><b>Previous server render:</b> {escape(_num(previous.get("total_ms"),1))} ms<br><b>Projection mutation:</b> OFF • <b>Sportsbook influence:</b> 0.0%</div>', unsafe_allow_html=True)
    finally:
        trace.add("page.total_server_render", perf_counter() - started)
        profiler.reset_active_trace(token)
        try:
            st.session_state["cfb_ou_perf_v1_last"] = {
                "version": profiler.MODEL_VERSION,
                "active_page": MODEL_VERSION,
                "active_runtime_slate": ACTIVE_RUNTIME_SLATE,
                "active_market_adapter": ACTIVE_MARKET_ADAPTER,
                "active_prewarm": ACTIVE_ANALYSIS_PREWARM,
                "active_logo_resolver": ACTIVE_LOGO_RESOLVER,
                "total_ms": trace.total_ms(),
                "stages": trace.aggregate(),
                "projection_weight": 0.0,
                "may_modify_projection": False,
            }
        except Exception:
            pass


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"Premium O/U Page V41 received unsupported market: {market}")
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_ANALYSIS_PREWARM", "ACTIVE_LOGO_RESOLVER", "ACTIVE_MARKET_ADAPTER",
    "ACTIVE_MARKET_INTELLIGENCE", "ACTIVE_PERFORMANCE_PROFILER", "ACTIVE_RUNTIME_SLATE",
    "ACTIVE_SCHEDULE", "FROZEN_PAGE", "FROZEN_PRESENTATION", "FROZEN_RUNTIME_SLATE", "MARKET",
    "MAY_MODIFY_PROJECTION", "MODEL_VERSION", "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_decision_state", "_driver_signal", "_nudge_line", "render_cfb_hub", "render_over_under_hub",
]
