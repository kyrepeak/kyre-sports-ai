"""Granular live-source gates for NFL Passing Yards production certification.

These stages exist so GitHub Actions identifies the exact live data layer that
fails even when full Actions logs are unavailable. Every stage uses exact ESPN
IDs and verified source payloads only. No sportsbook data is accepted.
"""
from __future__ import annotations

import argparse
import math
from statistics import stdev

import nfl_passing_yards_defense_v1 as defense_v1
import nfl_passing_yards_defense_v2 as defense_v2
import nfl_passing_yards_environment_v1 as environment_v1
import nfl_passing_yards_espn_stat_split_v1 as stat_split
import nfl_passing_yards_profile_v1 as profile
from devsystem import nfl_passing_yards_live_cert_v1 as cert


def _finite(value) -> bool:
    try:
        return math.isfinite(float(value))
    except Exception:
        return False


def _identities() -> tuple[dict, dict]:
    away = cert._resolve_side("TB", "Tampa Bay Buccaneers")
    home = cert._resolve_side("CIN", "Cincinnati Bengals")
    away_qb = away.get("qb1") or {}
    home_qb = home.get("qb1") or {}
    if "baker mayfield" not in str(away_qb.get("name") or "").lower():
        raise AssertionError(f"Expected Baker Mayfield as TB QB1, got {away_qb}")
    if "joe burrow" not in str(home_qb.get("name") or "").lower():
        raise AssertionError(f"Expected Joe Burrow as CIN QB1, got {home_qb}")
    return away, home


def _profiles(away: dict, home: dict) -> tuple[dict, dict]:
    original = profile._season_stats_payload
    profile._season_stats_payload = stat_split.athlete_stats_payload
    try:
        away_qb = away.get("qb1") or {}
        home_qb = home.get("qb1") or {}
        rows = (
            profile.build_qb_profile(
                str(away_qb.get("athlete_id") or ""),
                str(away_qb.get("name") or ""),
                cert.TARGET_YEAR,
                cert.SEASON_TYPE,
            ),
            profile.build_qb_profile(
                str(home_qb.get("athlete_id") or ""),
                str(home_qb.get("name") or ""),
                cert.TARGET_YEAR,
                cert.SEASON_TYPE,
            ),
        )
    finally:
        profile._season_stats_payload = original

    for label, row in zip(("Baker Mayfield", "Joe Burrow"), rows):
        if not row.get("ready"):
            raise AssertionError(f"{label} Step 2 profile unavailable: {cert._summary_profile(row)}")
        if int(row.get("season_year") or 0) != cert.BASELINE_YEAR:
            raise AssertionError(
                f"{label} expected verified {cert.BASELINE_YEAR} opening-week baseline, "
                f"got source_year={row.get('season_year')}"
            )
        season = row.get("season") or {}
        for field in ("games", "attempts_per_game", "yards_per_attempt"):
            if not _finite(season.get(field)):
                raise AssertionError(f"{label} Step 2 {field} unavailable: {cert._summary_profile(row)}")
    return rows


def certify_profile() -> None:
    away, home = _identities()
    _profiles(away, home)
    print("NFL_PASSING_YARDS_LIVE_PROFILE_GREEN")


def certify_matchup_inputs() -> None:
    away, home = _identities()
    original = defense_v1._team_stats_payload
    defense_v1._team_stats_payload = stat_split.team_stats_payload
    try:
        away_defense = defense_v2.build_pass_defense_profile(
            str(home.get("team_id") or ""),
            str(home.get("team") or "Cincinnati Bengals"),
            cert.TARGET_YEAR,
            cert.SEASON_TYPE,
            cert.CUTOFF_DATE,
        )
        home_defense = defense_v2.build_pass_defense_profile(
            str(away.get("team_id") or ""),
            str(away.get("team") or "Tampa Bay Buccaneers"),
            cert.TARGET_YEAR,
            cert.SEASON_TYPE,
            cert.CUTOFF_DATE,
        )
        for label, row in (("Cincinnati defense", away_defense), ("Tampa Bay defense", home_defense)):
            if not row.get("ready"):
                raise AssertionError(f"{label} Step 3 unavailable: {cert._summary_defense(row)}")
            season = row.get("season") or {}
            for field in ("passing_attempts_allowed_per_game", "yards_per_attempt_allowed"):
                if not _finite(season.get(field)):
                    raise AssertionError(f"{label} {field} unavailable: {cert._summary_defense(row)}")

        for label, side in (("Tampa Bay", away), ("Cincinnati", home)):
            payload, diag = stat_split.team_stats_payload(
                cert.BASELINE_YEAR,
                cert.SEASON_TYPE,
                str(side.get("team_id") or ""),
            )
            if not diag.get("ok"):
                raise AssertionError(f"{label} team stats unavailable: {diag}")
            pace = environment_v1.parse_team_pace(payload)
            if not pace.get("ready") or not _finite(pace.get("pass_attempts_per_game")):
                raise AssertionError(f"{label} Step 6 pace unavailable: diag={diag} pace={pace}")
    finally:
        defense_v1._team_stats_payload = original
    print("NFL_PASSING_YARDS_LIVE_MATCHUP_INPUTS_GREEN")


def certify_recent_variance() -> None:
    away, home = _identities()
    rows = _profiles(away, home)
    for label, row in zip(("Baker Mayfield", "Joe Burrow"), rows):
        recent = list(row.get("recent_games") or [])
        if len(recent) < 3:
            raise AssertionError(f"{label} has only {len(recent)} verified recent games; Step 9 requires >=3")
        yards = []
        for game in recent[:5]:
            event_id = str(game.get("event_id") or "")
            if not event_id.isdigit():
                raise AssertionError(f"{label} recent game missing exact ESPN event id: {game}")
            if not _finite(game.get("passing_yards")) or not _finite(game.get("attempts")):
                raise AssertionError(f"{label} recent game missing passing yards/attempts: {game}")
            yards.append(float(game.get("passing_yards")))
        if len(yards) < 3 or not _finite(stdev(yards)) or stdev(yards) <= 0:
            raise AssertionError(f"{label} verified recent passing-yard variance unavailable: {yards}")
    print("NFL_PASSING_YARDS_LIVE_RECENT_VARIANCE_GREEN")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("profile", "matchup", "recent"), required=True)
    args = parser.parse_args()
    if args.stage == "profile":
        certify_profile()
    elif args.stage == "matchup":
        certify_matchup_inputs()
    else:
        certify_recent_variance()


if __name__ == "__main__":
    main()
