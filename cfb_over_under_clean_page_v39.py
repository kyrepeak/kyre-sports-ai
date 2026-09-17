"""CFB Over/Under Clean Page V39 — compact evidence renderer.

Presentation-only additive page over certified Clean Page V38. Schedule, market,
runtime analysis, frozen model engines, thresholds, probabilities, full-slate
ranking, and sportsbook influence are reused unchanged. V39 replaces only the
visible lower Steps 1-10 presentation so verified team identity is not confused
with a missing step-specific provider metric.
"""
from __future__ import annotations

from copy import deepcopy
from html import escape
from time import perf_counter
from typing import Any, Mapping

import streamlit as st

import cfb_over_under_clean_page_v38 as frozen_page

MODEL_VERSION = "CFB O/U CLEAN PAGE V39 • COMPACT EVIDENCE RENDERER"
MARKET = frozen_page.MARKET
FROZEN_PRESENTATION = "cfb_over_under_clean_page_v38"
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
_quick_read_html = frozen_page._quick_read_html
_EASTERN = frozen_page._EASTERN

_CSS = r"""
<style>
.ou39-freeze{margin:9px 0 7px;border:1px solid rgba(154,111,255,.27);border-radius:10px;background:rgba(76,47,122,.16);padding:7px 9px;color:#bcaaff;font-size:.38rem;font-weight:900;letter-spacing:.015em}
.ou39-foundation{margin-top:8px;border:1px solid rgba(92,126,255,.20);border-radius:14px;background:#091622;padding:9px}
.ou39-foundation-head{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:7px}.ou39-foundation-head b{color:#eef5fa;font-size:.60rem}.ou39-foundation-head span{color:#7f94a7;font-size:.31rem}
.ou39-foundation-teams{display:grid;grid-template-columns:1fr 1fr;gap:7px}.ou39-foundation-team{display:grid;grid-template-columns:52px minmax(0,1fr);gap:8px;align-items:center;border:1px solid rgba(136,156,176,.13);border-radius:11px;background:#0b1824;padding:7px;min-width:0}.ou39-foundation-logo{width:52px;height:52px;border-radius:10px;background:#0f1f2d;display:flex;align-items:center;justify-content:center;overflow:hidden}.ou39-foundation-logo img{width:46px;height:46px;max-width:56px;object-fit:contain}.ou39-foundation-logo span{color:#dce8f0;font-size:.72rem;font-weight:950}.ou39-team-name{color:#f5f9fc;font-size:.68rem;font-weight:950;line-height:1.12}.ou39-team-meta{color:#8196a8;font-size:.34rem;font-weight:800;line-height:1.45;margin-top:2px}.ou39-id{color:#8ed7ff;font-size:.29rem;font-weight:900;margin-top:2px}
.ou39-context{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin-top:7px}.ou39-chip{border:1px solid rgba(127,148,170,.14);border-radius:9px;background:#0a151f;padding:6px 7px;min-width:0}.ou39-chip small{display:block;color:#708599;font-size:.25rem;font-weight:950;letter-spacing:.06em}.ou39-chip b{display:block;color:#dae6ee;font-size:.37rem;line-height:1.25;margin-top:2px;overflow-wrap:anywhere}
.ou39-foundation-steps{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px;margin-top:7px}.ou39-mini{border:1px solid rgba(128,148,169,.13);border-radius:9px;background:#0a151f;padding:6px 7px}.ou39-mini small{display:block;color:#74899b;font-size:.25rem;font-weight:950}.ou39-mini b{display:block;color:#e8f1f6;font-size:.39rem;margin-top:2px}.ou39-mini span{display:block;color:#8798a6;font-size:.29rem;line-height:1.35;margin-top:2px}
.ou39-step{border:1px solid rgba(126,147,169,.16);border-radius:10px;background:#0a151f;padding:8px;margin:2px 0 5px}.ou39-step-head{display:flex;align-items:center;justify-content:space-between;gap:8px}.ou39-step-title{color:#edf4f8;font-size:.48rem;font-weight:950}.ou39-badge{border-radius:999px;padding:3px 7px;font-size:.27rem;font-weight:950}.ou39-badge.ready{background:rgba(30,120,78,.25);color:#9aefbf}.ou39-badge.check{background:rgba(116,79,20,.24);color:#f0d37f}.ou39-badge.gated{background:rgba(124,42,48,.24);color:#ffafb5}.ou39-step-reason{color:#9aabb8;font-size:.32rem;line-height:1.45;margin-top:5px}.ou39-metrics{display:flex;flex-wrap:wrap;gap:5px;margin-top:6px}.ou39-metric{border:1px solid rgba(128,149,171,.15);border-radius:8px;background:#0d1b27;padding:4px 6px;color:#bed0dd;font-size:.28rem}.ou39-metric b{color:#eef5f8}.ou39-audit{color:#7f91a0;font-size:.30rem;line-height:1.45}
@media(max-width:760px){.ou39-foundation-teams{grid-template-columns:1fr}.ou39-context{grid-template-columns:repeat(2,minmax(0,1fr))}.ou39-foundation-steps{grid-template-columns:1fr}.ou39-foundation-logo{width:48px;height:48px}.ou39-foundation-logo img{width:42px;height:42px}.ou39-foundation-team{grid-template-columns:48px minmax(0,1fr)}}
@media(max-width:430px){.ou39-context{grid-template-columns:1fr}.ou39-foundation-head{align-items:flex-start;flex-direction:column}.ou39-step-head{align-items:flex-start;flex-direction:column}}
</style>
"""


