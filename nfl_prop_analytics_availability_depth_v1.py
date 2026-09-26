"""NFL Prop Analytics V1 — Step 6 Game-Day Availability + Depth Roles.

Consumes the frozen Step 5 two-source roster truth. Step 6 may attach only:
- exact ESPN depth-chart rank/role matched by the Step 5 ESPN athlete ID; and
- exact-event game-day availability state resolved by date + away/home matchup.

Before final game-day inactive reporting is complete, healthy pregame players stay
PENDING. Exact-event OUT/INACTIVE status overrides depth role. This layer adds
no player-prop lines, sportsbook odds, projections, recommendations, or
Passing Yards behavior.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import html as html_lib
from typing import Any

import streamlit as st

import nfl_game_day_availability_v1 as game_day
import nfl_moneyline_hub_v2 as depth_site
import nfl_moneyline_hub_v21 as depth_core
from sports_api import nfl_prop_player_eligibility_v1 as eligibility

MODEL_VERSION = "NFL PROP ANALYTICS V1 • STEP 6 GAME-DAY AVAILABILITY + DEPTH ROLES"
STEP = 6
PAGE = 2
AVAILABILITY_DEPTH_ONLY = True
PLAYER_PROP_LOGIC = False
SPORTSBOOK_ODDS_LOGIC = False
PROJECTION_LOGIC = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PASSING_YARDS = False
MAY_MODIFY_EXISTING_NFL_MARKETS = False

POSITIONS = ("QB", "RB", "WR", "TE")
ALLOWED_POSITIONS = frozenset(POSITIONS)
TEAM_ALIASES = {
    "WSH": "WAS",
    "WAS": "WAS",
    "JAC": "JAX",
    "LA": "LAR",
}
DEPTH_TEAM_ALIASES = {
    "WAS": "WSH",
}
AVAILABILITY_STATES = frozenset({"CONFIRMED", "PENDING", "UNVERIFIED", "CLOSED"})


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _canon_team(value: Any) -> str:
    raw = _text(value).upper()
    return TEAM_ALIASES.get(raw, raw)


def _depth_team(value: Any) -> str:
    team = _canon_team(value)
    return DEPTH_TEAM_ALIASES.get(team, team)


@st.cache_data(ttl=60, show_spinner=False)
def _resolve_espn_event_cached(
    target_date: str,
    away: str,
    home: str,
) -> dict[str, Any]:
    raw_date = "".join(ch for ch in _text(target_date) if ch.isdigit())
    away = _canon_team(away)
    home = _canon_team(home)
    if len(raw_date) != 8 or not away or not home:
        return {
            "ok": False,
            "event_id": "",
            "state": "",
            "http": None,
            "reason": "invalid matchup date/team identity",
        }

    payload, diag = depth_site._json_get(
        f"{depth_site.ESPN_BASE}/scoreboard?dates={raw_date}&limit=100"
    )
    if not diag.get("ok"):
        return {
            "ok": False,
            "event_id": "",
            "state": "",
            "http": diag.get("http"),
            "reason": "ESPN scoreboard unavailable",
        }

    for event in (payload or {}).get("events", []) or []:
        competitions = event.get("competitions") or []
        comp = competitions[0] if competitions and isinstance(competitions[0], dict) else {}
        sides: dict[str, str] = {}
        for competitor in comp.get("competitors", []) or []:
            if not isinstance(competitor, dict):
                continue
            side = _text(competitor.get("homeAway")).lower()
            team = competitor.get("team") or {}
            abbr = _canon_team(team.get("abbreviation"))
            if side in {"away", "home"} and abbr:
                sides[side] = abbr

        if sides.get("away") != away or sides.get("home") != home:
            continue

        status = comp.get("status") or event.get("status") or {}
        status_type = status.get("type") or {}
        event_id = _text(event.get("id"))
        return {
            "ok": bool(event_id.isdigit()),
            "event_id": event_id,
            "state": _text(status_type.get("state")).lower(),
            "http": diag.get("http"),
            "away": away,
            "home": home,
            "reason": "" if event_id.isdigit() else "ESPN event id missing",
        }

    return {
        "ok": False,
        "event_id": "",
        "state": "",
        "http": diag.get("http"),
        "reason": "exact ESPN matchup not found",
    }


def resolve_espn_event(handoff: dict[str, Any]) -> dict[str, Any]:
    return _resolve_espn_event_cached(
        _text(handoff.get("target_date")),
        _canon_team(handoff.get("away")),
        _canon_team(handoff.get("home")),
    )


def _load_team_depth(
    team: str,
    season: int,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    team = _canon_team(team)
    lookup = _depth_team(team)
    team_id = _text(depth_site.TEAM_IDS.get(lookup))
    if not team_id:
        return {}, {
            "ok": False,
            "team": team,
            "team_id": "",
            "source": "",
            "http": None,
            "reason": "unknown ESPN team id",
        }

    site_payload, site_diag = depth_site._depth_payload(team_id)
    parsed = (
        eligibility.parse_depth_chart(site_payload, ALLOWED_POSITIONS)
        if site_diag.get("ok")
        else {}
    )
    source = "ESPN SITE DEPTH"
    diag = site_diag

    if not parsed:
        core_payload, core_diag = depth_core._core_depth_payload(int(season), team_id)
        parsed = (
            eligibility.parse_depth_chart(core_payload, ALLOWED_POSITIONS)
            if core_diag.get("ok")
            else {}
        )
        source = "ESPN CORE DEPTH"
        diag = core_diag

    if not parsed:
        return {}, {
            "ok": False,
            "team": team,
            "team_id": team_id,
            "source": source,
            "http": diag.get("http"),
            "reason": "no exact-ID QB/RB/WR/TE depth rows",
        }

    normalized = {}
    for athlete_id, row in parsed.items():
        athlete_id = _text(athlete_id)
        position = _text(row.get("position")).upper()
        if not athlete_id.isdigit() or position not in ALLOWED_POSITIONS:
            continue
        try:
            rank = int(row.get("depth_rank") or 0)
        except (TypeError, ValueError):
            rank = 0
        if rank < 1:
            continue
        normalized[athlete_id] = {
            "espn_id": athlete_id,
            "position": position,
            "depth_rank": rank,
            "source": source,
        }

    return normalized, {
        "ok": bool(normalized),
        "team": team,
        "team_id": team_id,
        "source": source,
        "http": diag.get("http"),
        "depth_players": len(normalized),
        "reason": "" if normalized else "no usable exact-ID depth rows",
    }


def _unavailable_rows(
    snapshot: dict[str, Any],
    *,
    side: str,
) -> list[dict[str, Any]]:
    return list(snapshot.get(f"{side}_unavailable") or [])


def _unavailable_lookup(
    snapshot: dict[str, Any],
    *,
    side: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_id: dict[str, dict[str, Any]] = {}
    by_name: dict[str, dict[str, Any]] = {}
    for row in _unavailable_rows(snapshot, side=side):
        athlete_id = _text(row.get("athlete_id") or row.get("official_athlete_id"))
        name = _text(row.get("name") or row.get("player_name"))
        if athlete_id.isdigit():
            by_id[athlete_id] = row
        if name:
            by_name[name.lower()] = row
    return by_id, by_name


def _role_label(position: str, rank: int | None) -> str:
    if not rank:
        return "DEPTH UNVERIFIED"
    if int(rank) == 1:
        return f"{position}1 • STARTER"
    return f"{position}{int(rank)} • DEPTH"


def _availability_for_player(
    row: dict[str, Any],
    *,
    snapshot: dict[str, Any],
    side: str,
) -> tuple[str, str]:
    by_id, by_name = _unavailable_lookup(snapshot, side=side)
    athlete_id = _text(row.get("espn_id"))
    name = _text(row.get("name"))
    hit = by_id.get(athlete_id) or by_name.get(name.lower())

    if hit:
        status = _text(hit.get("status")) or "UNAVAILABLE"
        return "UNAVAILABLE", status.upper()

    state = _text(snapshot.get("state")).upper()
    if state == "CONFIRMED":
        return "AVAILABLE", "GAME-DAY AVAILABLE"
    if state == "PENDING":
        return "PENDING", "GAME-DAY PENDING"
    if state == "CLOSED":
        return "CLOSED", "GAME STARTED / CLOSED"
    return "UNVERIFIED", "AVAILABILITY UNVERIFIED"


def _annotate_team(
    team_truth: dict[str, Any],
    *,
    depth_rows: dict[str, dict[str, Any]],
    depth_diag: dict[str, Any],
    snapshot: dict[str, Any],
    side: str,
) -> dict[str, Any]:
    players: list[dict[str, Any]] = []
    for row in team_truth.get("verified", []) or []:
        athlete_id = _text(row.get("espn_id"))
        depth = depth_rows.get(athlete_id)
        rank = int(depth.get("depth_rank")) if depth else None
        position = _text(row.get("position")).upper()
        availability_state, availability_label = _availability_for_player(
            row,
            snapshot=snapshot,
            side=side,
        )
        players.append({
            **row,
            "depth_verified": bool(depth),
            "depth_rank": rank,
            "depth_role": _role_label(position, rank),
            "depth_source": _text((depth or {}).get("source")),
            "availability_state": availability_state,
            "availability_label": availability_label,
        })

    by_position = {
        pos: [row for row in players if row.get("position") == pos]
        for pos in POSITIONS
    }
    return {
        "team": _canon_team(team_truth.get("team")),
        "players": players,
        "by_position": by_position,
        "depth_verified_count": sum(1 for row in players if row["depth_verified"]),
        "starter_count": sum(
            1 for row in players
            if row["depth_verified"] and row.get("depth_rank") == 1
        ),
        "unavailable_count": sum(
            1 for row in players if row["availability_state"] == "UNAVAILABLE"
        ),
        "pending_count": sum(
            1 for row in players if row["availability_state"] == "PENDING"
        ),
        "depth_diag": depth_diag,
    }


def load_availability_depth_truth(
    handoff: dict[str, Any],
    roster_truth: dict[str, Any],
) -> dict[str, Any]:
    if (
        not isinstance(handoff, dict)
        or handoff.get("state") != "ready"
        or not isinstance(roster_truth, dict)
        or roster_truth.get("state") != "live"
    ):
        return {
            "state": "fail-closed",
            "reason": "frozen Step 5 roster truth is not live",
            "teams": {},
        }

    if _text(handoff.get("selection_key")) != _text(roster_truth.get("selection_key")):
        return {
            "state": "fail-closed",
            "reason": "Step 5 roster selection does not match Step 3 handoff",
            "teams": {},
        }

    event = resolve_espn_event(handoff)
    if not event.get("ok"):
        return {
            "state": "fail-closed",
            "reason": _text(event.get("reason")) or "exact ESPN event unresolved",
            "event": event,
            "teams": {},
        }

    event_map, event_diag = game_day.load_event_injury_map(event["event_id"])
    snapshot = game_day.event_availability_snapshot(
        event["event_id"],
        _canon_team(handoff.get("away")),
        _canon_team(handoff.get("home")),
        _text(event.get("state")),
        event_map=event_map,
        event_diag=event_diag,
    )
    availability_state = _text(snapshot.get("state")).upper()
    if availability_state not in AVAILABILITY_STATES or availability_state == "UNVERIFIED":
        return {
            "state": "fail-closed",
            "reason": "exact-event availability provider unverified",
            "event": event,
            "snapshot": snapshot,
            "teams": {},
        }

    try:
        season = int(_text(handoff.get("target_date"))[:4])
    except (TypeError, ValueError):
        return {
            "state": "fail-closed",
            "reason": "season missing from handoff date",
            "event": event,
            "snapshot": snapshot,
            "teams": {},
        }

    away = _canon_team(handoff.get("away"))
    home = _canon_team(handoff.get("home"))

    with ThreadPoolExecutor(max_workers=2) as pool:
        away_future = pool.submit(_load_team_depth, away, season)
        home_future = pool.submit(_load_team_depth, home, season)
        away_depth, away_diag = away_future.result()
        home_depth, home_diag = home_future.result()

    teams = {
        away: _annotate_team(
            roster_truth["teams"][away],
            depth_rows=away_depth,
            depth_diag=away_diag,
            snapshot=snapshot,
            side="away",
        ),
        home: _annotate_team(
            roster_truth["teams"][home],
            depth_rows=home_depth,
            depth_diag=home_diag,
            snapshot=snapshot,
            side="home",
        ),
    }

    required_depth_ready = all(
        any(row["depth_verified"] for row in teams[team]["by_position"][pos])
        for team in (away, home)
        for pos in POSITIONS
    )
    depth_sources_ready = bool(away_diag.get("ok") and home_diag.get("ok"))
    state = "live" if required_depth_ready and depth_sources_ready else "fail-closed"

    return {
        "state": state,
        "reason": "" if state == "live" else "required position depth roles incomplete",
        "selection_key": _text(handoff.get("selection_key")),
        "event": event,
        "event_id": event["event_id"],
        "availability_state": availability_state,
        "availability_confirmed": availability_state == "CONFIRMED",
        "availability_pending": availability_state == "PENDING",
        "teams": teams,
        "depth_verified_count": sum(
            teams[team]["depth_verified_count"] for team in (away, home)
        ),
        "starter_count": sum(
            teams[team]["starter_count"] for team in (away, home)
        ),
        "unavailable_count": sum(
            teams[team]["unavailable_count"] for team in (away, home)
        ),
        "pending_count": sum(
            teams[team]["pending_count"] for team in (away, home)
        ),
        "event_http": event_diag.get("http"),
        "snapshot": snapshot,
    }


def _availability_class(value: str) -> str:
    return {
        "AVAILABLE": "ks-pa6-available",
        "UNAVAILABLE": "ks-pa6-unavailable",
        "PENDING": "ks-pa6-pending",
        "CLOSED": "ks-pa6-closed",
    }.get(value, "ks-pa6-unverified")


def _player_row(row: dict[str, Any]) -> str:
    rank = row.get("depth_rank")
    rank_attr = str(rank or "")
    availability = _text(row.get("availability_state")).upper()
    return f"""
