"""CFB Over/Under Clean Page V40 — Premium Dashboard V2.

Presentation-only additive successor over frozen Clean Page V39. Schedule, market,
runtime analysis, team evidence, frozen projection math, selection probabilities,
full-slate ranking, and sportsbook influence stay owned by the certified stack.
"""
from __future__ import annotations

from html import escape
from time import perf_counter
from typing import Any, Mapping

import streamlit as st

import cfb_over_under_clean_page_v39 as frozen_page

MODEL_VERSION = "CFB O/U CLEAN PAGE V40 • PREMIUM DASHBOARD V2"
MARKET = frozen_page.MARKET
FROZEN_PRESENTATION = "cfb_over_under_clean_page_v39"
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
_hero_html = frozen_page._hero_html
_EASTERN = frozen_page._EASTERN
_v38 = frozen_page.frozen_page
_presentation = _v38._presentation

_CSS = r"""
<style>
.ou40-section{margin:18px 0 8px}.ou40-kicker{color:#81dcff;font-size:.30rem;font-weight:950;letter-spacing:.11em;text-transform:uppercase}.ou40-heading{color:#f4f8fb;font-size:.82rem;font-weight:950;margin-top:2px}.ou40-sub{color:#7f94a5;font-size:.34rem;line-height:1.45;margin-top:2px}
.ou40-decision{margin:10px 0 12px;border:1px solid rgba(127,99,255,.35);border-radius:20px;background:linear-gradient(145deg,rgba(42,31,96,.93),rgba(7,24,35,.97));padding:14px}.ou40-grid{display:grid;grid-template-columns:1.35fr repeat(4,minmax(0,1fr));gap:7px}.ou40-pick,.ou40-stat{border:1px solid rgba(125,151,176,.17);border-radius:14px;background:#091925;padding:11px}.ou40-pick{border-color:rgba(154,121,255,.38);background:linear-gradient(145deg,rgba(77,50,154,.34),rgba(8,20,32,.82))}.ou40-label{font-size:.26rem;color:#ad9dff;font-weight:950;letter-spacing:.09em}.ou40-pick strong{display:block;color:#fff;font-size:1.42rem;font-weight:950;margin-top:5px}.ou40-pick span,.ou40-stat span{display:block;color:#879aaa;font-size:.29rem;margin-top:4px}.ou40-stat small{display:block;color:#71889a;font-size:.24rem;font-weight:950}.ou40-stat b{display:block;color:#f1f7fa;font-size:.78rem;margin-top:5px}
.ou40-lab{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:7px}.ou40-lab div,.ou40-market div{border:1px solid rgba(111,151,183,.16);border-radius:12px;background:#091722;padding:8px}.ou40-lab small,.ou40-market small{display:block;color:#70879a;font-size:.24rem;font-weight:950}.ou40-lab b,.ou40-market b{display:block;color:#eef5f9;font-size:.57rem;margin-top:3px}.ou40-note{margin-top:6px;border-left:3px solid #69bfff;border-radius:0 9px 9px 0;background:rgba(27,77,109,.16);padding:7px 9px;color:#96aabb;font-size:.31rem;line-height:1.45}
.ou40-reasons,.ou40-drivers{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px}.ou40-card{border:1px solid rgba(124,150,175,.16);border-radius:13px;background:#091722;padding:10px}.ou40-card.primary{border-color:rgba(126,99,255,.34);background:rgba(63,45,127,.18)}.ou40-card.ready{border-color:rgba(44,194,124,.27);background:rgba(16,72,51,.18)}.ou40-card.gated{border-color:rgba(255,108,115,.26);background:rgba(85,30,35,.18)}.ou40-card small{display:block;color:#70879a;font-size:.23rem;font-weight:950}.ou40-card b{display:block;color:#eef5f8;font-size:.47rem;margin-top:3px}.ou40-card span{display:block;color:#899cab;font-size:.30rem;line-height:1.42;margin-top:4px}
.ou40-team{border:1px solid rgba(120,150,176,.16);border-radius:15px;background:#081621;overflow:hidden}.ou40-teamhead,.ou40-row{display:grid;grid-template-columns:minmax(0,1fr) 1.1fr minmax(0,1fr);align-items:center;padding:8px 9px}.ou40-teamhead{background:rgba(21,47,66,.55)}.ou40-row{border-top:1px solid rgba(120,150,176,.10)}.ou40-teamhead b,.ou40-row strong{color:#eef5f9;font-size:.46rem}.ou40-teamhead b:last-child,.ou40-row strong:last-child{text-align:right}.ou40-teamhead span,.ou40-row span{text-align:center;color:#71889a;font-size:.27rem;font-weight:900}
.ou40-market{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px}.ou40-rule{margin-top:7px;border:1px solid rgba(80,194,255,.18);border-radius:10px;background:rgba(21,70,99,.15);padding:8px;color:#95b5c8;font-size:.31rem;line-height:1.45}.ou40-diag{color:#8da0ae;font-size:.32rem;line-height:1.55}.ou40-diag b{color:#dce7ee}
@media(max-width:820px){.ou40-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.ou40-pick{grid-column:1/-1}.ou40-reasons,.ou40-drivers,.ou40-market{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:520px){.ou40-lab,.ou40-reasons,.ou40-drivers,.ou40-market{grid-template-columns:1fr}.ou40-teamhead,.ou40-row{grid-template-columns:.8fr 1fr .8fr}}
</style>
"""


