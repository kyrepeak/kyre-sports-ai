"""NFL Prop Analytics V1 — Step 5 Verified Roster Truth Layer.

Consumes the frozen Step 4 verified matchup shell and populates Page 2 with
verified QB/RB/WR/TE roster identity. A player is VERIFIED only when the
current ESPN roster and nflverse weekly roster agree on the exact ESPN athlete
ID and position, with both sources reporting roster-eligible status.

This step contains no player-prop lines, sportsbook odds, projections,
recommendations, or Passing Yards behavior.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
import html as html_lib
from io import StringIO
from typing import Any

import pandas as pd
import requests
import streamlit as st

import nfl_game_day_availability_v1 as game_day

MODEL_VERSION = "NFL PROP ANALYTICS V1 • STEP 5 VERIFIED ROSTER TRUTH"
STEP = 5
PAGE = 2
ROSTER_TRUTH_ONLY = True
PLAYER_PROP_LOGIC = False
SPORTSBOOK_ODDS_LOGIC = False
PROJECTION_LOGIC = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PASSING_YARDS = False
MAY_MODIFY_EXISTING_NFL_MARKETS = False

POSITIONS = ("QB", "RB", "WR", "TE")
NFLVERSE_WEEKLY_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "weekly_rosters/roster_weekly_{season}.csv"
)
REQUEST_HEADERS = {
    "User-Agent": "KyreSportsAI/1.0 roster-truth (+https://kyre-sports-ai.streamlit.app)"
}
NFLVERSE_ACTIVE_STATUSES = frozenset({"ACT", "ACTIVE"})
NFLVERSE_TEAM_ALIASES = {
    "LA": "LAR",
    "JAC": "JAX",
    "WSH": "WAS",
}


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _id_text(value: Any) -> str:
    raw = _text(value)
    if not raw or raw.lower() == "nan":
        return ""
    if raw.endswith(".0") and raw[:-2].isdigit():
        raw = raw[:-2]
    return raw if raw.isdigit() else ""


def _canon_team(value: Any) -> str:
    team = _text(value).upper()
    return NFLVERSE_TEAM_ALIASES.get(team, team)


def _canon_position(value: Any) -> str:
    return _text(value).upper()


def _status_key(value: Any) -> str:
    return "".join(ch for ch in _text(value).upper() if ch.isalnum())


def _nflverse_active(value: Any) -> bool:
    return _status_key(value) in NFLVERSE_ACTIVE_STATUSES


@st.cache_data(ttl=300, show_spinner=False)
def _load_nflverse_weekly(season: int) -> tuple[pd.DataFrame, dict[str, Any]]:
    url = NFLVERSE_WEEKLY_URL.format(season=int(season))
    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=20)
        response.raise_for_status()
        frame = pd.read_csv(StringIO(response.text), low_memory=False)
    except Exception as exc:
        return pd.DataFrame(), {
            "ok": False,
            "http": getattr(getattr(exc, "response", None), "status_code", None),
            "reason": f"{type(exc).__name__}:{exc}",
            "url": url,
        }

    required = {"season", "week", "team", "position", "status", "full_name", "espn_id"}
    missing = sorted(required - set(frame.columns))
    if missing:
        return pd.DataFrame(), {
            "ok": False,
            "http": response.status_code,
            "reason": "missing columns:" + ",".join(missing),
            "url": url,
        }

    return frame, {
        "ok": True,
        "http": response.status_code,
        "rows": int(len(frame)),
        "url": url,
    }


def _nflverse_team_week(
    frame: pd.DataFrame,
    *,
    team: str,
    season: int,
    week: int,
) -> list[dict[str, Any]]:
    if frame.empty:
        return []

    work = frame.copy()
    work["season_num"] = pd.to_numeric(work["season"], errors="coerce")
    work["week_num"] = pd.to_numeric(work["week"], errors="coerce")
    work["team_canon"] = work["team"].map(_canon_team)
    work["position_canon"] = work["position"].map(_canon_position)
    work["espn_id_canon"] = work["espn_id"].map(_id_text)

    selected = work[
        (work["season_num"] == int(season))
        & (work["week_num"] == int(week))
        & (work["team_canon"] == _canon_team(team))
        & (work["position_canon"].isin(POSITIONS))
    ]

    rows: list[dict[str, Any]] = []
    for _, row in selected.iterrows():
        espn_id = _id_text(row.get("espn_id"))
        if not espn_id:
            continue
        rows.append({
            "espn_id": espn_id,
            "name": _text(row.get("full_name")),
            "position": _canon_position(row.get("position")),
            "status": _text(row.get("status")),
            "jersey_number": _text(row.get("jersey_number")),
            "gsis_id": _text(row.get("gsis_id")),
            "headshot_url": _text(row.get("headshot_url")),
            "active": _nflverse_active(row.get("status")),
        })

    dedup: dict[str, dict[str, Any]] = {}
    for row in rows:
        prior = dedup.get(row["espn_id"])
        if prior is None or (not prior["active"] and row["active"]):
            dedup[row["espn_id"]] = row
    return list(dedup.values())


def _espn_team_rows(team: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, diag = game_day.load_current_team_roster(team)
    selected = []
    for row in rows:
        position = _canon_position(row.get("position"))
        athlete_id = _id_text(row.get("athlete_id"))
        if position not in POSITIONS or not athlete_id:
            continue
        selected.append({
            "espn_id": athlete_id,
            "name": _text(row.get("name")),
            "position": position,
            "roster_status": _text(row.get("roster_status")),
            "group_label": _text(row.get("group_label")),
            "active": bool(row.get("prop_eligible")),
        })
    return selected, dict(diag or {})


def _reconcile_team_roster(
    *,
    team: str,
    espn_rows: list[dict[str, Any]],
    nflverse_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    espn_by_id = {row["espn_id"]: row for row in espn_rows if row.get("espn_id")}
    nflverse_by_id = {row["espn_id"]: row for row in nflverse_rows if row.get("espn_id")}

    verified: list[dict[str, Any]] = []
    disagreements: list[dict[str, Any]] = []

    all_ids = sorted(set(espn_by_id) | set(nflverse_by_id))
    for athlete_id in all_ids:
        espn = espn_by_id.get(athlete_id)
        nflverse = nflverse_by_id.get(athlete_id)

        if espn is None or nflverse is None:
            disagreements.append({
                "espn_id": athlete_id,
                "reason": "missing-independent-source",
                "espn_present": espn is not None,
                "nflverse_present": nflverse is not None,
            })
            continue

        same_position = espn["position"] == nflverse["position"]
        both_active = bool(espn["active"] and nflverse["active"])
        if not same_position or not both_active:
            disagreements.append({
                "espn_id": athlete_id,
                "reason": "position-or-status-disagreement",
                "espn_position": espn["position"],
                "nflverse_position": nflverse["position"],
                "espn_active": bool(espn["active"]),
                "nflverse_active": bool(nflverse["active"]),
            })
            continue

        verified.append({
            "espn_id": athlete_id,
            "team": _canon_team(team),
            "name": espn["name"] or nflverse["name"],
            "position": espn["position"],
            "jersey_number": nflverse.get("jersey_number", ""),
            "gsis_id": nflverse.get("gsis_id", ""),
            "headshot_url": nflverse.get("headshot_url", ""),
            "espn_roster_status": espn.get("roster_status", ""),
            "nflverse_roster_status": nflverse.get("status", ""),
            "source_count": 2,
            "sources": ("ESPN", "NFLVERSE"),
            "verified": True,
        })

    position_order = {pos: i for i, pos in enumerate(POSITIONS)}
    verified.sort(
        key=lambda row: (
            position_order.get(row["position"], 99),
            int(row["jersey_number"]) if str(row["jersey_number"]).isdigit() else 999,
            row["name"],
        )
    )

    by_position = {
        pos: [row for row in verified if row["position"] == pos]
        for pos in POSITIONS
    }
    return {
        "team": _canon_team(team),
        "verified": verified,
        "by_position": by_position,
        "verified_count": len(verified),
        "disagreements": disagreements,
        "disagreement_count": len(disagreements),
    }


def load_verified_roster_truth(
    handoff: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(handoff, dict) or handoff.get("state") != "ready":
        return {
            "state": "fail-closed",
            "reason": "verified matchup handoff missing",
            "teams": {},
            "sources_available": (),
        }

    away = _canon_team(handoff.get("away"))
    home = _canon_team(handoff.get("home"))
    if not away or not home:
        return {
            "state": "fail-closed",
            "reason": "matchup teams missing",
            "teams": {},
            "sources_available": (),
        }

    try:
        season = int(str(handoff.get("target_date") or "")[:4])
        week = int(handoff.get("week"))
    except (TypeError, ValueError):
        return {
            "state": "fail-closed",
            "reason": "season/week missing",
            "teams": {},
            "sources_available": (),
        }

    nflverse_frame, nflverse_diag = _load_nflverse_weekly(season)

    with ThreadPoolExecutor(max_workers=2) as pool:
        away_future = pool.submit(_espn_team_rows, away)
        home_future = pool.submit(_espn_team_rows, home)
        away_espn, away_diag = away_future.result()
        home_espn, home_diag = home_future.result()

    source_ok = bool(
        nflverse_diag.get("ok")
        and away_diag.get("ok")
        and home_diag.get("ok")
    )
    sources_available = []
    if away_diag.get("ok") and home_diag.get("ok"):
        sources_available.append("ESPN")
    if nflverse_diag.get("ok"):
        sources_available.append("NFLVERSE")

    away_nv = _nflverse_team_week(
        nflverse_frame,
        team=away,
        season=season,
        week=week,
    )
    home_nv = _nflverse_team_week(
        nflverse_frame,
        team=home,
        season=season,
        week=week,
    )

    away_truth = _reconcile_team_roster(
        team=away,
        espn_rows=away_espn,
        nflverse_rows=away_nv,
    )
    home_truth = _reconcile_team_roster(
        team=home,
        espn_rows=home_espn,
        nflverse_rows=home_nv,
    )

    required_positions_ready = all(
        away_truth["by_position"][pos]
        and home_truth["by_position"][pos]
        for pos in POSITIONS
    )
    state = "live" if source_ok and required_positions_ready else "fail-closed"

    return {
        "state": state,
        "reason": "" if state == "live" else "independent roster verification incomplete",
        "season": season,
        "week": week,
        "selection_key": _text(handoff.get("selection_key")),
        "away": away,
        "home": home,
        "teams": {
            away: away_truth,
            home: home_truth,
        },
        "sources_available": tuple(sources_available),
        "source_count": len(sources_available),
        "nflverse_diag": nflverse_diag,
        "espn_diag": {
            away: away_diag,
            home: home_diag,
        },
        "verified_count": away_truth["verified_count"] + home_truth["verified_count"],
        "disagreement_count": (
            away_truth["disagreement_count"] + home_truth["disagreement_count"]
        ),
    }


def _player_card(row: dict[str, Any]) -> str:
    jersey = f"#{row['jersey_number']}" if row.get("jersey_number") else "—"
    return f"""