<div class="ks-pa6-player"
     data-prop-step6-player-id="{html_lib.escape(str(row['espn_id']))}"
     data-prop-step6-player-position="{html_lib.escape(str(row['position']))}"
     data-prop-step6-depth-verified="{str(bool(row['depth_verified'])).lower()}"
     data-prop-step6-depth-rank="{html_lib.escape(rank_attr)}"
     data-prop-step6-availability="{html_lib.escape(availability)}">
  <div class="ks-pa6-player-main">
    <strong>{html_lib.escape(str(row['name']))}</strong>
    <span>{html_lib.escape(str(row['depth_role']))}</span>
  </div>
  <div class="ks-pa6-player-state {_availability_class(availability)}">
    {html_lib.escape(str(row['availability_label']))}
  </div>
</div>
"""


def _team_html(team_truth: dict[str, Any], team_name: str) -> str:
    sections = []
    for position in POSITIONS:
        rows = team_truth["by_position"].get(position, [])
        sections.append(
            f"""
<section class="ks-pa6-position"
         data-prop-step6-position="{position}"
         data-prop-step6-team="{html_lib.escape(team_truth['team'])}"
         data-prop-step6-depth-count="{sum(1 for row in rows if row['depth_verified'])}">
  <div class="ks-pa6-pos-head">
    <strong>{position}</strong>
    <span>{sum(1 for row in rows if row['depth_verified'])} depth verified</span>
  </div>
  <div class="ks-pa6-player-list">
    {''.join(_player_row(row) for row in rows)}
  </div>
