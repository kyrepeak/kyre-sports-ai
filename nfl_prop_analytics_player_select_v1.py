"""NFL Prop Analytics V1 — Step 7 Eligible Player Selection + Prop Page Handoff.

Consumes the frozen Step 6 availability/depth truth. Step 7 only selects a
player already admitted by Steps 5-6 and builds an exact player handoff for a
future prop page.

A PENDING player may be selected for navigation continuity, but the handoff
keeps the downstream prop-analysis gate CLOSED until Step 6 reports AVAILABLE.
UNAVAILABLE, CLOSED, UNVERIFIED, or depth-unverified players are never
selectable.

No player-prop lines, sportsbook odds, projections, recommendations, or
Passing Yards behavior live here.
"""
from __future__ import annotations

import html as html_lib
from typing import Any

import streamlit as st

MODEL_VERSION = "NFL PROP ANALYTICS V1 • STEP 7 ELIGIBLE PLAYER SELECTION + PROP PAGE HANDOFF"
STEP = 7
PAGE = 2
SELECTION_HANDOFF_ONLY = True
PLAYER_PROP_LOGIC = False
SPORTSBOOK_ODDS_LOGIC = False
PROJECTION_LOGIC = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PASSING_YARDS = False
MAY_MODIFY_EXISTING_NFL_MARKETS = False

POSITIONS = ("QB", "RB", "WR", "TE")
SELECTABLE_AVAILABILITY = frozenset({"PENDING", "AVAILABLE"})
BLOCKED_AVAILABILITY = frozenset({"UNAVAILABLE", "CLOSED", "UNVERIFIED"})
SESSION_KEY = "nfl_prop_analytics_selected_player_v1"
QUERY_KEY = "ks_pa_player"
HANDOFF_VERSION = "v1"


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _query_value(key: str) -> str:
    try:
        raw = st.query_params.get(key, "")
    except Exception:
        return ""
    if isinstance(raw, list):
        return str(raw[0] if raw else "")
    return str(raw or "")


def _selection_eligible(row: dict[str, Any]) -> bool:
    athlete_id = _text(row.get("espn_id"))
    position = _text(row.get("position")).upper()
    availability = _text(row.get("availability_state")).upper()
    return bool(
        athlete_id.isdigit()
        and position in POSITIONS
        and bool(row.get("verified"))
        and int(row.get("source_count") or 0) >= 2
        and bool(row.get("depth_verified"))
        and availability in SELECTABLE_AVAILABILITY
    )