def _float(value: Any) -> float | None:
    try:
        return None if value in (None, "") else float(value)
    except Exception:
        return None


def _pct(value: Any) -> str:
    number = _float(value)
    if number is None:
        return "—"
    if abs(number) <= 1.0:
        number *= 100.0
    return f"{number:.1f}%"


def _decision_state(result: Mapping[str, Any], line: float) -> dict[str, Any]:
    """Read certified result fields for display; do not recompute model probability."""
    raw = dict(result.get("raw") or {})
    final = dict(result.get("final") or {})
    selection = _clean(final.get("selection") or final.get("pick") or raw.get("model_lean")).upper() or "PASS"
    projected = _float(raw.get("projected_total"))
    under = _float(raw.get("under_probability"))
    over = _float(raw.get("over_probability"))
    probability = _float(final.get("selection_probability"))
    if probability is None:
        probability = under if selection == "UNDER" else over if selection == "OVER" else None
    edge = None if projected is None else round(abs(float(line) - projected), 1)
    return {
        "selection": selection,
        "projected_total": projected,
        "analysis_line": float(line),
        "edge_points": edge,
        "selection_probability": probability,
        "under_probability": under,
        "over_probability": over,
    }


def _section(kicker: str, title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="ou40-section"><div class="ou40-kicker">{escape(kicker)}</div><div class="ou40-heading">{escape(title)}</div><div class="ou40-sub">{escape(subtitle)}</div></div>',
        unsafe_allow_html=True,
    )


def _decision_html(state: Mapping[str, Any]) -> str:
    selection = _clean(state.get("selection")) or "PASS"
    line = _num(state.get("analysis_line"), 1)
    projected = _num(state.get("projected_total"), 1)
    edge = _num(state.get("edge_points"), 1)
    probability = _pct(state.get("selection_probability"))
    return f'''<div class="ou40-decision"><div class="ou40-grid">
      <div class="ou40-pick"><div class="ou40-label">MODEL PICK</div><strong>{escape(selection)} {escape(line)}</strong><span>Certified frozen-model decision</span></div>
      <div class="ou40-stat"><small>PROBABILITY</small><b>{escape(probability)}</b><span>Selection probability</span></div>
      <div class="ou40-stat"><small>PROJECTED TOTAL</small><b>{escape(projected)}</b><span>Frozen projection</span></div>
      <div class="ou40-stat"><small>ANALYSIS LINE</small><b>{escape(line)}</b><span>Threshold only</span></div>
      <div class="ou40-stat"><small>MODEL EDGE</small><b>{escape(edge)} pts</b><span>Projection-to-line gap</span></div>
    </div></div>'''


def _line_lab_html(state: Mapping[str, Any], live_line: float | None) -> str:
    live = f"{float(live_line):.1f}" if live_line is not None else "Unavailable"
    return f'''<div class="ou40-lab">
      <div><small>UNDER PROBABILITY</small><b>{escape(_pct(state.get("under_probability")))}</b></div>
      <div><small>OVER PROBABILITY</small><b>{escape(_pct(state.get("over_probability")))}</b></div>
      <div><small>PROJECTED TOTAL</small><b>{escape(_num(state.get("projected_total"),1))}</b></div>
      <div><small>VERIFIED MARKET</small><b>{escape(live)}</b></div>
    </div><div class="ou40-note">Move the line in 0.5-point increments. The existing certified runtime evaluates that threshold; sportsbook data remains comparison-only with 0.0% model influence.</div>'''


