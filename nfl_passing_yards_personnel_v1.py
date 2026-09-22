"""NFL Passing Yards Step 5 — weapons + injuries personnel context.

Descriptive evidence only. Uses verified ESPN team IDs, exact ESPN athlete IDs,
current ESPN injury listings, depth charts, and explicit receiving-target stats when
available. No fuzzy player matching is used. Target share is calculated only when
ESPN exposes an explicit target count for the athlete; otherwise it fails closed.

This module does not create or alter a passing-yards projection, sportsbook grade,
fair line, probability, EV, Monte Carlo result, ranking, or recommendation.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import math
import re
from typing import Any

import nfl_moneyline_hub_v2 as depth_base
import nfl_passing_yards_profile_v1 as profile

MODEL_VERSION = "NFL PASSING YARDS STEP 5 • WEAPONS + INJURIES V1"
SKILL_POSITIONS = {"WR", "TE", "RB", "FB"}
OL_POSITIONS = {"LT", "LG", "C", "RG", "RT", "OT", "OG", "G", "T", "OL"}
SECONDARY_POSITIONS = {"CB", "S", "FS", "SS", "DB", "NB"}


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _num(value: Any):
    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("%", "").strip()
        out = float(value)
        return out if math.isfinite(out) else math.nan
    except Exception:
        return math.nan


def _finite(value: Any) -> bool:
    return math.isfinite(_num(value))


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", _safe(value).lower())


def _position(value: Any) -> str:
    text = re.sub(r"[^A-Z]", "", _safe(value).upper())
    aliases = {
        "WIDERECEIVER": "WR", "TIGHTEND": "TE", "RUNNINGBACK": "RB", "FULLBACK": "FB",
        "LEFTTACKLE": "LT", "LEFTGUARD": "LG", "CENTER": "C", "RIGHTGUARD": "RG", "RIGHTTACKLE": "RT",
        "OFFENSIVETACKLE": "OT", "OFFENSIVEGUARD": "OG", "OFFENSIVELINE": "OL",
        "CORNERBACK": "CB", "SAFETY": "S", "FREESAFETY": "FS", "STRONGSAFETY": "SS", "DEFENSIVEBACK": "DB",
        "QUARTERBACK": "QB",
    }
    return aliases.get(text, text)


def status_tier(status: Any) -> str:
    s = _safe(status).upper()
    if any(token in s for token in ("OUT", "INJURED RESERVE", " IR", "IR ", "PUP", "RESERVE", "DOUBTFUL")) or s == "IR":
        return "HARD"
    if any(token in s for token in ("QUESTIONABLE", "PROBABLE")):
        return "WATCH"
    return "OTHER"


def parse_depth_positions(payload: dict) -> list[dict]:
    rows: list[dict] = []
    for chart in (payload or {}).get("depthCharts", []) or []:
        positions = chart.get("positions") or {}
        blocks = list(positions.values()) if isinstance(positions, dict) else positions if isinstance(positions, list) else []
        for block in blocks:
            if not isinstance(block, dict):
                continue
            pos_obj = block.get("position") or {}
            pos = _position(pos_obj.get("abbreviation") or pos_obj.get("name"))
            if not pos:
                continue
            for item in block.get("athletes", []) or []:
                athlete = item.get("athlete") or {}
                rank = _num(item.get("rank"))
                rows.append({
                    "position": pos,
                    "rank": int(rank) if _finite(rank) else 99,
                    "athlete_id": _safe(athlete.get("id")),
                    "name": _safe(athlete.get("displayName") or athlete.get("fullName"), "Unknown player"),
                })
    rows.sort(key=lambda r: (r.get("position", ""), int(r.get("rank", 99)), r.get("name", "")))
    return rows


def _receiving_category(payload: dict) -> dict:
    splits = (payload or {}).get("splits") or {}
    categories = splits.get("categories") if isinstance(splits, dict) else None
    if not isinstance(categories, list):
        categories = (payload or {}).get("categories") or []
    for cat in categories:
        if not isinstance(cat, dict):
            continue
        name = _norm(cat.get("name") or cat.get("displayName") or cat.get("abbreviation"))
        if "receiv" in name:
            return cat
    return {}


def parse_receiving_usage(payload: dict) -> dict:
    cat = _receiving_category(payload)
    stats: dict[str, float] = {}
    for item in cat.get("stats") or []:
        if not isinstance(item, dict):
            continue
        value = item.get("value") if _finite(item.get("value")) else item.get("displayValue")
        value = _num(value)
        if not _finite(value):
            continue
        for key in (_norm(item.get("name")), _norm(item.get("displayName")), _norm(item.get("shortDisplayName")), _norm(item.get("abbreviation"))):
            if key:
                stats[key] = value

    def pick(*aliases):
        for alias in aliases:
            key = _norm(alias)
            if key in stats and _finite(stats[key]):
                return float(stats[key])
        return math.nan

    targets = pick("receivingTargets", "targets", "target", "TGT")
    receptions = pick("receptions", "REC")
    yards = pick("receivingYards", "REC YDS", "YDS")
    return {
        "ready": bool(_finite(targets)),
        "targets": targets,
        "receptions": receptions,
        "receiving_yards": yards,
    }


def _depth_map(rows: list[dict]) -> dict[str, dict]:
    return {r.get("athlete_id"): r for r in rows if r.get("athlete_id")}


def _classify_injuries(injuries: list[dict], allowed: set[str], depth_rows: list[dict]) -> list[dict]:
    depth_by_id = _depth_map(depth_rows)
    out = []
    for item in injuries or []:
        pos = _position(item.get("position"))
        if pos not in allowed:
            continue
        row = dict(item)
        row["position"] = pos
        row["tier"] = status_tier(row.get("status"))
        linked = depth_by_id.get(_safe(row.get("athlete_id"))) or {}
        row["depth_rank"] = linked.get("rank")
        row["depth_name"] = linked.get("name") or ""
        row["exact_depth_link"] = bool(linked)
        out.append(row)
    out.sort(key=lambda r: ({"HARD": 0, "WATCH": 1, "OTHER": 2}.get(r.get("tier"), 3), r.get("position", ""), r.get("name", "")))
    return out


def _usage_for_injured_skill(rows: list[dict], year: int, season_type: int, team_pass_attempts: Any) -> list[dict]:
    candidates = [r for r in rows if _safe(r.get("athlete_id")).isdigit()][:8]
    usage_by_id: dict[str, dict] = {}
    if candidates:
        with ThreadPoolExecutor(max_workers=min(6, len(candidates))) as pool:
            future_map = {
                pool.submit(profile._season_stats_payload, int(year), int(season_type), _safe(row.get("athlete_id"))): _safe(row.get("athlete_id"))
                for row in candidates
            }
            for future in as_completed(future_map):
                athlete_id = future_map[future]
                try:
                    payload, diag = future.result()
                except Exception:
                    continue
                usage = parse_receiving_usage(payload) if diag.get("ok") else {"ready": False}
                usage["http"] = diag.get("http")
                usage_by_id[athlete_id] = usage

    attempts = _num(team_pass_attempts)
    enriched = []
    for row in rows:
        item = dict(row)
        usage = usage_by_id.get(_safe(item.get("athlete_id"))) or {"ready": False}
        item["targets"] = usage.get("targets")
        item["receptions"] = usage.get("receptions")
        item["receiving_yards"] = usage.get("receiving_yards")
        item["usage_http"] = usage.get("http")
        item["target_share"] = (
            100.0 * _num(usage.get("targets")) / attempts
            if usage.get("ready") and _finite(attempts) and attempts > 0
            else math.nan
        )
        item["target_share_verified"] = bool(usage.get("ready") and _finite(item["target_share"]))
        enriched.append(item)
    return enriched


def _sum_share(rows: list[dict], tier: str):
    values = [_num(r.get("target_share")) for r in rows if r.get("tier") == tier and _finite(r.get("target_share"))]
    return sum(values) if values else math.nan


def _impact_count(rows: list[dict], group: str) -> int:
    count = 0
    for row in rows:
        if row.get("tier") != "HARD":
            continue
        rank = row.get("depth_rank")
        share = _num(row.get("target_share"))
        if group == "skill" and ((_finite(share) and share >= 10.0) or (isinstance(rank, int) and rank <= 2)):
            count += 1
        elif group in {"ol", "secondary"} and isinstance(rank, int) and rank <= 1:
            count += 1
    return count


def personnel_label(qb_status: str, skill: list[dict], ol: list[dict], secondary: list[dict], hard_target_share: Any, feed_ok: bool) -> tuple[str, str]:
    if not feed_ok:
        return "CHECK", "current ESPN injury feed unavailable"
    qb_hard = status_tier(qb_status) == "HARD"
    skill_impact = _impact_count(skill, "skill")
    ol_impact = _impact_count(ol, "ol")
    secondary_impact = _impact_count(secondary, "secondary")
    share = _num(hard_target_share)
    offense_hit = qb_hard or skill_impact >= 2 or ol_impact >= 2 or (_finite(share) and share >= 20.0)
    defense_thin = secondary_impact >= 2
    if offense_hit and defense_thin:
        return "MIXED", "meaningful offensive absences and opponent secondary absences"
    if offense_hit:
        return "HURT", "meaningful offensive availability loss"
    if defense_thin:
        return "HELP", "opponent secondary has multiple verified starter-level absences"
    watch = status_tier(qb_status) == "WATCH" or any(r.get("tier") == "WATCH" for r in skill + ol + secondary)
    if watch:
        return "WATCH", "questionable/probable personnel status remains unresolved"
    return "NEUTRAL", "no verified high-impact personnel imbalance detected"


def build_personnel_matchup(offense_ctx: dict, defense_ctx: dict, year: int, season_type: int, team_pass_attempts: Any) -> dict:
    offense_id = _safe(offense_ctx.get("team_id"))
    defense_id = _safe(defense_ctx.get("team_id"))
    if not offense_id.isdigit() or not defense_id.isdigit():
        return {"ready": False, "reason": "verified ESPN offense and defense team IDs are required", "projection_adjustment": 0.0}

    with ThreadPoolExecutor(max_workers=2) as pool:
        off_future = pool.submit(depth_base._depth_payload, offense_id)
        def_future = pool.submit(depth_base._depth_payload, defense_id)
        off_payload, off_diag = off_future.result()
        def_payload, def_diag = def_future.result()
    off_depth = parse_depth_positions(off_payload) if off_diag.get("ok") else []
    def_depth = parse_depth_positions(def_payload) if def_diag.get("ok") else []

    offense_injuries = list(offense_ctx.get("injuries") or [])
    defense_injuries = list(defense_ctx.get("injuries") or [])
    skill = _classify_injuries(offense_injuries, SKILL_POSITIONS, off_depth)
    skill = _usage_for_injured_skill(skill, year, season_type, team_pass_attempts)
    ol = _classify_injuries(offense_injuries, OL_POSITIONS, off_depth)
    secondary = _classify_injuries(defense_injuries, SECONDARY_POSITIONS, def_depth)

    qb = offense_ctx.get("qb1") or {}
    qb_status = _safe(qb.get("injury_status"), "No listed injury")
    feed_ok = bool(offense_ctx.get("injury_feed_ok") and defense_ctx.get("injury_feed_ok"))
    hard_share = _sum_share(skill, "HARD")
    watch_share = _sum_share(skill, "WATCH")
    label, basis = personnel_label(qb_status, skill, ol, secondary, hard_share, feed_ok)

    return {
        "ready": bool(feed_ok),
        "reason": "" if feed_ok else "current ESPN injury feed could not be verified",
        "offense_team_id": offense_id,
        "offense_team_name": _safe(offense_ctx.get("team"), offense_ctx.get("abbr")),
        "defense_team_id": defense_id,
        "defense_team_name": _safe(defense_ctx.get("team"), defense_ctx.get("abbr")),
        "qb_name": _safe(qb.get("name"), "Unresolved QB1"),
        "qb_status": qb_status,
        "skill_injuries": skill,
        "ol_injuries": ol,
        "secondary_injuries": secondary,
        "skill_hard_count": sum(1 for r in skill if r.get("tier") == "HARD"),
        "skill_watch_count": sum(1 for r in skill if r.get("tier") == "WATCH"),
        "ol_hard_count": sum(1 for r in ol if r.get("tier") == "HARD"),
        "secondary_hard_count": sum(1 for r in secondary if r.get("tier") == "HARD"),
        "hard_target_share": hard_share,
        "watch_target_share": watch_share,
        "target_share_state": "VERIFIED WHERE EXPLICIT TARGETS EXIST" if any(r.get("target_share_verified") for r in skill) else "UNAVAILABLE — explicit ESPN targets not returned",
        "personnel_label": label,
        "personnel_basis": basis,
        "offense_depth_http": off_diag.get("http"),
        "defense_depth_http": def_diag.get("http"),
        "offense_depth_rows": off_depth,
        "defense_depth_rows": def_depth,
        "projection_adjustment": 0.0,
    }


__all__ = [
    "MODEL_VERSION",
    "build_personnel_matchup",
    "parse_depth_positions",
    "parse_receiving_usage",
    "personnel_label",
    "status_tier",
]
