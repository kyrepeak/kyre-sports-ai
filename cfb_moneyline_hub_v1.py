"""College Football Moneyline Hub V1 — Step 4 page/UI foundation.

Additive presentation layer over permanently frozen CFB Steps 1-3.

Step 4 purpose
--------------
Build a dedicated Moneyline page that makes the verified schedule identity and
team-data evidence quick to read before any CFB win-probability model is turned
on.

This module intentionally does NOT compute:
- win probability,
- fair moneyline,
- projected score,
- betting edge,
- pick/rank,
- Monte Carlo output.

All evidence is read from frozen Step 2/3 providers.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import streamlit as st

import cfb_hub_v2 as identity_ui
import cfb_hub_v3 as frozen_v3
import cfb_schedule_v1 as schedule
import cfb_team_data_v1 as team_data

MODEL_VERSION = "CFB MONEYLINE HUB V1 • STEP 4 PAGE UI"
FROZEN_CFB_HUB = "cfb_hub_v3"
MARKET = "Moneyline"

_ET = ZoneInfo("America/New_York")

_CSS = r"""
<style>
.cfb4-shell{border:1px solid rgba(83,180,255,.28);border-radius:17px;
background:linear-gradient(145deg,#07131f,#091925);padding:14px;margin-top:8px}
.cfb4-kicker{color:#72d8ff;font-size:.58rem;font-weight:950;letter-spacing:.10em}
.cfb4-title{color:#f4fbff;font-size:1.45rem;font-weight:950;margin-top:3px}
.cfb4-sub{color:#8da6b7;font-size:.67rem;line-height:1.45;margin-top:4px}
.cfb4-status{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.cfb4-pill{border:1px solid #2c485c;border-radius:999px;background:#0a1b28;color:#a9c1d0;
padding:5px 8px;font-size:.47rem;font-weight:900}
.cfb4-pill.good{border-color:#287355;background:#0a2d22;color:#83e7b6}
.cfb4-pill.wait{border-color:#765f1c;background:#30280e;color:#f2d675}
.cfb4-hero{margin-top:11px;border:1px solid rgba(98,164,205,.24);border-radius:16px;
background:#07131d;overflow:hidden}
.cfb4-hero-top{display:flex;justify-content:space-between;gap:8px;align-items:center;
padding:9px 11px;border-bottom:1px solid rgba(98,164,205,.18)}
.cfb4-hero-top b{color:#73d9ff;font-size:.50rem;letter-spacing:.08em}
.cfb4-verified{border:1px solid #277353;border-radius:999px;background:#0b2d22;color:#84e7b6;
padding:4px 7px;font-size:.43rem;font-weight:950}
.cfb4-match{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);
gap:9px;align-items:center;padding:14px 12px}
.cfb4-side{min-width:0}.cfb4-side.home{text-align:right}
.cfb4-rank{color:#6bd8ff;font-size:.48rem;font-weight:900;text-transform:uppercase}
.cfb4-team{color:#f3f8fb;font-size:1.04rem;font-weight:950;line-height:1.12;margin-top:2px}
.cfb4-meta{color:#7892a4;font-size:.48rem;font-weight:800;text-transform:uppercase;margin-top:3px}
.cfb4-at{color:#627e90;font-size:.70rem;font-weight:950}
.cfb4-context{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;
padding:0 12px 12px}
.cfb4-context div{border:1px solid rgba(98,164,205,.17);border-radius:9px;background:#091824;
padding:7px;min-width:0}
.cfb4-context strong{display:block;color:#dceaf2;font-size:.44rem;text-transform:uppercase;
letter-spacing:.05em}.cfb4-context span{display:block;color:#9bb0bd;font-size:.55rem;margin-top:2px}
.cfb4-ready{margin-top:10px;border:1px solid rgba(126,231,180,.20);border-radius:14px;
background:#071912;padding:10px}
.cfb4-ready-title{color:#83e7b6;font-size:.52rem;font-weight:950;letter-spacing:.08em}
.cfb4-ready-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:7px}
.cfb4-ready-item{border:1px solid rgba(126,231,180,.17);border-radius:9px;background:#081a14;padding:7px}
.cfb4-ready-item b{display:block;color:#e6f7ee;font-size:.62rem}.cfb4-ready-item span{display:block;
color:#78998a;font-size:.43rem;text-transform:uppercase;margin-top:2px}
.cfb4-blocked{margin-top:10px;border:1px solid #6e5a1d;border-radius:13px;background:#2d260d;padding:10px}
.cfb4-blocked b{display:block;color:#f4da78;font-size:.57rem}.cfb4-blocked span{display:block;
color:#b9a963;font-size:.48rem;line-height:1.45;margin-top:3px}
@media(max-width:760px){
  .cfb4-title{font-size:1.20rem}.cfb4-context{grid-template-columns:repeat(2,minmax(0,1fr))}
  .cfb4-ready-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .cfb4-team{font-size:.84rem}.cfb4-match{gap:5px}
}
</style>
"""


def _rank_text(profile: Mapping[str, Any]) -> str:
    rank = profile.get("ap_rank")
    if rank is None:
        return "UNRANKED"
    try:
        return f"#{int(rank)} AP"
    except Exception:
        return "RANK N/A"


def _quality_text(profile: Mapping[str, Any]) -> str:
    return str((profile.get("data_quality") or {}).get("grade") or "CHECK").upper()


def _record(profile: Mapping[str, Any]) -> str:
    return escape(str(profile.get("record_text") or "0-0"))


def _moneyline_hero(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> str:
    verified = bool(game.get("identity_verified") and game.get("date_matches_query"))
    venue = escape(str(game.get("venue") or "Venue unavailable"))
    kickoff = escape(str(game.get("kickoff_et") or "TBD"))
    status = escape(str(game.get("status") or "Status unavailable"))
    broadcast = escape(str(game.get("broadcast") or "Broadcast unavailable"))

    return f"""
<div class="cfb4-hero">
  <div class="cfb4-hero-top">
    <b>SELECTED MONEYLINE MATCHUP</b>
    <span class="cfb4-verified">{'IDENTITY VERIFIED' if verified else 'CHECK IDENTITY'}</span>
  </div>
  <div class="cfb4-match">
    <div class="cfb4-side">
      <div class="cfb4-rank">{escape(_rank_text(away))}</div>
      <div class="cfb4-team">{escape(str(away.get('team') or game.get('away_team') or 'Away'))}</div>
      <div class="cfb4-meta">{escape(str(away.get('conference') or game.get('away_conference') or 'Conference unavailable'))} • {_record(away)}</div>
    </div>
    <div class="cfb4-at">@</div>
    <div class="cfb4-side home">
      <div class="cfb4-rank">{escape(_rank_text(home))}</div>
      <div class="cfb4-team">{escape(str(home.get('team') or game.get('home_team') or 'Home'))}</div>
      <div class="cfb4-meta">{escape(str(home.get('conference') or game.get('home_conference') or 'Conference unavailable'))} • {_record(home)}</div>
    </div>
  </div>
  <div class="cfb4-context">
    <div><strong>Kickoff</strong><span>{kickoff}</span></div>
    <div><strong>Venue</strong><span>{venue}</span></div>
    <div><strong>Status</strong><span>{status}</span></div>
    <div><strong>Broadcast</strong><span>{broadcast}</span></div>
  </div>
</div>
"""


def _readiness_panel(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> str:
    identity = "READY" if bool(game.get("identity_verified") and game.get("date_matches_query")) else "CHECK"
    away_grade = _quality_text(away)
    home_grade = _quality_text(home)
    away_games = int(((away.get("record") or {}).get("games")) or 0)
    home_games = int(((home.get("record") or {}).get("games")) or 0)

    return f"""
<div class="cfb4-ready">
  <div class="cfb4-ready-title">MONEYLINE PAGE READINESS • MODEL STILL OFF</div>
  <div class="cfb4-ready-grid">
    <div class="cfb4-ready-item"><b>{escape(identity)}</b><span>Game identity</span></div>
    <div class="cfb4-ready-item"><b>{escape(away_grade)}</b><span>Away team data</span></div>
    <div class="cfb4-ready-item"><b>{escape(home_grade)}</b><span>Home team data</span></div>
    <div class="cfb4-ready-item"><b>{away_games} / {home_games}</b><span>Completed-game samples</span></div>
  </div>
</div>
"""


def _model_locked_panel() -> str:
    return """
<div class="cfb4-blocked">
  <b>STEP 4 • MONEYLINE OUTPUT RESERVED</b>
  <span>
    This page is now laid out for Moneyline analysis, but no winner probability,
    fair moneyline, projected score, edge, pick, or simulation is generated yet.
    Those remain locked for Step 5+ so presentation cannot masquerade as a model.
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


def render_moneyline_hub(
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    """Render the dedicated Step-4 College Football Moneyline page."""
    st.caption("🏈 COLLEGE FOOTBALL • MONEYLINE • Step 4 dedicated page UI ACTIVE")
    st.markdown(identity_ui._CSS, unsafe_allow_html=True)
    st.markdown(frozen_v3._STEP3_CSS, unsafe_allow_html=True)
    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown(
        """
<div class="cfb4-shell">
  <div class="cfb4-kicker">CFB STEP 4 • MONEYLINE PAGE FOUNDATION</div>
  <div class="cfb4-title">🏆 College Football Moneyline</div>
  <div class="cfb4-sub">
    Verified matchup identity + frozen Step 3 team evidence, organized specifically
    for winner analysis. The actual win-probability model remains disabled.
  </div>
  <div class="cfb4-status">
    <span class="cfb4-pill good">ROUTE ✅</span>
    <span class="cfb4-pill good">SCHEDULE + ID ✅</span>
    <span class="cfb4-pill good">TEAM DATA ✅</span>
    <span class="cfb4-pill good">MONEYLINE UI ✅</span>
    <span class="cfb4-pill wait">MODEL ⏳</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    today_et = datetime.now(_ET).date()
    selected = st.date_input(
        "📅 CFB Moneyline slate date",
        value=today_et,
        key="cfb_step4_moneyline_date",
        help="Loads the frozen Step 2 NCAA FBS schedule and Step 3 team-data evidence.",
    )
    selected_day = selected.isoformat()

    games, schedule_diag = schedule.load_with_diagnostics(selected_day)
    st.markdown(identity_ui._diagnostic_badges(schedule_diag), unsafe_allow_html=True)

    if not games:
        st.warning(
            "No verified FBS games were returned for this date. The Moneyline page fails closed—"
            "no matchup, winner, probability, or pick will be invented."
        )
        attempts = _diag_rows(schedule_diag)
        if attempts:
            with st.expander("Schedule provider diagnostics"):
                st.dataframe(attempts, use_container_width=True, hide_index=True)
        return

    index = st.selectbox(
        "🏟️ Moneyline matchup",
        options=list(range(len(games))),
        format_func=lambda i: identity_ui._matchup_label(games[int(i)]),
        key=f"cfb_step4_moneyline_matchup_{selected_day}",
    )
    game = games[int(index)]

    profiles, team_diag = team_data.load_matchup_team_data(game, selected_day)
    away = profiles.get("away") or {}
    home = profiles.get("home") or {}

    st.markdown(_moneyline_hero(game, away, home), unsafe_allow_html=True)
    st.markdown(_readiness_panel(game, away, home), unsafe_allow_html=True)

    st.markdown(
        f"""
<div class="cfb3-section">
  <div class="cfb3-title">STEP 3 EVIDENCE • FROZEN TEAM COMPARISON</div>
  <div class="cfb3-sub">
    These are verified inputs only. Step 4 changes presentation, not team-data values.
  </div>
  {frozen_v3._team_data_diagnostics(team_diag)}
  <div class="cfb3-grid">
    {frozen_v3._team_card(away)}
    {frozen_v3._team_card(home)}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown(_model_locked_panel(), unsafe_allow_html=True)

    with st.expander(f"Full verified Moneyline slate • {selected_day}"):
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

    team_attempts = _diag_rows(team_diag)
    if team_attempts:
        with st.expander("Moneyline team-data provider diagnostics"):
            st.dataframe(team_attempts, use_container_width=True, hide_index=True)

    st.info(
        "Step 4 is Moneyline presentation only. Win probability, fair odds, projected score, "
        "pick ranking, sportsbook comparison, and Monte Carlo remain OFF."
    )


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    """Moneyline advances to Step 4; other CFB pages remain frozen at Step 3."""
    if market != MARKET:
        return frozen_v3.render_cfb_hub(market, section_header, status_info, team_logo, h)
    return render_moneyline_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_CFB_HUB",
    "MARKET",
    "MODEL_VERSION",
    "_model_locked_panel",
    "_moneyline_hero",
    "_readiness_panel",
    "render_cfb_hub",
    "render_moneyline_hub",
]
