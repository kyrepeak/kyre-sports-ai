"""Temporary-safe diagnostic for ESPN athlete/team statistics payload shapes."""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import nfl_passing_yards_espn_stat_split_v1 as stats


def compact(value, depth=0):
    if depth >= 3:
        if isinstance(value, dict):
            return {"keys": list(value)[:30]}
        if isinstance(value, list):
            return {"list_len": len(value)}
        return value
    if isinstance(value, dict):
        out = {}
        for key, item in list(value.items())[:30]:
            if key in {"stats", "categories", "splits", "items", "children"}:
                out[key] = compact(item, depth + 1)
            elif isinstance(item, (dict, list)):
                out[key] = compact(item, depth + 1)
            else:
                out[key] = item
        return out
    if isinstance(value, list):
        return [compact(x, depth + 1) for x in value[:8]]
    return value


for name, athlete_id in (("Baker Mayfield", "3052587"), ("Joe Burrow", "3915511")):
    payload, diag = stats.athlete_stats_payload(2025, 2, athlete_id)
    print(f"=== ATHLETE {name} {athlete_id} ===")
    print(json.dumps({"diag": diag, "payload": compact(payload)}, indent=2, default=str))

for name, team_id in (("Tampa Bay Buccaneers", "27"), ("Cincinnati Bengals", "4")):
    payload, diag = stats.team_stats_payload(2025, 2, team_id)
    print(f"=== TEAM {name} {team_id} ===")
    print(json.dumps({"diag": diag, "payload": compact(payload)}, indent=2, default=str))
