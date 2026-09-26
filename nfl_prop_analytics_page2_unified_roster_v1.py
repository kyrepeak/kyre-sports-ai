"""NFL Prop Analytics Page 2 Polish Step 2 — unified roster + availability presentation.

Presentation-only composition. It consumes the frozen Step 5 roster truth and
frozen Step 6 availability/depth truth, then renders each player exactly once.
No roster reconciliation, event resolution, depth, availability, player
eligibility, prop, odds, projection, router, or Passing Yards logic is changed.
"""
from __future__ import annotations

import html as html_lib
from typing import Any

import streamlit as st

from nfl_prop_analytics_roster_truth_v1 import load_verified_roster_truth
from nfl_prop_analytics_availability_depth_v1 import load_availability_depth_truth

MODEL_VERSION = "NFL PROP ANALYTICS PAGE 2 POLISH STEP 2 • UNIFIED ROSTER + AVAILABILITY"
STEP = 3
PAGE = 2
PRESENTATION_ONLY = True
MAY_MODIFY_PASSING_YARDS = False
MAY_MODIFY_EXISTING_NFL_MARKETS = False
POSITIONS = ("QB", "RB", "WR", "TE")
FILTERS = ("ALL", "QB", "RB", "WR", "TE")
FILTER_KEY = "nfl_prop_analytics_page2_position_filter_v1"


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _availability_class(value: str) -> str:
    return {
        "AVAILABLE": "ks-pa-u-available",
        "UNAVAILABLE": "ks-pa-u-unavailable",
        "PENDING": "ks-pa-u-pending",
        "CLOSED": "ks-pa-u-closed",
    }.get(_text(value).upper(), "ks-pa-u-unverified")


def _player_card(row: dict[str, Any]) -> str:
    athlete_id = _text(row.get("espn_id"))
    name = _text(row.get("name"))
    team = _text(row.get("team")).upper()
    position = _text(row.get("position")).upper()
    jersey = f"#{_text(row.get('jersey_number'))}" if _text(row.get("jersey_number")) else "—"
    depth = _text(row.get("depth_role")) or "DEPTH UNVERIFIED"
    availability = _text(row.get("availability_state")).upper()
    availability_label = _text(row.get("availability_label")) or availability or "UNVERIFIED"
    verified = bool(row.get("verified"))
    source_count = int(row.get("source_count") or 0)
    return f"""
<div class="ks-pa-u-player"
     data-prop-page2-unified-player-id="{html_lib.escape(athlete_id)}"
     data-prop-page2-unified-team="{html_lib.escape(team)}"
     data-prop-page2-unified-position="{html_lib.escape(position)}"
     data-prop-page2-unified-roster-verified="{str(verified).lower()}"
     data-prop-page2-unified-source-count="{source_count}"
     data-prop-page2-unified-depth-verified="{str(bool(row.get('depth_verified'))).lower()}"
     data-prop-page2-unified-depth-rank="{html_lib.escape(_text(row.get('depth_rank')))}"
     data-prop-page2-unified-availability="{html_lib.escape(availability)}">
  <div class="ks-pa-u-main">
    <div class="ks-pa-u-name">
      <strong>{html_lib.escape(name)}</strong>
      <span>{html_lib.escape(jersey)} • {html_lib.escape(position)}</span>
    </div>
    <span class="ks-pa-u-depth">{html_lib.escape(depth)}</span>
  </div>
  <div class="ks-pa-u-bottom">
    <span class="ks-pa-u-verified">VERIFIED • ESPN + NFLVERSE</span>
    <span class="ks-pa-u-state {_availability_class(availability)}">{html_lib.escape(availability_label)}</span>
  </div>
</div>
"""


def _team_column(team_truth: dict[str, Any], team_name: str) -> str:
    sections = []
    for position in POSITIONS:
        rows = team_truth.get("by_position", {}).get(position, []) or []
        cards = "".join(_player_card(row) for row in rows)
        sections.append(f"""
<section class="ks-pa-u-position"
         data-prop-page2-unified-position-section="{position}"
         data-prop-page2-unified-position-team="{html_lib.escape(_text(team_truth.get('team')))}"
         data-prop-page2-unified-position-count="{len(rows)}">
  <div class="ks-pa-u-pos-head">
    <strong>{position}</strong>
    <span>{len(rows)} players</span>
  </div>
  <div class="ks-pa-u-list">{cards}</div>
</section>
""")
    return f"""
<article class="ks-pa-u-team"
         data-prop-page2-unified-team-shell="{html_lib.escape(_text(team_truth.get('team')))}"
         data-prop-page2-unified-team-count="{len(team_truth.get('players', []) or [])}">
  <div class="ks-pa-u-team-head">
    <b>{html_lib.escape(_text(team_truth.get('team')))}</b>
    <span>{html_lib.escape(team_name)}</span>
  </div>
  {''.join(sections)}
</article>
"""


