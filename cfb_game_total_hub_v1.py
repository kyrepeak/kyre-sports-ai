"""College Football Game Total Hub V1 — Step 10 foundation.

Additive Game Total foundation above permanently frozen CFB Steps 1-9.

Purpose
-------
Activate a dedicated College Football -> Game Total page with verified current
matchup identity and certified scoring evidence prepared specifically for an
independent combined-score distribution model.

Step 10 intentionally does NOT compute or publish:
- projected combined game total,
- total median/mode,
- exact-total or band probabilities,
- percentile distribution,
- sportsbook total/price,
- fair total,
- edge/EV,
- final pick/rank,
- Monte Carlo simulation.

Moneyline and Over/Under remain permanently frozen and unchanged.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import streamlit as st

import cfb_hub_v2 as identity_ui
import cfb_hub_v3 as team_ui
import cfb_schedule_v3 as schedule
import cfb_team_data_v2 as team_data

MODEL_VERSION = "CFB GAME TOTAL HUB V1 • STEP 10 FOUNDATION"
MARKET = "Game Total"
SCHEDULE_PROVIDER = "cfb_schedule_v3"
TEAM_DATA_PROVIDER = "cfb_team_data_v2"

_ET = ZoneInfo("America/New_York")

_CSS = r"""
<style>
.cfb10-shell{border:1px solid rgba(124,181,255,.28);border-radius:17px;
background:linear-gradient(145deg,#081728,#11131d);padding:14px;margin-top:8px}
.cfb10-kicker{color:#83bfff;font-size:.58rem;font-weight:950;letter-spacing:.10em}
.cfb10-title{color:#f4f8ff;font-size:1.45rem;font-weight:950;margin-top:3px}
.cfb10-sub{color:#8ea1b7;font-size:.67rem;line-height:1.45;margin-top:4px}
.cfb10-status{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.cfb10-pill{border:1px solid #334b65;border-radius:999px;background:#0a1b2d;color:#a7c2dc;
padding:5px 8px;font-size:.47rem;font-weight:900}
.cfb10-pill.good{border-color:#326a55;background:#09251c;color:#86e6b8}
.cfb10-pill.wait{border-color:#62511f;background:#2b250c;color:#e6cf78}
.cfb10-hero{margin-top:11px;border:1px solid rgba(124,181,255,.22);border-radius:16px;
background:#0b1420;overflow:hidden}
.cfb10-hero-top{display:flex;justify-content:space-between;gap:8px;align-items:center;
padding:9px 11px;border-bottom:1px solid rgba(124,181,255,.14)}
.cfb10-hero-top b{color:#83bfff;font-size:.50rem;letter-spacing:.08em}
.cfb10-verified{border:1px solid #277353;border-radius:999px;background:#0b2d22;color:#84e7b6;
padding:4px 7px;font-size:.43rem;font-weight:950}
.cfb10-match{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);
gap:9px;align-items:center;padding:14px 12px}
.cfb10-side{min-width:0}.cfb10-side.home{text-align:right}
.cfb10-rank{color:#83bfff;font-size:.48rem;font-weight:900;text-transform:uppercase}
.cfb10-team{color:#f5f8fc;font-size:1.04rem;font-weight:950;line-height:1.12;margin-top:2px}
.cfb10-meta{color:#8191a3;font-size:.48rem;font-weight:800;text-transform:uppercase;margin-top:3px}
.cfb10-at{color:#60758a;font-size:.70rem;font-weight:950}
.cfb10-context{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;
padding:0 12px 12px}
.cfb10-context div{border:1px solid rgba(124,181,255,.12);border-radius:9px;background:#101927;
padding:7px;min-width:0}
.cfb10-context strong{display:block;color:#d8e5f2;font-size:.44rem;text-transform:uppercase;
letter-spacing:.05em}.cfb10-context span{display:block;color:#8fa2b4;font-size:.55rem;margin-top:2px}
.cfb10-ready{margin-top:10px;border:1px solid rgba(126,231,180,.20);border-radius:14px;
background:#071912;padding:10px}
.cfb10-ready-title{color:#83e7b6;font-size:.52rem;font-weight:950;letter-spacing:.08em}
.cfb10-ready-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:7px}
.cfb10-ready-item{border:1px solid rgba(126,231,180,.16);border-radius:9px;background:#081a14;padding:7px}
.cfb10-ready-item b{display:block;color:#e5f7ee;font-size:.62rem}.cfb10-ready-item span{display:block;
color:#78998a;font-size:.43rem;text-transform:uppercase;margin-top:2px}
.cfb10-env{margin-top:10px;border:1px solid rgba(124,181,255,.17);border-radius:14px;background:#0d1724;padding:10px}
.cfb10-env-title{color:#83bfff;font-size:.52rem;font-weight:950;letter-spacing:.08em}
.cfb10-env-sub{color:#8397aa;font-size:.45rem;line-height:1.45;margin-top:3px}
.cfb10-env-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:8px}
.cfb10-metric{border:1px solid rgba(124,181,255,.12);border-radius:9px;background:#111c2a;padding:7px}
.cfb10-metric b{display:block;color:#edf4fb;font-size:.66rem}.cfb10-metric span{display:block;
color:#8297aa;font-size:.42rem;text-transform:uppercase;margin-top:2px}
.cfb10-combined{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:8px}
.cfb10-combined-card{border:1px solid rgba(124,181,255,.13);border-radius:10px;background:#0f1a27;padding:8px}
.cfb10-combined-card strong{display:block;color:#dce9f5;font-size:.47rem;text-transform:uppercase}
.cfb10-combined-card span{display:block;color:#90a6b8;font-size:.55rem;line-height:1.45;margin-top:4px}
.cfb10-locked{margin-top:10px;border:1px solid #62511f;border-radius:13px;background:#2b250c;padding:10px}
.cfb10-locked b{display:block;color:#e9d37c;font-size:.57rem}.cfb10-locked span{display:block;
color:#b5a55f;font-size:.48rem;line-height:1.45;margin-top:3px}
@media(max-width:760px){
  .cfb10-title{font-size:1.20rem}.cfb10-context{grid-template-columns:repeat(2,minmax(0,1fr))}
  .cfb10-ready-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .cfb10-env-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .cfb10-combined{grid-template-columns:1fr}.cfb10-team{font-size:.84rem}.cfb10-match{gap:5px}
}
</style>
"""


def _fmt(value: Any, digits: int = 1) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return escape(str(value))


def _rank_text(profile: Mapping[str, Any]) -> str:
    rank = profile.get("ap_rank")
    if rank is None:
        return "UNRANKED"
    try:
        return f"#{int(rank)} AP"
    except Exception:
        return "RANK N/A"


def _quality(profile: Mapping[str, Any]) -> str:
    return str((profile.get("data_quality") or {}).get("grade") or "CHECK").upper()


def _sample(profile: Mapping[str, Any]) -> int:
    try:
        return int(((profile.get("record") or {}).get("games")) or 0)
    except Exception:
        return 0


def _identity_ready(game: Mapping[str, Any]) -> bool:
    return bool(game.get("identity_verified") and game.get("date_matches_query"))


def _foundation_ready(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> bool:
    has_scoring = all(
        value is not None
        for value in (
            away.get("ppg"),
            away.get("points_allowed_pg"),
            home.get("ppg"),
            home.get("points_allowed_pg"),
        )
    )
    grades = {_quality(away), _quality(home)}
    return (
        _identity_ready(game)
        and "CHECK" not in grades
        and _sample(away) > 0
        and _sample(home) > 0
        and has_scoring
    )


def _descriptive_combined_context(
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> dict[str, float | None]:
    try:
        offense_sum = float(away.get("ppg")) + float(home.get("ppg"))
    except Exception:
        offense_sum = None
    try:
        allowance_sum = float(away.get("points_allowed_pg")) + float(
            home.get("points_allowed_pg")
        )
    except Exception:
        allowance_sum = None
    try:
        recent_offense_sum = float(away.get("recent_ppg")) + float(
            home.get("recent_ppg")
        )
    except Exception:
        recent_offense_sum = None
    try:
        recent_allowance_sum = float(
            away.get("recent_points_allowed_pg")
        ) + float(home.get("recent_points_allowed_pg"))
    except Exception:
        recent_allowance_sum = None
    return {
        "season_offense_sum": offense_sum,
        "season_allowance_sum": allowance_sum,
        "recent_offense_sum": recent_offense_sum,
        "recent_allowance_sum": recent_allowance_sum,
    }


def _hero(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> str:
    away_name = escape(str(away.get("team") or game.get("away_team") or "Away"))
    home_name = escape(str(home.get("team") or game.get("home_team") or "Home"))
    verified = _identity_ready(game)
    return f"""
<div class="cfb10-hero">
  <div class="cfb10-hero-top">
    <b>SELECTED GAME TOTAL MATCHUP</b>
    <span class="cfb10-verified">{'IDENTITY VERIFIED' if verified else 'CHECK IDENTITY'}</span>
  </div>
  <div class="cfb10-match">
    <div class="cfb10-side">
      <div class="cfb10-rank">{escape(_rank_text(away))}</div>
      <div class="cfb10-team">{away_name}</div>
      <div class="cfb10-meta">{escape(str(away.get('conference') or game.get('away_conference') or 'Conference unavailable'))} • {escape(str(away.get('record_text') or '0-0'))}</div>
    </div>
    <div class="cfb10-at">@</div>
    <div class="cfb10-side home">
      <div class="cfb10-rank">{escape(_rank_text(home))}</div>
      <div class="cfb10-team">{home_name}</div>
      <div class="cfb10-meta">{escape(str(home.get('conference') or game.get('home_conference') or 'Conference unavailable'))} • {escape(str(home.get('record_text') or '0-0'))}</div>
    </div>
  </div>
  <div class="cfb10-context">
    <div><strong>Kickoff</strong><span>{escape(str(game.get('kickoff_et') or 'TBD'))}</span></div>
    <div><strong>Venue</strong><span>{escape(str(game.get('venue') or 'Venue unavailable'))}</span></div>
    <div><strong>Status</strong><span>{escape(str(game.get('status') or 'Status unavailable'))}</span></div>
    <div><strong>Broadcast</strong><span>{escape(str(game.get('broadcast') or 'Broadcast unavailable'))}</span></div>
  </div>
</div>
"""


def _readiness_panel(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> str:
    ready = _foundation_ready(game, away, home)
    return f"""
<div class="cfb10-ready">
  <div class="cfb10-ready-title">GAME TOTAL DISTRIBUTION FOUNDATION • MODEL STILL OFF</div>
  <div class="cfb10-ready-grid">
    <div class="cfb10-ready-item"><b>{'READY' if _identity_ready(game) else 'CHECK'}</b><span>Game identity</span></div>
    <div class="cfb10-ready-item"><b>{escape(_quality(away))}</b><span>Away scoring data</span></div>
    <div class="cfb10-ready-item"><b>{escape(_quality(home))}</b><span>Home scoring data</span></div>
    <div class="cfb10-ready-item"><b>{'READY' if ready else 'LIMITED'}</b><span>Step 11 input foundation</span></div>
  </div>
</div>
"""


def _environment_panel(
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> str:
    away_name = escape(str(away.get("team") or "Away"))
    home_name = escape(str(home.get("team") or "Home"))
    combined = _descriptive_combined_context(away, home)
    return f"""
<div class="cfb10-env">
  <div class="cfb10-env-title">COMBINED-SCORE EVIDENCE • DESCRIPTIVE ONLY</div>
  <div class="cfb10-env-sub">
    Certified team scoring and allowance rates are organized for an independent
    combined-score distribution model. The sums below are descriptive arithmetic,
    not a projected game total and not a betting recommendation.
  </div>
  <div class="cfb10-env-grid">
    <div class="cfb10-metric"><b>{_fmt(away.get('ppg'))}</b><span>{away_name} points/game</span></div>
    <div class="cfb10-metric"><b>{_fmt(home.get('ppg'))}</b><span>{home_name} points/game</span></div>
    <div class="cfb10-metric"><b>{_fmt(away.get('points_allowed_pg'))}</b><span>{away_name} allowed/game</span></div>
    <div class="cfb10-metric"><b>{_fmt(home.get('points_allowed_pg'))}</b><span>{home_name} allowed/game</span></div>
    <div class="cfb10-metric"><b>{_fmt(away.get('recent_ppg'))}</b><span>{away_name} recent points/game</span></div>
    <div class="cfb10-metric"><b>{_fmt(home.get('recent_ppg'))}</b><span>{home_name} recent points/game</span></div>
    <div class="cfb10-metric"><b>{_fmt(away.get('recent_points_allowed_pg'))}</b><span>{away_name} recent allowed/game</span></div>
    <div class="cfb10-metric"><b>{_fmt(home.get('recent_points_allowed_pg'))}</b><span>{home_name} recent allowed/game</span></div>
  </div>
  <div class="cfb10-combined">
    <div class="cfb10-combined-card">
      <strong>Raw combined scoring context</strong>
      <span>Season offense sum {_fmt(combined.get('season_offense_sum'))} • Recent offense sum {_fmt(combined.get('recent_offense_sum'))}</span>
    </div>
    <div class="cfb10-combined-card">
      <strong>Raw combined allowance context</strong>
      <span>Season allowance sum {_fmt(combined.get('season_allowance_sum'))} • Recent allowance sum {_fmt(combined.get('recent_allowance_sum'))}</span>
    </div>
  </div>
</div>
"""


def _distribution_locked_panel() -> str:
    return """
<div class="cfb10-locked">
  <b>STEP 10 • GAME TOTAL DISTRIBUTION OUTPUT RESERVED</b>
  <span>
    Projected combined total, median/mode, exact-total probabilities, total bands,
    percentiles, sportsbook total/price, edge/EV, picks/ranking, and Monte Carlo
    remain OFF. Step 11 owns the first independent Game Total distribution model;
    Step 12 owns final synthesis/ranking.
  </span>
</div>
"""


def _diag_rows(diag: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "Provider": attempt.get("provider"),
            "Transport": attempt.get("transport"),
            "HTTP": attempt.get("http"),
            "Bytes": attempt.get("bytes"),
            "Error": attempt.get("error"),
        }
        for attempt in diag.get("attempts") or []
    ]


def render_game_total_hub(
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    st.caption("🏈 COLLEGE FOOTBALL • GAME TOTAL • Step 10 foundation ACTIVE")
    st.markdown(identity_ui._CSS, unsafe_allow_html=True)
    st.markdown(team_ui._STEP3_CSS, unsafe_allow_html=True)
    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown(
        """
<div class="cfb10-shell">
  <div class="cfb10-kicker">CFB STEP 10 • GAME TOTAL FOUNDATION</div>
  <div class="cfb10-title">🧮 College Football Game Total</div>
  <div class="cfb10-sub">
    Verified NCAA matchup identity + certified combined-score evidence prepared for
    an independent exact-total / distribution model.
  </div>
  <div class="cfb10-status">
    <span class="cfb10-pill good">ROUTE ✅</span>
    <span class="cfb10-pill good">CURRENT NCAA SLATE ✅</span>
    <span class="cfb10-pill good">TEAM SCORING DATA ✅</span>
    <span class="cfb10-pill good">DISTRIBUTION FOUNDATION ✅</span>
    <span class="cfb10-pill wait">MODEL ⏳ STEP 11</span>
    <span class="cfb10-pill wait">FINAL / RANKING ⏳ STEP 12</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    selected = st.date_input(
        "📅 CFB Game Total slate date",
        value=datetime.now(_ET).date(),
        key="cfb_step10_game_total_date",
        help="Loads the certified NCAA scoreboard and team-data foundation.",
    )
    selected_day = selected.isoformat()

    games, schedule_diag = schedule.load_with_diagnostics(selected_day)
    st.markdown(identity_ui._diagnostic_badges(schedule_diag), unsafe_allow_html=True)

    if not games:
        st.warning(
            "No verified FBS-scoped games were returned for this date. Step 10 fails "
            "closed—no projected total or distribution is invented."
        )
        attempts = _diag_rows(schedule_diag)
        if attempts:
            with st.expander("Schedule provider diagnostics"):
                st.dataframe(attempts, use_container_width=True, hide_index=True)
        return

    index = st.selectbox(
        "🏟️ Game Total matchup",
        options=list(range(len(games))),
        format_func=lambda i: identity_ui._matchup_label(games[int(i)]),
        key=f"cfb_step10_game_total_matchup_{selected_day}",
    )
    game = games[int(index)]

    profiles, team_diag = team_data.load_matchup_team_data(game, selected_day)
    away = profiles.get("away") or {}
    home = profiles.get("home") or {}

    st.markdown(_hero(game, away, home), unsafe_allow_html=True)
    st.markdown(_readiness_panel(game, away, home), unsafe_allow_html=True)
    st.markdown(_environment_panel(away, home), unsafe_allow_html=True)

    st.markdown(
        f"""
<div class="cfb3-section">
  <div class="cfb3-title">CERTIFIED TEAM EVIDENCE • STEP 10 INPUT AUDIT</div>
  <div class="cfb3-sub">
    Game Total reads the same certified schedule/team-data layers without modifying
    the frozen Moneyline or Over/Under sections.
  </div>
  {team_ui._team_data_diagnostics(team_diag)}
  <div class="cfb3-grid">
    {team_ui._team_card(away)}
    {team_ui._team_card(home)}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown(_distribution_locked_panel(), unsafe_allow_html=True)

    with st.expander(f"Full verified Game Total slate • {selected_day}"):
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

    attempts = _diag_rows(team_diag)
    if attempts:
        with st.expander("Game Total team-data provider diagnostics"):
            st.dataframe(attempts, use_container_width=True, hide_index=True)

    st.info(
        "Step 10 is the Game Total foundation only. Moneyline and Over/Under remain "
        "permanently frozen. The independent total distribution model arrives in "
        "Step 11; final synthesis/ranking arrives in Step 12."
    )


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Step 10 Game Total hub received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "MARKET",
    "MODEL_VERSION",
    "SCHEDULE_PROVIDER",
    "TEAM_DATA_PROVIDER",
    "_descriptive_combined_context",
    "_distribution_locked_panel",
    "_environment_panel",
    "_foundation_ready",
    "_hero",
    "_readiness_panel",
    "render_cfb_hub",
    "render_game_total_hub",
]