<div class="ks-pa5-player"
     data-prop-roster-player-id="{html_lib.escape(str(row['espn_id']))}"
     data-prop-roster-player-position="{html_lib.escape(str(row['position']))}"
     data-prop-roster-player-team="{html_lib.escape(str(row['team']))}"
     data-prop-roster-verified="true"
     data-prop-roster-source-count="2">
  <div class="ks-pa5-player-main">
    <strong>{html_lib.escape(str(row['name']))}</strong>
    <span>{html_lib.escape(jersey)}</span>
  </div>
  <div class="ks-pa5-player-proof">VERIFIED • ESPN + NFLVERSE</div>
</div>
"""


def _team_roster_html(team_truth: dict[str, Any], team_name: str) -> str:
    sections = []
    for position in POSITIONS:
        players = team_truth["by_position"].get(position, [])
        cards = "".join(_player_card(row) for row in players)
        sections.append(
            f"""
<section class="ks-pa5-position"
         data-prop-roster-position="{position}"
         data-prop-roster-team="{html_lib.escape(team_truth['team'])}"
         data-prop-roster-position-count="{len(players)}">
  <div class="ks-pa5-pos-head">
    <strong>{position}</strong>
    <span>{len(players)} verified</span>
  </div>
  <div class="ks-pa5-player-list">{cards}</div>