def render_unified_roster_availability(
    handoff: dict[str, Any],
    roster_truth: dict[str, Any] | None = None,
    availability_truth: dict[str, Any] | None = None,
) -> dict[str, Any]:
    roster_truth = roster_truth if isinstance(roster_truth, dict) else load_verified_roster_truth(handoff)
    if roster_truth.get("state") != "live":
        st.markdown(
            f"""
<section data-nfl-prop-analytics-page2-unified-roster="v1"
         data-prop-page2-unified-state="fail-closed"
         data-prop-page2-unified-roster-state="{html_lib.escape(_text(roster_truth.get('state')))}">
  <div class="ks-pa-u-empty">
    <strong>Verified roster truth is not complete.</strong>
    <span>{html_lib.escape(_text(roster_truth.get('reason')) or 'Independent roster verification is incomplete.')}</span>
  </div>
</section>
""",
            unsafe_allow_html=True,
        )
        return roster_truth

    truth = availability_truth if isinstance(availability_truth, dict) else load_availability_depth_truth(handoff, roster_truth)
    if truth.get("state") != "live":
        st.markdown(
            f"""
<section data-nfl-prop-analytics-page2-unified-roster="v1"
         data-prop-page2-unified-state="fail-closed"
         data-prop-page2-unified-roster-state="live"
         data-prop-page2-unified-availability-state="{html_lib.escape(_text(truth.get('state')))}">
  <div class="ks-pa-u-empty">
    <strong>Availability + depth truth is not complete.</strong>
    <span>{html_lib.escape(_text(truth.get('reason')) or 'Exact-event/depth evidence is incomplete.')}</span>
  </div>
</section>
""",
            unsafe_allow_html=True,
        )
        return truth

    away = _text(handoff.get("away")).upper()
    home = _text(handoff.get("home")).upper()
    away_name = _text(handoff.get("away_name")) or away
    home_name = _text(handoff.get("home_name")) or home
    all_rows = [
        row
        for team in (away, home)
        for row in truth["teams"][team].get("players", [])
    ]
    verified_count = sum(1 for row in all_rows if row.get("verified"))
    availability_state = _text(truth.get("availability_state")).upper()
    status_copy = (
        "Final game-day availability confirmed."
        if availability_state == "CONFIRMED"
        else "Game-day availability is pending; no player is called available without final confirmation."
        if availability_state == "PENDING"
        else "Pregame availability gate is closed."
    )

    st.markdown(
        f"""
<section class="ks-pa-u-board"
         data-nfl-prop-analytics-page2-unified-roster="v1"
         data-prop-page2-unified-state="live"
         data-prop-page2-unified-selection="{html_lib.escape(_text(truth.get('selection_key')))}"
         data-prop-page2-unified-event-id="{html_lib.escape(_text(truth.get('event_id')))}"
         data-prop-page2-unified-player-count="{len(all_rows)}"
         data-prop-page2-unified-verified-count="{verified_count}"
         data-prop-page2-unified-depth-verified-count="{int(truth.get('depth_verified_count') or 0)}"
         data-prop-page2-unified-availability-state="{html_lib.escape(availability_state)}">
  <div class="ks-pa-u-top">
    <div>
      <div class="ks-pa-u-eyebrow">PAGE 2 • VERIFIED PLAYERS</div>
      <h3>Roster + availability</h3>
    </div>
    <div class="ks-pa-u-proof">
      <strong>{verified_count} verified players</strong>
      <span>{html_lib.escape(status_copy)}</span>
    </div>
  </div>

  <div class="ks-pa-u-grid">
    {_team_column(filtered_truth["teams"][away], away_name, selected_position)}
    {_team_column(filtered_truth["teams"][home], home_name, selected_position)}
  </div>
</section>

<style data-nfl-prop-analytics-page2-unified-roster-css="v1">
.ks-pa-u-board{{width:100%;max-width:100%;min-width:0;overflow-x:clip;margin:12px 0 28px;padding:clamp(14px,2.2vw,20px);border:1px solid rgba(125,211,252,.20);border-radius:18px;background:linear-gradient(145deg,rgba(5,12,21,.99),rgba(8,20,35,.96))}}
.ks-pa-u-top{{display:flex;justify-content:space-between;gap:14px;align-items:flex-end;margin-bottom:13px}}
.ks-pa-u-eyebrow{{color:#7dd3fc;font-size:.67rem;font-weight:900;letter-spacing:.14em}}
.ks-pa-u-top h3{{margin:.3rem 0 0;color:#f8fafc;font-size:clamp(1.08rem,3vw,1.45rem)}}
.ks-pa-u-proof{{max-width:390px;display:flex;flex-direction:column;align-items:flex-end;gap:3px;text-align:right}}
.ks-pa-u-proof strong{{color:#bae6fd;font-size:.72rem}}.ks-pa-u-proof span{{color:#71869f;font-size:.62rem;line-height:1.35}}
.ks-pa-u-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}}
.ks-pa-u-team{{min-width:0;padding:12px;border:1px solid rgba(125,211,252,.13);border-radius:15px;background:rgba(2,8,16,.35)}}
.ks-pa-u-team-head{{display:flex;align-items:baseline;gap:7px;margin-bottom:9px}}
.ks-pa-u-team-head b{{color:#f8fafc;font-size:1rem}}.ks-pa-u-team-head span{{color:#8fa4bd;font-size:.7rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.ks-pa-u-position{{padding:9px 0;border-top:1px solid rgba(148,163,184,.09)}}.ks-pa-u-position:first-of-type{{border-top:0}}
.ks-pa-u-pos-head{{display:flex;justify-content:space-between;gap:8px;margin-bottom:6px}}.ks-pa-u-pos-head strong{{color:#e0f2fe;font-size:.73rem;letter-spacing:.07em}}.ks-pa-u-pos-head span{{color:#6f839c;font-size:.6rem}}
.ks-pa-u-list{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}}
.ks-pa-u-player{{min-width:0;padding:9px;border:1px solid rgba(148,163,184,.10);border-radius:11px;background:rgba(15,23,42,.44)}}
.ks-pa-u-main{{display:flex;justify-content:space-between;gap:7px;align-items:flex-start}}
.ks-pa-u-name{{display:flex;flex-direction:column;min-width:0}}.ks-pa-u-name strong{{color:#f1f5f9;font-size:.67rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.ks-pa-u-name span{{margin-top:2px;color:#7690aa;font-size:.54rem}}
.ks-pa-u-depth{{color:#7dd3fc;font-size:.54rem;font-weight:900;white-space:nowrap}}
.ks-pa-u-bottom{{display:flex;justify-content:space-between;gap:7px;align-items:center;margin-top:6px;padding-top:5px;border-top:1px solid rgba(148,163,184,.07)}}
.ks-pa-u-verified{{color:#5f738b;font-size:.49rem;white-space:nowrap}}.ks-pa-u-state{{font-size:.5rem;font-weight:900;letter-spacing:.025em;text-align:right}}
.ks-pa-u-available{{color:#86efac}}.ks-pa-u-unavailable{{color:#fca5a5}}.ks-pa-u-pending{{color:#fde68a}}.ks-pa-u-closed{{color:#c4b5fd}}.ks-pa-u-unverified{{color:#94a3b8}}
.ks-pa-u-empty{{padding:15px;border:1px solid rgba(248,113,113,.3);border-radius:14px;background:rgba(127,29,29,.12);display:flex;flex-direction:column;gap:4px}}.ks-pa-u-empty strong{{color:#fecaca}}.ks-pa-u-empty span{{color:#cbd5e1;font-size:.78rem}}
@media(max-width:760px){{.ks-pa-u-grid{{grid-template-columns:1fr}}}}
@media(max-width:470px){{.ks-pa-u-board{{padding:12px 10px}}.ks-pa-u-top{{align-items:flex-start;flex-direction:column}}.ks-pa-u-proof{{align-items:flex-start;text-align:left}}.ks-pa-u-list{{grid-template-columns:1fr}}}}
</style>
""",
        unsafe_allow_html=True,
    )
    return truth


__all__ = [
    "MAY_MODIFY_EXISTING_NFL_MARKETS",
    "MAY_MODIFY_PASSING_YARDS",
    "MODEL_VERSION",
    "PAGE",
    "FILTERS",
    "FILTER_KEY",
    "POSITIONS",
    "PRESENTATION_ONLY",
    "STEP",
    "render_unified_roster_availability",
]