def eligible_players(step6_truth: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(step6_truth, dict) or step6_truth.get("state") != "live":
        return []

    rows: list[dict[str, Any]] = []
    for team_truth in (step6_truth.get("teams") or {}).values():
        if not isinstance(team_truth, dict):
            continue
        for row in team_truth.get("players", []) or []:
            if not isinstance(row, dict) or not _selection_eligible(row):
                continue
            availability = _text(row.get("availability_state")).upper()
            rows.append({
                **row,
                "espn_id": _text(row.get("espn_id")),
                "team": _text(row.get("team")).upper(),
                "position": _text(row.get("position")).upper(),
                "availability_state": availability,
                "selection_eligible": True,
                "prop_analysis_gate_open": availability == "AVAILABLE",
            })

    position_order = {pos: i for i, pos in enumerate(POSITIONS)}
    rows.sort(
        key=lambda row: (
            row.get("team", ""),
            position_order.get(row.get("position"), 99),
            int(row.get("depth_rank") or 999),
            row.get("name", ""),
        )
    )
    return rows


def _player_key(row: dict[str, Any]) -> str:
    return _text(row.get("espn_id"))


def _player_label(row: dict[str, Any]) -> str:
    gate = "CLEARED" if row.get("prop_analysis_gate_open") else "PENDING"
    return (
        f"{row.get('team', '')} • {row.get('position', '')} • "
        f"{row.get('name', '')} • {row.get('depth_role', '')} • {gate}"
    )


def _resolve_initial_index(
    players: list[dict[str, Any]],
    requested_player_id: str | None,
    session_player_id: str | None,
) -> int:
    keys = [_player_key(row) for row in players]
    for candidate in (
        _text(requested_player_id),
        _text(session_player_id),
    ):
        if candidate in keys:
            return keys.index(candidate)
    return 0


def build_player_handoff(
    matchup_handoff: dict[str, Any],
    step6_truth: dict[str, Any],
    player: dict[str, Any],
) -> dict[str, Any]:
    if not _selection_eligible(player):
        raise ValueError("Player is not Step 7 selection-eligible.")

    availability = _text(player.get("availability_state")).upper()
    prop_gate_open = availability == "AVAILABLE"
    return {
        "version": HANDOFF_VERSION,
        "state": "ready",
        "selection_key": _text(matchup_handoff.get("selection_key")),
        "event_id": _text(step6_truth.get("event_id")),
        "player_id": _text(player.get("espn_id")),
        "player_name": _text(player.get("name")),
        "team": _text(player.get("team")).upper(),
        "position": _text(player.get("position")).upper(),
        "depth_rank": int(player.get("depth_rank") or 0),
        "depth_role": _text(player.get("depth_role")),
        "availability_state": availability,
        "roster_verified": bool(player.get("verified")),
        "roster_source_count": int(player.get("source_count") or 0),
        "depth_verified": bool(player.get("depth_verified")),
        "selection_eligible": True,
        "prop_analysis_gate_open": prop_gate_open,
        "prop_page_ready": True,
    }


def get_selected_player_handoff() -> dict[str, Any] | None:
    value = st.session_state.get(SESSION_KEY)
    if isinstance(value, dict) and value.get("state") == "ready":
        return dict(value)
    return None


def _persist_query(player_id: str) -> None:
    try:
        st.query_params[QUERY_KEY] = player_id
    except Exception:
        pass


def render_player_selection_handoff(
    matchup_handoff: dict[str, Any],
    step6_truth: dict[str, Any],
) -> dict[str, Any] | None:
    players = eligible_players(step6_truth)
    if not players:
        st.session_state.pop(SESSION_KEY, None)
        st.markdown(
            """
<section data-nfl-prop-analytics-step7-player-selection="v1"
         data-prop-step7-state="fail-closed"
         data-prop-step7-candidate-count="0">
  <div class="ks-pa7-empty">
    <strong>No eligible player handoff is available.</strong>
    <span>Step 7 requires frozen Step 5 identity + Step 6 exact depth and a non-blocked availability state.</span>
  </div>
</section>
""",
            unsafe_allow_html=True,
        )
        return None

    prior = st.session_state.get(SESSION_KEY) or {}
    requested = _query_value(QUERY_KEY)
    session_player_id = (
        prior.get("player_id") if isinstance(prior, dict) else ""
    )
    index = _resolve_initial_index(players, requested, session_player_id)

    chosen_index = st.selectbox(
        "Choose eligible player",
        options=list(range(len(players))),
        index=index,
        format_func=lambda idx: _player_label(players[int(idx)]),
        key="nfl_prop_analytics_player_picker_v1",
    )
    selected = players[int(chosen_index)]
    handoff = build_player_handoff(matchup_handoff, step6_truth, selected)
    st.session_state[SESSION_KEY] = handoff
    _persist_query(handoff["player_id"])

    candidate_ids = ",".join(_player_key(row) for row in players)
    gate_state = "OPEN" if handoff["prop_analysis_gate_open"] else "CLOSED"
    gate_copy = (
        "Game-day availability is confirmed for this player."
        if handoff["prop_analysis_gate_open"]
        else "Player navigation is ready, but prop analysis stays closed while game-day availability is pending."
    )

    st.markdown(
        f"""
<section class="ks-pa7-board"
         data-nfl-prop-analytics-step7-player-selection="v1"
         data-prop-step7-state="ready"
         data-prop-step7-candidate-count="{len(players)}"
         data-prop-step7-candidate-ids="{html_lib.escape(candidate_ids)}"
         data-prop-step7-player-id="{html_lib.escape(handoff['player_id'])}"
         data-prop-step7-player-team="{html_lib.escape(handoff['team'])}"
         data-prop-step7-player-position="{html_lib.escape(handoff['position'])}"
         data-prop-step7-player-depth-rank="{handoff['depth_rank']}"
         data-prop-step7-availability="{html_lib.escape(handoff['availability_state'])}"
         data-prop-step7-prop-gate="{gate_state}"
         data-prop-step7-prop-page-ready="true">
  <div class="ks-pa7-top">
    <div>
      <div class="ks-pa7-eyebrow">STEP 7 • ELIGIBLE PLAYER HANDOFF</div>
      <h3>{html_lib.escape(handoff['player_name'])}</h3>
      <div class="ks-pa7-meta">
        <span>{html_lib.escape(handoff['team'])}</span>
        <span>{html_lib.escape(handoff['position'])}</span>
        <span>{html_lib.escape(handoff['depth_role'])}</span>
        <span>ESPN ID {html_lib.escape(handoff['player_id'])}</span>
      </div>
    </div>
    <div class="ks-pa7-gate">
      <strong>PROP ANALYSIS GATE {gate_state}</strong>
      <span>{html_lib.escape(gate_copy)}</span>
    </div>
  </div>

  <div class="ks-pa7-handoff">
    <strong>Prop-page handoff ready</strong>
    <span>Exact matchup + event + player identity + depth + availability state are locked for the next page.</span>
  </div>
</section>

<style data-nfl-prop-analytics-step7-css="v1">
.ks-pa7-board{{
  width:100%;max-width:100%;min-width:0;overflow-x:clip;
  margin:12px 0 34px;padding:clamp(14px,2.2vw,20px);
  border:1px solid rgba(125,211,252,.20);border-radius:18px;
  background:linear-gradient(145deg,rgba(5,12,21,.99),rgba(8,20,35,.96));
}}
.ks-pa7-top{{display:flex;justify-content:space-between;gap:15px;align-items:flex-start}}
.ks-pa7-eyebrow{{color:#7dd3fc;font-size:.67rem;font-weight:900;letter-spacing:.14em}}
.ks-pa7-top h3{{margin:.3rem 0 .5rem;color:#f8fafc;font-size:clamp(1.15rem,3vw,1.55rem)}}
.ks-pa7-meta{{display:flex;flex-wrap:wrap;gap:6px}}
.ks-pa7-meta span{{padding:5px 7px;border:1px solid rgba(148,163,184,.11);border-radius:999px;color:#8fa4bd;font-size:.62rem}}
.ks-pa7-gate{{max-width:370px;display:flex;flex-direction:column;align-items:flex-end;gap:4px;text-align:right}}
.ks-pa7-gate strong{{color:#bae6fd;font-size:.72rem}}
.ks-pa7-gate span{{color:#71869f;font-size:.62rem;line-height:1.4}}
.ks-pa7-handoff{{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-top:14px;padding-top:12px;border-top:1px solid rgba(148,163,184,.10)}}
.ks-pa7-handoff strong{{color:#e0f2fe;font-size:.72rem}}
.ks-pa7-handoff span{{color:#7890ab;font-size:.64rem;text-align:right}}
.ks-pa7-empty{{padding:15px;border:1px solid rgba(248,113,113,.3);border-radius:14px;background:rgba(127,29,29,.12);display:flex;flex-direction:column;gap:4px}}
.ks-pa7-empty strong{{color:#fecaca}}.ks-pa7-empty span{{color:#cbd5e1;font-size:.78rem}}
@media(max-width:620px){{
  .ks-pa7-top,.ks-pa7-handoff{{align-items:flex-start;flex-direction:column}}
  .ks-pa7-gate{{align-items:flex-start;text-align:left}}
  .ks-pa7-handoff span{{text-align:left}}
}}
</style>
""",
        unsafe_allow_html=True,
    )
    return handoff


__all__ = [
    "BLOCKED_AVAILABILITY",
    "HANDOFF_VERSION",
    "MAY_MODIFY_EXISTING_NFL_MARKETS",
    "MAY_MODIFY_PASSING_YARDS",
    "MODEL_VERSION",
    "PAGE",
    "PLAYER_PROP_LOGIC",
    "POSITIONS",
    "PROJECTION_LOGIC",
    "QUERY_KEY",
    "SELECTION_HANDOFF_ONLY",
    "SELECTABLE_AVAILABILITY",
    "SESSION_KEY",
    "SPORTSBOOK_ODDS_LOGIC",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP",
    "build_player_handoff",
    "eligible_players",
    "get_selected_player_handoff",
    "render_player_selection_handoff",
]
