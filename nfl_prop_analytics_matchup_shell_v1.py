"""NFL Prop Analytics V1 — Step 4 Page 2 Matchup Shell + Position Sections.

Consumes the frozen Step 3 verified matchup handoff and renders a real Page 2
surface. This step owns navigation plus the structural QB/RB/WR/TE sections
for both teams. It intentionally contains no roster data, player props,
sportsbook odds, projections, or Passing Yards behavior.
"""
from __future__ import annotations

import html as html_lib
from datetime import date
from typing import Any

import streamlit as st

from nfl_prop_analytics_game_select_v1 import (
    _handoff_kickoff_label,
    build_matchup_handoff,
    get_selected_game_handoff,
)
from nfl_prop_analytics_schedule_v1 import load_schedule_truth, team_logo_url

MODEL_VERSION = "NFL PROP ANALYTICS V1 • STEP 4 PAGE 2 MATCHUP SHELL"
STEP = 4
PAGE = 2
SHELL_ONLY = True
ROSTER_DATA_LOGIC = False
PLAYER_PROP_LOGIC = False
SPORTSBOOK_ODDS_LOGIC = False
PROJECTION_LOGIC = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PASSING_YARDS = False
MAY_MODIFY_EXISTING_NFL_MARKETS = False

PAGE_QUERY_KEY = "ks_pa_page"
PAGE_QUERY_VALUE = "matchup"
GAME_QUERY_KEY = "ks_pa_game"
POSITIONS = ("QB", "RB", "WR", "TE")


def _query_value(key: str) -> str:
    try:
        raw = st.query_params.get(key, "")
    except Exception:
        return ""
    if isinstance(raw, list):
        return str(raw[0] if raw else "")
    return str(raw or "")


def is_matchup_page() -> bool:
    return _query_value(PAGE_QUERY_KEY).strip().lower() == PAGE_QUERY_VALUE


def _selection_key(game: dict[str, Any]) -> str:
    return f"{game['away']}-{game['home']}"


def resolve_matchup_handoff() -> dict[str, Any] | None:
    handoff = get_selected_game_handoff()
    requested = _query_value(GAME_QUERY_KEY).strip().upper()

    if isinstance(handoff, dict) and handoff.get("state") == "ready":
        if not requested or str(handoff.get("selection_key", "")).upper() == requested:
            return handoff

    if not requested:
        return None

    truth = load_schedule_truth()
    for game in truth.get("games", []):
        if not bool(game.get("verified")):
            continue
        if _selection_key(game).upper() != requested:
            continue
        return build_matchup_handoff(
            game,
            str(truth.get("target_date") or ""),
        )
    return None


def open_matchup_page(handoff: dict[str, Any]) -> None:
    st.query_params[GAME_QUERY_KEY] = str(handoff["selection_key"])
    st.query_params[PAGE_QUERY_KEY] = PAGE_QUERY_VALUE
    st.rerun()


def return_to_schedule_page() -> None:
    try:
        del st.query_params[PAGE_QUERY_KEY]
    except Exception:
        st.query_params[PAGE_QUERY_KEY] = ""
    st.rerun()


def render_matchup_open_control(handoff: dict[str, Any] | None) -> None:
    if not handoff or handoff.get("state") != "ready":
        return
    if st.button(
        "Open matchup",
        key="nfl_prop_analytics_open_matchup_v1",
        use_container_width=True,
    ):
        open_matchup_page(handoff)