</section>
"""
        )

    return f"""
<article class="ks-pa6-team"
         data-prop-step6-team-shell="{html_lib.escape(team_truth['team'])}"
         data-prop-step6-team-depth-count="{team_truth['depth_verified_count']}"
         data-prop-step6-team-starters="{team_truth['starter_count']}"
         data-prop-step6-team-unavailable="{team_truth['unavailable_count']}">
  <div class="ks-pa6-team-head">
    <b>{html_lib.escape(team_truth['team'])}</b>
    <span>{html_lib.escape(team_name)}</span>
  </div>
  {''.join(sections)}
</article>
"""


def render_availability_depth_truth(
    handoff: dict[str, Any],
    roster_truth: dict[str, Any],
) -> dict[str, Any]:
    truth = load_availability_depth_truth(handoff, roster_truth)
    away = _canon_team(handoff.get("away"))
    home = _canon_team(handoff.get("home"))
    away_name = _text(handoff.get("away_name")) or away
    home_name = _text(handoff.get("home_name")) or home

    if truth.get("state") != "live":
        st.markdown(
            f"""
<section data-nfl-prop-analytics-step6-availability="v1"
         data-prop-step6-state="fail-closed"
         data-prop-step6-selection="{html_lib.escape(str(handoff.get('selection_key') or ''))}">
  <div class="ks-pa6-empty">
    <strong>Availability + depth truth is not complete.</strong>
    <span>{html_lib.escape(str(truth.get('reason') or 'Exact-event/depth evidence is incomplete.'))}</span>
  </div>