</section>
"""
        )

    return f"""
<article class="ks-pa5-team"
         data-prop-roster-team-shell="{html_lib.escape(team_truth['team'])}"
         data-prop-roster-team-count="{team_truth['verified_count']}">
  <div class="ks-pa5-team-head">
    <b>{html_lib.escape(team_truth['team'])}</b>
    <span>{html_lib.escape(team_name)}</span>
  </div>
  {''.join(sections)}
</article>
"""


def render_verified_roster_truth(
    handoff: dict[str, Any],
) -> dict[str, Any]:
    truth = load_verified_roster_truth(handoff)
    away = _canon_team(handoff.get("away"))
    home = _canon_team(handoff.get("home"))
    away_name = _text(handoff.get("away_name")) or away
    home_name = _text(handoff.get("home_name")) or home

    if truth.get("state") != "live":
        st.markdown(
            f"""
<section data-nfl-prop-analytics-step5-roster="v1"
         data-prop-roster-state="fail-closed"
         data-prop-roster-selection="{html_lib.escape(str(handoff.get('selection_key') or ''))}"
         data-prop-roster-source-count="{truth.get('source_count', 0)}"
         data-prop-roster-verified-count="{truth.get('verified_count', 0)}">
  <div class="ks-pa5-empty">
    <strong>Verified roster truth is not complete.</strong>
    <span>{html_lib.escape(str(truth.get('reason') or 'Independent roster sources did not reconcile.'))}</span>
  </div>