def _first(mapping: Mapping[str, Any] | None, *keys: str) -> Any:
    if not isinstance(mapping, Mapping):
        return None
    for key in keys:
        value = mapping.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def _record(profile: Mapping[str, Any]) -> str:
    value = _first(profile, "record", "overall_record", "team_record")
    if isinstance(value, Mapping):
        wins = int(value.get("wins") or 0)
        losses = int(value.get("losses") or 0)
        ties = int(value.get("ties") or 0)
        return f"{wins}-{losses}" + (f"-{ties}" if ties else "")
    return _clean(value) or "—"


def _team_id(side: str, game: Mapping[str, Any], profile: Mapping[str, Any], visual: Mapping[str, Any]) -> str:
    value = _first(
        visual,
        "team_id",
        "espn_team_id",
        "espn_id",
        "id",
    ) or _first(
        profile,
        "team_id",
        "espn_team_id",
        "espn_id",
        "id",
    ) or _first(
        game,
        f"{side}_team_id",
        f"{side}_espn_team_id",
        f"{side}_espn_id",
    )
    return _clean(value)


def _identity_state(game: Mapping[str, Any], away: Mapping[str, Any], home: Mapping[str, Any]) -> dict[str, Any]:
    display = _display_game(game)
    visuals = _resolve_visuals(display)
    away_name = _clean(display.get("away_team")) or _clean(away.get("team")) or "Away"
    home_name = _clean(display.get("home_team")) or _clean(home.get("team")) or "Home"
    away_id = _team_id("away", display, away, visuals.get("away") or {})
    home_id = _team_id("home", display, home, visuals.get("home") or {})
    return {
        "verified": bool(away_name and home_name and away_id and home_id),
        "away_team": away_name,
        "home_team": home_name,
        "away_id": away_id,
        "home_id": home_id,
        "visuals": visuals,
        "display_game": display,
    }


def _scalar_metrics(engine: Mapping[str, Any]) -> list[tuple[str, str]]:
    ignored = {"status", "reason", "ready", "display_ready", "coverage", "errors", "error", "source", "sources"}
    rows: list[tuple[str, str]] = []
    for key, value in engine.items():
        if key in ignored or isinstance(value, (Mapping, list, tuple, set)) or value in (None, ""):
            continue
        if isinstance(value, bool):
            continue
        label = str(key).replace("_", " ").title()
        if isinstance(value, float):
            if "rate" in key.lower() or "prob" in key.lower() or "pct" in key.lower():
                shown = f"{100.0 * value:.1f}%" if abs(value) <= 1.0 else f"{value:.1f}%"
            else:
                shown = f"{value:.2f}".rstrip("0").rstrip(".")
        else:
            shown = str(value)
        rows.append((label, shown))
        if len(rows) >= 4:
            break
    return rows


