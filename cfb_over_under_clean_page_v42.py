"""CFB Over/Under Clean Page V42 — Instant Line Lab V1.

Performance-only successor over frozen V41. The selected matchup still receives
one normal certified V14 analysis. Slider reruns are then isolated inside a
Streamlit fragment and replay only deterministic line-dependent math from that
already-built result. No external source, schedule, market, identity, team-data,
or evidence-engine build is allowed on a slider move.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from time import perf_counter
from typing import Any, Mapping

import streamlit as st

import cfb_over_under_analysis_prewarm_v1 as prewarm
import cfb_over_under_clean_page_v39 as evidence_page
import cfb_over_under_clean_page_v41 as frozen_page
import cfb_over_under_fast_line_lab_v1 as fast_line

MODEL_VERSION = "CFB O/U CLEAN PAGE V42 • INSTANT LINE LAB V1"
MARKET = frozen_page.MARKET
FROZEN_PRESENTATION = "cfb_over_under_clean_page_v41"
FROZEN_PAGE = frozen_page.FROZEN_PAGE
FROZEN_RUNTIME_SLATE = frozen_page.FROZEN_RUNTIME_SLATE
ACTIVE_LOGO_RESOLVER = frozen_page.ACTIVE_LOGO_RESOLVER
ACTIVE_MARKET_ADAPTER = frozen_page.ACTIVE_MARKET_ADAPTER
ACTIVE_MARKET_INTELLIGENCE = frozen_page.ACTIVE_MARKET_INTELLIGENCE
ACTIVE_SCHEDULE = frozen_page.ACTIVE_SCHEDULE
ACTIVE_RUNTIME_SLATE = frozen_page.ACTIVE_RUNTIME_SLATE
ACTIVE_PERFORMANCE_PROFILER = frozen_page.ACTIVE_PERFORMANCE_PROFILER
ACTIVE_ANALYSIS_PREWARM = prewarm.MODEL_VERSION
ACTIVE_FAST_LINE_LAB = fast_line.MODEL_VERSION
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
MAY_FETCH_EXTERNAL_DATA_ON_SLIDER = False

schedule_v6 = frozen_page.schedule_v6
market_adapter = frozen_page.market_adapter
runtime_slate = frozen_page.runtime_slate
final_model = frozen_page.final_model
profiler = frozen_page.profiler
_line_board = frozen_page._line_board
_market_caption = frozen_page._market_caption
_clean = frozen_page._clean
_float = frozen_page._float
_num = frozen_page._num
_pct = frozen_page._pct
_market_line = frozen_page._market_line
_kickoff_phoenix = frozen_page._kickoff_phoenix
_decision_state = frozen_page._decision_state
_clamp_line = frozen_page._clamp_line
_nudge_line = frozen_page._nudge_line
_section = frozen_page._section
_compact_matchup_html = frozen_page._compact_matchup_html
_decision_html = frozen_page._decision_html
_slider_marker_html = frozen_page._slider_marker_html
_line_lab_html = frozen_page._line_lab_html
_why_html = frozen_page._why_html
_drivers_html = frozen_page._drivers_html
_team_html = frozen_page._team_html
_market_html = frozen_page._market_html
_presentation = frozen_page._presentation
_EASTERN = frozen_page._EASTERN

_FAST_CSS = r"""
<style>
.ou42-fast{display:flex;align-items:center;gap:8px;margin:8px 0 11px;border:1px solid rgba(57,197,121,.24);border-radius:12px;background:rgba(17,72,50,.16);padding:9px 11px;color:#acd9be;font-size:.84rem;line-height:1.4}.ou42-fast b{color:#eafff1}.ou42-fast-dot{width:8px;height:8px;border-radius:999px;background:#45d486;box-shadow:0 0 0 4px rgba(69,212,134,.10)}
.ou42-perf{margin-top:8px;color:#91a8b8;font-size:.80rem;line-height:1.45}.ou42-perf b{color:#dce8ef}
</style>
"""


def _identity(game: Mapping[str, Any]) -> str:
    return _clean(game.get("identity_key") or game.get("game_id"))


def _safe_index(value: Any, size: int) -> int:
    try:
        index = int(value)
    except Exception:
        index = 0
    return max(0, min(max(0, int(size) - 1), index))


def _prewarm_and_market(
    selected_game: Mapping[str, Any],
    day: str,
    trace: Any,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Overlap selected-game provider warmup with the unchanged market wait."""
    prewarm_started = perf_counter()
    with ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(prewarm.warm_selected_game, dict(selected_game), day)
        market_payload, market_diag = market_adapter.load_odds_for_date(day, "FanDuel")
        wait_started = perf_counter()
        try:
            prewarm_diag = dict(future.result() or {})
        except Exception as exc:
            prewarm_diag = {
                "version": prewarm.MODEL_VERSION,
                "status": "UNAVAILABLE",
                "elapsed_ms": round((perf_counter() - prewarm_started) * 1000.0, 1),
                "error": f"{type(exc).__name__}: {exc}"[:400],
            }
        wait_seconds = perf_counter() - wait_started

    total_seconds = perf_counter() - prewarm_started
    if trace is not None:
        trace.add("analysis.prewarm.parallel", total_seconds)
        trace.add("analysis.prewarm.wait_after_market", wait_seconds)
    return dict(market_payload or {}), dict(market_diag or {}), prewarm_diag


def _render_advanced(
    result: Mapping[str, Any],
    games: list[Mapping[str, Any]],
    game_identity: str,
    line: float,
    day: str,
) -> None:
    game = dict(result.get("game") or {})
    away = dict(result.get("away") or {})
    home = dict(result.get("home") or {})
    identity = evidence_page._identity_state(game, away, home)
    with st.expander("🧠 ADVANCED ANALYTICS", expanded=False):
        for step, title, key in (
            (5, "Explosive Plays", "explosive_engine"),
            (6, "Red Zone", "red_zone_engine"),
            (7, "Third Down", "third_down_engine"),
            (8, "Turnover Volatility", "turnover_engine"),
            (9, "Game-Day Environment", "environment_engine"),
            (10, "Historical Matchup", "history_engine"),
        ):
            state_row = evidence_page._step_evidence_state(
                step,
                title,
                result.get(key) or {},
                identity,
            )
            metrics = " • ".join(
                f"{name}: {value}"
                for name, value in (state_row.get("metrics") or [])[:3]
            )
            st.markdown(
                f"**{title} — {_clean(state_row.get('display_status'))}**  \n"
                f"{metrics or _clean(state_row.get('display_reason'))}"
            )

        st.caption("Full-slate scan remains explicit and separate from the instant Line Lab.")
        if st.checkbox("Open full-slate scan workspace", key=f"cfb_ou_v42_scan_open_{day}"):
            editor = st.data_editor(
                _line_board(games, game_identity, float(line)),
                use_container_width=True,
                hide_index=True,
                key=f"cfb_ou_v42_board_{day}",
            )
            try:
                records = editor.to_dict("records")
            except Exception:
                records = list(editor) if isinstance(editor, list) else []
            selected_lines: dict[str, float] = {}
            for row in records:
                identity_key = _clean(row.get("Identity"))
                row_line = _float(row.get("Analysis Line"))
                if bool(row.get("Use")) and identity_key and row_line is not None:
                    selected_lines[identity_key] = float(row_line)
            if st.button(
                f"Run O/U scan for {len(selected_lines)} selected game(s)",
                key=f"cfb_ou_v42_scan_{day}",
                type="primary",
                disabled=not bool(selected_lines),
            ):
                rows, scan_diag = runtime_slate.scan_slate(
                    games,
                    day,
                    selected_lines,
                )
                st.session_state[f"cfb_ou_v42_top5_{day}"] = final_model.rank_slate(rows, limit=5)
                st.session_state[f"cfb_ou_v42_scan_diag_{day}"] = scan_diag
            for rank, row in enumerate(
                st.session_state.get(f"cfb_ou_v42_top5_{day}") or [],
                start=1,
            ):
                g = row.get("game") or {}
                f = row.get("final") or {}
                r = row.get("raw") or {}
                st.markdown(
                    f"**#{rank} {g.get('away_team')} @ {g.get('home_team')} — "
                    f"{f.get('selection') or r.get('model_lean') or 'PASS'}** • "
                    f"projected {_num(r.get('projected_total'),1)} • "
                    f"line {_num(row.get('analysis_line'),1)}"
                )


def render_over_under_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    trace = profiler.PerfTrace()
    token = profiler.set_active_trace(trace)
    started = perf_counter()
    try:
        st.markdown(frozen_page._CSS + _FAST_CSS, unsafe_allow_html=True)
        selected = st.date_input(
            "📅 CFB Over/Under slate date",
            value=datetime.now(_EASTERN).date(),
            key="cfb_ou_v42_date",
        )
        day = selected.isoformat()
        games, schedule_diag = schedule_v6.load_with_diagnostics(day)
        if not games:
            st.warning("No verified College Football games were returned for this date.")
            return

        matchup_key = f"cfb_ou_v42_matchup_{day}"
        context_index = _safe_index(st.session_state.get(matchup_key, 0), len(games))
        context_game = dict(games[context_index])
        odds_payload, market_diag, prewarm_diag = _prewarm_and_market(
            context_game,
            day,
            trace,
        )
        games, attach_diag = market_adapter.attach_market_lines(games, odds_payload)

        index = st.selectbox(
            "🏟️ Over/Under matchup",
            options=list(range(len(games))),
            format_func=lambda i: (
                f"{games[int(i)].get('away_team')} @ {games[int(i)].get('home_team')} • "
                f"{_kickoff_phoenix(games[int(i)])}"
                + (
                    f" • O/U {_market_line(games[int(i)]):.1f}"
                    if _market_line(games[int(i)]) is not None
                    else " • O/U unavailable"
                )
            ),
            key=matchup_key,
        )
        selected_game = dict(games[int(index)])

        # If attachment changed ordering/identity unexpectedly, warm the actual
        # selected row before the one normal baseline analysis.
        if _identity(selected_game) != _identity(context_game):
            try:
                prewarm_diag = dict(prewarm.warm_selected_game(selected_game, day) or {})
            except Exception as exc:
                prewarm_diag = {
                    "version": prewarm.MODEL_VERSION,
                    "status": "UNAVAILABLE",
                    "error": f"{type(exc).__name__}: {exc}"[:400],
                }

        game_identity = _identity(selected_game) or str(index)
        live_line = _market_line(selected_game)
        baseline_line = _clamp_line(live_line if live_line is not None else 50.5)
        try:
            base_result = runtime_slate.analyze_game(selected_game, day, baseline_line)
        except Exception as exc:
            st.error(f"Current runtime analysis failed visibly: {type(exc).__name__}: {exc}")
            return

        line_key = f"cfb_ou_v42_line_{day}_{game_identity}"
        if line_key not in st.session_state:
            st.session_state[line_key] = baseline_line

        try:
            st.session_state["cfb_ou_prewarm_v1_last"] = prewarm_diag
        except Exception:
            pass

        @st.fragment
        def _render_interactive_fragment() -> None:
            current_line = _clamp_line(st.session_state.get(line_key, baseline_line))
            st.markdown(
                '<div class="ou42-fast"><span class="ou42-fast-dot"></span>'
                '<div><b>⚡ FAST LINE LAB</b> • isolated fragment • '
                '0 external fetches per slider move</div></div>',
                unsafe_allow_html=True,
            )

            line_started = perf_counter()
            result = fast_line.reline_result(base_result, float(current_line))
            game = dict(result.get("game") or selected_game)
            away = dict(result.get("away") or {})
            home = dict(result.get("home") or {})
            state = _decision_state(result, float(current_line))

            st.markdown(
                _compact_matchup_html(game, away, home, live_line),
                unsafe_allow_html=True,
            )
            st.markdown(_decision_html(state), unsafe_allow_html=True)

            _section(
                "INTERACTIVE THRESHOLD",
                "LINE LAB",
                "Drag left or right; only threshold-dependent math reruns while matchup evidence stays warm.",
            )
            st.markdown(
                _slider_marker_html(float(current_line), live_line),
                unsafe_allow_html=True,
            )
            minus_col, slider_col, plus_col = st.columns([1.15, 7.7, 1.15])
            with minus_col:
                st.button(
                    "−0.5",
                    key=f"{line_key}_minus",
                    on_click=_nudge_line,
                    args=(line_key, -0.5),
                    use_container_width=True,
                )
            with slider_col:
                line = st.slider(
                    "🎚️ Line Lab total",
                    min_value=20.0,
                    max_value=100.0,
                    step=0.5,
                    key=line_key,
                )
            with plus_col:
                st.button(
                    "+0.5",
                    key=f"{line_key}_plus",
                    on_click=_nudge_line,
                    args=(line_key, 0.5),
                    use_container_width=True,
                )

            # The widget may have changed the line for this fragment run. Re-line
            # once more only when needed; still pure in-memory and provider-free.
            if float(line) != float(current_line):
                result = fast_line.reline_result(base_result, float(line))
                state = _decision_state(result, float(line))
            else:
                line = current_line

            st.markdown(_line_lab_html(state, live_line), unsafe_allow_html=True)
            _section(
                "PLAIN-ENGLISH READ",
                "WHY THE MODEL LIKES IT",
                "Three fast signals explain the current certified decision.",
            )
            st.markdown(_why_html(result, state), unsafe_allow_html=True)
            _section(
                "EVIDENCE DRIVERS",
                "WHAT MOVES THE TOTAL",
                "Evidence engines stay fixed while the slider changes only the comparison threshold.",
            )
            st.markdown(_drivers_html(result), unsafe_allow_html=True)
            _section(
                "SIDE-BY-SIDE",
                "TEAM MATCHUP",
                "Verified runtime snapshot; unavailable fields stay blank instead of being guessed.",
            )
            st.markdown(_team_html(game, away, home), unsafe_allow_html=True)
            _section(
                "PRICE CONTEXT",
                "MARKET INTELLIGENCE",
                "Market information stays separate from the frozen projection.",
            )
            st.markdown(
                _market_html(selected_game, live_line, float(line), market_diag, attach_diag),
                unsafe_allow_html=True,
            )

            _render_advanced(result, games, game_identity, float(line), day)

            with st.expander("📚 SOURCE & DATA QUALITY", expanded=False):
                team_diag = result.get("team_diag") or {}
                st.markdown(
                    f"Schedule: **{_clean(schedule_diag.get('status')) or 'CHECK'}** • "
                    f"ESPN-enriched matchups: **{int(schedule_diag.get('espn_matches') or 0)}**  \n"
                    f"Market: **{_clean(market_diag.get('status')) or 'CHECK'}** • "
                    f"verified totals attached: **{int(attach_diag.get('market_lines_attached') or 0)}**  \n"
                    f"Runtime team data: **{_clean(team_diag.get('runtime_status')) or 'CHECK'}** • "
                    f"issues: **{len(team_diag.get('runtime_issues') or [])}**"
                )
                st.markdown(_market_caption(selected_game, market_diag), unsafe_allow_html=True)

            with st.expander("🧪 MODEL TRANSPARENCY", expanded=False):
                st.markdown(
                    "Sportsbook projection influence: **0.0%**. The fast Line Lab "
                    "reuses the exact certified matchup evidence and changes only "
                    "the comparison threshold."
                )
                st.markdown(
                    _presentation._model_step(
                        11,
                        "CURRENT FORM + SCHEDULE STRENGTH",
                        result.get("form_strength_engine") or {},
                    ),
                    unsafe_allow_html=True,
                )
                st.markdown(_presentation._cert_step(result), unsafe_allow_html=True)
                st.markdown(_presentation._final(result), unsafe_allow_html=True)

            fragment_ms = round((perf_counter() - line_started) * 1000.0, 2)
            try:
                st.session_state["cfb_ou_fast_line_v1_last_ms"] = fragment_ms
            except Exception:
                pass
            with st.expander("🛠 DIAGNOSTICS", expanded=False):
                previous = st.session_state.get("cfb_ou_perf_v1_last") or {}
                fast_compute = _float(result.get("fast_line_compute_ms")) or 0.0
                st.markdown(
                    f'<div class="ou41-diag"><b>Presentation:</b> {MODEL_VERSION}'
                    f'<br><b>Runtime slate:</b> {_clean(ACTIVE_RUNTIME_SLATE)}'
                    f'<br><b>Fast-line pure compute:</b> {fast_compute:.3f} ms'
                    f'<br><b>Fragment server work:</b> {fragment_ms:.2f} ms'
                    f'<br><b>External fetches on slider:</b> 0'
                    f'<br><b>Prewarm:</b> {_clean(prewarm_diag.get("status")) or "CHECK"}'
                    f'<br><b>Previous full render:</b> {_num(previous.get("total_ms"),1)} ms'
                    f'<br><b>Projection mutation:</b> OFF • <b>Sportsbook influence:</b> 0.0%</div>',
                    unsafe_allow_html=True,
                )

        _render_interactive_fragment()
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
                "active_fast_line_lab": ACTIVE_FAST_LINE_LAB,
                "total_ms": trace.total_ms(),
                "stages": trace.aggregate(),
                "projection_weight": 0.0,
                "may_modify_projection": False,
                "slider_external_fetches": 0,
            }
        except Exception:
            pass


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"Instant O/U Page V42 received unsupported market: {market}")
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_ANALYSIS_PREWARM",
    "ACTIVE_FAST_LINE_LAB",
    "ACTIVE_LOGO_RESOLVER",
    "ACTIVE_MARKET_ADAPTER",
    "ACTIVE_MARKET_INTELLIGENCE",
    "ACTIVE_PERFORMANCE_PROFILER",
    "ACTIVE_RUNTIME_SLATE",
    "ACTIVE_SCHEDULE",
    "FROZEN_PAGE",
    "FROZEN_PRESENTATION",
    "FROZEN_RUNTIME_SLATE",
    "MARKET",
    "MAY_FETCH_EXTERNAL_DATA_ON_SLIDER",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "render_cfb_hub",
    "render_over_under_hub",
]