</section>
""",
            unsafe_allow_html=True,
        )
        return truth

    away_truth = truth["teams"][away]
    home_truth = truth["teams"][home]
    source_label = " + ".join(truth["sources_available"])

    st.markdown(
        f"""
<section class="ks-pa5-board"
         data-nfl-prop-analytics-step5-roster="v1"
         data-prop-roster-state="live"
         data-prop-roster-selection="{html_lib.escape(str(truth['selection_key']))}"
         data-prop-roster-source-count="{truth['source_count']}"
         data-prop-roster-verified-count="{truth['verified_count']}"
         data-prop-roster-disagreement-count="{truth['disagreement_count']}"
         data-prop-roster-positions="QB,RB,WR,TE">
  <div class="ks-pa5-top">
    <div>
      <div class="ks-pa5-eyebrow">STEP 5 • VERIFIED ROSTER TRUTH</div>
      <h3>QB / RB / WR / TE</h3>
    </div>
    <div class="ks-pa5-proof">
      <strong>{truth['verified_count']} verified players</strong>
      <span>{html_lib.escape(source_label)}</span>
    </div>
  </div>

  <div class="ks-pa5-grid">
    {_team_roster_html(away_truth, away_name)}
    {_team_roster_html(home_truth, home_name)}
  </div>
</section>