</section>
""",
            unsafe_allow_html=True,
        )
        return truth

    availability_state = truth["availability_state"]
    availability_message = (
        "Final inactive reporting confirmed."
        if availability_state == "CONFIRMED"
        else "Final inactive reporting is still pending; no unlisted player is called available yet."
        if availability_state == "PENDING"
        else "Game has started; pregame availability gate is closed."
    )

    st.markdown(
        f"""
<section class="ks-pa6-board"
         data-nfl-prop-analytics-step6-availability="v1"
         data-prop-step6-state="live"
         data-prop-step6-selection="{html_lib.escape(str(truth['selection_key']))}"
         data-prop-step6-event-id="{html_lib.escape(str(truth['event_id']))}"
         data-prop-step6-availability-state="{html_lib.escape(availability_state)}"
         data-prop-step6-depth-verified-count="{truth['depth_verified_count']}"
         data-prop-step6-starter-count="{truth['starter_count']}"
         data-prop-step6-unavailable-count="{truth['unavailable_count']}"
         data-prop-step6-pending-count="{truth['pending_count']}">
  <div class="ks-pa6-top">
    <div>
      <div class="ks-pa6-eyebrow">STEP 6 • GAME-DAY AVAILABILITY + DEPTH</div>
      <h3>Verified roles, fail-closed availability</h3>
    </div>
    <div class="ks-pa6-status">
      <strong>{html_lib.escape(availability_state)}</strong>
      <span>{html_lib.escape(availability_message)}</span>
    </div>
  </div>

  <div class="ks-pa6-grid">
    {_team_html(truth['teams'][away], away_name)}
    {_team_html(truth['teams'][home], home_name)}
  </div>
