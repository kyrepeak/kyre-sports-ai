"""CFB Game Total Monster Page V2 — live-data recovery + compact dashboard.

This is an additive presentation/data-handoff layer over the frozen Step-11 and
Step-12 Game Total math. It fixes the live page problems observed on 2026-09-16:
old V149 presentation, stale 0-0 records, missing exact-ID logos, inaccessible
evidence, and an overly tall audit wall.

Frozen model formulas, thresholds, final synthesis and Top-5 ranking remain
unchanged. The only model-input change is routing the already-certified runtime
team-data adapter into the frozen slate orchestrator so current records/scoring
evidence reach the existing math. Sportsbook projection influence remains 0.0%.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from html import escape
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import streamlit as st

import cfb_game_total_hub_v3 as frozen_page
import cfb_game_total_clean_page_v1 as prior_page
import cfb_over_under_logo_resolver_v3 as logo_v3
import cfb_over_under_runtime_team_data_v1 as runtime_data
import cfb_schedule_v5_runtime_snapshot as schedule_v5

MODEL_VERSION = "CFB GAME TOTAL MONSTER PAGE V2 • V151 LIVE RECOVERY"
MARKET = "Game Total"
FROZEN_GAME_TOTAL_HUB = "cfb_game_total_hub_v3"
RUNTIME_TEAM_DATA = "cfb_over_under_runtime_team_data_v1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

_PHOENIX = ZoneInfo("America/Phoenix")

_CSS = r"""
<style>
.gt151-wrap{margin:.35rem 0 .75rem;padding:14px;border:1px solid rgba(146,111,255,.28);border-radius:22px;background:radial-gradient(circle at 92% 0%,rgba(116,64,216,.22),transparent 24rem),linear-gradient(145deg,#06111c,#081522 60%,#0d1020);box-shadow:0 14px 42px rgba(0,0,0,.22)}
.gt151-kicker{font-size:.62rem;font-weight:950;letter-spacing:.11em;color:#a98cff}.gt151-title{font-size:1.52rem;line-height:1.05;font-weight:950;color:#f7fbff;margin-top:4px}.gt151-sub{font-size:.69rem;color:#91a4b8;margin-top:6px;line-height:1.45}.gt151-pills{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}.gt151-pill{padding:5px 8px;border-radius:999px;border:1px solid rgba(129,151,174,.24);font-size:.46rem;font-weight:900;color:#b7c5d3;background:#0a1825}.gt151-pill.good{color:#8cf0ba;border-color:rgba(58,210,137,.36);background:rgba(15,80,52,.30)}.gt151-pill.purple{color:#ceb6ff;border-color:rgba(174,121,255,.38);background:rgba(81,48,132,.30)}.gt151-pill.amber{color:#f3cf76;border-color:rgba(238,184,67,.36);background:rgba(100,70,15,.28)}
.gt151-score{margin-top:10px;border:1px solid rgba(95,158,218,.22);border-radius:18px;background:#07131f;overflow:hidden}.gt151-teams{display:grid;grid-template-columns:minmax(0,1fr) 64px minmax(0,1fr);gap:8px;padding:10px}.gt151-team{display:flex;align-items:center;gap:10px;padding:10px;border:1px solid rgba(150,166,184,.12);border-radius:14px;background:linear-gradient(145deg,#0a1825,#09131d);min-width:0}.gt151-team.home{flex-direction:row-reverse;text-align:right}.gt151-logo{width:62px;height:62px;flex:0 0 62px;border:1px solid rgba(255,255,255,.10);border-radius:14px;background:#0d1c29;display:flex;align-items:center;justify-content:center}.gt151-logo img{max-width:54px;max-height:54px;object-fit:contain}.gt151-mono{font-size:.92rem;font-weight:950;color:#dbe8f2}.gt151-rank{font-size:.42rem;font-weight:950;color:#72d2ff;text-transform:uppercase}.gt151-name{font-size:1.08rem;font-weight:950;color:#f5f9fc;line-height:1.05;margin-top:2px}.gt151-rec{font-size:.58rem;font-weight:900;color:#aebdca;margin-top:4px}.gt151-at{display:flex;flex-direction:column;align-items:center;justify-content:center;color:#687f93;font-size:.40rem;font-weight:900}.gt151-at b{font-size:1.15rem;color:#f0f5f8}.gt151-context{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border-top:1px solid rgba(90,151,207,.12)}.gt151-context div{padding:9px;border-right:1px solid rgba(90,151,207,.09)}.gt151-context div:last-child{border-right:0}.gt151-context small{display:block;font-size:.34rem;color:#728699;font-weight:950;text-transform:uppercase}.gt151-context strong{display:block;margin-top:3px;font-size:.52rem;color:#dce8f0;line-height:1.3}
.gt151-read{display:grid;grid-template-columns:1.3fr repeat(4,minmax(0,.7fr));gap:7px;margin-top:9px}.gt151-main,.gt151-stat{border:1px solid rgba(140,157,176,.14);border-radius:13px;background:#081520;padding:10px}.gt151-main{border-color:rgba(163,107,255,.35);background:linear-gradient(145deg,rgba(84,48,141,.30),#091622)}.gt151-main small,.gt151-stat small{display:block;font-size:.34rem;text-transform:uppercase;font-weight:950;color:#7e92a3}.gt151-main small{color:#bfa4ff}.gt151-main strong{display:block;font-size:1.35rem;color:#fff;margin-top:3px}.gt151-main span{display:block;font-size:.40rem;color:#8999aa;margin-top:3px}.gt151-stat b{display:block;font-size:.70rem;color:#ecf3f7;margin-top:4px}.gt151-status{margin-top:8px;padding:8px 10px;border-radius:11px;border:1px solid rgba(62,207,138,.25);background:rgba(15,76,51,.20);color:#9cecc1;font-size:.48rem;font-weight:850}.gt151-status.check{border-color:rgba(245,179,67,.30);background:rgba(105,72,14,.20);color:#f2ce7a}.gt151-status.gated{border-color:rgba(255,102,115,.28);background:rgba(95,31,38,.22);color:#ffb1b8}
.gt151-teamfacts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.gt151-fact{border:1px solid rgba(133,153,174,.14);border-radius:12px;background:#08141f;padding:9px}.gt151-fact b{display:block;color:#eef4f8;font-size:.68rem}.gt151-fact span{display:block;color:#8497a8;font-size:.44rem;line-height:1.5;margin-top:3px}.gt151-source{font-size:.43rem;color:#7f91a0;line-height:1.5}.gt151-alert{border-left:3px solid #f0b94e;border-radius:0 10px 10px 0;background:rgba(111,76,16,.18);padding:9px 10px;color:#efcf88;font-size:.48rem;line-height:1.45;margin-top:8px}
@media(max-width:760px){.gt151-title{font-size:1.28rem}.gt151-teams{grid-template-columns:1fr}.gt151-at{min-height:24px}.gt151-team.home{flex-direction:row;text-align:left}.gt151-logo{width:54px;height:54px;flex-basis:54px}.gt151-logo img{max-width:46px;max-height:46px}.gt151-context{grid-template-columns:repeat(2,minmax(0,1fr))}.gt151-read{grid-template-columns:repeat(2,minmax(0,1fr))}.gt151-main{grid-column:1/-1}.gt151-teamfacts{grid-template-columns:1fr}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any, digits: int = 1) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return "—"


def _pct(value: Any) -> str:
    try:
        return f"{100.0 * float(value):.1f}%"
    except Exception:
        return "—"


def _rank(profile: Mapping[str, Any]) -> str:
    try:
        rank = int(profile.get("ap_rank"))
        return f"AP #{rank}" if rank > 0 else "UNRANKED"
    except Exception:
        return "UNRANKED"


def _record(profile: Mapping[str, Any], runtime_status: str) -> str:
    text = _clean(profile.get("record_text"))
    if text in {"", "—"}:
        return "Record unavailable"
    if text == "0-0" and runtime_status != "GREEN":
        return "Record unavailable"
    return text


def _monogram(name: str) -> str:
    bits = [x for x in _clean(name).replace("&", " ").split() if x]
    return "".join(x[0].upper() for x in bits[:2]) or "CFB"


def _logo_html(name: str, visual: Mapping[str, Any]) -> str:
    url = _clean(visual.get("logo"))
    if url:
        return f'<div class="gt151-logo"><img src="{escape(url, quote=True)}" alt="{escape(name)} logo"></div>'
    return f'<div class="gt151-logo"><span class="gt151-mono">{escape(_monogram(name))}</span></div>'


def _runtime_game_with_ids(game: Mapping[str, Any], away: Mapping[str, Any], home: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(game)
    for side, profile in (("away", away), ("home", home)):
        team_id = _clean(profile.get("espn_team_id"))
        if team_id.isdigit():
            out[f"{side}_espn_team_id"] = team_id
    return out


@contextmanager
def _runtime_team_data_for_frozen_slate():
    """Swap only the team-data provider; Step-11/12 model functions stay frozen."""
    original = frozen_page.slate.team_data
    frozen_page.slate.team_data = runtime_data
    try:
        yield
    finally:
        frozen_page.slate.team_data = original


def _analyze(game: Mapping[str, Any], selected_day: str) -> dict[str, Any]:
    with _runtime_team_data_for_frozen_slate():
        try:
            frozen_page.slate.clear_scan_cache()
        except Exception:
            pass
        return frozen_page.slate.analyze_game(dict(game), selected_day)


def _scan(games: list[Mapping[str, Any]], selected_day: str):
    with _runtime_team_data_for_frozen_slate():
        try:
            frozen_page.slate.clear_scan_cache()
        except Exception:
            pass
        return frozen_page.slate.scan_slate(games, selected_day)


def _hero(game: Mapping[str, Any], away: Mapping[str, Any], home: Mapping[str, Any], runtime_status: str) -> str:
    visuals = logo_v3.resolve_visuals(game)
    away_name = _clean(away.get("team")) or _clean(game.get("away_team")) or "Away"
    home_name = _clean(home.get("team")) or _clean(game.get("home_team")) or "Home"
    return f"""
<div class="gt151-score">
  <div class="gt151-teams">
    <div class="gt151-team">{_logo_html(away_name, visuals.get('away') or {})}<div><div class="gt151-rank">{escape(_rank(away))}</div><div class="gt151-name">{escape(away_name)}</div><div class="gt151-rec">{escape(_record(away, runtime_status))}</div></div></div>
    <div class="gt151-at"><span>GAME TOTAL</span><b>@</b></div>
    <div class="gt151-team home">{_logo_html(home_name, visuals.get('home') or {})}<div><div class="gt151-rank">{escape(_rank(home))}</div><div class="gt151-name">{escape(home_name)}</div><div class="gt151-rec">{escape(_record(home, runtime_status))}</div></div></div>
  </div>
  <div class="gt151-context">
    <div><small>Kickoff • Phoenix</small><strong>{escape(prior_page._kickoff_phoenix(game))}</strong></div>
    <div><small>Venue</small><strong>{escape(_clean(game.get('venue')) or 'Venue unavailable')}</strong></div>
    <div><small>Status</small><strong>{escape(_clean(game.get('status')) or 'Scheduled')}</strong></div>
    <div><small>Broadcast</small><strong>{escape(_clean(game.get('broadcast')) or 'Broadcast unavailable')}</strong></div>
  </div>
</div>
"""


def _quick(raw: Mapping[str, Any], final: Mapping[str, Any], away: Mapping[str, Any], home: Mapping[str, Any]) -> str:
    ready = bool(final.get("ready"))
    projected = final.get("projected_combined_total") if ready else raw.get("projected_combined_total")
    core = final.get("core_50_range") or {}
    core_text = f"{int(core.get('low') or 0)}–{int(core.get('high') or 0)}" if ready and core else "—"
    headline = _num(projected) if projected is not None else "GATED"
    grade = _clean(final.get("grade")) if ready else "GATED"
    strength = _pct(final.get("forecast_strength")) if ready else "—"
    sample = min(int((away.get("record") or {}).get("games") or 0), int((home.get("record") or {}).get("games") or 0))
    return f"""
<div class="gt151-read">
  <div class="gt151-main"><small>Independent Game Total forecast</small><strong>{escape(headline)}</strong><span>{'Qualified frozen-model output' if ready else 'No forecast is invented until evidence clears the gate'}</span></div>
  <div class="gt151-stat"><small>Core range</small><b>{escape(core_text)}</b></div>
  <div class="gt151-stat"><small>Grade</small><b>{escape(grade or '—')}</b></div>
  <div class="gt151-stat"><small>Strength</small><b>{escape(strength)}</b></div>
  <div class="gt151-stat"><small>Min sample</small><b>{sample} game{'s' if sample != 1 else ''}</b></div>
</div>
"""


def _status(raw: Mapping[str, Any], final: Mapping[str, Any], runtime_diag: Mapping[str, Any]) -> str:
    data_status = _clean(runtime_diag.get("runtime_status")) or "CHECK"
    s11 = bool(raw.get("ready"))
    s12 = bool(final.get("ready"))
    cls = "" if data_status == "GREEN" and s11 and s12 else ("check" if data_status == "GREEN" else "gated")
    message = f"LIVE DATA {data_status} • STEP 11 {'READY' if s11 else 'GATED'} • STEP 12 {'READY' if s12 else 'GATED'}"
    return f'<div class="gt151-status {cls}">{escape(message)}</div>'


def _team_evidence_html(profile: Mapping[str, Any], runtime_status: str) -> str:
    name = _clean(profile.get("team")) or "Team"
    recent = _clean(profile.get("recent_form")) or "—"
    coach = _clean(profile.get("head_coach")) or "Unavailable"
    return f"""
<div class="gt151-fact"><b>{escape(name)} • {escape(_record(profile, runtime_status))}</b><span>
PF/G <b>{escape(_num(profile.get('ppg')))}</b> • PA/G <b>{escape(_num(profile.get('points_allowed_pg')))}</b> • Diff/G <b>{escape(_num(profile.get('point_diff_pg')))}</b><br>
Recent form: {escape(recent)} • Coach: {escape(coach)} • {_rank(profile)}
</span></div>
"""


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown("""
<div class="gt151-wrap">
  <div class="gt151-kicker">🔥 MONSTER MODE • CFB GAME TOTAL V151</div>
  <div class="gt151-title">Game Total — fast, live, and actually readable</div>
  <div class="gt151-sub">One scoreboard. One forecast readout. Tap-to-open evidence. Current team data is reconciled before the unchanged Step-11/12 math runs.</div>
  <div class="gt151-pills"><span class="gt151-pill good">LIVE DATA RECOVERY ✅</span><span class="gt151-pill purple">FROZEN MATH ✅</span><span class="gt151-pill good">LOGO ID PATH ✅</span><span class="gt151-pill amber">SPORTSBOOK 0.0%</span></div>
</div>
""", unsafe_allow_html=True)

    selected = st.date_input("📅 Slate date", value=datetime.now(_PHOENIX).date(), key="cfb_v151_game_total_date")
    selected_day = selected.isoformat()

    games, schedule_diag = schedule_v5.load_with_diagnostics(selected_day)
    if not games:
        st.warning("No verified CFB games were returned for this date. Nothing is invented.")
        return

    index = st.selectbox(
        "🏟️ Matchup",
        options=list(range(len(games))),
        format_func=lambda i: frozen_page.frozen_v2.frozen_v1.identity_ui._matchup_label(games[int(i)]),
        key=f"cfb_v151_game_total_matchup_{selected_day}",
    )
    base_game = dict(games[int(index)])

    with st.spinner("Syncing current team evidence…"):
        runtime_game, runtime_away, runtime_home, runtime_diag = runtime_data.reconcile_runtime(base_game, selected_day)
        runtime_game = _runtime_game_with_ids(runtime_game, runtime_away, runtime_home)
        result = _analyze(runtime_game, selected_day)

    away = result.get("away") or runtime_away
    home = result.get("home") or runtime_home
    raw = result.get("raw") or {}
    final = result.get("final") or {}
    model_team_diag = result.get("team_diag") or {}
    runtime_status = _clean(runtime_diag.get("runtime_status")) or "CHECK"

    # Keep display identity synced to whichever runtime profile was used by model.
    runtime_game = _runtime_game_with_ids(runtime_game, away, home)
    st.markdown(_hero(runtime_game, away, home, runtime_status), unsafe_allow_html=True)
    st.markdown(_quick(raw, final, away, home), unsafe_allow_html=True)
    st.markdown(_status(raw, final, runtime_diag), unsafe_allow_html=True)

    issues = list(runtime_diag.get("runtime_issues") or [])
    if issues:
        st.markdown('<div class="gt151-alert"><b>DATA CHECK:</b> ' + escape(" • ".join(str(x) for x in issues)) + '</div>', unsafe_allow_html=True)

    with st.expander("👀 Open team evidence", expanded=False):
        st.markdown('<div class="gt151-teamfacts">' + _team_evidence_html(away, runtime_status) + _team_evidence_html(home, runtime_status) + '</div>', unsafe_allow_html=True)
        st.caption("Current record/scoring/form evidence comes through the certified runtime reconciliation path; stale 0-0 is never presented as trustworthy when reconciliation is incomplete.")

    with st.expander("🧠 Open model evidence", expanded=False):
        st.markdown(frozen_page.frozen_v2._distribution_card(raw), unsafe_allow_html=True)
        if final:
            st.markdown(frozen_page._final_card(runtime_game, final), unsafe_allow_html=True)
        reasons = list(raw.get("reasons") or []) + list(final.get("reasons") or [])
        if reasons:
            st.caption("Gate reasons: " + " • ".join(dict.fromkeys(str(x) for x in reasons)))

    with st.expander("🛡️ Open data-source diagnostics", expanded=False):
        visuals = logo_v3.resolve_visuals(runtime_game)
        st.markdown(
            f"**Runtime:** `{runtime_status}`  ·  **Snapshot used:** `{bool(runtime_diag.get('runtime_snapshot_used'))}`  ·  "
            f"**Deep live reconciliation:** `{bool(runtime_diag.get('deep_reconciliation_ok'))}`  ·  "
            f"**Away logo ID:** `{_clean((visuals.get('away') or {}).get('team_id')) or 'missing'}`  ·  "
            f"**Home logo ID:** `{_clean((visuals.get('home') or {}).get('team_id')) or 'missing'}`"
        )
        st.caption(
            f"Schedule: {schedule_diag.get('version') or 'unknown'} • Team adapter: {runtime_diag.get('version') or MODEL_VERSION} • Frozen model team diagnostics retained: {bool(model_team_diag)}"
        )
        deep_error = _clean(runtime_diag.get("deep_reconciliation_error"))
        if deep_error:
            st.code(deep_error)

    st.markdown("#### 🏆 Strongest qualified Game Totals")
    scan_key = f"cfb_v151_top5_{selected_day}"
    diag_key = f"cfb_v151_scan_diag_{selected_day}"
    if st.button("🔥 Run Top-5 scan", type="primary", key=f"cfb_v151_scan_{selected_day}"):
        with st.spinner("Running frozen Step-11/12 math with current team evidence…"):
            rows, diag = _scan(games, selected_day)
            st.session_state[scan_key] = frozen_page.final_model.rank_slate(rows, limit=5)
            st.session_state[diag_key] = diag

    top5 = st.session_state.get(scan_key) or []
    diag = st.session_state.get(diag_key) or {}
    if top5:
        for row in top5:
            st.markdown(frozen_page._top_card(row), unsafe_allow_html=True)
    elif diag:
        st.info(
            f"{int(diag.get('games_analyzed') or 0)} analyzed • {int(diag.get('final_ready') or 0)} final-ready • "
            f"{int(diag.get('qualified_forecasts') or 0)} qualified. No fake Top-5 is forced."
        )
    else:
        st.caption("Tap once to scan the whole verified slate. The page stays compact until you ask for it.")

    st.caption("V151 recovery layer • frozen Game Total formulas/thresholds unchanged • sportsbook projection influence 0.0%")


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"V151 Game Total page received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_GAME_TOTAL_HUB",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "RUNTIME_TEAM_DATA",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_record",
    "_runtime_game_with_ids",
    "render_cfb_hub",
    "render_game_total_hub",
]