<style data-nfl-prop-analytics-step5-css="v1">
.ks-pa5-board{{
  width:100%;max-width:100%;min-width:0;overflow-x:clip;
  margin:12px 0 30px;padding:clamp(14px,2.2vw,20px);
  border:1px solid rgba(125,211,252,.20);border-radius:18px;
  background:linear-gradient(145deg,rgba(5,12,21,.99),rgba(8,20,35,.96));
}}
.ks-pa5-top{{display:flex;justify-content:space-between;gap:12px;align-items:flex-end;margin-bottom:13px}}
.ks-pa5-eyebrow{{color:#7dd3fc;font-size:.67rem;font-weight:900;letter-spacing:.14em}}
.ks-pa5-top h3{{margin:.3rem 0 0;color:#f8fafc;font-size:clamp(1.08rem,3vw,1.45rem)}}
.ks-pa5-proof{{display:flex;flex-direction:column;align-items:flex-end;gap:3px}}
.ks-pa5-proof strong{{color:#bae6fd;font-size:.72rem}}
.ks-pa5-proof span{{color:#71869f;font-size:.63rem}}
.ks-pa5-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}}
.ks-pa5-team{{min-width:0;padding:12px;border:1px solid rgba(125,211,252,.13);border-radius:15px;background:rgba(2,8,16,.35)}}
.ks-pa5-team-head{{display:flex;align-items:baseline;gap:7px;margin-bottom:10px}}
.ks-pa5-team-head b{{color:#f8fafc;font-size:1rem}}
.ks-pa5-team-head span{{color:#8fa4bd;font-size:.7rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.ks-pa5-position{{padding:9px 0;border-top:1px solid rgba(148,163,184,.09)}}
.ks-pa5-position:first-of-type{{border-top:0}}
.ks-pa5-pos-head{{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:6px}}
.ks-pa5-pos-head strong{{color:#e0f2fe;font-size:.73rem;letter-spacing:.07em}}
.ks-pa5-pos-head span{{color:#6f839c;font-size:.6rem}}
.ks-pa5-player-list{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}}
.ks-pa5-player{{min-width:0;padding:8px;border:1px solid rgba(148,163,184,.10);border-radius:10px;background:rgba(15,23,42,.44)}}
.ks-pa5-player-main{{display:flex;justify-content:space-between;gap:6px;align-items:center}}
.ks-pa5-player-main strong{{min-width:0;color:#f1f5f9;font-size:.67rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.ks-pa5-player-main span{{color:#7dd3fc;font-size:.6rem;font-weight:800}}
.ks-pa5-player-proof{{margin-top:4px;color:#5f738b;font-size:.52rem;letter-spacing:.035em}}
.ks-pa5-empty{{padding:15px;border:1px solid rgba(248,113,113,.3);border-radius:14px;background:rgba(127,29,29,.12);display:flex;flex-direction:column;gap:4px}}
.ks-pa5-empty strong{{color:#fecaca}}.ks-pa5-empty span{{color:#cbd5e1;font-size:.78rem}}
@media(max-width:760px){{
  .ks-pa5-grid{{grid-template-columns:1fr}}
}}
@media(max-width:470px){{
  .ks-pa5-board{{padding:12px 10px}}
  .ks-pa5-top{{align-items:flex-start;flex-direction:column}}
  .ks-pa5-proof{{align-items:flex-start}}
  .ks-pa5-player-list{{grid-template-columns:1fr}}
}}
</style>
""",
        unsafe_allow_html=True,
    )
    return truth


__all__ = [
    "MAY_MODIFY_EXISTING_NFL_MARKETS",
    "MAY_MODIFY_PASSING_YARDS",
    "MODEL_VERSION",
    "NFLVERSE_WEEKLY_URL",
    "PAGE",
    "PLAYER_PROP_LOGIC",
    "POSITIONS",
    "PROJECTION_LOGIC",
    "ROSTER_TRUTH_ONLY",
    "SPORTSBOOK_ODDS_LOGIC",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP",
    "load_verified_roster_truth",
    "render_verified_roster_truth",
]