</section>

<style data-nfl-prop-analytics-step6-css="v1">
.ks-pa6-board{{
  width:100%;max-width:100%;min-width:0;overflow-x:clip;
  margin:12px 0 32px;padding:clamp(14px,2.2vw,20px);
  border:1px solid rgba(125,211,252,.20);border-radius:18px;
  background:linear-gradient(145deg,rgba(5,12,21,.99),rgba(8,20,35,.96));
}}
.ks-pa6-top{{display:flex;justify-content:space-between;gap:14px;align-items:flex-end;margin-bottom:13px}}
.ks-pa6-eyebrow{{color:#7dd3fc;font-size:.67rem;font-weight:900;letter-spacing:.14em}}
.ks-pa6-top h3{{margin:.3rem 0 0;color:#f8fafc;font-size:clamp(1.08rem,3vw,1.45rem)}}
.ks-pa6-status{{max-width:360px;display:flex;flex-direction:column;align-items:flex-end;gap:3px;text-align:right}}
.ks-pa6-status strong{{color:#bae6fd;font-size:.72rem}}
.ks-pa6-status span{{color:#71869f;font-size:.62rem;line-height:1.35}}
.ks-pa6-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}}
.ks-pa6-team{{min-width:0;padding:12px;border:1px solid rgba(125,211,252,.13);border-radius:15px;background:rgba(2,8,16,.35)}}
.ks-pa6-team-head{{display:flex;align-items:baseline;gap:7px;margin-bottom:9px}}
.ks-pa6-team-head b{{color:#f8fafc;font-size:1rem}}
.ks-pa6-team-head span{{color:#8fa4bd;font-size:.7rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.ks-pa6-position{{padding:9px 0;border-top:1px solid rgba(148,163,184,.09)}}
.ks-pa6-position:first-of-type{{border-top:0}}
.ks-pa6-pos-head{{display:flex;justify-content:space-between;gap:8px;margin-bottom:6px}}
.ks-pa6-pos-head strong{{color:#e0f2fe;font-size:.73rem;letter-spacing:.07em}}
.ks-pa6-pos-head span{{color:#6f839c;font-size:.6rem}}
.ks-pa6-player-list{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}}
.ks-pa6-player{{min-width:0;padding:8px;border:1px solid rgba(148,163,184,.10);border-radius:10px;background:rgba(15,23,42,.44)}}
.ks-pa6-player-main{{display:flex;justify-content:space-between;gap:6px;align-items:center}}
.ks-pa6-player-main strong{{min-width:0;color:#f1f5f9;font-size:.66rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.ks-pa6-player-main span{{color:#7dd3fc;font-size:.56rem;font-weight:800;white-space:nowrap}}
.ks-pa6-player-state{{margin-top:5px;font-size:.52rem;font-weight:900;letter-spacing:.035em}}
.ks-pa6-available{{color:#86efac}}.ks-pa6-unavailable{{color:#fca5a5}}
.ks-pa6-pending{{color:#fde68a}}.ks-pa6-closed{{color:#c4b5fd}}.ks-pa6-unverified{{color:#94a3b8}}
.ks-pa6-empty{{padding:15px;border:1px solid rgba(248,113,113,.3);border-radius:14px;background:rgba(127,29,29,.12);display:flex;flex-direction:column;gap:4px}}
.ks-pa6-empty strong{{color:#fecaca}}.ks-pa6-empty span{{color:#cbd5e1;font-size:.78rem}}
@media(max-width:760px){{
  .ks-pa6-grid{{grid-template-columns:1fr}}
}}
@media(max-width:470px){{
  .ks-pa6-board{{padding:12px 10px}}
  .ks-pa6-top{{align-items:flex-start;flex-direction:column}}
  .ks-pa6-status{{align-items:flex-start;text-align:left}}
  .ks-pa6-player-list{{grid-template-columns:1fr}}
}}
</style>
""",
        unsafe_allow_html=True,
    )
    return truth


__all__ = [
    "AVAILABILITY_DEPTH_ONLY",
    "AVAILABILITY_STATES",
    "MAY_MODIFY_EXISTING_NFL_MARKETS",
    "MAY_MODIFY_PASSING_YARDS",
    "MODEL_VERSION",
    "PAGE",
    "PLAYER_PROP_LOGIC",
    "POSITIONS",
    "PROJECTION_LOGIC",
    "SPORTSBOOK_ODDS_LOGIC",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP",
    "load_availability_depth_truth",
    "render_availability_depth_truth",
    "resolve_espn_event",
]