def _step_evidence_state(step: int, title: str, engine: Mapping[str, Any], identity_state: Mapping[str, Any]) -> dict[str, Any]:
    """Map frozen engine evidence to truthful display state without mutation."""
    frozen = deepcopy(dict(engine or {}))
    frozen_status = _clean(frozen.get("status") or ("READY" if frozen.get("ready") else "CHECK")).upper()
    frozen_reason = _clean(frozen.get("reason"))
    identity_verified = bool(identity_state.get("verified"))
    metrics = _scalar_metrics(frozen)
    reason_lower = frozen_reason.lower()

    if not identity_verified:
        display_status = "GATED"
        display_reason = frozen_reason or "Team identity is unresolved for one or both teams."
    elif frozen_status in {"READY", "GREEN", "PASS", "OK"} and (metrics or frozen.get("ready") is not False):
        display_status = "READY"
        display_reason = frozen_reason or f"Certified {title.lower()} evidence is available for both verified teams."
    else:
        provider_gap = any(
            token in reason_lower
            for token in (
                "identity is unavailable",
                "identity unavailable",
                "evidence unavailable",
                "data unavailable",
                "not available",
                "missing",
                "insufficient",
                "no certified",
                "provider",
            )
        )
        if provider_gap or not metrics:
            display_status = "CHECK"
            display_reason = f"Teams verified. NCAA {title.lower()} evidence is unavailable or incomplete. Frozen prior preserved."
        else:
            display_status = "GATED"
            display_reason = frozen_reason or f"Frozen Step {step} model gate remains active."

    return {
        "step": int(step),
        "title": title,
        "display_status": display_status,
        "display_reason": display_reason,
        "identity_verified": identity_verified,
        "metrics": metrics,
        "frozen_status": frozen_status,
        "frozen_reason": frozen_reason,
        "frozen_engine": frozen,
    }


def _monogram(name: str) -> str:
    tokens = [token for token in _clean(name).replace("&", " ").split() if token]
    return "".join(token[0].upper() for token in tokens[:2]) or "CFB"


def _foundation_logo(name: str, visual: Mapping[str, Any]) -> str:
    url = _clean(_first(visual, "logo", "logo_url", "image"))
    if url:
        return f'<div class="ou39-foundation-logo"><img src="{escape(url, quote=True)}" alt="{escape(name)} logo"></div>'
    return f'<div class="ou39-foundation-logo"><span>{escape(_monogram(name))}</span></div>'


def _profile_meta(profile: Mapping[str, Any]) -> str:
    bits: list[str] = []
    record = _record(profile)
    if record != "—":
        bits.append(record)
    conference = _clean(_first(profile, "conference", "conference_name", "league"))
    if conference:
        bits.append(conference)
    rank = _first(profile, "rank", "ap_rank", "ranking")
    try:
        rank_int = int(rank)
        if rank_int > 0:
            bits.append(f"AP #{rank_int}")
    except Exception:
        pass
    return " • ".join(bits) or "Verified team profile"


def _compact_engine_summary(label: str, engine: Mapping[str, Any]) -> str:
    status = _clean(engine.get("status") or ("READY" if engine.get("ready") else "CHECK")).upper()
    metrics = _scalar_metrics(engine)
    short = " • ".join(f"{name}: {value}" for name, value in metrics[:2])
    reason = _clean(engine.get("reason"))
    detail = short or reason or "Frozen engine evidence preserved."
    return f'<div class="ou39-mini"><small>{escape(label.upper())}</small><b>{escape(status)}</b><span>{escape(detail)}</span></div>'


