"""Kyre Sports AI — NFL Moneyline V2.1 Step-2 depth verification repair.

Repairs Step 2 without changing its model guardrails:
- keep the site API depth-chart path first;
- add ESPN season-specific Core depthcharts as the verified secondary path;
- resolve Core athlete refs to names;
- use roster only as a last-resort display fallback;
- never label roster order as QB1/QB2/QB3.

No sportsbook, probability, Monte Carlo, ranking or recommendation logic is added.
"""
from __future__ import annotations

import re

import pandas as pd
import streamlit as st

import nfl_moneyline_hub_v2 as base

CORE_BASE = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
MODEL_VERSION = "NFL MONEYLINE V2.1 • STEP 2 CORE DEPTH REPAIR"


@st.cache_data(ttl=300, show_spinner=False)
def _core_depth_payload(year: int, team_id: str):
    return base._json_get(f"{CORE_BASE}/seasons/{int(year)}/teams/{team_id}/depthcharts")


@st.cache_data(ttl=3600, show_spinner=False)
def _core_athlete_payload(ref: str):
    url = str(ref or "").strip().replace("http://", "https://", 1)
    if not url:
        return {}, {"ok": False, "http": None, "error": "missing athlete ref"}
    return base._json_get(url)


def _athlete_from_ref(ref: str):
    payload, diag = _core_athlete_payload(ref)
    if not diag.get("ok"):
        return "", ""
    athlete_id = base._safe(payload.get("id"))
    name = base._safe(payload.get("displayName") or payload.get("fullName"))
    if not athlete_id:
        m = re.search(r"/athletes/(\d+)", str(ref or ""))
        athlete_id = m.group(1) if m else ""
    return athlete_id, name


def _parse_core_qb_depth(payload: dict):
    rows = []
    for chart in (payload or {}).get("items", []) or []:
        if not isinstance(chart, dict):
            continue
        positions = chart.get("positions") or {}
        blocks = list(positions.values()) if isinstance(positions, dict) else (positions if isinstance(positions, list) else [])
        for block in blocks:
            if not isinstance(block, dict):
                continue
            pos = block.get("position") or {}
            abbr = base._safe(pos.get("abbreviation")).upper()
            name = base._safe(pos.get("name")).lower()
            if abbr != "QB" and "quarterback" not in name:
                continue
            for idx, item in enumerate(block.get("athletes", []) or [], start=1):
                if not isinstance(item, dict):
                    continue
                athlete = item.get("athlete") or {}
                athlete_id = base._safe(athlete.get("id")) if isinstance(athlete, dict) else ""
                athlete_name = base._safe(athlete.get("displayName") or athlete.get("fullName")) if isinstance(athlete, dict) else ""
                ref = base._safe(athlete.get("$ref") or athlete.get("ref")) if isinstance(athlete, dict) else base._safe(athlete)
                if (not athlete_name) and ref:
                    resolved_id, resolved_name = _athlete_from_ref(ref)
                    athlete_id = athlete_id or resolved_id
                    athlete_name = resolved_name
                rank_raw = pd.to_numeric(item.get("rank"), errors="coerce")
                rank = int(rank_raw) if pd.notna(rank_raw) else idx
                if athlete_name:
                    rows.append({
                        "rank": rank,
                        "athlete_id": athlete_id,
                        "name": athlete_name,
                        "source": "ESPN CORE DEPTH CHART",
                    })
    rows = sorted(rows, key=lambda x: (x.get("rank", 99), x.get("name", "")))
    out, seen = [], set()
    for row in rows:
        key = row.get("athlete_id") or row.get("name")
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _selected_year() -> int:
    value = st.session_state.get("nfl_v1_date")
    try:
        return int(pd.to_datetime(value).year)
    except Exception:
        return int(pd.Timestamp.now(tz=base.ET).year)


def _team_context(abbr: str, team_name: str, injury_map: dict, injury_feed_ok: bool):
    abbr = base._safe(abbr).upper()
    team_id = base.TEAM_IDS.get(abbr, "")
    result = {
        "abbr": abbr,
        "team": team_name,
        "team_id": team_id,
        "qbs": [],
        "depth_state": "CHECK",
        "depth_http": None,
        "injury_state": "VERIFIED" if injury_feed_ok else "CHECK",
        "injuries": list(injury_map.get(abbr, [])),
        "rotation_state": "UNVERIFIED",
    }
    if not team_id:
        return result

    # Path 1: existing site API depthchart.
    site_payload, sdiag = base._depth_payload(team_id)
    result["depth_http"] = sdiag.get("http")
    qbs = base._parse_qb_depth(site_payload) if sdiag.get("ok") else []

    # Path 2: season-specific Core API depthchart.
    if not qbs:
        core_payload, cdiag = _core_depth_payload(_selected_year(), team_id)
        core_qbs = _parse_core_qb_depth(core_payload) if cdiag.get("ok") else []
        if core_qbs:
            qbs = core_qbs
            result["depth_http"] = cdiag.get("http")

    if qbs:
        result["qbs"] = qbs
        result["depth_state"] = "VERIFIED"
    else:
        # Last-resort display fallback only. It does not unlock depth readiness.
        roster_payload, rdiag = base._roster_payload(team_id)
        fallback = base._parse_qb_roster(roster_payload) if rdiag.get("ok") else []
        if fallback:
            result["qbs"] = fallback
            result["depth_state"] = "ROSTER FALLBACK"
            result["depth_http"] = result["depth_http"] or rdiag.get("http")

    injuries = sorted(result["injuries"], key=lambda x: (base._injury_priority(x.get("status")), x.get("name", "")))
    result["injuries"] = injuries
    by_id = {x.get("athlete_id"): x for x in injuries if x.get("athlete_id")}
    by_name = {x.get("name", "").lower(): x for x in injuries if x.get("name")}
    for qb in result["qbs"]:
        hit = by_id.get(qb.get("athlete_id")) or by_name.get(qb.get("name", "").lower())
        qb["injury_status"] = base._safe((hit or {}).get("status"), "No listed injury")
        qb["injury_detail"] = base._safe((hit or {}).get("detail"))
    return result


def _qb_table(ctx: dict):
    rows = []
    verified = ctx.get("depth_state") == "VERIFIED"
    for qb in ctx.get("qbs", [])[:4]:
        rows.append({
            "Depth": f"QB{int(qb.get('rank', len(rows)+1))}" if verified else "—",
            "Quarterback": qb.get("name", "Unknown"),
            "Injury listing": qb.get("injury_status", "No listed injury"),
            "Source": qb.get("source", "—"),
        })
    return pd.DataFrame(rows)


# Patch only Step-2 data-resolution/display helpers; base render flow and all locks stay intact.
base._team_context = _team_context
base._qb_table = _qb_table


def render_nfl_moneyline_hub():
    return base.render_nfl_moneyline_hub()


__all__ = ["MODEL_VERSION", "render_nfl_moneyline_hub"]