def _display_date(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "DATE TBD"
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return raw
    return f"{parsed.strftime('%a • %b').upper()} {parsed.day}"


def _premium_matchup_header(handoff: dict[str, Any]) -> str:
    away = str(handoff["away"])
    home = str(handoff["home"])
    away_name = str(handoff.get("away_name") or away)
    home_name = str(handoff.get("home_name") or home)
    kickoff = _handoff_kickoff_label(handoff)
    target_date = str(handoff.get("target_date") or "")
    display_date = _display_date(target_date)
    network = str(handoff.get("network") or "Network TBD")
    venue = str(handoff.get("venue") or "Venue TBD")
    week = str(handoff.get("week") or "").strip()
    away_logo = team_logo_url(away)
    home_logo = team_logo_url(home)
    week_label = f"WEEK {week} • NFL" if week else "NFL • MATCHUP"

    return f"""
<section class="ks-pa4-premium-head"
         data-prop-page2-premium-header="v1"
         data-prop-page2-header-away="{html_lib.escape(away)}"
         data-prop-page2-header-home="{html_lib.escape(home)}"
         data-prop-page2-header-kickoff="{html_lib.escape(kickoff)}"
         data-prop-page2-header-date="{html_lib.escape(target_date)}"
         data-prop-page2-header-network="{html_lib.escape(network)}"
         data-prop-page2-header-venue="{html_lib.escape(venue)}">
  <div class="ks-pa4-premium-team ks-pa4-premium-away">
    <img class="ks-pa4-premium-logo"
         data-prop-page2-header-logo="{html_lib.escape(away)}"
         data-prop-page2-header-logo-side="away"
         src="{html_lib.escape(away_logo)}"
         alt="{html_lib.escape(away_name)} logo">
    <div class="ks-pa4-premium-team-copy">
      <b>{html_lib.escape(away)}</b>
      <span>{html_lib.escape(away_name)}</span>
    </div>
  </div>

  <div class="ks-pa4-premium-center">
    <div class="ks-pa4-premium-kicker">{html_lib.escape(week_label)}</div>
    <div class="ks-pa4-premium-at">@</div>
    <strong data-prop-page2-header-kickoff-label>{html_lib.escape(kickoff)}</strong>
    <span>{html_lib.escape(display_date)}</span>
  </div>

  <div class="ks-pa4-premium-team ks-pa4-premium-home">
    <div class="ks-pa4-premium-team-copy">
      <b>{html_lib.escape(home)}</b>
      <span>{html_lib.escape(home_name)}</span>
    </div>
    <img class="ks-pa4-premium-logo"
         data-prop-page2-header-logo="{html_lib.escape(home)}"
         data-prop-page2-header-logo-side="home"
         src="{html_lib.escape(home_logo)}"
         alt="{html_lib.escape(home_name)} logo">
  </div>
</section>

<div class="ks-pa4-premium-meta">
  <span>{html_lib.escape(network)}</span>
  <span>{html_lib.escape(venue)}</span>
  <span>VERIFIED MATCHUP</span>
</div>
"""

def _team_position_shell(team: str, name: str, side: str) -> str:
    sections = []
    for position in POSITIONS:
        sections.append(
            f"""
<div class="ks-pa4-position"
     data-prop-page2-position="{position}"
     data-prop-page2-team="{html_lib.escape(team)}"
     data-prop-page2-side="{side}"
     data-prop-page2-roster-state="pending">
  <div class="ks-pa4-pos-title">{position}</div>
  <div class="ks-pa4-pos-copy">Roster layer arrives in the next step.</div>
</div>
"""
        )

    return f"""
<section class="ks-pa4-team"
         data-prop-page2-team-shell="{html_lib.escape(team)}"
         data-prop-page2-side="{side}">
  <div class="ks-pa4-team-head">
    <b>{html_lib.escape(team)}</b>
    <span>{html_lib.escape(name)}</span>
  </div>
  <div class="ks-pa4-position-grid">
    {''.join(sections)}
  </div>
</section>
"""


def render_matchup_shell() -> dict[str, Any] | None:
    handoff = resolve_matchup_handoff()

    if st.button(
        "← All Sunday games",
        key="nfl_prop_analytics_back_to_games_v1",
    ):
        return_to_schedule_page()

    if not handoff:
        st.markdown(
            """
<section data-nfl-prop-analytics-step4-page2="v1"
         data-prop-page2-state="fail-closed"
         data-prop-page2-handoff="not-ready">
  <div class="ks-pa4-empty">
    <strong>No verified matchup handoff is available.</strong>
    <span>Return to Page 1 and choose a verified game.</span>
  </div>
</section>
""",
            unsafe_allow_html=True,
        )
        return None

    away = str(handoff["away"])
    home = str(handoff["home"])
    away_name = str(handoff.get("away_name") or away)
    home_name = str(handoff.get("home_name") or home)
    network = str(handoff.get("network") or "Network TBD")
    venue = str(handoff.get("venue") or "Venue TBD")
    target_date = str(handoff.get("target_date") or "")
    source_count = int(handoff.get("source_count") or 0)

    st.markdown(
        f"""
<section class="ks-pa4-page"
         data-nfl-prop-analytics-step4-page2="v1"
         data-prop-page2-state="ready"
         data-prop-page2-handoff="ready"
         data-prop-page2-selected-game="{html_lib.escape(str(handoff['selection_key']))}"
         data-prop-page2-away="{html_lib.escape(away)}"
         data-prop-page2-home="{html_lib.escape(home)}"
         data-prop-page2-date="{html_lib.escape(target_date)}"
         data-prop-page2-source-count="{source_count}"
         data-prop-page2-position-count="8"
         data-prop-page2-positions="QB,RB,WR,TE">
  <div class="ks-pa4-eyebrow">PAGE 2 • MATCHUP HUB</div>
  {_premium_matchup_header(handoff)}

  <div class="ks-pa4-status">
    <strong>Position shell ready</strong>
    <span>Roster data is intentionally deferred to the next step.</span>
  </div>

  <div class="ks-pa4-teams">
    {_team_position_shell(away, away_name, "away")}
    {_team_position_shell(home, home_name, "home")}
  </div>
</section>

<style data-nfl-prop-analytics-step4-css="v1">
.ks-pa4-page{{
  width:100%;max-width:100%;min-width:0;overflow-x:clip;
  margin:8px 0 28px;padding:clamp(15px,2.5vw,24px);
  border:1px solid rgba(125,211,252,.22);border-radius:18px;
  background:
    radial-gradient(circle at 90% 8%,rgba(14,165,233,.10),transparent 22rem),
    linear-gradient(145deg,rgba(7,14,24,.99),rgba(10,22,38,.96));
}}
.ks-pa4-eyebrow{{color:#7dd3fc;font-size:.69rem;font-weight:900;letter-spacing:.15em}}
.ks-pa4-premium-head{{
  display:grid;grid-template-columns:minmax(0,1fr) minmax(118px,.62fr) minmax(0,1fr);
  align-items:center;gap:14px;margin:14px 0 10px;padding:16px 18px;
  border:1px solid rgba(125,211,252,.18);border-radius:16px;
  background:linear-gradient(145deg,rgba(3,10,18,.72),rgba(10,27,46,.68));
  box-shadow:inset 0 1px 0 rgba(255,255,255,.025);
}}
.ks-pa4-premium-team{{display:grid;grid-template-columns:auto minmax(0,1fr);align-items:center;gap:11px;min-width:0}}
.ks-pa4-premium-home{{grid-template-columns:minmax(0,1fr) auto;text-align:right}}
.ks-pa4-premium-logo{{width:clamp(48px,7vw,70px);height:clamp(48px,7vw,70px);object-fit:contain;filter:drop-shadow(0 7px 12px rgba(0,0,0,.28))}}
.ks-pa4-premium-team-copy{{display:flex;flex-direction:column;min-width:0}}
.ks-pa4-premium-team-copy b{{color:#f8fafc;font-size:clamp(1.15rem,3vw,1.65rem);line-height:1;font-weight:950;letter-spacing:-.025em}}
.ks-pa4-premium-team-copy span{{margin-top:5px;color:#93a8c0;font-size:.69rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.ks-pa4-premium-center{{display:flex;flex-direction:column;align-items:center;text-align:center;min-width:0}}
.ks-pa4-premium-kicker{{color:#6f8aa7;font-size:.57rem;font-weight:900;letter-spacing:.12em;white-space:nowrap}}
.ks-pa4-premium-at{{margin:2px 0 -1px;color:#38bdf8;font-size:.65rem;font-weight:950}}
.ks-pa4-premium-center strong{{color:#e0f2fe;font-size:clamp(.98rem,2.8vw,1.28rem);line-height:1.1;white-space:nowrap}}
.ks-pa4-premium-center span{{margin-top:4px;color:#8da3bc;font-size:.62rem;font-weight:800;white-space:nowrap}}
.ks-pa4-premium-meta{{display:flex;justify-content:center;flex-wrap:wrap;gap:6px;margin:0 0 13px}}
.ks-pa4-premium-meta span{{padding:5px 8px;border:1px solid rgba(125,211,252,.12);border-radius:999px;color:#7f95ae;background:rgba(14,165,233,.035);font-size:.58rem;font-weight:800}}
.ks-pa4-matchup{{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);align-items:center;gap:12px;margin:15px 0 11px}}
.ks-pa4-match-team{{display:flex;flex-direction:column;min-width:0}}
.ks-pa4-match-team b{{color:#f8fafc;font-size:clamp(1.4rem,4vw,2.25rem);line-height:1}}
.ks-pa4-match-team span{{margin-top:5px;color:#a8bad0;font-size:.78rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.ks-pa4-home{{align-items:flex-end;text-align:right}}
.ks-pa4-at{{color:#38bdf8;font-weight:900;font-size:.8rem}}
.ks-pa4-meta{{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:11px}}
.ks-pa4-meta span{{padding:6px 8px;border:1px solid rgba(148,163,184,.11);border-radius:999px;color:#8297b0;font-size:.65rem}}
.ks-pa4-status{{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:10px 0 13px;border-top:1px solid rgba(148,163,184,.10);border-bottom:1px solid rgba(148,163,184,.10)}}
.ks-pa4-status strong{{color:#bae6fd;font-size:.75rem}}
.ks-pa4-status span{{color:#7890ab;font-size:.68rem;text-align:right}}
.ks-pa4-teams{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:13px}}
.ks-pa4-team{{min-width:0;padding:12px;border:1px solid rgba(125,211,252,.14);border-radius:15px;background:rgba(3,10,18,.38)}}
.ks-pa4-team-head{{display:flex;align-items:baseline;gap:7px;margin-bottom:10px}}
.ks-pa4-team-head b{{color:#f8fafc;font-size:1rem}}
.ks-pa4-team-head span{{color:#8fa4bd;font-size:.7rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.ks-pa4-position-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}}
.ks-pa4-position{{min-width:0;padding:10px;border:1px solid rgba(148,163,184,.10);border-radius:11px;background:rgba(15,23,42,.44)}}
.ks-pa4-pos-title{{color:#e0f2fe;font-size:.77rem;font-weight:900;letter-spacing:.08em}}
.ks-pa4-pos-copy{{margin-top:4px;color:#6f839c;font-size:.62rem;line-height:1.35}}
.ks-pa4-empty{{padding:16px;border:1px solid rgba(248,113,113,.3);border-radius:14px;background:rgba(127,29,29,.12);display:flex;flex-direction:column;gap:4px}}
.ks-pa4-empty strong{{color:#fecaca}}
.ks-pa4-empty span{{color:#cbd5e1;font-size:.8rem}}
@media(max-width:720px){{
  .ks-pa4-teams{{grid-template-columns:1fr}}
}}
@media(max-width:520px){{
  .ks-pa4-premium-head{{grid-template-columns:minmax(0,1fr) 104px minmax(0,1fr);gap:6px;padding:12px 8px}}
  .ks-pa4-premium-team{{gap:6px}}
  .ks-pa4-premium-logo{{width:43px;height:43px}}
  .ks-pa4-premium-team-copy b{{font-size:1rem}}
  .ks-pa4-premium-team-copy span{{font-size:.56rem}}
  .ks-pa4-premium-kicker{{font-size:.49rem;letter-spacing:.07em}}
  .ks-pa4-premium-center strong{{font-size:.88rem}}
  .ks-pa4-premium-center span{{font-size:.53rem}}
  .ks-pa4-premium-meta span{{font-size:.52rem;padding:4px 6px}}
}}
@media(max-width:460px){{
  .ks-pa4-page{{padding:13px 11px;border-radius:15px}}
  .ks-pa4-status{{align-items:flex-start;flex-direction:column}}
  .ks-pa4-status span{{text-align:left}}
  .ks-pa4-position-grid{{grid-template-columns:1fr 1fr}}
}}
</style>
""",
        unsafe_allow_html=True,
    )
    return handoff


__all__ = [
    "GAME_QUERY_KEY",
    "MAY_MODIFY_EXISTING_NFL_MARKETS",
    "MAY_MODIFY_PASSING_YARDS",
    "MODEL_VERSION",
    "PAGE",
    "PAGE_QUERY_KEY",
    "PAGE_QUERY_VALUE",
    "PLAYER_PROP_LOGIC",
    "POSITIONS",
    "PROJECTION_LOGIC",
    "ROSTER_DATA_LOGIC",
    "SHELL_ONLY",
    "SPORTSBOOK_ODDS_LOGIC",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP",
    "_display_date",
    "_premium_matchup_header",
    "is_matchup_page",
    "open_matchup_page",
    "render_matchup_open_control",
    "render_matchup_shell",
    "resolve_matchup_handoff",
    "return_to_schedule_page",
]
