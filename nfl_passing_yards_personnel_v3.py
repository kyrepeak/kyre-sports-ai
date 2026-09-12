"""NFL Passing Yards Step 5 V3 — exact ESPN Core depth recovery.

V2 proved that explicit recent target usage is available from exact ESPN event
box scores, but the live site depth endpoint changed shape from ``depthCharts``
to ``depthchart`` and therefore returned zero non-QB depth rows to frozen V1.

V3 leaves V1/V2 frozen and adds the same season-specific ESPN Core depth source
already certified by the NFL identity stack. It uses exact ESPN team IDs and
exact athlete IDs only, then reclassifies current injuries and joins V2 target
usage to current WR/TE/RB/FB depth IDs. No player-name matching is identity
authority and roster order is never promoted to verified depth.

Projection adjustment = 0.0. Sportsbook influence = 0.0. Stake sizing stays OFF.
"""
from __future__ import annotations

import math
import re
from typing import Any

import streamlit as st

import nfl_moneyline_hub_v2 as depth_base
import nfl_passing_yards_personnel_v1 as v1
import nfl_passing_yards_personnel_v2 as prior

MODEL_VERSION = "NFL PASSING YARDS STEP 5 V3 • EXACT ESPN CORE DEPTH RECOVERY"
FROZEN_PRIOR = "nfl_passing_yards_personnel_v2"
CORE_BASE = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _num(value: Any):
    try:
        out = float(value)
        return out if math.isfinite(out) else math.nan
    except Exception:
        return math.nan


def _finite(value: Any) -> bool:
    return math.isfinite(_num(value))


@st.cache_data(ttl=300, show_spinner=False)
def _core_depth_payload(year: int, team_id: str):
    team_id = _safe(team_id)
    if not team_id.isdigit():
        return {}, {"ok": False, "http": None, "error": "missing verified ESPN team id"}
    return depth_base._json_get(f"{CORE_BASE}/seasons/{int(year)}/teams/{team_id}/depthcharts")


def _athlete_id(athlete: Any) -> str:
    if isinstance(athlete, dict):
        direct = _safe(athlete.get("id"))
        if direct.isdigit():
            return direct
        ref = _safe(athlete.get("$ref") or athlete.get("ref"))
    else:
        ref = _safe(athlete)
    match = re.search(r"/athletes/(\d+)", ref)
    return match.group(1) if match else ""