def _render_compact_foundation(game: Mapping[str, Any], away: Mapping[str, Any], home: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]:
    identity = _identity_state(game, away, home)
    display = identity["display_game"]
    visuals = identity["visuals"]
    away_name = identity["away_team"]
    home_name = identity["home_team"]
    venue = _clean(_first(display, "venue", "venue_name")) or "Venue unavailable"
    broadcast = _clean(_first(display, "broadcast", "network", "tv")) or "Broadcast unavailable"
    status = _clean(_first(display, "status", "game_status")) or "Scheduled"
    kickoff = _kickoff_phoenix(display)

    html = f'''
<div class="ou39-foundation" data-testid="ou39-matchup-foundation">
  <div class="ou39-foundation-head"><b>🏟️ Matchup Foundation</b><span>Steps 1–4 • compact verified evidence</span></div>
  <div class="ou39-foundation-teams">
    <div class="ou39-foundation-team">{_foundation_logo(away_name, visuals.get("away") or {})}<div><div class="ou39-team-name">{escape(away_name)}</div><div class="ou39-team-meta">{escape(_profile_meta(away))}</div><div class="ou39-id">ESPN ID {escape(identity["away_id"] or "—")}</div></div></div>
    <div class="ou39-foundation-team">{_foundation_logo(home_name, visuals.get("home") or {})}<div><div class="ou39-team-name">{escape(home_name)}</div><div class="ou39-team-meta">{escape(_profile_meta(home))}</div><div class="ou39-id">ESPN ID {escape(identity["home_id"] or "—")}</div></div></div>
  </div>
  <div class="ou39-context">
    <div class="ou39-chip"><small>KICKOFF</small><b>{escape(kickoff)}</b></div>
    <div class="ou39-chip"><small>VENUE</small><b>{escape(venue)}</b></div>
    <div class="ou39-chip"><small>BROADCAST</small><b>{escape(broadcast)}</b></div>
    <div class="ou39-chip"><small>STATUS</small><b>{escape(status)}</b></div>
  </div>
  <div class="ou39-foundation-steps">
    {_compact_engine_summary("Step 2 • Team Scoring", result.get("team_scoring_engine") or result.get("scoring_engine") or {})}
    {_compact_engine_summary("Step 3 • Matchup", result.get("matchup_engine") or {})}
    {_compact_engine_summary("Step 4 • Pace", result.get("pace_engine") or {})}
  </div>
</div>'''
    st.markdown(html, unsafe_allow_html=True)
    return identity


def _metric_html(metrics: list[tuple[str, str]]) -> str:
    if not metrics:
        return ""
    return '<div class="ou39-metrics">' + "".join(
        f'<div class="ou39-metric"><b>{escape(name)}</b> {escape(value)}</div>' for name, value in metrics
    ) + "</div>"


def _compact_step_card(state: Mapping[str, Any]) -> str:
    status = _clean(state.get("display_status")).upper() or "CHECK"
    css = status.lower() if status in {"READY", "CHECK", "GATED"} else "check"
    reason = _clean(state.get("display_reason"))
    return f'''
<div class="ou39-step" data-testid="ou39-step-{int(state.get('step') or 0)}">
  <div class="ou39-step-head"><div class="ou39-step-title">Step {int(state.get('step') or 0)} • {escape(_clean(state.get('title')))}</div><span class="ou39-badge {css}">{escape(status)}</span></div>
  <div class="ou39-step-reason">{escape(reason)}</div>
  {_metric_html(list(state.get("metrics") or []))}
</div>'''


