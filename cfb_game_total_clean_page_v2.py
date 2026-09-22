"""CFB Game Total Clean Page V2 — live evidence + compact Monster dashboard.

Additive presentation/data-reconciliation layer over the permanently frozen
Game Total Hub V3 and the already-certified V150 compact presentation.

The frozen Game Total analysis always runs first on the original certified game
object. A COPY is then passed through the existing CFB runtime reconciliation
adapter strictly for user-visible records, team identity/logos, venue,
broadcast and evidence. The reconciled copy cannot flow back into frozen
Step-11/Step-12 calculations.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Mapping

import streamlit as st

import cfb_game_total_clean_page_v1 as prior
import cfb_game_total_hub_v3 as frozen_page
import cfb_over_under_logo_resolver_v3 as logo_v3
import cfb_over_under_runtime_team_data_v1 as runtime_display

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V2 • LIVE EVIDENCE MONSTER DASHBOARD"
MARKET = "Game Total"
FROZEN_GAME_TOTAL_HUB = "cfb_game_total_hub_v3"
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False


_V151_CSS = r"""
<style>
.gt151-head{margin:8px 0 10px;padding:12px 14px;border:1px solid rgba(168,116,255,.32);border-radius:18px;background:radial-gradient(circle at 95% 0%,rgba(112,65,210,.20),transparent 22rem),linear-gradient(145deg,#07111d,#0a1421)}
.gt151-kicker{color:#c1aaff;font-size:.58rem;font-weight:950;letter-spacing:.10em;text-transform:uppercase}.gt151-title{color:#f7fbff;font-size:1.35rem;font-weight:950;letter-spacing:-.025em;margin-top:3px}.gt151-sub{color:#91a3b5;font-size:.62rem;line-height:1.45;margin-top:4px}.gt151-chips{display:flex;flex-wrap:wrap;gap:5px;margin-top:8px}.gt151-chip{padding:4px 7px;border-radius:999px;border:1px solid rgba(115,138,160,.24);background:#0b1926;color:#a9b9c8;font-size:.36rem;font-weight:900}.gt151-chip.live{border-color:rgba(60,207,137,.40);background:rgba(20,91,61,.24);color:#9cf0c2}.gt151-chip.purple{border-color:rgba(168,116,255,.40);background:rgba(74,42,127,.25);color:#d0b9ff}.gt151-chip.amber{border-color:rgba(244,191,77,.36);background:rgba(95,68,19,.24);color:#f2d582}
.gt151-evidence{margin-top:10px}.gt151-sectionline{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:0 2px 6px}.gt151-sectionline b{color:#edf5fb;font-size:.58rem;font-weight:950;letter-spacing:.07em}.gt151-sectionline span{color:#7e91a2;font-size:.34rem}.gt151-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.gt151-team{border:1px solid rgba(92,156,211,.20);border-radius:15px;background:linear-gradient(145deg,#091723,#0a131e);padding:10px;min-width:0}.gt151-teamhead{display:flex;align-items:center;justify-content:space-between;gap:8px}.gt151-teamname{color:#f5f9fc;font-size:.78rem;font-weight:950;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.gt151-record{padding:4px 7px;border-radius:999px;background:rgba(83,57,139,.30);border:1px solid rgba(170,125,255,.32);color:#d5c2ff;font-size:.43rem;font-weight:950;white-space:nowrap}.gt151-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin-top:8px}.gt151-metric{border:1px solid rgba(134,154,173,.12);border-radius:9px;background:#0b1823;padding:7px 6px;min-width:0}.gt151-metric b{display:block;color:#e8f0f6;font-size:.58rem;line-height:1.15;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.gt151-metric span{display:block;color:#71869a;font-size:.27rem;font-weight:850;text-transform:uppercase;margin-top:3px;line-height:1.25}.gt151-source{margin-top:7px;color:#75899a;font-size:.31rem;line-height:1.4;overflow-wrap:anywhere}.gt151-source strong{color:#91e4ba}.gt151-warning{margin-top:7px;padding:7px 9px;border-left:3px solid #f0b94d;border-radius:0 9px 9px 0;background:rgba(104,74,18,.18);color:#d9c48e;font-size:.34rem;line-height:1.45}
.gt151-results{display:flex;flex-wrap:wrap;gap:4px;margin-top:6px}.gt151-result{padding:3px 6px;border-radius:7px;background:#0d1b27;border:1px solid rgba(119,139,159,.14);color:#9fb0bf;font-size:.30rem}.gt151-result.win{color:#99eabe;border-color:rgba(60,207,137,.22)}.gt151-result.loss{color:#ffadb3;border-color:rgba(255,104,112,.22)}
@media(max-width:760px){.gt151-head{padding:10px}.gt151-title{font-size:1.15rem}.gt151-grid{grid-template-columns:1fr}.gt151-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any, digits: int = 1) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return "—"


def _record(profile: Mapping[str, Any], game: Mapping[str, Any], side: str, verified: bool) -> str:
    event = _clean(game.get(f"{side}_record_summary"))
    text = _clean(profile.get("record_text"))
    if event:
        return event
    if text and (verified or text != "0-0"):
        return text
    return "—"


def _data_source(profile: Mapping[str, Any], display_diag: Mapping[str, Any]) -> str:
    if display_diag.get("runtime_snapshot_used"):
        return "Verified runtime snapshot"
    if display_diag.get("deep_reconciliation_ok"):
        return "Live ESPN reconciliation"
    return _clean(profile.get("data_source")) or "Current evidence unavailable"


def _recent_results(profile: Mapping[str, Any]) -> str:
    rows = profile.get("completed_games") or []
    chips: list[str] = []
    for row in rows[-5:]:
        if not isinstance(row, Mapping):
            continue
        result = _clean(row.get("result"))
        if not result:
            pf = row.get("points_for")
            pa = row.get("points_against")
            try:
                result = "W" if float(pf) > float(pa) else "L" if float(pf) < float(pa) else "T"
            except Exception:
                result = ""
        opp = _clean(row.get("opponent")) or _clean(row.get("opponent_name")) or "Opponent"
        score = _clean(row.get("score"))
        klass = "win" if result == "W" else "loss" if result == "L" else ""
        label = " ".join(x for x in (result, score, opp) if x)
        if label:
            chips.append(f'<span class="gt151-result {klass}">{escape(label)}</span>')
    return "".join(chips) or '<span class="gt151-result">Recent results unavailable</span>'


def _display_bundle(
    game: Mapping[str, Any],
    selected_day: str,
    frozen_away: Mapping[str, Any],
    frozen_home: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Reconcile a copy for display only; frozen model inputs never receive it."""
    safe_game = dict(game)
    try:
        display_game, display_away, display_home, display_diag = runtime_display.reconcile_runtime(
            safe_game,
            selected_day,
        )
        display_game = dict(display_game or safe_game)
        display_away = dict(display_away or frozen_away)
        display_home = dict(display_home or frozen_home)
        display_diag = dict(display_diag or {})

        # Deep reconciliation stores exact ESPN IDs on the reconciled profiles.
        # Promote only those exact numeric IDs into the DISPLAY game copy so the
        # strict V3 logo resolver can render without fuzzy/name-based matching.
        for side, profile in (("away", display_away), ("home", display_home)):
            team_id = _clean(profile.get("espn_team_id"))
            if team_id.isdigit():
                display_game[f"{side}_espn_team_id"] = team_id

        return display_game, display_away, display_home, display_diag
    except Exception as exc:
        fallback = prior._display_game(safe_game)
        return (
            fallback,
            dict(frozen_away),
            dict(frozen_home),
            {
                "runtime_status": "PARTIAL",
                "runtime_snapshot_used": False,
                "deep_reconciliation_ok": False,
                "runtime_issues": [f"display reconciliation failed: {type(exc).__name__}"],
            },
        )


def _team_evidence_card(
    profile: Mapping[str, Any],
    game: Mapping[str, Any],
    side: str,
    display_diag: Mapping[str, Any],
) -> str:
    name = _clean(profile.get("team")) or _clean(game.get(f"{side}_team")) or side.title()
    verified = bool(display_diag.get("runtime_snapshot_used") or display_diag.get("deep_reconciliation_ok"))
    record = _record(profile, game, side, verified)
    recent = _clean(profile.get("recent_form")) or "—"
    source = _data_source(profile, display_diag)
    return f"""
<div class="gt151-team">
  <div class="gt151-teamhead"><div class="gt151-teamname">{escape(name)}</div><div class="gt151-record">{escape(record)}</div></div>
  <div class="gt151-metrics">
    <div class="gt151-metric"><b>{escape(_num(profile.get('ppg')))}</b><span>PPG</span></div>
    <div class="gt151-metric"><b>{escape(_num(profile.get('points_allowed_pg')))}</b><span>ALLOWED / GAME</span></div>
    <div class="gt151-metric"><b>{escape(_num(profile.get('point_diff_pg')))}</b><span>POINT DIFF / GAME</span></div>
    <div class="gt151-metric"><b>{escape(recent)}</b><span>RECENT FORM</span></div>
  </div>
  <div class="gt151-results">{_recent_results(profile)}</div>
  <div class="gt151-source"><strong>DATA SOURCE</strong> • {escape(source)}</div>
</div>
"""


def _live_evidence(
    display_game: Mapping[str, Any],
    display_away: Mapping[str, Any],
    display_home: Mapping[str, Any],
    display_diag: Mapping[str, Any],
) -> str:
    issues = [str(x) for x in display_diag.get("runtime_issues") or [] if str(x).strip()]
    warning = ""
    if issues:
        warning = '<div class="gt151-warning">⚠️ ' + escape(" • ".join(issues)) + "</div>"
    return f"""
<div class="gt151-evidence">
  <div class="gt151-sectionline"><b>🔎 LIVE TEAM EVIDENCE</b><span>Visible even when the forecast gate is closed</span></div>
  <div class="gt151-grid">
    {_team_evidence_card(display_away, display_game, 'away', display_diag)}
    {_team_evidence_card(display_home, display_game, 'home', display_diag)}
  </div>
  {warning}
</div>
"""


def _evidence_locker(
    display_game: Mapping[str, Any],
    display_away: Mapping[str, Any],
    display_home: Mapping[str, Any],
    display_diag: Mapping[str, Any],
) -> None:
    with st.expander("🧰 Evidence locker • records, identity & sources", expanded=False):
        visuals = logo_v3.resolve_visuals(display_game)
        left, right = st.columns(2)
        for col, side, profile in (
            (left, "away", display_away),
            (right, "home", display_home),
        ):
            visual = visuals.get(side) or {}
            with col:
                st.markdown(f"**{_clean(profile.get('team')) or _clean(display_game.get(f'{side}_team')) or side.title()}**")
                st.caption(
                    f"Record: {_record(profile, display_game, side, bool(display_diag.get('runtime_snapshot_used') or display_diag.get('deep_reconciliation_ok')))} • "
                    f"ESPN team ID: {_clean(visual.get('team_id')) or 'unavailable'} • "
                    f"logo identity: {_clean(visual.get('resolution_method')) or 'unavailable'}"
                )
                st.caption(f"Source: {_data_source(profile, display_diag)}")
        st.caption(
            "Runtime evidence status: "
            + (_clean(display_diag.get("runtime_status")) or "UNKNOWN")
            + " • frozen Game Total calculation inputs remain unchanged."
        )


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    st.markdown(prior._CSS + _V151_CSS, unsafe_allow_html=True)
    st.markdown(
        """
<div class="gt151-head">
  <div class="gt151-kicker">CFB GAME TOTAL • MONSTER DASHBOARD • V151 LIVE EVIDENCE</div>
  <div class="gt151-title">🏁 College Football Game Total • Monster Dashboard</div>
  <div class="gt151-sub">Compact first. Current team evidence is reconciled live for display while the certified Step-11/12 Game Total math stays frozen.</div>
  <div class="gt151-chips"><span class="gt151-chip live">LIVE EVIDENCE ✅</span><span class="gt151-chip purple">FROZEN MODEL ✅</span><span class="gt151-chip live">EXACT-ID LOGOS ✅</span><span class="gt151-chip">PHOENIX TIME ✅</span><span class="gt151-chip amber">SPORTSBOOK 0.0%</span></div>
</div>
""",
        unsafe_allow_html=True,
    )

    selected = st.date_input(
        "📅 CFB Game Total slate date",
        value=datetime.now(prior._PHOENIX).date(),
        key="cfb_v151_game_total_date",
    )
    selected_day = selected.isoformat()

    games, schedule_diag = frozen_page.frozen_v2.frozen_v1.schedule.load_with_diagnostics(selected_day)
    st.markdown(
        frozen_page.frozen_v2.frozen_v1.identity_ui._diagnostic_badges(schedule_diag),
        unsafe_allow_html=True,
    )
    if not games:
        st.warning("No verified FBS-scoped games were returned for this date. V151 fails closed—no Game Total forecast is invented.")
        return

    index = st.selectbox(
        "🏟️ Game Total matchup",
        options=list(range(len(games))),
        format_func=lambda i: frozen_page.frozen_v2.frozen_v1.identity_ui._matchup_label(games[int(i)]),
        key=f"cfb_v151_game_total_matchup_{selected_day}",
    )
    game = games[int(index)]

    # CERTIFIED MODEL PATH: original game only. Do not move display reconciliation above this line.
    selected_result = frozen_page.slate.analyze_game(game, selected_day)
    frozen_away = selected_result.get("away") or {}
    frozen_home = selected_result.get("home") or {}
    raw = selected_result.get("raw") or {}
    final = selected_result.get("final") or {}

    # DISPLAY PATH: reconcile a copy only. This repairs records, IDs/logos and evidence.
    display_game, display_away, display_home, display_diag = _display_bundle(
        game,
        selected_day,
        frozen_away,
        frozen_home,
    )

    # Resolve once here as an explicit identity contract; prior._hero uses the same exact-ID resolver.
    logo_v3.resolve_visuals(display_game)
    st.markdown(prior._hero(display_game, display_away, display_home), unsafe_allow_html=True)
    st.markdown(prior._quick_read(raw, final), unsafe_allow_html=True)
    st.markdown(_live_evidence(display_game, display_away, display_home, display_diag), unsafe_allow_html=True)
    _evidence_locker(display_game, display_away, display_home, display_diag)
    st.markdown(prior._status_cards(raw, final), unsafe_allow_html=True)

    with st.expander("📊 Deep model evidence • Step 11 distribution", expanded=False):
        st.markdown(frozen_page.frozen_v2._distribution_card(raw), unsafe_allow_html=True)
        for panel in (
            frozen_page.frozen_v2._band_panel(raw),
            frozen_page.frozen_v2._around_projection_panel(raw),
            frozen_page.frozen_v2._exact_panel(raw),
            frozen_page.frozen_v2._components_panel(raw),
        ):
            if panel:
                st.markdown(panel, unsafe_allow_html=True)

    with st.expander("🏁 Deep model evidence • Step 12 final synthesis", expanded=False):
        st.markdown(frozen_page._final_card(game, final), unsafe_allow_html=True)

    with st.expander("🏆 Top-5 slate scanner", expanded=False):
        scan_key = f"cfb_v151_top5_{selected_day}"
        diag_key = f"cfb_v151_scan_diag_{selected_day}"
        if st.button(
            "Run final Game Total Top-5 scan",
            type="primary",
            key=f"cfb_v151_scan_button_{selected_day}",
        ):
            with st.spinner("Scanning the verified CFB slate through frozen Steps 11–12..."):
                rows, diag = frozen_page.slate.scan_slate(games, selected_day)
                st.session_state[scan_key] = frozen_page.final_model.rank_slate(rows, limit=5)
                st.session_state[diag_key] = diag

        top5 = st.session_state.get(scan_key) or []
        diag = st.session_state.get(diag_key) or {}
        if diag:
            st.caption(
                f"Final scanner: {int(diag.get('games_analyzed') or 0)} analyzed • "
                f"{int(diag.get('final_ready') or 0)} final-ready • "
                f"{int(diag.get('qualified_forecasts') or 0)} ranked-eligible • "
                f"{len(diag.get('errors') or [])} errors"
            )
        if top5:
            for row in top5:
                st.markdown(frozen_page._top_card(row), unsafe_allow_html=True)
        elif diag:
            st.warning("No game cleared the frozen Step-12 qualification thresholds. V151 will not force a Top-5.")
        else:
            st.caption("Run the final slate scan to rank the strongest qualified Game Total forecasts.")

    st.caption("🛡️ V151 display reconciliation only • frozen Game Total math preserved • sportsbook projection influence 0.0%")


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"V151 Game Total page received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_GAME_TOTAL_HUB",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_display_bundle",
    "render_cfb_hub",
    "render_game_total_hub",
]