def _engine_ready(engine: Mapping[str, Any]) -> bool:
    status = _clean(engine.get("status") or ("READY" if engine.get("ready") else "CHECK")).upper()
    return status in {"READY", "GREEN", "PASS", "OK"}


def _why_html(result: Mapping[str, Any], state: Mapping[str, Any]) -> str:
    projected = _float(state.get("projected_total"))
    line = _float(state.get("analysis_line"))
    edge = _float(state.get("edge_points")) or 0.0
    selection = _clean(state.get("selection")) or "PASS"
    if projected is None or line is None:
        gap = "Projection gap unavailable; the certified decision is preserved without inventing a value."
    elif selection == "UNDER":
        gap = f"The frozen model projects {projected:.1f}, {edge:.1f} points below the {line:.1f} line."
    elif selection == "OVER":
        gap = f"The frozen model projects {projected:.1f}, {edge:.1f} points above the {line:.1f} line."
    else:
        gap = f"The frozen model projects {projected:.1f} against {line:.1f} and does not clear the decision threshold."
    engines = [result.get(k) or {} for k in ("explosive_engine","red_zone_engine","third_down_engine","turnover_engine","environment_engine","history_engine")]
    ready = sum(1 for engine in engines if _engine_ready(engine))
    return f'''<div class="ou40-reasons">
      <div class="ou40-card primary"><b>Projection gap</b><span>{escape(gap)}</span></div>
      <div class="ou40-card ready"><b>Probability signal</b><span>Certified selection probability: {escape(_pct(state.get("selection_probability")))}.</span></div>
      <div class="ou40-card"><b>Evidence coverage</b><span>{ready} of 6 deep evidence engines are READY; limited engines stay visible instead of being treated as evidence.</span></div>
    </div>'''


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
        css = "ready" if status in {"READY","GREEN","PASS","OK"} else "gated" if status in {"GATED","FAIL","BLOCKED"} else ""
        metrics = frozen_page._scalar_metrics(engine)
        detail = " • ".join(f"{name}: {value}" for name, value in metrics[:2]) or _clean(engine.get("reason")) or "Certified engine state preserved."
        cards.append(f'<div class="ou40-card {css}"><small>{escape(status)}</small><b>{escape(title)}</b><span>{escape(detail)}</span></div>')
    return '<div class="ou40-drivers">' + "".join(cards) + "</div>"


