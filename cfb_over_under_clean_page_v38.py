"""CFB Over/Under Clean Page V38 — Monster compact dashboard.

Presentation-only additive page over certified Clean Page V37. The V37 exact
ESPN team-ID Step-1 logo wiring and the inherited V35 schedule, market adapter,
prewarm/cache path, runtime analysis, final model, thresholds, and full-slate
ranking behavior are reused unchanged.

V38 changes only presentation:
- Phoenix, Arizona kickoff-time display,
- compact matchup hero and Quick Read,
- compact Steps 5-10 summary cards,
- deep model evidence preserved inside collapsed expanders,
- full-slate scan preserved inside a collapsed workspace.

Sportsbook data remains context/threshold only and has exactly 0.0% projection
influence. No frozen projection or probability math is implemented here.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from time import perf_counter
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import streamlit as st

import cfb_over_under_clean_page_v37 as frozen_page
import cfb_over_under_logo_resolver_v3 as logo_v3
import cfb_over_under_performance_profiler_v1 as profiler
import cfb_over_under_runtime_team_data_v1 as runtime_display

MODEL_VERSION = "CFB O/U CLEAN PAGE V38 • MONSTER COMPACT DASHBOARD"
MARKET = "Over/Under"
FROZEN_PAGE = "cfb_over_under_clean_page_v37"
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

_PHOENIX = ZoneInfo("America/Phoenix")
_EASTERN = ZoneInfo("America/New_York")

# Pull the effective dependencies out of certified V37. V37 already owns the
# corrected exact ESPN-ID Step-1 renderer; these runtime objects preserve the
# market freshness, prewarm/cache, identity and frozen V14 calculation paths.
_BASE_GLOBALS = frozen_page._RENDER_V37.__globals__
schedule_v6 = _BASE_GLOBALS["schedule_v6"]
market_adapter = _BASE_GLOBALS["market_adapter"]
_presentation = _BASE_GLOBALS["frozen_page"]
runtime_slate = _presentation.runtime_slate
final_model = _presentation.final_model
_line_board = _BASE_GLOBALS["_line_board"]
_market_caption = _BASE_GLOBALS["_market_caption"]

_CSS = r"""
<style>
.ou38-shell{box-sizing:border-box;margin:8px 0 12px;border:1px solid rgba(92,126,255,.28);border-radius:20px;background:radial-gradient(circle at 92% 0%,rgba(124,58,237,.16),transparent 24rem),linear-gradient(145deg,#07111e,#0a1525 58%,#0d1120);padding:14px;overflow:hidden}
.ou38-kicker{color:#a594ff;font-size:.58rem;font-weight:950;letter-spacing:.10em;text-transform:uppercase}.ou38-title{color:#f8fbff;font-size:1.45rem;font-weight:950;letter-spacing:-.03em;margin-top:3px}.ou38-sub{color:#8fa2b7;font-size:.64rem;line-height:1.45;margin-top:4px}
.ou38-pills{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}.ou38-pill{border:1px solid rgba(119,140,166,.25);border-radius:999px;background:#0d1b2a;color:#b5c2d1;padding:5px 8px;font-size:.40rem;font-weight:900;white-space:nowrap}.ou38-pill.good{border-color:rgba(60,207,137,.40);background:rgba(21,92,61,.27);color:#94efbd}.ou38-pill.blue{border-color:rgba(62,177,255,.35);background:rgba(20,73,108,.25);color:#8dd6ff}.ou38-pill.purple{border-color:rgba(168,116,255,.40);background:rgba(75,41,127,.26);color:#cbb1ff}.ou38-pill.amber{border-color:rgba(244,191,77,.36);background:rgba(101,72,18,.26);color:#f5d47d}
.ou38-hero{margin-top:10px;border:1px solid rgba(76,153,220,.23);border-radius:17px;background:#081522;overflow:hidden}.ou38-match{display:grid;grid-template-columns:minmax(0,1fr) 58px minmax(0,1fr);gap:8px;align-items:stretch;padding:10px}.ou38-team{display:grid;grid-template-columns:62px minmax(0,1fr);gap:9px;align-items:center;border:1px solid rgba(148,163,184,.12);border-radius:14px;background:linear-gradient(145deg,#0a1724,#0b1420);padding:9px;min-width:0}.ou38-team.home{grid-template-columns:minmax(0,1fr) 62px;text-align:right}.ou38-team.home .ou38-logo{grid-column:2}.ou38-team.home .ou38-team-copy{grid-column:1;grid-row:1}.ou38-logo{width:62px;height:62px;border:1px solid rgba(255,255,255,.10);border-radius:13px;background:#0e1b28;display:flex;align-items:center;justify-content:center;overflow:hidden}.ou38-logo img{width:53px;height:53px;object-fit:contain}.ou38-mono{color:#dce9f3;font-size:.92rem;font-weight:950}.ou38-rank{color:#79d6ff;font-size:.38rem;font-weight:950;text-transform:uppercase}.ou38-name{color:#f5f9fc;font-size:1rem;font-weight:950;line-height:1.1;margin-top:2px}.ou38-meta{color:#8195a8;font-size:.41rem;font-weight:800;line-height:1.42;margin-top:4px}.ou38-at{display:flex;flex-direction:column;align-items:center;justify-content:center;color:#71889c;font-size:.31rem;font-weight:900}.ou38-at b{display:block;color:#edf5fa;font-size:1.04rem}
.ou38-context{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));border-top:1px solid rgba(76,153,220,.11)}.ou38-context div{padding:8px 9px;border-right:1px solid rgba(76,153,220,.08);min-width:0}.ou38-context div:last-child{border-right:0}.ou38-context small{display:block;color:#72889b;font-size:.28rem;font-weight:950;text-transform:uppercase}.ou38-context strong{display:block;color:#dce8f0;font-size:.44rem;margin-top:3px;line-height:1.35}
.ou38-section{margin-top:11px}.ou38-section-title{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:0 1px 7px}.ou38-section-title b{color:#eaf2f7;font-size:.56rem;font-weight:950;letter-spacing:.07em}.ou38-section-title span{color:#798b9d;font-size:.35rem}.ou38-quick{display:grid;grid-template-columns:1.2fr repeat(4,minmax(0,.72fr));gap:6px}.ou38-pick{border:1px solid rgba(164,112,255,.34);border-radius:14px;background:linear-gradient(145deg,rgba(71,42,118,.31),#0a1622);padding:10px}.ou38-pick small{display:block;color:#b9a2ff;font-size:.32rem;font-weight:950;text-transform:uppercase}.ou38-pick strong{display:block;color:#fbfaff;font-size:1.22rem;margin-top:3px}.ou38-pick span{display:block;color:#8f9caf;font-size:.35rem;margin-top:3px}.ou38-q{border:1px solid rgba(137,157,179,.14);border-radius:11px;background:#0a1620;padding:9px;min-width:0}.ou38-q b{display:block;color:#e8f0f5;font-size:.65rem;line-height:1.2}.ou38-q span{display:block;color:#748797;font-size:.28rem;text-transform:uppercase;margin-top:3px;line-height:1.3}
.ou38-factors{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}.ou38-factor{border:1px solid rgba(130,151,172,.16);border-radius:11px;background:#0a151f;padding:8px;min-width:0}.ou38-factor small{display:block;color:#7c91a2;font-size:.27rem;font-weight:950;text-transform:uppercase}.ou38-factor b{display:block;color:#ecf3f7;font-size:.53rem;margin-top:3px}.ou38-factor span{display:block;color:#8699a6;font-size:.30rem;line-height:1.35;margin-top:3px}.ou38-factor.ready{border-color:rgba(60,207,137,.28);background:rgba(17,72,51,.19)}.ou38-factor.ready b{color:#a1efc5}.ou38-factor.limited{border-color:rgba(244,191,77,.28);background:rgba(90,67,17,.18)}.ou38-factor.limited b{color:#f2d685}.ou38-factor.gated{border-color:rgba(255,104,112,.28);background:rgba(90,31,37,.18)}.ou38-factor.gated b{color:#ffb1b6}.ou38-factor.check{border-color:rgba(70,169,236,.23);background:rgba(16,58,86,.17)}.ou38-factor.check b{color:#9cdbff}.ou38-note{margin-top:7px;border-left:3px solid #8d6cff;background:rgba(87,60,139,.12);border-radius:0 9px 9px 0;padding:8px 9px;color:#a8b1c1;font-size:.35rem;line-height:1.5}
@media(max-width:760px){.ou38-shell{padding:11px}.ou38-title{font-size:1.22rem}.ou38-match{grid-template-columns:1fr;padding:8px}.ou38-at{min-height:23px}.ou38-team,.ou38-team.home{grid-template-columns:54px minmax(0,1fr);text-align:left}.ou38-team.home .ou38-logo{grid-column:1}.ou38-team.home .ou38-team-copy{grid-column:2;grid-row:1}.ou38-logo{width:54px;height:54px}.ou38-logo img{width:46px;height:46px}.ou38-context{grid-template-columns:repeat(2,minmax(0,1fr))}.ou38-context div:last-child{grid-column:1/-1}.ou38-quick{grid-template-columns:repeat(2,minmax(0,1fr))}.ou38-pick{grid-column:1/-1}.ou38-factors{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:430px){.ou38-factors{grid-template-columns:1fr}.ou38-name{font-size:.90rem}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any, digits: int = 1, signed: bool = False) -> str:
    try:
        number = float(value)
    except Exception:
        return "—"
    prefix = "+" if signed and number > 0 else ""
    return f"{prefix}{number:.{digits}f}"


def _pct(value: Any) -> str:
    try:
        return f"{100.0 * float(value):.1f}%"
    except Exception:
        return "—"


def _record(value: Any) -> str:
    if isinstance(value, Mapping):
        wins = int(value.get("wins") or 0)
        losses = int(value.get("losses") or 0)
        ties = int(value.get("ties") or 0)
        return f"{wins}-{losses}" + (f"-{ties}" if ties else "")
    return _clean(value) or "—"


def _kickoff_datetime(game: Mapping[str, Any]) -> datetime | None:
    raw = _clean(game.get("kickoff_iso"))
    if raw:
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=_EASTERN)
            return parsed.astimezone(_PHOENIX)
        except Exception:
            pass
    day = _clean(game.get("game_date"))
    text = _clean(game.get("kickoff_et"))
    if day and text:
        cleaned = text.replace(" ET", "").replace(" EST", "").replace(" EDT", "").strip()
        for fmt in ("%I:%M %p", "%H:%M"):
            try:
                parsed = datetime.strptime(f"{day} {cleaned}", f"%Y-%m-%d {fmt}").replace(tzinfo=_EASTERN)
                return parsed.astimezone(_PHOENIX)
            except Exception:
                pass
    return None


def _kickoff_phoenix(game: Mapping[str, Any]) -> str:
    parsed = _kickoff_datetime(game)
    if parsed is None:
        return "TBD Phoenix"
    return parsed.strftime("%I:%M %p").lstrip("0") + " Phoenix"


def _display_game(game: Mapping[str, Any]) -> dict[str, Any]:
    """Presentation-only enrichment copy; frozen analysis receives original data."""
    out = dict(game)
    try:
        snapshot = runtime_display._find_snapshot(out)
        if snapshot:
            runtime_display._merge_game_snapshot(out, snapshot)
            out["ou38_display_snapshot_enriched"] = True
    except Exception:
        pass
    return out


def _resolve_visuals(game: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    try:
        return logo_v3.resolve_visuals(game)
    except Exception:
        return {"away": {}, "home": {}}


def _monogram(name: str) -> str:
    tokens = [token for token in _clean(name).replace("&", " ").split() if token]
    return "".join(token[0].upper() for token in tokens[:2]) or "CFB"


def _logo_html(name: str, visual: Mapping[str, Any]) -> str:
    url = _clean(visual.get("logo"))
    if url:
        return f'<div class="ou38-logo"><img src="{escape(url, quote=True)}" alt="{escape(name)} logo"></div>'
    return f'<div class="ou38-logo"><span class="ou38-mono">{escape(_monogram(name))}</span></div>'


def _rank_text(value: Any) -> str:
    try:
        rank = int(value)
        return f"AP #{rank}" if rank > 0 else "Unranked"
    except Exception:
        return "Unranked"


def _market_line(game: Mapping[str, Any]) -> float | None:
    try:
        return market_adapter.market_line(game)
    except Exception:
        return None


def _selection(result: Mapping[str, Any]) -> tuple[str, Any]:
    raw = result.get("raw") or {}
    final = result.get("final") or {}
    selection = _clean(final.get("selection") or final.get("pick") or raw.get("model_lean")) or "PASS"
    probability = final.get("selection_probability")
    if probability is None:
        if selection.upper() == "UNDER":
            probability = raw.get("under_probability")
        elif selection.upper() == "OVER":
            probability = raw.get("over_probability")
    return selection, probability


def _hero_html(game: Mapping[str, Any], away: Mapping[str, Any], home: Mapping[str, Any], live_line: float | None, attach_diag: Mapping[str, Any]) -> str:
    display = _display_game(game)
    visuals = _resolve_visuals(display)
    away_name = _clean(display.get("away_team")) or "Away"
    home_name = _clean(display.get("home_team")) or "Home"
    venue = _clean(display.get("venue")) or "Venue unavailable"
    broadcast = _clean(display.get("broadcast")) or "Broadcast unavailable"
    day = _clean(display.get("game_date")) or "Date TBD"
    sportsbook = _clean(display.get("market_sportsbook")) or "FanDuel"
    market_text = f"{live_line:.1f}" if live_line is not None else "Unavailable"
    attached = int(attach_diag.get("market_lines_attached") or 0)
    away_record = _record(away.get("record") or display.get("away_record"))
    home_record = _record(home.get("record") or display.get("home_record"))
    return f'''
<div class="ou38-shell">
 <div class="ou38-kicker">CFB OVER / UNDER • MONSTER DASHBOARD</div><div class="ou38-title">{escape(away_name)} @ {escape(home_name)}</div><div class="ou38-sub">Fast first read up top. Certified evidence stays available below without turning the page into a wall of one-color cards.</div>
 <div class="ou38-pills"><span class="ou38-pill good">V37 EXACT LOGOS PRESERVED</span><span class="ou38-pill purple">SPORTSBOOK INFLUENCE 0.0%</span><span class="ou38-pill blue">{escape(_kickoff_phoenix(display))}</span><span class="ou38-pill amber">{escape(sportsbook)} O/U {escape(market_text)}</span></div>
 <div class="ou38-hero"><div class="ou38-match"><div class="ou38-team">{_logo_html(away_name, visuals.get("away") or {})}<div class="ou38-team-copy"><div class="ou38-rank">{escape(_rank_text(display.get("away_rank")))}</div><div class="ou38-name">{escape(away_name)}</div><div class="ou38-meta">Record {escape(away_record)}</div></div></div><div class="ou38-at"><b>@</b>{escape(_kickoff_phoenix(display))}</div><div class="ou38-team home">{_logo_html(home_name, visuals.get("home") or {})}<div class="ou38-team-copy"><div class="ou38-rank">{escape(_rank_text(display.get("home_rank")))}</div><div class="ou38-name">{escape(home_name)}</div><div class="ou38-meta">Record {escape(home_record)}</div></div></div></div>
 <div class="ou38-context"><div><small>Date</small><strong>{escape(day)}</strong></div><div><small>Kickoff</small><strong>{escape(_kickoff_phoenix(display))}</strong></div><div><small>Venue</small><strong>{escape(venue)}</strong></div><div><small>Broadcast</small><strong>{escape(broadcast)}</strong></div><div><small>Live totals attached</small><strong>{attached}</strong></div></div></div>
</div>'''


def _quick_read_html(result: Mapping[str, Any], line: float) -> str:
    raw = result.get("raw") or {}
    selection, probability = _selection(result)
    projected = raw.get("projected_total")
    try:
        edge = float(projected) - float(line)
    except Exception:
        edge = None
    sigma = raw.get("structural_total_sigma")
    edge_text = _num(edge, 1, signed=True) if edge is not None else "—"
    return f'''<div class="ou38-section"><div class="ou38-section-title"><b>⚡ QUICK READ</b><span>Model output first • deep evidence below</span></div><div class="ou38-quick"><div class="ou38-pick"><small>Monster lean</small><strong>{escape(selection)}</strong><span>Certified frozen output • not sportsbook-generated</span></div><div class="ou38-q"><b>{escape(_num(projected,1))}</b><span>Projected total</span></div><div class="ou38-q"><b>{escape(_num(line,1))}</b><span>Analysis line</span></div><div class="ou38-q"><b>{escape(edge_text)}</b><span>Projection minus line</span></div><div class="ou38-q"><b>{escape(_pct(probability))}</b><span>Selection probability</span></div></div><div class="ou38-note">Structural sigma: <b>{escape(_num(sigma,2))}</b> • Market total remains a comparison threshold only. It does not enter the frozen projection formula.</div></div>'''


def _factor_card(step: int, title: str, engine: Mapping[str, Any]) -> str:
    try:
        status = _clean(_presentation._engine_ready(engine)) or "CHECK"
    except Exception:
        status = "CHECK"
    try:
        metrics = list(_presentation._interesting(engine, limit=2))
    except Exception:
        metrics = []
    metric_text = " • ".join(f"{label}: {value}" for label, value in metrics) or "Open deep evidence for details"
    reason = _clean(engine.get("reason")) or "Certified engine output available."
    tone = status.lower() if status.lower() in {"ready", "limited", "gated", "check"} else "check"
    return f'<div class="ou38-factor {escape(tone)}"><small>Step {int(step)} • {escape(status)}</small><b>{escape(title)}</b><span>{escape(metric_text)}<br>{escape(reason[:150])}</span></div>'


def _render_factor_cards(factors: list[tuple[int, str, Mapping[str, Any]]]) -> None:
    cards = "".join(_factor_card(step, title, engine) for step, title, engine in factors)
    st.markdown('<div class="ou38-section"><div class="ou38-section-title"><b>🧠 WHAT MOVES THE TOTAL</b><span>Steps 5–10 compact view</span></div>' f'<div class="ou38-factors">{cards}</div></div>', unsafe_allow_html=True)


def render_over_under_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    trace = profiler.PerfTrace()
    token = profiler.set_active_trace(trace)
    perf_slot = st.empty()
    started = perf_counter()
    try:
        st.caption("🟣 CFB O/U • CLEAN PAGE V38 ACTIVE • MONSTER COMPACT DASHBOARD • V37 EXACT-LOGO CONTRACT PRESERVED • PHOENIX TIME • COMPACT STEPS 5-10 • DEEP EVIDENCE EXPANDERS • 0.0% SPORTSBOOK PROJECTION INFLUENCE")
        st.markdown(_CSS, unsafe_allow_html=True)
        selected = st.date_input("📅 CFB Over/Under slate date", value=datetime.now(_EASTERN).date(), key="cfb_ou_v18_date")
        day = selected.isoformat()
        games, schedule_diag = schedule_v6.load_with_diagnostics(day)
        if not games:
            st.warning("No verified College Football games were returned for this date.")
            return
        odds_payload, market_diag = market_adapter.load_odds_for_date(day, "FanDuel")
        games, attach_diag = market_adapter.attach_market_lines(games, odds_payload)
        index = st.selectbox("🏟️ Over/Under matchup", options=list(range(len(games))), format_func=lambda i: f"{games[int(i)].get('away_team')} @ {games[int(i)].get('home_team')} • {_kickoff_phoenix(games[int(i)])} " + (f"• O/U {_market_line(games[int(i)]):.1f}" if _market_line(games[int(i)]) is not None else "• O/U unavailable"), key=f"cfb_ou_v18_matchup_{day}")
        selected_game = dict(games[int(index)])
        identity = _clean(selected_game.get("identity_key") or selected_game.get("game_id") or index)
        live_line = _market_line(selected_game)
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
        st.markdown(_hero_html(game, away, home, live_line, attach_diag), unsafe_allow_html=True)
        st.markdown(_quick_read_html(result, float(line)), unsafe_allow_html=True)
        runtime_status = _clean(diag.get("runtime_status")) or "CHECK"
        issue_count = len(diag.get("runtime_issues") or [])
        market_state = _clean(market_diag.get("status")) or "CHECK"
        st.caption(f"Runtime data {runtime_status} • Market {market_state} • {int(schedule_diag.get('espn_matches') or 0)} ESPN-enriched matchups • {int(attach_diag.get('market_lines_attached') or 0)} live totals • {issue_count} runtime issue(s)")

        with st.expander("📈 Market context • sportsbook details", expanded=False):
            st.markdown(_market_caption(selected_game, market_diag), unsafe_allow_html=True)
        with st.expander("🏟️ Steps 1–4 • matchup foundation", expanded=False):
            st.markdown(_presentation._step1(game, away, home), unsafe_allow_html=True)
            st.markdown(_presentation._step2(away, home), unsafe_allow_html=True)
            try:
                readable_matchup = _presentation.readable_step3.build_matchup_step3(game, away, home)
            except Exception as exc:
                readable_matchup = {"ready": True, "display_ready": False, "reason": f"Readable Step 3 data failed visibly: {type(exc).__name__}: {exc}"}
            st.markdown(_presentation._step3_readable(readable_matchup, result.get("matchup_engine") or {}), unsafe_allow_html=True)
            st.markdown(_presentation._model_step(4, "PACE / EXPECTED POSSESSIONS", result.get("pace_engine") or {}), unsafe_allow_html=True)

        factors = [(5, "Explosive Plays", result.get("explosive_engine") or {}), (6, "Red Zone", result.get("red_zone_engine") or {}), (7, "Third Down", result.get("third_down_engine") or {}), (8, "Turnover Volatility", result.get("turnover_engine") or {}), (9, "Game-Day Environment", result.get("environment_engine") or {}), (10, "Historical Matchup", result.get("history_engine") or {})]
        _render_factor_cards(factors)
        for step, title, engine in factors:
            with st.expander(f"Step {step} • {title} — deep evidence", expanded=False):
                st.markdown(_presentation._model_step(step, title.upper(), engine), unsafe_allow_html=True)
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
                st.markdown(f"**#{rank} {game_row.get('away_team')} @ {game_row.get('home_team')} — {final_row.get('selection') or raw_row.get('model_lean') or 'PASS'}** • projected total {_num(raw_row.get('projected_total'),1)} • analysis line {_num(row.get('analysis_line'),1)}")
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
        raise ValueError(f"Clean O/U Page V38 received unsupported market: {market}")
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = ["ACTIVE_ANALYSIS_PREWARM", "ACTIVE_LOGO_RESOLVER", "ACTIVE_MARKET_ADAPTER", "ACTIVE_MARKET_INTELLIGENCE", "ACTIVE_PERFORMANCE_PROFILER", "ACTIVE_RUNTIME_SLATE", "ACTIVE_SCHEDULE", "FROZEN_PAGE", "FROZEN_RUNTIME_SLATE", "MARKET", "MAY_MODIFY_PROJECTION", "MODEL_VERSION", "SPORTSBOOK_PROJECTION_INFLUENCE", "_display_game", "_kickoff_phoenix", "_render_factor_cards", "render_cfb_hub", "render_over_under_hub"]