def parse_core_depth_positions(payload: dict) -> list[dict]:
    """Normalize all exact-ID Core depth positions without resolving names."""
    rows: list[dict] = []
    for chart in (payload or {}).get("items") or []:
        if not isinstance(chart, dict):
            continue
        positions = chart.get("positions") or {}
        blocks = list(positions.values()) if isinstance(positions, dict) else positions if isinstance(positions, list) else []
        for block in blocks:
            if not isinstance(block, dict):
                continue
            pos_obj = block.get("position") or {}
            pos = v1._position((pos_obj or {}).get("abbreviation") or (pos_obj or {}).get("name"))
            if not pos:
                continue
            for index, item in enumerate(block.get("athletes") or [], start=1):
                if not isinstance(item, dict):
                    continue
                athlete = item.get("athlete") or {}
                athlete_id = _athlete_id(athlete)
                if not athlete_id.isdigit():
                    continue
                rank_raw = _num(item.get("rank"))
                rank = int(rank_raw) if _finite(rank_raw) else index
                name = _safe((athlete or {}).get("displayName") or (athlete or {}).get("fullName")) if isinstance(athlete, dict) else ""
                rows.append({
                    "position": pos,
                    "rank": rank,
                    "athlete_id": athlete_id,
                    "name": name or "Unknown player",
                    "source": "ESPN CORE DEPTH CHART",
                })
    rows.sort(key=lambda row: (row.get("position", ""), int(row.get("rank", 99)), row.get("athlete_id", "")))
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (row.get("position", ""), row.get("athlete_id", ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _recover_depth(existing: list[dict], year: int, team_id: str) -> tuple[list[dict], dict]:
    if existing:
        return list(existing), {"ok": True, "http": None, "source": "ESPN SITE DEPTH CHART"}
    payload, diag = _core_depth_payload(year, team_id)
    rows = parse_core_depth_positions(payload) if diag.get("ok") else []
    return rows, {**dict(diag or {}), "source": "ESPN CORE DEPTH CHART" if rows else "UNAVAILABLE"}


def _fill_exact_names(depth_rows: list[dict], usage: dict) -> list[dict]:
    usage_by_id = usage.get("players") or {}
    out = []
    for raw in depth_rows or []:
        row = dict(raw)
        hit = usage_by_id.get(_safe(row.get("athlete_id"))) or {}
        if _safe(row.get("name")) in {"", "Unknown player"} and hit:
            row["name"] = _safe(hit.get("name"), "Unknown player")
        out.append(row)
    return out


def build_personnel_matchup(
    offense_ctx: dict,
    defense_ctx: dict,
    year: int,
    season_type: int,
    team_pass_attempts: Any,
    cutoff_date: str | None = None,
) -> dict:
    row = dict(prior.build_personnel_matchup(
        offense_ctx,
        defense_ctx,
        year,
        season_type,
        team_pass_attempts,
        cutoff_date=cutoff_date,
    ) or {})

    offense_id = _safe(row.get("offense_team_id") or offense_ctx.get("team_id"))
    defense_id = _safe(row.get("defense_team_id") or defense_ctx.get("team_id"))
    if not offense_id.isdigit() or not defense_id.isdigit():
        row["projection_adjustment"] = 0.0
        row["sportsbook_influence"] = 0.0
        return row

    off_depth, off_diag = _recover_depth(list(row.get("offense_depth_rows") or []), int(year), offense_id)
    def_depth, def_diag = _recover_depth(list(row.get("defense_depth_rows") or []), int(year), defense_id)

    usage = prior.recent_weapon_usage(offense_id, int(year), int(season_type), _safe(cutoff_date)) if _safe(cutoff_date) else {"ready": False, "players": {}}
    off_depth = _fill_exact_names(off_depth, usage)

    offense_injuries = list(offense_ctx.get("injuries") or [])
    defense_injuries = list(defense_ctx.get("injuries") or [])
    skill = v1._classify_injuries(offense_injuries, v1.SKILL_POSITIONS, off_depth)
    skill = prior._enrich_injury_usage(skill, usage)
    ol = v1._classify_injuries(offense_injuries, v1.OL_POSITIONS, off_depth)
    secondary = v1._classify_injuries(defense_injuries, v1.SECONDARY_POSITIONS, def_depth)

    row["offense_depth_rows"] = off_depth
    row["defense_depth_rows"] = def_depth
    row["offense_depth_source"] = off_diag.get("source")
    row["defense_depth_source"] = def_diag.get("source")
    row["offense_depth_http"] = off_diag.get("http") or row.get("offense_depth_http")
    row["defense_depth_http"] = def_diag.get("http") or row.get("defense_depth_http")
    row["skill_injuries"] = skill
    row["ol_injuries"] = ol
    row["secondary_injuries"] = secondary
    row["skill_hard_count"] = sum(1 for item in skill if item.get("tier") == "HARD")
    row["skill_watch_count"] = sum(1 for item in skill if item.get("tier") == "WATCH")
    row["ol_hard_count"] = sum(1 for item in ol if item.get("tier") == "HARD")
    row["secondary_hard_count"] = sum(1 for item in secondary if item.get("tier") == "HARD")
    row["hard_target_share"] = prior._share_for_tier(skill, "HARD")
    row["watch_target_share"] = prior._share_for_tier(skill, "WATCH")
    row["top_weapons"] = prior._current_weapon_rows(off_depth, usage)

    qb = offense_ctx.get("qb1") or {}
    qb_status = _safe(row.get("qb_status") or qb.get("injury_status"), "No listed injury")
    feed_ok = bool(offense_ctx.get("injury_feed_ok") and defense_ctx.get("injury_feed_ok"))
    label, basis = v1.personnel_label(qb_status, skill, ol, secondary, row.get("hard_target_share"), feed_ok)
    row["personnel_label"] = label
    row["personnel_basis"] = basis
    row["depth_recovery_ready"] = bool(off_depth and def_depth)
    row["depth_recovery_state"] = (
        f"OFFENSE {row['offense_depth_source']} • DEFENSE {row['defense_depth_source']}"
        if row["depth_recovery_ready"] else "CHECK — exact ESPN depth rows incomplete"
    )
    row["projection_adjustment"] = 0.0
    row["sportsbook_influence"] = 0.0
    return row


parse_team_receiving_game = prior.parse_team_receiving_game
recent_weapon_usage = prior.recent_weapon_usage
status_tier = v1.status_tier
personnel_label = v1.personnel_label

__all__ = [
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "build_personnel_matchup",
    "parse_core_depth_positions",
    "parse_team_receiving_game",
    "recent_weapon_usage",
    "status_tier",
    "personnel_label",
]
