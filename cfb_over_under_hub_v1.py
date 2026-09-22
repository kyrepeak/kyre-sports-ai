"""College Football Over/Under Hub V1 — Step 7 foundation.

Additive presentation/data foundation above permanently frozen CFB Steps 1-6.

Step 7 activates a dedicated College Football Over/Under page using the
current certified NCAA scoreboard (Schedule V3) and certified team-data layer
(Team Data V2). It organizes scoring-environment evidence for total analysis.

This step intentionally does NOT compute or publish:
- projected game total,
- Over/Under probability,
- sportsbook total/price,
- fair total,
- betting edge,
- pick/rank,
- Monte Carlo simulation.

Moneyline remains permanently frozen on Step 6. Game Total remains on the
prior frozen route until Step 10.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import streamlit as st

import cfb_hub_v2 as identity_ui
import cfb_hub_v3 as frozen_team_ui
import cfb_schedule_v3 as schedule
import cfb_team_data_v2 as team_data

MODEL_VERSION = "CFB OVER/UNDER HUB V1 • STEP 7 FOUNDATION"
MARKET = "Over/Under"
FROZEN_TEAM_UI = "cfb_hub_v3"
SCHEDULE_PROVIDER = "cfb_schedule_v3"
TEAM_DATA_PROVIDER = "cfb_team_data_v2"

_ET = ZoneInfo("America/New_York")

_CSS = r"""
<style>
.cfb7-shell{border:1px solid rgba(247,193,78,.28);border-radius:17px;
background:linear-gradient(145deg,#171204,#101723);padding:14px;margin-top:8px}
.cfb7-kicker{color:#ffd978;font-size:.58rem;font-weight:950;letter-spacing:.10em}
.cfb7-title{color:#fff9e8;font-size:1.45rem;font-weight:950;margin-top:3px}
.cfb7-sub{color:#afa487;font-size:.67rem;line-height:1.45;margin-top:4px}
.cfb7-status{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.cfb7-pill{border:1px solid #62562f;border-radius:999px;background:#211c0b;color:#d7c989;
padding:5px 8px;font-size:.47rem;font-weight:900}
.cfb7-pill.good{border-color:#287355;background:#0a2d22;color:#83e7b6}
.cfb7-pill.wait{border-color:#765f1c;background:#30280e;color:#f2d675}
.cfb7-hero{margin-top:11px;border:1px solid rgba(247,193,78,.23);border-radius:16px;
background:#11150e;overflow:hidden}
.cfb7-hero-top{display:flex;justify-content:space-between;gap:8px;align-items:center;
padding:9px 11px;border-bottom:1px solid rgba(247,193,78,.16)}
.cfb7-hero-top b{color:#ffd978;font-size:.50rem;letter-spacing:.08em}
.cfb7-verified{border:1px solid #277353;border-radius:999px;background:#0b2d22;color:#84e7b6;
padding:4px 7px;font-size:.43rem;font-weight:950}
.cfb7-match{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);
gap:9px;align-items:center;padding:14px 12px}
.cfb7-side{min-width:0}.cfb7-side.home{text-align:right}
.cfb7-rank{color:#ffd978;font-size:.48rem;font-weight:900;text-transform:uppercase}
.cfb7-team{color:#f7f3e9;font-size:1.04rem;font-weight:950;line-height:1.12;margin-top:2px}
.cfb7-meta{color:#918a78;font-size:.48rem;font-weight:800;text-transform:uppercase;margin-top:3px}
.cfb7-at{color:#82785d;font-size:.70rem;font-weight:950}
.cfb7-context{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;
padding:0 12px 12px}
.cfb7-context div{border:1px solid rgba(247,193,78,.14);border-radius:9px;background:#171a12;
padding:7px;min-width:0}
.cfb7-context strong{display:block;color:#ece5d2;font-size:.44rem;text-transform:uppercase;
letter-spacing:.05em}.cfb7-context span{display:block;color:#b1a78c;font-size:.55rem;margin-top:2px}
.cfb7-ready{margin-top:10px;border:1px solid rgba(126,231,180,.20);border-radius:14px;
background:#071912;padding:10px}
.cfb7-ready-title{color:#83e7b6;font-size:.52rem;font-weight:950;letter-spacing:.08em}
.cfb7-ready-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:7px}
.cfb7-ready-item{border:1px solid rgba(126,231,180,.17);border-radius:9px;background:#081a14;padding:7px}
.cfb7-ready-item b{display:block;color:#e6f7ee;font-size:.62rem}.cfb7-ready-item span{display:block;
color:#78998a;font-size:.43rem;text-transform:uppercase;margin-top:2px}
.cfb7-env{margin-top:10px;border:1px solid rgba(247,193,78,.19);border-radius:14px;background:#15180f;padding:10px}
.cfb7-env-title{color:#ffd978;font-size:.52rem;font-weight:950;letter-spacing:.08em}
.cfb7-env-sub{color:#9f977f;font-size:.45rem;line-height:1.45;margin-top:3px}
.cfb7-env-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:8px}
.cfb7-metric{border:1px solid rgba(247,193,78,.13);border-radius:9px;background:#191c13;padding:7px}
.cfb7-metric b{display:block;color:#f4ecd7;font-size:.66rem}.cfb7-metric span{display:block;
color:#9e957e;font-size:.42rem;text-transform:uppercase;margin-top:2px}
.cfb7-battle{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:8px}
.cfb7-battle-card{border:1px solid rgba(247,193,78,.13);border-radius:10px;background:#14170f;padding:8px}
.cfb7-battle-card strong{display:block;color:#e9dfc5;font-size:.47rem;text-transform:uppercase}
.cfb7-battle-card span{display:block;color:#b3a98e;font-size:.53rem;line-height:1.45;margin-top:4px}
.cfb7-blocked{margin-top:10px;border:1px solid #6e5a1d;border-radius:13px;background:#2d260d;padding:10px}
.cfb7-blocked b{display:block;color:#f4da78;font-size:.57rem}.cfb7-blocked span{display:block;
color:#b9a963;font-size:.48rem;line-height:1.45;margin-top:3px}
@media(max-width:760px){
  .cfb7-title{font-size:1.20rem}.cfb7-context{grid-template-columns:repeat(2,minmax(0,1fr))}
  .cfb7-ready-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .cfb7-env-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .cfb7-battle{grid-template-columns:1fr}.cfb7-team{font-size:.84rem}.cfb7-match{gap:5px}
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
    return int(((profile.get("record") or {}).get("games")) or 0)


def _identity_ready(game: Mapping[str, Any]) -> bool:
    return bool(game.get("identity_verified") and game.get("date_matches_query"))


def _foundation_ready(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> bool:
    grades = {_quality(away), _quality(home)}
    has_scoring = all(
        value is not None
        for value in (
            away.get("ppg"),
            away.get("points_allowed_pg"),
            home.get("ppg"),
            home.get("points_allowed_pg"),
        )
    )
    return (
        _identity_ready(game)
        and "CHECK" not in grades
        and _sample(away) > 0
        and _sample(home) > 0
        and has_scoring
    )


def _hero(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> str:
    verified = _identity_ready(game)
    away_name = escape(str(away.get("team") or game.get("away_team") or "Away"))
    home_name = escape(str(home.get("team") or game.get("home_team") or "Home"))
    return f"""
<div class="cfb7-hero">
  <div class="cfb7-hero-top">
    <b>SELECTED OVER/UNDER MATCHUP</b>
    <span class="cfb7-verified">{'IDENTITY VERIFIED' if verified else 'CHECK IDENTITY'}</span>
  </div>
  <div class="cfb7-match">
    <div class="cfb7-side">
      <div class="cfb7-rank">{escape(_rank_text(away))}</div>
      <div class="cfb7-team">{away_name}</div>
      <div class="cfb7-meta">{escape(str(away.get('conference') or game.get('away_conference') or 'Conference unavailable'))} • {escape(str(away.get('record_text') or '0-0'))}</div>
    </div>
    <div class="cfb7-at">@</div>
    <div class="cfb7-side home">
      <div class="cfb7-rank">{escape(_rank_text(home))}</div>
      <div class="cfb7-team">{home_name}</div>
      <div class="cfb7-meta">{escape(str(home.get('conference') or game.get('home_conference') or 'Conference unavailable'))} • {escape(str(home.get('record_text') or '0-0'))}</div>
    </div>
  </div>
  <div class="cfb7-context">
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
<div class="cfb7-ready">
  <div class="cfb7-ready-title">OVER/UNDER FOUNDATION READINESS • MODEL STILL OFF</div>
  <div class="cfb7-ready-grid">
    <div class="cfb7-ready-item"><b>{'READY' if _identity_ready(game) else 'CHECK'}</b><span>Game identity</span></div>
    <div class="cfb7-ready-item"><b>{escape(_quality(away))}</b><span>Away scoring data</span></div>
    <div class="cfb7-ready-item"><b>{escape(_quality(home))}</b><span>Home scoring data</span></div>
    <div class="cfb7-ready-item"><b>{'READY' if ready else 'LIMITED'}</b><span>Step 8 input foundation</span></div>
  </div>
</div>
"""


def _environment_panel(
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> str:
    away_name = escape(str(away.get("team") or "Away"))
    home_name = escape(str(home.get("team") or "Home"))
    return f"""
<div class="cfb7-env">
  <div class="cfb7-env-title">SCORING ENVIRONMENT EVIDENCE • DESCRIPTIVE ONLY</div>
  <div class="cfb7-env-sub">
    Raw team scoring/allowance context from the certified team-data layer. These values
    are evidence inputs, not a projected game total and not an Over/Under recommendation.
  </div>
  <div class="cfb7-env-grid">
    <div class="cfb7-metric"><b>{_fmt(away.get('ppg'))}</b><span>{away_name} points/game</span></div>
    <div class="cfb7-metric"><b>{_fmt(away.get('points_allowed_pg'))}</b><span>{away_name} allowed/game</span></div>
    <div class="cfb7-metric"><b>{_fmt(home.get('ppg'))}</b><span>{home_name} points/game</span></div>
    <div class="cfb7-metric"><b>{_fmt(home.get('points_allowed_pg'))}</b><span>{home_name} allowed/game</span></div>
    <div class="cfb7-metric"><b>{_fmt(away.get('recent_ppg'))}</b><span>{away_name} recent points/game</span></div>
    <div class="cfb7-metric"><b>{_fmt(away.get('recent_points_allowed_pg'))}</b><span>{away_name} recent allowed/game</span></div>
    <div class="cfb7-metric"><b>{_fmt(home.get('recent_ppg'))}</b><span>{home_name} recent points/game</span></div>
    <div class="cfb7-metric"><b>{_fmt(home.get('recent_points_allowed_pg'))}</b><span>{home_name} recent allowed/game</span></div>
  </div>
  <div class="cfb7-battle">
    <div class="cfb7-battle-card">
      <strong>{away_name} offense vs {home_name} defense</strong>
      <span>{_fmt(away.get('ppg'))} offensive PPG • {_fmt(home.get('points_allowed_pg'))} opponent allowance</span>
    </div>
    <div class="cfb7-battle-card">
      <strong>{home_name} offense vs {away_name} defense</strong>
      <span>{_fmt(home.get('ppg'))} offensive PPG • {_fmt(away.get('points_allowed_pg'))} opponent allowance</span>
    </div>
  </div>
</div>
"""


def _model_locked_panel() -> str:
    return """
<div class="cfb7-blocked">
  <b>STEP 7 • OVER/UNDER OUTPUT RESERVED</b>
  <span>
    The dedicated total-analysis foundation is active, but projected game total,
    Over/Under probability, sportsbook total/price, fair total, edge, pick ranking,
    and Monte Carlo simulation remain OFF. Step 8 owns the first Over/Under model;
    Step 9 owns slate ranking.
  </span>
</div>
"""


def _diag_rows(diag: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "Provider": a.get("provider"),
            "Transport": a.get("transport"),
            "HTTP": a.get("http"),
            "Bytes": a.get("bytes"),
            "Error": a.get("error"),
        }
        for a in diag.get("attempts") or []
    ]


def render_over_under_hub(
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    st.caption("🏈 COLLEGE FOOTBALL • OVER/UNDER • Step 7 foundation ACTIVE")
    st.markdown(identity_ui._CSS, unsafe_allow_html=True)
    st.markdown(frozen_team_ui._STEP3_CSS, unsafe_allow_html=True)
    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown(
        """
<div class="cfb7-shell">
  <div class="cfb7-kicker">CFB STEP 7 • OVER/UNDER FOUNDATION</div>
  <div class="cfb7-title">↕️ College Football Over/Under</div>
  <div class="cfb7-sub">
    Current NCAA matchup identity + certified team scoring evidence, organized for
    total analysis. No total model or sportsbook line influence is active yet.
  </div>
  <div class="cfb7-status">
    <span class="cfb7-pill good">ROUTE ✅</span>
    <span class="cfb7-pill good">CURRENT NCAA SLATE ✅</span>
    <span class="cfb7-pill good">TEAM SCORING DATA ✅</span>
    <span class="cfb7-pill good">O/U FOUNDATION ✅</span>
    <span class="cfb7-pill wait">MODEL ⏳ STEP 8</span>
    <span class="cfb7-pill wait">RANKING ⏳ STEP 9</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    today_et = datetime.now(_ET).date()
    selected = st.date_input(
        "📅 CFB Over/Under slate date",
        value=today_et,
        key="cfb_step7_over_under_date",
        help="Loads the certified current NCAA scoreboard and certified team-data evidence.",
    )
    selected_day = selected.isoformat()

    games, schedule_diag = schedule.load_with_diagnostics(selected_day)
    st.markdown(identity_ui._diagnostic_badges(schedule_diag), unsafe_allow_html=True)

    if not games:
        st.warning(
            "No verified FBS-scoped games were returned for this date. Step 7 fails closed—"
            "no total, Over/Under probability, or pick is invented."
        )
        attempts = _diag_rows(schedule_diag)
        if attempts:
            with st.expander("Schedule provider diagnostics"):
                st.dataframe(attempts, use_container_width=True, hide_index=True)
        return

    index = st.selectbox(
        "🏟️ Over/Under matchup",
        options=list(range(len(games))),
        format_func=lambda i: identity_ui._matchup_label(games[int(i)]),
        key=f"cfb_step7_over_under_matchup_{selected_day}",
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
  <div class="cfb3-title">CERTIFIED TEAM EVIDENCE • STEP 7 INPUT AUDIT</div>
  <div class="cfb3-sub">
    Step 7 reorganizes certified scoring evidence for totals work; it does not modify
    the underlying team-data values or the permanently frozen Moneyline model.
  </div>
  {frozen_team_ui._team_data_diagnostics(team_diag)}
  <div class="cfb3-grid">
    {frozen_team_ui._team_card(away)}
    {frozen_team_ui._team_card(home)}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown(_model_locked_panel(), unsafe_allow_html=True)

    with st.expander(f"Full verified Over/Under slate • {selected_day}"):
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
        with st.expander("Over/Under team-data provider diagnostics"):
            st.dataframe(attempts, use_container_width=True, hide_index=True)

    st.info(
        "Step 7 is the Over/Under foundation only. Moneyline Step 6 remains frozen. "
        "Projected totals and Over/Under probabilities arrive in Step 8; slate ranking "
        "arrives in Step 9."
    )


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Step 7 Over/Under hub received unsupported market: {market}")
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_TEAM_UI",
    "MARKET",
    "MODEL_VERSION",
    "SCHEDULE_PROVIDER",
    "TEAM_DATA_PROVIDER",
    "_environment_panel",
    "_foundation_ready",
    "_hero",
    "_model_locked_panel",
    "_readiness_panel",
    "render_cfb_hub",
    "render_over_under_hub",
]
