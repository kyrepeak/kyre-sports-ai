"""NFL Passing Yards pass-defense V2 — early-season verified bridge.

Wraps certified V1. Current-season pass-defense evidence always wins. If the
selected regular season has no usable season sample yet, V2 uses the immediately
prior regular season as a labelled baseline and fills the recent-five window with
verified prior-season game summaries.

ESPN's team all-splits season payload exposes offensive passing totals and core
defensive counts, but it does not expose opponent passing yards/attempts for the
2025 NFL regular season. When that exact source shape is encountered, V2 derives
the prior-season pass-defense baseline from the team's verified ESPN regular-
season schedule plus each exact ESPN event box score. Every included game must
have verified passing yards and attempts; otherwise the fallback fails closed.
No sportsbook data, fuzzy identity, or synthetic default is used.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import math
from typing import Any

import nfl_passing_yards_defense_v1 as base
import nfl_passing_yards_early_season_v1 as early

MODEL_VERSION = "NFL PASSING YARDS PASS DEFENSE V2 • EARLY SEASON VERIFIED BOX-SCORE BRIDGE"


def _num(value: Any):
    try:
        out = float(value)
        return out if math.isfinite(out) else math.nan
    except Exception:
        return math.nan


def _finite(value: Any) -> bool:
    return math.isfinite(_num(value))


def _avg(rows: list[dict], key: str):
    values = [_num(row.get(key)) for row in rows]
    values = [x for x in values if _finite(x)]
    return sum(values) / len(values) if values else math.nan


def _sum(rows: list[dict], key: str):
    values = [_num(row.get(key)) for row in rows]
    if not values or any(not _finite(value) for value in values):
        return math.nan
    return sum(values)


def _verified_boxscore_season(
    team_id: str,
    year: int,
    season_type: int,
    cutoff_date: str,
    partial_season: dict | None = None,
) -> tuple[dict, list[dict], dict]:
    """Derive pass-defense season totals only from exact verified ESPN games.

    This is an evidence recovery path, not model logic. The schedule supplies
    exact event IDs; each event summary supplies the opponent passing box score.
    If any completed regular-season event lacks a usable summary row, the season
    aggregate is withheld instead of silently estimating the missing game.
    """
    schedule, schedule_diag = base._team_schedule_payload(year, season_type, team_id)
    if not schedule_diag.get("ok"):
        return {"ready": False}, [], {
            "ready": False,
            "reason": "verified ESPN team schedule unavailable",
            "schedule_http": schedule_diag.get("http"),
            "expected_games": 0,
            "parsed_games": 0,
        }

    events = base._completed_event_rows(schedule, cutoff_date, max_games=25)
    if not events:
        return {"ready": False}, [], {
            "ready": False,
            "reason": "no completed verified ESPN regular-season events",
            "schedule_http": schedule_diag.get("http"),
            "expected_games": 0,
            "parsed_games": 0,
        }

    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=min(8, len(events))) as pool:
        future_map = {pool.submit(base._summary_payload, event["event_id"]): event for event in events}
        for future in as_completed(future_map):
            event = future_map[future]
            try:
                summary, diag = future.result()
            except Exception:
                continue
            if not diag.get("ok"):
                continue
            parsed = base.parse_recent_defense_game(summary, team_id)
            if not parsed:
                continue
            attempts = _num(parsed.get("attempts_allowed"))
            yards = _num(parsed.get("passing_yards_allowed"))
            if not (_finite(attempts) and attempts > 0 and _finite(yards)):
                continue
            parsed = dict(parsed)
            parsed["event_id"] = str(event.get("event_id") or "")
            parsed["date"] = event["date"].strftime("%Y-%m-%d")
            rows.append(parsed)

    rows.sort(key=lambda row: row.get("date", ""), reverse=True)
    expected_games = len(events)
    if len(rows) != expected_games:
        return {"ready": False}, rows, {
            "ready": False,
            "reason": "one or more verified ESPN event box scores were unavailable",
            "schedule_http": schedule_diag.get("http"),
            "expected_games": expected_games,
            "parsed_games": len(rows),
        }

    games = float(len(rows))
    yards = _sum(rows, "passing_yards_allowed")
    attempts = _sum(rows, "attempts_allowed")
    completions = _sum(rows, "completions_allowed")
    ready = bool(
        games > 0
        and _finite(yards)
        and _finite(attempts)
        and attempts > 0
        and _finite(completions)
    )
    if not ready:
        return {"ready": False}, rows, {
            "ready": False,
            "reason": "verified box-score season aggregate incomplete",
            "schedule_http": schedule_diag.get("http"),
            "expected_games": expected_games,
            "parsed_games": len(rows),
        }

    partial = dict(partial_season or {})
    interceptions = _num(partial.get("interceptions"))
    sacks = _num(partial.get("sacks"))
    season = {
        "ready": True,
        "games": games,
        "passing_yards_allowed": yards,
        "passing_yards_allowed_per_game": yards / games,
        "passing_attempts_allowed": attempts,
        "passing_attempts_allowed_per_game": attempts / games,
        "passing_completions_allowed": completions,
        "passing_completions_allowed_per_game": completions / games,
        "completion_pct_allowed": 100.0 * completions / attempts,
        "yards_per_attempt_allowed": yards / attempts,
        "passing_tds_allowed": math.nan,
        "interceptions": interceptions,
        "sacks": sacks,
        "passing_yards_allowed_rank": None,
        "source": "VERIFIED ESPN EVENT BOX-SCORE AGGREGATE",
    }
    return season, rows, {
        "ready": True,
        "reason": "",
        "schedule_http": schedule_diag.get("http"),
        "expected_games": expected_games,
        "parsed_games": len(rows),
        "source": "verified ESPN schedule + exact event box scores",
    }


def build_pass_defense_profile(team_id: str, team_name: str, year: int, season_type: int, cutoff_date: str) -> dict:
    current = dict(base.build_pass_defense_profile(team_id, team_name, year, season_type, cutoff_date) or {})
    current_recent = list(current.get("recent_games") or [])
    source_year = int(year)
    fallback_used = False
    prior: dict = {}

    if early.allow_prior_regular_fallback(season_type) and (not current.get("ready") or len(current_recent) < 5):
        prior_year = early.prior_regular_year(year)
        prior = dict(base.build_pass_defense_profile(team_id, team_name, prior_year, 2, cutoff_date) or {})
        prior_recent = list(prior.get("recent_games") or [])

        if not current.get("ready") and prior.get("ready"):
            current["season"] = dict(prior.get("season") or {})
            current["matchup_grade"] = prior.get("matchup_grade")
            current["grade_basis"] = f"{prior.get('grade_basis') or 'prior regular-season baseline'} • early-season fallback"
            current["ready"] = True
            current["reason"] = ""
            source_year = prior_year
            fallback_used = True
        elif not current.get("ready"):
            recovered_season, recovered_rows, recovered_diag = _verified_boxscore_season(
                team_id,
                prior_year,
                2,
                cutoff_date,
                partial_season=prior.get("season") or {},
            )
            current["season_aggregation_diag"] = recovered_diag
            if recovered_season.get("ready"):
                current["season"] = recovered_season
                current["matchup_grade"] = "CHECK"
                current["grade_basis"] = "verified prior regular-season ESPN event box-score aggregate • rank unavailable"
                current["ready"] = True
                current["reason"] = ""
                source_year = prior_year
                fallback_used = True
                if not prior_recent:
                    prior_recent = list(recovered_rows[:5])

        recent = early.merge_recent_rows(current_recent, prior_recent, limit=5)
        current["recent_games"] = recent
        current["recent3_yards_allowed"] = _avg(recent[:3], "passing_yards_allowed")
        current["recent5_yards_allowed"] = _avg(recent[:5], "passing_yards_allowed")
        current["recent3_completion_pct_allowed"] = _avg(recent[:3], "completion_pct_allowed")
        current["recent3_ypa_allowed"] = _avg(recent[:3], "yards_per_attempt_allowed")
        current["recent_verified_games"] = len(recent)
        current["prior_recent_games_used"] = max(0, len(recent) - len(current_recent[:5]))

    current.update(early.provenance(bool(current.get("ready") and not fallback_used), fallback_used, int(year), source_year))
    current["requested_season_year"] = int(year)
    current["sportsbook_influence"] = 0.0
    return current


# Re-export parser helpers used by tests/consumers without changing V1 contracts.
matchup_grade = base.matchup_grade
parse_recent_defense_game = base.parse_recent_defense_game
parse_season_pass_defense = base.parse_season_pass_defense

__all__ = [
    "MODEL_VERSION",
    "build_pass_defense_profile",
    "matchup_grade",
    "parse_recent_defense_game",
    "parse_season_pass_defense",
]