def _metric(profile: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        number = _float(profile.get(key))
        if number is not None:
            return f"{number:.1f}"
    return "—"


def _record(profile: Mapping[str, Any]) -> str:
    value = profile.get("record")
    if isinstance(value, Mapping):
        return f"{int(value.get('wins') or 0)}-{int(value.get('losses') or 0)}"
    return _clean(profile.get("record_text") or value) or "—"


def _team_html(game: Mapping[str, Any], away: Mapping[str, Any], home: Mapping[str, Any]) -> str:
    display = _display_game(game)
    away_name = _clean(display.get("away_team")) or "Away"
    home_name = _clean(display.get("home_team")) or "Home"
    rows = [
        ("Record", _record(away), _record(home)),
        ("Points / game", _metric(away,"ppg","points_per_game"), _metric(home,"ppg","points_per_game")),
        ("Allowed / game", _metric(away,"points_allowed_pg"), _metric(home,"points_allowed_pg")),
        ("Point diff / game", _metric(away,"point_diff_pg"), _metric(home,"point_diff_pg")),
        ("Recent form", _clean(away.get("recent_form")) or "—", _clean(home.get("recent_form")) or "—"),
    ]
    body = "".join(f'<div class="ou40-row"><strong>{escape(a)}</strong><span>{escape(label)}</span><strong>{escape(h)}</strong></div>' for label,a,h in rows)
    return f'<div class="ou40-team"><div class="ou40-teamhead"><b>{escape(away_name)}</b><span>TEAM MATCHUP</span><b>{escape(home_name)}</b></div>{body}</div>'


def _market_html(game: Mapping[str, Any], live_line: float | None, line: float, market_diag: Mapping[str, Any], attach_diag: Mapping[str, Any]) -> str:
    sportsbook = _clean(game.get("market_sportsbook")) or "Verified market"
    live = f"{float(live_line):.1f}" if live_line is not None else "Unavailable"
    status = _clean(market_diag.get("status")) or "CHECK"
    attached = int(attach_diag.get("market_lines_attached") or 0)
    return f'''<div class="ou40-market">
      <div><small>CURRENT TOTAL</small><b>{escape(live)}</b><span>{escape(sportsbook)}</span></div>
      <div><small>ANALYSIS LINE</small><b>{float(line):.1f}</b><span>Editable threshold</span></div>
      <div><small>MARKET STATUS</small><b>{escape(status)}</b><span>{attached} verified total(s)</span></div>
      <div><small>MODEL INFLUENCE</small><b>0.0%</b><span>Comparison only</span></div>
    </div><div class="ou40-rule">Sportsbook pricing is deliberately separated from projection math. The model projection is not fitted to the book.</div>'''


def render_over_under_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    trace = profiler.PerfTrace()
    token = profiler.set_active_trace(trace)
    started = perf_counter()
    try:
        st.markdown(_CSS, unsafe_allow_html=True)
        selected = st.date_input("📅 CFB Over/Under slate date", value=frozen_page.frozen_page.datetime.now(_EASTERN).date(), key="cfb_ou_v40_date")
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
            key=f"cfb_ou_v40_matchup_{day}",
        )
        selected_game = dict(games[int(index)])
        game_identity = _clean(selected_game.get("identity_key") or selected_game.get("game_id") or index)
        live_line = _market_line(selected_game)
        default_line = float(live_line) if live_line is not None else 50.5

        hero_slot = st.empty()
        decision_slot = st.empty()
        _section("INTERACTIVE THRESHOLD", "LINE LAB", "Move the total and the existing certified model evaluates that threshold on rerun.")
        line = st.number_input("🎚️ Line Lab total", min_value=20.0, max_value=100.0, value=default_line, step=0.5, key=f"cfb_ou_v40_line_{day}_{game_identity}")
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
        hero_slot.markdown(_hero_html(game, away, home, live_line, attach_diag), unsafe_allow_html=True)
        decision_slot.markdown(_decision_html(state), unsafe_allow_html=True)
        lab_slot.markdown(_line_lab_html(state, live_line), unsafe_allow_html=True)

        _section("PLAIN-ENGLISH READ", "WHY THE MODEL LIKES IT", "The fastest explanation of the current certified decision.")
        st.markdown(_why_html(result, state), unsafe_allow_html=True)
        _section("EVIDENCE DRIVERS", "WHAT MOVES THE TOTAL", "Six certified engine states at a glance; deep evidence remains below.")
        st.markdown(_drivers_html(result), unsafe_allow_html=True)
        _section("SIDE-BY-SIDE", "TEAM MATCHUP", "Verified runtime snapshot only; unavailable fields stay blank instead of being guessed.")
        st.markdown(_team_html(game, away, home), unsafe_allow_html=True)
        _section("PRICE CONTEXT", "MARKET INTELLIGENCE", "Market information stays separate from the frozen projection.")
        st.markdown(_market_html(selected_game, live_line, float(line), market_diag, attach_diag), unsafe_allow_html=True)

        identity = frozen_page._identity_state(game, away, home)
        with st.expander("🧠 ADVANCED ANALYTICS", expanded=False):
            for step,title,key in ((5,"Explosive Plays","explosive_engine"),(6,"Red Zone","red_zone_engine"),(7,"Third Down","third_down_engine"),(8,"Turnover Volatility","turnover_engine"),(9,"Game-Day Environment","environment_engine"),(10,"Historical Matchup","history_engine")):
                state_row = frozen_page._step_evidence_state(step, title, result.get(key) or {}, identity)
                metrics = " • ".join(f"{name}: {value}" for name,value in (state_row.get("metrics") or [])[:3])
                st.markdown(f"**{title} — {_clean(state_row.get('display_status'))}**  \n{metrics or _clean(state_row.get('display_reason'))}")
            st.caption("Full-slate scan remains available without changing the single-game model.")
            if st.checkbox("Open full-slate scan workspace", key=f"cfb_ou_v40_scan_open_{day}"):
                editor = st.data_editor(_line_board(games, game_identity, float(line)), use_container_width=True, hide_index=True, key=f"cfb_ou_v40_board_{day}")
                try:
                    records = editor.to_dict("records")
                except Exception:
                    records = list(editor) if isinstance(editor, list) else []
                selected_lines = {}
                for row in records:
                    if bool(row.get("Use")) and _clean(row.get("Identity")) and _float(row.get("Analysis Line")) is not None:
                        selected_lines[_clean(row.get("Identity"))] = float(row.get("Analysis Line"))
                if st.button(f"Run O/U scan for {len(selected_lines)} selected game(s)", key=f"cfb_ou_v40_scan_{day}", type="primary", disabled=not bool(selected_lines)):
                    rows, scan_diag = runtime_slate.scan_slate(games, day, selected_lines)
                    st.session_state[f"cfb_ou_v40_top5_{day}"] = final_model.rank_slate(rows, limit=5)
                    st.session_state[f"cfb_ou_v40_scan_diag_{day}"] = scan_diag
                for rank,row in enumerate(st.session_state.get(f"cfb_ou_v40_top5_{day}") or [], start=1):
                    g = row.get("game") or {}; f = row.get("final") or {}; r = row.get("raw") or {}
                    st.markdown(f"**#{rank} {g.get('away_team')} @ {g.get('home_team')} — {f.get('selection') or r.get('model_lean') or 'PASS'}** • projected {_num(r.get('projected_total'),1)} • line {_num(row.get('analysis_line'),1)}")

        with st.expander("📚 SOURCE & DATA QUALITY", expanded=False):
            team_diag = result.get("team_diag") or {}
            st.markdown(f"Schedule: **{_clean(schedule_diag.get('status')) or 'CHECK'}** • ESPN-enriched matchups: **{int(schedule_diag.get('espn_matches') or 0)}**  \nMarket: **{_clean(market_diag.get('status')) or 'CHECK'}** • verified totals attached: **{int(attach_diag.get('market_lines_attached') or 0)}**  \nRuntime team data: **{_clean(team_diag.get('runtime_status')) or 'CHECK'}** • issues: **{len(team_diag.get('runtime_issues') or [])}**")
            st.markdown(_market_caption(selected_game, market_diag), unsafe_allow_html=True)

        with st.expander("🧪 MODEL TRANSPARENCY", expanded=False):
            st.markdown("Sportsbook projection influence: **0.0%**. The Line Lab changes the threshold only; frozen projection/probability ownership is unchanged.")
            st.markdown(_presentation._model_step(11, "CURRENT FORM + SCHEDULE STRENGTH", result.get("form_strength_engine") or {}), unsafe_allow_html=True)
            st.markdown(_presentation._cert_step(result), unsafe_allow_html=True)
            st.markdown(_presentation._final(result), unsafe_allow_html=True)

        with st.expander("🛠 DIAGNOSTICS", expanded=False):
            previous = st.session_state.get("cfb_ou_perf_v1_last") or {}
            st.markdown(f'<div class="ou40-diag"><b>Presentation:</b> {escape(MODEL_VERSION)}<br><b>Runtime slate:</b> {escape(_clean(ACTIVE_RUNTIME_SLATE))}<br><b>Previous server render:</b> {escape(_num(previous.get("total_ms"),1))} ms<br><b>Projection mutation:</b> OFF • <b>Sportsbook influence:</b> 0.0%</div>', unsafe_allow_html=True)
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
        raise ValueError(f"Premium O/U Page V40 received unsupported market: {market}")
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_ANALYSIS_PREWARM","ACTIVE_LOGO_RESOLVER","ACTIVE_MARKET_ADAPTER",
    "ACTIVE_MARKET_INTELLIGENCE","ACTIVE_PERFORMANCE_PROFILER","ACTIVE_RUNTIME_SLATE",
    "ACTIVE_SCHEDULE","FROZEN_PAGE","FROZEN_PRESENTATION","FROZEN_RUNTIME_SLATE","MARKET",
    "MAY_MODIFY_PROJECTION","MODEL_VERSION","SPORTSBOOK_PROJECTION_INFLUENCE",
    "_decision_state","render_cfb_hub","render_over_under_hub",
]
