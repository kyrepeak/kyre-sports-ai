from __future__ import annotations

import json

import nfl_passing_yards_defense_v1 as defense_v1
import nfl_passing_yards_espn_stat_split_v1 as stat_split
import nfl_passing_yards_pressure_v4 as pressure_v4


def _compact(row: dict) -> dict:
    off = dict(row.get("offense") or {})
    deff = dict(row.get("defense") or {})
    return {
        "ready": row.get("ready"),
        "reason": row.get("reason"),
        "offense_team_id": row.get("offense_team_id"),
        "defense_team_id": row.get("defense_team_id"),
        "pressure_label": row.get("pressure_label"),
        "pressure_basis": row.get("pressure_basis"),
        "requested_season_year": row.get("requested_season_year"),
        "baseline_source_year": row.get("baseline_source_year"),
        "early_season_fallback": row.get("early_season_fallback"),
        "offense": {
            "ready": off.get("ready"),
            "games": off.get("games"),
            "passing_attempts": off.get("passing_attempts"),
            "sacks_allowed": off.get("sacks_allowed"),
            "sacks_allowed_per_game": off.get("sacks_allowed_per_game"),
            "sack_yards_lost": off.get("sack_yards_lost"),
            "sack_rate_allowed": off.get("sack_rate_allowed"),
        },
        "defense": {
            "ready": deff.get("ready"),
            "games": deff.get("games"),
            "sacks_made": deff.get("sacks_made"),
            "sacks_per_game": deff.get("sacks_per_game"),
            "opponent_pass_attempts": deff.get("opponent_pass_attempts"),
            "sack_rate_generated": deff.get("sack_rate_generated"),
        },
        "recent_offense_count": len(row.get("recent_offense") or []),
        "recent_defense_count": len(row.get("recent_defense") or []),
        "recent_offense": row.get("recent_offense") or [],
        "recent_defense": row.get("recent_defense") or [],
        "offense_stats_http": row.get("offense_stats_http"),
        "defense_stats_http": row.get("defense_stats_http"),
        "timezone_normalization": row.get("timezone_normalization"),
        "sportsbook_influence": row.get("sportsbook_influence"),
        "projection_adjustment": row.get("projection_adjustment"),
    }


def _stat_tokens(payload: dict) -> list[dict]:
    out = []
    splits = (payload or {}).get("splits") or {}
    cats = splits.get("categories") if isinstance(splits, dict) else None
    if not isinstance(cats, list):
        cats = (payload or {}).get("categories") or []
    for cat in cats:
        if not isinstance(cat, dict):
            continue
        cname = str(cat.get("name") or cat.get("displayName") or "")
        for stat in cat.get("stats") or []:
            if not isinstance(stat, dict):
                continue
            text = " ".join(str(stat.get(k) or "") for k in ("name", "displayName", "shortDisplayName", "abbreviation"))
            if any(token in text.lower() for token in ("sack", "attempt", "game")):
                out.append({
                    "category": cname,
                    "name": stat.get("name"),
                    "displayName": stat.get("displayName"),
                    "abbreviation": stat.get("abbreviation"),
                    "value": stat.get("value"),
                    "perGameValue": stat.get("perGameValue"),
                    "displayValue": stat.get("displayValue"),
                })
    return out


def main() -> None:
    original = defense_v1._team_stats_payload
    defense_v1._team_stats_payload = stat_split.team_stats_payload
    try:
        for tid in ("27", "4"):
            payload, diag = stat_split.team_stats_payload(2025, 2, tid)
            print("LIVE_STATS", tid, json.dumps({"diag": diag, "tokens": _stat_tokens(payload)}, default=str, sort_keys=True))

        cases = [
            ("27", "Tampa Bay Buccaneers", "4", "Cincinnati Bengals"),
            ("4", "Cincinnati Bengals", "27", "Tampa Bay Buccaneers"),
        ]
        for offense_id, offense_name, defense_id, defense_name in cases:
            row = pressure_v4.build_pressure_matchup(
                offense_id,
                offense_name,
                defense_id,
                defense_name,
                2026,
                2,
                "2026-09-13",
            )
            print("LIVE_PRESSURE", offense_id, defense_id, json.dumps(_compact(row), default=str, sort_keys=True))
    finally:
        defense_v1._team_stats_payload = original


if __name__ == "__main__":
    main()
