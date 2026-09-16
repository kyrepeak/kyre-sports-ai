"""CFB Game Total Clean Page V4 — completed-game team stats.

Additive over frozen/closed V3 identity work. The certified Game Total model is
still evaluated first on the original selected game. V4 then reconciles only a
copied display object through the Game-Total-only runtime adapter and derives
visible record/scoring/split/SOS evidence from completed games. Empty evidence
fails closed to CHECK instead of showing a synthetic 0-0.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
import re
from statistics import fmean
from typing import Any, Mapping

import streamlit as st

import cfb_game_total_clean_page_v3 as prior
import cfb_game_total_runtime_display_v1 as runtime_display

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V4 • V152 COMPLETED GAME STATS"
MARKET = "Game Total"
FROZEN_GAME_TOTAL_HUB = "cfb_game_total_hub_v3"
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v3"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

frozen_page = prior.frozen_page
logo_v3 = prior.logo_v3

_V152_STATS_CSS = r"""
<style>
.gt152-stats{margin:9px 0 10px}.gt152-statsline{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:0 2px 6px}.gt152-statsline b{color:#edf5fb;font-size:.58rem;font-weight:950;letter-spacing:.07em}.gt152-statsline span{color:#7e91a2;font-size:.34rem}.gt152-statsgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.gt152-statteam{border:1px solid rgba(92,156,211,.20);border-radius:15px;background:linear-gradient(145deg,#091723,#0a131e);padding:10px;min-width:0}.gt152-stathead{display:flex;align-items:center;justify-content:space-between;gap:8px}.gt152-statname{color:#f5f9fc;font-size:.76rem;font-weight:950;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.gt152-statrecord{padding:4px 7px;border-radius:999px;background:rgba(83,57,139,.30);border:1px solid rgba(170,125,255,.32);color:#d5c2ff;font-size:.43rem;font-weight:950;white-space:nowrap}.gt152-quality{padding:3px 6px;border-radius:999px;font-size:.31rem;font-weight:950}.gt152-quality.green{color:#9cf0c2;border:1px solid rgba(60,207,137,.32);background:rgba(20,91,61,.20)}.gt152-quality.check{color:#f2d582;border:1px solid rgba(244,191,77,.34);background:rgba(95,68,19,.20)}.gt152-statmetrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin-top:8px}.gt152-statmetric{border:1px solid rgba(134,154,173,.12);border-radius:9px;background:#0b1823;padding:7px 6px;min-width:0}.gt152-statmetric b{display:block;color:#e8f0f6;font-size:.57rem;line-height:1.15;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.gt152-statmetric span{display:block;color:#71869a;font-size:.25rem;font-weight:850;text-transform:uppercase;margin-top:3px;line-height:1.25}.gt152-statfoot{display:flex;flex-wrap:wrap;gap:5px;margin-top:7px}.gt152-statchip{padding:3px 6px;border-radius:7px;background:#0d1b27;border:1px solid rgba(119,139,159,.14);color:#9fb0bf;font-size:.29rem}.gt152-statsource{margin-top:7px;color:#75899a;font-size:.30rem;line-height:1.4;overflow-wrap:anywhere}.gt152-statsource strong{color:#91e4ba}
@media(max-width:760px){.gt152-statsgrid{grid-template-columns:1fr}.gt152-statmetrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _score_points(row: Mapping[str, Any]) -> tuple[float | None, float | None]:
    direct_for = _float(row.get("points_for"))
    direct_against = _float(row.get("points_against"))
    if direct_for is not None and direct_against is not None:
        return direct_for, direct_against

    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*", _clean(row.get("score")))
    if not match:
        return None, None
    return float(match.group(1)), float(match.group(2))


def _result(row: Mapping[str, Any], points_for: float | None, points_against: float | None) -> str:
    explicit = _clean(row.get("result")).upper()
    if explicit in {"W", "L", "T"}:
        return explicit
    if points_for is None or points_against is None:
        return ""
    return "W" if points_for > points_against else "L" if points_for < points_against else "T"


def _record_label(results: list[str]) -> str:
    if not results:
        return "—"
    wins = sum(1 for result in results if result == "W")
    losses = sum(1 for result in results if result == "L")
    ties = sum(1 for result in results if result == "T")
    return f"{wins}-{losses}" + (f"-{ties}" if ties else "")


def _team_stats_state(
    profile: Mapping[str, Any],
    game: Mapping[str, Any],
    side: str,
) -> dict[str, Any]:
    """Build display-only current-team stats from verified completed-game rows."""
    rows = [dict(row) for row in (profile.get("completed_games") or []) if isinstance(row, Mapping)]
    normalized: list[dict[str, Any]] = []
    for row in rows:
        points_for, points_against = _score_points(row)
        result = _result(row, points_for, points_against)
        if not result and points_for is None and points_against is None:
            continue
        normalized.append(
            {
                **row,
                "points_for": points_for,
                "points_against": points_against,
                "result": result,
                "location": _clean(row.get("location")).lower(),
            }
        )

    team = _clean(profile.get("team")) or _clean(game.get(f"{side}_team")) or side.title()
    source = _clean(profile.get("data_source")) or "Completed-game evidence"
    if not normalized:
        return {
            "team": team,
            "record": "—",
            "ppg": None,
            "allowed_pg": None,
            "point_diff_pg": None,
            "recent_form": "—",
            "recent_ppg": None,
            "recent_allowed_pg": None,
            "home_split": "—",
            "away_split": "—",
            "neutral_split": "—",
            "sos_opponent_win_pct": None,
            "sos_coverage": None,
            "sample_games": 0,
            "quality": "CHECK",
            "source": source,
        }

    results = [row["result"] for row in normalized if row.get("result") in {"W", "L", "T"}]
    scored = [
        row
        for row in normalized
        if row.get("points_for") is not None and row.get("points_against") is not None
    ]
    recent = normalized[-5:]
    recent_scored = [
        row
        for row in recent
        if row.get("points_for") is not None and row.get("points_against") is not None
    ]

    ppg = float(fmean([float(row["points_for"]) for row in scored])) if scored else _float(profile.get("ppg"))
    allowed_pg = (
        float(fmean([float(row["points_against"]) for row in scored]))
        if scored
        else _float(profile.get("points_allowed_pg"))
    )
    point_diff_pg = (
        ppg - allowed_pg
        if ppg is not None and allowed_pg is not None
        else _float(profile.get("point_diff_pg"))
    )
    recent_ppg = (
        float(fmean([float(row["points_for"]) for row in recent_scored]))
        if recent_scored
        else _float(profile.get("recent_ppg"))
    )
    recent_allowed_pg = (
        float(fmean([float(row["points_against"]) for row in recent_scored]))
        if recent_scored
        else _float(profile.get("recent_points_allowed_pg"))
    )

    home_results = [row["result"] for row in normalized if row.get("location") == "home" and row.get("result")]
    away_results = [row["result"] for row in normalized if row.get("location") == "away" and row.get("result")]
    neutral_results = [row["result"] for row in normalized if row.get("location") == "neutral" and row.get("result")]

    opp_pcts = [
        value
        for value in (_float(row.get("opponent_record_pct")) for row in normalized)
        if value is not None
    ]
    if opp_pcts:
        sos_opponent_win_pct = float(fmean(opp_pcts))
        sos_coverage = len(opp_pcts) / len(normalized)
    else:
        sos_opponent_win_pct = _float(profile.get("sos_opponent_win_pct"))
        sos_coverage = _float(profile.get("sos_coverage"))

    quality = "GREEN" if results and ppg is not None and allowed_pg is not None else "CHECK"
    return {
        "team": team,
        "record": _record_label(results),
        "ppg": ppg,
        "allowed_pg": allowed_pg,
        "point_diff_pg": point_diff_pg,
        "recent_form": "".join(row["result"] for row in recent if row.get("result")) or "—",
        "recent_ppg": recent_ppg,
        "recent_allowed_pg": recent_allowed_pg,
        "home_split": _record_label(home_results),
        "away_split": _record_label(away_results),
        "neutral_split": _record_label(neutral_results),
        "sos_opponent_win_pct": sos_opponent_win_pct,
        "sos_coverage": sos_coverage,
        "sample_games": len(normalized),
        "quality": quality,
        "source": source,
    }


def _num(value: Any, digits: int = 1) -> str:
    numeric = _float(value)
    return "—" if numeric is None else f"{numeric:.{digits}f}"


def _pct(value: Any) -> str:
    numeric = _float(value)
    return "—" if numeric is None else f"{numeric * 100:.0f}%"


def _stats_team_card(state: Mapping[str, Any]) -> str:
    quality = _clean(state.get("quality")) or "CHECK"
    quality_class = "green" if quality == "GREEN" else "check"
    return f"""
<div class="gt152-statteam" data-testid="gt152-team-stats-{escape(_clean(state.get('team')).lower().replace(' ', '-'))}">
  <div class="gt152-stathead">
    <div class="gt152-statname">{escape(_clean(state.get('team')))}</div>
    <div style="display:flex;gap:5px;align-items:center"><div class="gt152-statrecord">{escape(_clean(state.get('record')))}</div><div class="gt152-quality {quality_class}">{escape(quality)}</div></div>
  </div>
  <div class="gt152-statmetrics">
    <div class="gt152-statmetric"><b>{escape(_num(state.get('ppg')))}</b><span>PPG</span></div>
    <div class="gt152-statmetric"><b>{escape(_num(state.get('allowed_pg')))}</b><span>ALLOWED / GAME</span></div>
    <div class="gt152-statmetric"><b>{escape(_num(state.get('point_diff_pg')))}</b><span>POINT DIFF / GAME</span></div>
    <div class="gt152-statmetric"><b>{escape(_clean(state.get('recent_form')) or '—')}</b><span>RECENT FORM</span></div>
  </div>
  <div class="gt152-statfoot">
    <span class="gt152-statchip">Home {escape(_clean(state.get('home_split')))}</span>
    <span class="gt152-statchip">Away {escape(_clean(state.get('away_split')))}</span>
    <span class="gt152-statchip">Recent PPG {_num(state.get('recent_ppg'))}</span>
    <span class="gt152-statchip">Recent allowed {_num(state.get('recent_allowed_pg'))}</span>
    <span class="gt152-statchip">SOS opp win {_pct(state.get('sos_opponent_win_pct'))}</span>
    <span class="gt152-statchip">SOS coverage {_pct(state.get('sos_coverage'))}</span>
    <span class="gt152-statchip">Sample {int(state.get('sample_games') or 0)} games</span>
  </div>
  <div class="gt152-statsource"><strong>DATA SOURCE</strong> • {escape(_clean(state.get('source')))}</div>
</div>
"""


def _stats_panel(away: Mapping[str, Any], home: Mapping[str, Any]) -> str:
    return f"""
<div class="gt152-stats" data-testid="gt152-team-stats-panel">
  <div class="gt152-statsline"><b>📈 CURRENT TEAM SAMPLE</b><span>Completed games only • display evidence</span></div>
  <div class="gt152-statsgrid">{_stats_team_card(away)}{_stats_team_card(home)}</div>
</div>
"""


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    st.markdown(
        prior.prior.prior._CSS + prior.prior._V151_CSS + prior._V152_IDENTITY_CSS + _V152_STATS_CSS,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
<div class="gt151-head">
  <div class="gt151-kicker">CFB GAME TOTAL • V152 PRODUCTION ACTIVE • CURRENT TEAM STATS</div>
  <div class="gt151-title">🏁 College Football Game Total • Monster Dashboard</div>
  <div class="gt151-sub">Exact identity plus completed-game records and scoring evidence. Frozen Step-11/12 Game Total math remains untouched.</div>
  <div class="gt151-chips"><span class="gt151-chip live">V152 PRODUCTION ACTIVE ✅</span><span class="gt151-chip purple">FROZEN MODEL ✅</span><span class="gt151-chip live">EXACT-ID LOGOS</span><span class="gt151-chip live">COMPLETED-GAME STATS</span><span class="gt151-chip amber">SPORTSBOOK 0.0%</span></div>
</div>
""",
        unsafe_allow_html=True,
    )

    selected = st.date_input(
        "📅 CFB Game Total slate date",
        value=datetime.now(prior.prior.prior._PHOENIX).date(),
        key="cfb_v152_game_total_date",
    )
    selected_day = selected.isoformat()
    games, schedule_diag = frozen_page.frozen_v2.frozen_v1.schedule.load_with_diagnostics(selected_day)
    st.markdown(
        frozen_page.frozen_v2.frozen_v1.identity_ui._diagnostic_badges(schedule_diag),
        unsafe_allow_html=True,
    )
    if not games:
        st.warning("No verified FBS-scoped games were returned for this date. V152 fails closed—no Game Total forecast is invented.")
        return

    index = st.selectbox(
        "🏟️ Game Total matchup",
        options=list(range(len(games))),
        format_func=lambda i: frozen_page.frozen_v2.frozen_v1.identity_ui._matchup_label(games[int(i)]),
        key=f"cfb_v152_game_total_matchup_{selected_day}",
    )
    game = games[int(index)]

    # FROZEN MODEL PATH: always runs on the untouched selected game first.
    selected_result = frozen_page.slate.analyze_game(game, selected_day)
    frozen_away = selected_result.get("away") or {}
    frozen_home = selected_result.get("home") or {}
    raw = selected_result.get("raw") or {}
    final = selected_result.get("final") or {}

    # DISPLAY-ONLY PATH: copied game + Game-Total-only evidence overlay.
    display_game, display_away, display_home, display_diag = runtime_display.reconcile_display_bundle(
        game,
        selected_day,
        frozen_away,
        frozen_home,
    )
    visuals = logo_v3.resolve_visuals(display_game)
    identity = prior._identity_state(display_game, display_away, display_home, visuals)
    away_stats = _team_stats_state(display_away, display_game, "away")
    home_stats = _team_stats_state(display_home, display_game, "home")

    st.markdown(prior._identity_panel(identity), unsafe_allow_html=True)
    st.markdown(prior.prior.prior._quick_read(raw, final), unsafe_allow_html=True)
    st.markdown(_stats_panel(away_stats, home_stats), unsafe_allow_html=True)
    prior.prior._evidence_locker(display_game, display_away, display_home, display_diag)
    st.markdown(prior.prior.prior._status_cards(raw, final), unsafe_allow_html=True)

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
        scan_key = f"cfb_v152_top5_{selected_day}"
        diag_key = f"cfb_v152_scan_diag_{selected_day}"
        if st.button(
            "Run final Game Total Top-5 scan",
            type="primary",
            key=f"cfb_v152_scan_button_{selected_day}",
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
            st.warning("No game cleared the frozen Step-12 qualification thresholds. V152 will not force a Top-5.")
        else:
            st.caption("Run the final slate scan to rank the strongest qualified Game Total forecasts.")

    st.caption("🛡️ V152 completed-game display evidence only • frozen Game Total math preserved • sportsbook projection influence 0.0%")


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"V152 Game Total V4 page received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_GAME_TOTAL_HUB",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_team_stats_state",
    "render_cfb_hub",
    "render_game_total_hub",
]