def _render_compact_step_expanders(factors: list[tuple[int, str, Mapping[str, Any]]], identity: Mapping[str, Any]) -> None:
    st.markdown('<div class="ou39-freeze">Frozen O/U math • Mutation OFF • Sportsbook 0.0%</div>', unsafe_allow_html=True)
    for step, title, engine in factors:
        state = _step_evidence_state(step, title, engine, identity)
        with st.expander(f"Step {step} • {title}", expanded=False):
            st.markdown(_compact_step_card(state), unsafe_allow_html=True)
            with st.expander("Model Audit", expanded=False):
                frozen_status = escape(_clean(state.get("frozen_status")) or "CHECK")
                frozen_reason = escape(_clean(state.get("frozen_reason")) or "No frozen reason supplied.")
                st.markdown(
                    f'<div class="ou39-audit"><b>Frozen engine status:</b> {frozen_status}<br><b>Frozen reason:</b> {frozen_reason}<br>Presentation mapping only — the frozen engine object is not modified.</div>',
                    unsafe_allow_html=True,
                )


def render_over_under_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    trace = profiler.PerfTrace()
    token = profiler.set_active_trace(trace)
    perf_slot = st.empty()
    started = perf_counter()
    try:
        st.caption("🟣 CFB O/U • CLEAN PAGE V39 ACTIVE • COMPACT EVIDENCE RENDERER • VERIFIED IDENTITY ≠ MISSING STEP METRIC • PHOENIX TIME • 0.0% SPORTSBOOK PROJECTION INFLUENCE")
        st.markdown(frozen_page._CSS + _CSS, unsafe_allow_html=True)
        selected = st.date_input("📅 CFB Over/Under slate date", value=frozen_page.datetime.now(_EASTERN).date(), key="cfb_ou_v18_date")
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
            format_func=lambda i: f"{games[int(i)].get('away_team')} @ {games[int(i)].get('home_team')} • {_kickoff_phoenix(games[int(i)])} " + (f"• O/U {_market_line(games[int(i)]):.1f}" if _market_line(games[int(i)]) is not None else "• O/U unavailable"),
            key=f"cfb_ou_v18_matchup_{day}",
        )
        selected_game = dict(games[int(index)])
        game_identity = _clean(selected_game.get("identity_key") or selected_game.get("game_id") or index)
        live_line = _market_line(selected_game)
        default_line = float(live_line) if live_line is not None else 50.5
        line = st.number_input(
            "🎯 Analysis total line — threshold only (0.0% projection weight)",
            min_value=20.0,
            max_value=100.0,
            value=default_line,
            step=0.5,
            key=f"cfb_ou_v18_line_{day}_{game_identity}",
        )
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

        identity = _render_compact_foundation(game, away, home, result)
        factors = [
            (5, "Explosive Plays", result.get("explosive_engine") or {}),
            (6, "Red Zone", result.get("red_zone_engine") or {}),
            (7, "Third Down", result.get("third_down_engine") or {}),
            (8, "Turnover Volatility", result.get("turnover_engine") or {}),
            (9, "Game-Day Environment", result.get("environment_engine") or {}),
            (10, "Historical Matchup", result.get("history_engine") or {}),
        ]
        _render_compact_step_expanders(factors, identity)

        with st.expander("🧪 Steps 11–12 • current form + certification", expanded=False):
            st.markdown(frozen_page._presentation._model_step(11, "CURRENT FORM + SCHEDULE STRENGTH", result.get("form_strength_engine") or {}), unsafe_allow_html=True)
            st.markdown(frozen_page._presentation._cert_step(result), unsafe_allow_html=True)
            st.markdown(frozen_page._presentation._final(result), unsafe_allow_html=True)

        with st.expander("📋 Full-slate scan workspace", expanded=False):
            st.caption("Every game keeps its own live FanDuel total when available. Analysis Line is editable and remains a threshold only.")
            editor = st.data_editor(_line_board(games, game_identity, float(line)), use_container_width=True, hide_index=True, key=f"cfb_ou_v18_board_{day}")
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
    "FROZEN_PRESENTATION",
    "FROZEN_RUNTIME_SLATE",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_identity_state",
    "_render_compact_foundation",
    "_render_compact_step_expanders",
    "_step_evidence_state",
    "render_cfb_hub",
    "render_over_under_hub",
]
