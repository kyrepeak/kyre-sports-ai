"""College Football hub V3 — Step 3 team data foundation.

Additive wrapper over permanently frozen CFB Hub V2.

Step 3 adds verified team context beneath the Step 2 matchup identity:
- season record
- scoring offense / scoring defense baseline
- point differential
- home / away / neutral splits
- recent five-game form
- opponent-win-percentage schedule strength context
- NCAA team-stat enrichment
- AP ranking context
- explicit data-quality readiness

No CFB win probability, projected score, sportsbook total, fair odds, pick
ranking, Monte Carlo, or calibration output is generated in this step.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import streamlit as st

import cfb_hub_v2 as frozen_v2
import cfb_schedule_v1 as schedule
import cfb_team_data_v1 as team_data

MODEL_VERSION = "CFB HUB V3 • STEP 3 TEAM DATA FOUNDATION"
FROZEN_CFB_HUB = "cfb_hub_v2"
CFB_MARKETS = list(frozen_v2.CFB_MARKETS)

_ET = ZoneInfo("America/New_York")

_PAGE_META = {
    "Moneyline": ("🏆", "College Football Moneyline", "Team-strength evidence foundation. No win probability yet."),
    "Over/Under": ("↕️", "College Football Over/Under", "Scoring-environment evidence foundation. No total probability yet."),
    "Game Total": ("🧮", "College Football Game Total", "Combined-score inputs foundation. No projected total yet."),
}

_STEP3_CSS = r"""
<style>
.cfb3-section{margin-top:12px;border:1px solid rgba(126,231,180,.24);border-radius:16px;
background:linear-gradient(145deg,#071912,#08151d);padding:13px}
.cfb3-title{color:#83e7b6;font-size:.67rem;font-weight:950;letter-spacing:.09em;text-transform:uppercase}
.cfb3-sub{color:#8fa8a0;font-size:.56rem;margin-top:3px}
.cfb3-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}
.cfb3-team{border:1px solid rgba(91,140,166,.22);border-radius:14px;background:#08141d;overflow:hidden}
.cfb3-team-head{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:10px 11px;
border-bottom:1px solid rgba(91,140,166,.18)}
.cfb3-name{min-width:0}.cfb3-name .rank{color:#6fe0ff;font-size:.52rem;font-weight:900;text-transform:uppercase}
.cfb3-name b{display:block;color:#f5fbff;font-size:.92rem;line-height:1.15;margin-top:1px}
.cfb3-name span{color:#7f98a9;font-size:.52rem;font-weight:800;text-transform:uppercase}
.cfb3-quality{border:1px solid #445562;border-radius:999px;padding:5px 8px;font-size:.48rem;font-weight:950}
.cfb3-quality.ready{border-color:#277353;background:#0a3024;color:#83e7b6}
.cfb3-quality.limited{border-color:#77611c;background:#342b0d;color:#f5db73}
.cfb3-quality.check{border-color:#7a3838;background:#341515;color:#ffaaa5}
.cfb3-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;padding:10px 11px}
.cfb3-metric{border:1px solid rgba(91,140,166,.17);border-radius:9px;background:#0a1822;padding:7px 7px}
.cfb3-metric strong{display:block;color:#f0f6fa;font-size:.72rem;line-height:1.05}
.cfb3-metric span{display:block;color:#7f96a5;font-size:.44rem;text-transform:uppercase;letter-spacing:.04em;margin-top:3px}
.cfb3-detail{display:grid;grid-template-columns:1fr 1fr;gap:6px;padding:0 11px 10px}
.cfb3-item{border:1px solid rgba(91,140,166,.16);border-radius:9px;background:#07131c;padding:7px;
color:#a6bac6;font-size:.52rem;line-height:1.35}
.cfb3-item strong{display:block;color:#dfeaf0;font-size:.45rem;text-transform:uppercase;letter-spacing:.05em;margin-bottom:2px}
.cfb3-stats{padding:0 11px 10px}
.cfb3-statrow{display:flex;justify-content:space-between;gap:8px;padding:5px 0;border-top:1px solid rgba(91,140,166,.13);
color:#8fa4b2;font-size:.50rem}
.cfb3-statrow b{color:#d8e6ed}
.cfb3-source{padding:8px 11px;border-top:1px solid rgba(91,140,166,.16);color:#69818f;font-size:.44rem;line-height:1.4}
.cfb3-dq{display:flex;flex-wrap:wrap;gap:5px;margin-top:8px}
.cfb3-chip{border:1px solid #2e4656;border-radius:999px;background:#0a1822;color:#9fb3bf;padding:4px 7px;
font-size:.46rem;font-weight:850}
.cfb3-chip.good{border-color:#277353;background:#0a2a20;color:#83e7b6}
.cfb3-chip.warn{border-color:#77611c;background:#30280d;color:#f0d675}
@media(max-width:760px){
  .cfb3-grid{grid-template-columns:1fr}.cfb3-metrics{grid-template-columns:repeat(3,minmax(0,1fr))}
}
</style>
"""


def _fmt(value: Any, digits: int = 1, suffix: str = "") -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.{digits}f}{suffix}"
    except Exception:
        return escape(str(value))


def _pct(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"{100.0 * float(value):.1f}%"
    except Exception:
        return "—"


def _record_text(record: Mapping[str, Any] | None) -> str:
    if not record:
        return "0-0"
    wins = int(record.get("wins") or 0)
    losses = int(record.get("losses") or 0)
    ties = int(record.get("ties") or 0)
    return f"{wins}-{losses}" + (f"-{ties}" if ties else "")


def _quality_class(grade: str) -> str:
    grade = str(grade or "CHECK").upper()
    if grade == "READY":
        return "ready"
    if grade == "LIMITED":
        return "limited"
    return "check"


def _stat_rows(profile: Mapping[str, Any]) -> str:
    stats = profile.get("official_stats") or {}
    if not stats:
        return (
            '<div class="cfb3-statrow"><span>Official NCAA team-stat enrichment</span>'
            '<b>UNAVAILABLE / LIMITED</b></div>'
        )
    order = (
        "scoring_offense",
        "total_offense",
        "scoring_defense",
        "total_defense",
        "turnover_margin",
    )
    rows = []
    for key in order:
        item = stats.get(key)
        if not item:
            continue
        label = escape(str(item.get("label") or key))
        value = escape(str(item.get("value") or "—"))
        rows.append(f'<div class="cfb3-statrow"><span>{label}</span><b>{value}</b></div>')
    return "".join(rows)


def _quality_chips(profile: Mapping[str, Any]) -> str:
    quality = profile.get("data_quality") or {}
    components = quality.get("components") or {}
    labels = {
        "record": "RECORD",
        "scoring_baseline": "SCORING",
        "recent_form": "RECENT",
        "home_away_splits": "SPLITS",
        "sos": "SOS",
        "official_stats": "NCAA STATS",
        "ranking": "RANK",
    }
    chips = []
    for key, label in labels.items():
        good = bool(components.get(key))
        chips.append(
            f'<span class="cfb3-chip {"good" if good else "warn"}">{label} {"✓" if good else "!"}</span>'
        )
    return "".join(chips)


def _team_card(profile: Mapping[str, Any]) -> str:
    quality = profile.get("data_quality") or {}
    grade = str(quality.get("grade") or "CHECK").upper()
    rank = profile.get("ap_rank")
    rank_text = f"#{int(rank)} AP" if rank is not None else "UNRANKED / RANK N/A"
    name = escape(str(profile.get("team") or "Team"))
    conf = escape(str(profile.get("conference") or "Conference unavailable"))

    return f"""
<div class="cfb3-team">
  <div class="cfb3-team-head">
    <div class="cfb3-name">
      <div class="rank">{escape(rank_text)} • {escape(str(profile.get('rank_source') or 'rank source unavailable'))}</div>
      <b>{name}</b>
      <span>{conf}</span>
    </div>
    <span class="cfb3-quality {_quality_class(grade)}">{escape(grade)}</span>
  </div>
  <div class="cfb3-metrics">
    <div class="cfb3-metric"><strong>{escape(str(profile.get('record_text') or '0-0'))}</strong><span>Season record</span></div>
    <div class="cfb3-metric"><strong>{_fmt(profile.get('ppg'))}</strong><span>Points / game</span></div>
    <div class="cfb3-metric"><strong>{_fmt(profile.get('points_allowed_pg'))}</strong><span>Allowed / game</span></div>
    <div class="cfb3-metric"><strong>{_fmt(profile.get('point_diff_pg'), 1, '')}</strong><span>Point diff / game</span></div>
    <div class="cfb3-metric"><strong>{escape(str(profile.get('recent_form') or '—'))}</strong><span>Last 5 form</span></div>
    <div class="cfb3-metric"><strong>{_pct(profile.get('sos_opponent_win_pct'))}</strong><span>Opp win % (SOS)</span></div>
  </div>
  <div class="cfb3-detail">
    <div class="cfb3-item"><strong>Home split</strong>{escape(_record_text(profile.get('home_record')))}</div>
    <div class="cfb3-item"><strong>Away split</strong>{escape(_record_text(profile.get('away_record')))}</div>
    <div class="cfb3-item"><strong>Neutral split</strong>{escape(_record_text(profile.get('neutral_record')))}</div>
    <div class="cfb3-item"><strong>Recent scoring</strong>{_fmt(profile.get('recent_ppg'))} PF • {_fmt(profile.get('recent_points_allowed_pg'))} PA</div>
    <div class="cfb3-item"><strong>Recent point diff</strong>{_fmt(profile.get('recent_point_diff_pg'))} / game</div>
    <div class="cfb3-item"><strong>SOS coverage</strong>{_pct(profile.get('sos_coverage'))}</div>
  </div>
  <div class="cfb3-stats">
    {_stat_rows(profile)}
    <div class="cfb3-dq">{_quality_chips(profile)}</div>
  </div>
  <div class="cfb3-source">
    Source: {escape(str(profile.get('data_source') or 'source unavailable'))} •
    sample {int((profile.get('record') or {}).get('games') or 0)} completed games •
    evidence only; no Step 3 betting probability adjustment.
  </div>
</div>
"""


def _team_data_diagnostics(diag: Mapping[str, Any]) -> str:
    source_ok = diag.get("schedule_source") != "unavailable"
    stats_ok = diag.get("stats_source") != "unavailable"
    rank_ok = diag.get("ranking_source") != "unavailable"
    return f"""
<div class="cfb3-dq">
  <span class="cfb3-chip {'good' if source_ok else 'warn'}">SEASON SCHEDULE {'✓' if source_ok else '!'}</span>
  <span class="cfb3-chip {'good' if stats_ok else 'warn'}">NCAA TEAM STATS {'✓' if stats_ok else '!'}</span>
  <span class="cfb3-chip {'good' if rank_ok else 'warn'}">AP RANKINGS {'✓' if rank_ok else '!'}</span>
  <span class="cfb3-chip good">{int(diag.get('completed_contests') or 0)} FINAL GAMES INGESTED</span>
  <span class="cfb3-chip good">FUTURE GAME GUARD ACTIVE</span>
</div>
"""


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    """Render frozen Step 2 identity plus additive Step 3 team-data evidence."""
    if market not in CFB_MARKETS:
        st.error(f"Unknown College Football market: {market}")
        return

    icon, title, subtitle = _PAGE_META[market]
    st.caption("🏈 COLLEGE FOOTBALL • Step 3 team data foundation ACTIVE")
    st.markdown(frozen_v2._CSS, unsafe_allow_html=True)
    st.markdown(_STEP3_CSS, unsafe_allow_html=True)

    st.markdown(
        f"""
<div class="cfb2-shell">
  <div class="cfb2-kicker">CFB STEP 3 • TEAM DATA FOUNDATION</div>
  <div class="cfb2-title">{icon} {title}</div>
  <div class="cfb2-sub">{subtitle}</div>
  <div class="cfb2-badges">
    <span class="cfb2-badge good">ROUTE ✅</span>
    <span class="cfb2-badge good">PAGE ✅</span>
    <span class="cfb2-badge good">SCHEDULE + ID ✅</span>
    <span class="cfb2-badge good">TEAM DATA ✅</span>
    <span class="cfb2-badge">MODEL ⏳</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    today_et = datetime.now(_ET).date()
    selected = st.date_input(
        "📅 CFB slate date",
        value=today_et,
        key=f"cfb_step3_date_{market.lower().replace('/', '_').replace(' ', '_')}",
        help="Loads the certified NCAA FBS Step 2 schedule and Step 3 team evidence.",
    )
    selected_day = selected.isoformat()

    games, schedule_diag = schedule.load_with_diagnostics(selected_day)
    st.markdown(frozen_v2._diagnostic_badges(schedule_diag), unsafe_allow_html=True)

    if not games:
        st.warning(
            "No verified FBS games were returned for this date. Team data is not attached "
            "to an unverified matchup, and no projection is invented."
        )
        attempts = frozen_v2._attempt_summary(schedule_diag)
        if attempts:
            with st.expander("Schedule provider diagnostics"):
                st.dataframe(attempts, use_container_width=True, hide_index=True)
        return

    index = st.selectbox(
        "🏟️ Matchup",
        options=list(range(len(games))),
        format_func=lambda i: frozen_v2._matchup_label(games[int(i)]),
        key=f"cfb_step3_matchup_{market.lower().replace('/', '_').replace(' ', '_')}_{selected_day}",
    )
    game = games[int(index)]
    st.markdown(frozen_v2._game_card(game), unsafe_allow_html=True)

    profiles, team_diag = team_data.load_matchup_team_data(game, selected_day)
    away = profiles.get("away") or {}
    home = profiles.get("home") or {}

    st.markdown(
        f"""
<div class="cfb3-section">
  <div class="cfb3-title">STEP 3 • TEAM DATA FOUNDATION</div>
  <div class="cfb3-sub">
    Record, offense/defense scoring baseline, recent form, splits, schedule strength,
    NCAA team stats, rankings, and data-quality evidence. Still no model prediction.
  </div>
  {_team_data_diagnostics(team_diag)}
  <div class="cfb3-grid">
    {_team_card(away)}
    {_team_card(home)}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    with st.expander(f"Full verified slate • {selected_day}"):
        rows = [
            {
                "Matchup": f"{g.get('away_team')} @ {g.get('home_team')}",
                "Kickoff ET": g.get("kickoff_et"),
                "Away conf": g.get("away_conference"),
                "Home conf": g.get("home_conference"),
                "Venue": g.get("venue"),
                "Status": g.get("status"),
                "NCAA ID": g.get("game_id"),
            }
            for g in games
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)

    team_attempts = [
        {
            "Provider": attempt.get("provider"),
            "Transport": attempt.get("transport"),
            "HTTP": attempt.get("http"),
            "Bytes": attempt.get("bytes"),
            "Error": attempt.get("error"),
        }
        for attempt in team_diag.get("attempts") or []
    ]
    if team_attempts:
        with st.expander("Step 3 team-data provider diagnostics"):
            st.dataframe(team_attempts, use_container_width=True, hide_index=True)

    st.info(
        "Step 3 is evidence-only. College Football win probabilities, projected scores, "
        "fair moneylines, Over/Under probabilities, picks, rankings of bets, and Monte Carlo "
        "simulations remain OFF until later certified steps."
    )


__all__ = [
    "CFB_MARKETS",
    "FROZEN_CFB_HUB",
    "MODEL_VERSION",
    "_team_card",
    "_team_data_diagnostics",
    "render_cfb_hub",
]
