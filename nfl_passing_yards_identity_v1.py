"""NFL Passing Yards Step 1 — verified matchup + quarterback identity.

This layer is identity-only. It reuses the existing ESPN NFL schedule/depth/injury
contracts and does not create passing projections, sportsbook grades, Monte Carlo,
rankings, or recommendations.

Guardrails:
- strict ESPN game IDs from the verified NFL slate;
- site depth chart first, season-specific ESPN Core depth chart second;
- roster fallback is display-only and never promoted to verified QB1;
- a verified depth QB1 is not treated as confirmed game participation;
- preseason participation remains explicitly unconfirmed until a later game-plan step.
"""
from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

import nfl_moneyline_hub_v2 as depth_base
import nfl_moneyline_hub_v21 as depth_repair

MODEL_VERSION = "NFL PASSING YARDS STEP 1 • VERIFIED MATCHUP + QB IDENTITY V1"


def _safe(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _rank(value: Any, default: int = 99) -> int:
    parsed = pd.to_numeric(value, errors="coerce")
    return int(parsed) if pd.notna(parsed) else int(default)


@st.cache_data(ttl=120, show_spinner=False)
def load_current_injury_map():
    payload, diag = depth_base._league_injuries_payload()
    rows = depth_base._parse_injuries(payload) if diag.get("ok") else {}
    return rows, diag


def _attach_qb_injuries(qbs: list[dict], injuries: list[dict]) -> list[dict]:
    by_id = {x.get("athlete_id"): x for x in injuries if x.get("athlete_id")}
    by_name = {str(x.get("name") or "").lower(): x for x in injuries if x.get("name")}
    out = []
    for qb in qbs:
        row = dict(qb)
        hit = by_id.get(row.get("athlete_id")) or by_name.get(str(row.get("name") or "").lower())
        row["injury_status"] = depth_base._safe((hit or {}).get("status"), "No listed injury")
        row["injury_detail"] = depth_base._safe((hit or {}).get("detail"))
        out.append(row)
    return out


def resolve_team_qb_identity(
    abbr: str,
    team_name: str,
    season_year: int,
    injury_map: dict | None = None,
    injury_feed_ok: bool = False,
) -> dict:
    """Resolve one team's QB identity with fail-closed depth semantics."""
    abbr = _safe(abbr).upper()
    team_id = depth_base.TEAM_IDS.get(abbr, "")
    result = {
        "abbr": abbr,
        "team": _safe(team_name, abbr),
        "team_id": team_id,
        "qbs": [],
        "depth_state": "CHECK",
        "depth_source": "",
        "depth_http": None,
        "identity_verified": False,
        "qb1": {},
        "injury_feed_ok": bool(injury_feed_ok),
        "injuries": list((injury_map or {}).get(abbr, [])),
        "availability_alert": False,
    }
    if not team_id:
        return result

    site_payload, site_diag = depth_base._depth_payload(team_id)
    result["depth_http"] = site_diag.get("http")
    qbs = depth_base._parse_qb_depth(site_payload) if site_diag.get("ok") else []

    if not qbs:
        core_payload, core_diag = depth_repair._core_depth_payload(int(season_year), team_id)
        core_qbs = depth_repair._parse_core_qb_depth(core_payload) if core_diag.get("ok") else []
        if core_qbs:
            qbs = core_qbs
            result["depth_http"] = core_diag.get("http")

    if qbs:
        result["depth_state"] = "VERIFIED"
        result["depth_source"] = _safe(qbs[0].get("source"), "ESPN DEPTH CHART")
    else:
        roster_payload, roster_diag = depth_base._roster_payload(team_id)
        qbs = depth_base._parse_qb_roster(roster_payload) if roster_diag.get("ok") else []
        if qbs:
            result["depth_state"] = "ROSTER FALLBACK"
            result["depth_source"] = "ESPN ROSTER FALLBACK"
            result["depth_http"] = result["depth_http"] or roster_diag.get("http")

    qbs = _attach_qb_injuries(qbs, result["injuries"])
    result["qbs"] = qbs

    verified_qb1 = None
    if result["depth_state"] == "VERIFIED":
        ordered = sorted(qbs, key=lambda x: (_rank(x.get("rank")), _safe(x.get("name"))))
        if ordered and _rank(ordered[0].get("rank")) == 1:
            candidate = ordered[0]
            if _safe(candidate.get("athlete_id")) and _safe(candidate.get("name")):
                verified_qb1 = candidate

    if verified_qb1:
        result["qb1"] = verified_qb1
        result["identity_verified"] = True
        status = _safe(verified_qb1.get("injury_status")).upper()
        result["availability_alert"] = any(token in status for token in ("OUT", "DOUBTFUL", "INJURED RESERVE", "IR"))
    return result


def resolve_matchup_identity(game: dict, season_year: int) -> dict:
    """Resolve both teams for one verified slate row; never synthesizes game identity."""
    game_id = _safe(game.get("game_id"))
    if not game_id or not game_id.isdigit():
        return {
            "ready": False,
            "reason": "missing or invalid official ESPN game ID",
            "game_id": game_id,
            "away": {},
            "home": {},
        }

    injury_map, injury_diag = load_current_injury_map()
    injury_ok = bool(injury_diag.get("ok"))
    away = resolve_team_qb_identity(
        _safe(game.get("away_abbr")),
        _safe(game.get("away_team"), "Away"),
        season_year,
        injury_map,
        injury_ok,
    )
    home = resolve_team_qb_identity(
        _safe(game.get("home_abbr")),
        _safe(game.get("home_team"), "Home"),
        season_year,
        injury_map,
        injury_ok,
    )
    ready = bool(away.get("identity_verified") and home.get("identity_verified"))
    return {
        "ready": ready,
        "reason": "" if ready else "one or both verified depth QB1 identities are unresolved",
        "game_id": game_id,
        "injury_feed_ok": injury_ok,
        "injury_http": injury_diag.get("http"),
        "away": away,
        "home": home,
    }


__all__ = [
    "MODEL_VERSION",
    "load_current_injury_map",
    "resolve_matchup_identity",
    "resolve_team_qb_identity",
]
