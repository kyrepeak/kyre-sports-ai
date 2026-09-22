"""Live source certification for NFL Passing Yards opening-week production data.

This is deliberately not a mocked unit test. It reaches the same public ESPN
source family used by production, resolves current QB1 identity for Tampa Bay
and Cincinnati, exercises the early-season prior-season bridge, builds the
certified Step 7 baseline, and proves Matchup Spotlight has numeric Expected
ATT, Expected YPA, and Step 7 Base values for both quarterbacks.

No sportsbook input is used. Intended for GitHub Actions with outbound access.
"""
from __future__ import annotations

import json
import math

import nfl_passing_yards_defense_v1 as defense_v1
import nfl_passing_yards_defense_v2 as defense_v2
import nfl_passing_yards_environment_v1 as environment_v1
import nfl_passing_yards_espn_stat_split_v1 as stat_split
import nfl_passing_yards_hub_v16 as ui_v16
import nfl_passing_yards_identity_v1 as identity
import nfl_passing_yards_profile_v1 as profile
import nfl_passing_yards_projection_v1 as projection

TARGET_YEAR = 2026
BASELINE_YEAR = 2025
SEASON_TYPE = 2
CUTOFF_DATE = "2026-09-13"


def _finite(value) -> bool:
    try:
        return math.isfinite(float(value))
    except Exception:
        return False


def _summary_profile(row: dict) -> dict:
    season = row.get("season") or {}
    return {
        "ready": bool(row.get("ready")),
        "reason": row.get("reason"),
        "qb_name": row.get("qb_name"),
        "athlete_id": row.get("athlete_id"),
        "source_year": row.get("source_year") or row.get("baseline_year"),
        "early_season_fallback": bool(row.get("early_season_fallback")),
        "games": season.get("games"),
        "attempts_per_game": season.get("attempts_per_game"),
        "yards_per_attempt": season.get("yards_per_attempt"),
        "recent3_attempts": row.get("recent3_attempts"),
        "recent3_yards": row.get("recent3_yards"),
        "recent_games": len(row.get("recent_games") or []),
        "season_http": row.get("season_http"),
        "fallback_season_http": row.get("fallback_season_http"),
    }


def _summary_defense(row: dict) -> dict:
    season = row.get("season") or {}
    return {
        "ready": bool(row.get("ready")),
        "reason": row.get("reason"),
        "team": row.get("team_name"),
        "team_id": row.get("team_id"),
        "source_year": row.get("source_year") or row.get("baseline_year"),
        "early_season_fallback": bool(row.get("early_season_fallback")),
        "attempts_allowed_per_game": season.get("passing_attempts_allowed_per_game"),
        "ypa_allowed": season.get("yards_per_attempt_allowed"),
        "recent3_ypa_allowed": row.get("recent3_ypa_allowed"),
        "recent_games": len(row.get("recent_games") or []),
    }


def _resolve_side(abbr: str, team_name: str) -> dict:
    row = identity.resolve_team_qb_identity(
        abbr,
        team_name,
        TARGET_YEAR,
        injury_map={},
        injury_feed_ok=False,
    )
    if not row.get("identity_verified"):
        raise AssertionError(f"{abbr} verified QB1 identity unavailable: {row}")
    return row


def _build_pace(team_id: str) -> dict:
    payload, diag = stat_split.team_stats_payload(BASELINE_YEAR, SEASON_TYPE, team_id)
    if not diag.get("ok"):
        raise AssertionError(f"team stats unavailable team_id={team_id}: {diag}")
    pace = environment_v1.parse_team_pace(payload)
    if not pace.get("ready"):
        raise AssertionError(
            f"team pace parse unavailable team_id={team_id}: "
            f"diag={diag} payload_keys={list(payload)[:20]} pace={pace}"
        )
    return pace


def run_live_certification() -> dict:
    # Production V17 installs these exact transports during its render.
    original_profile_loader = profile._season_stats_payload
    original_team_loader = defense_v1._team_stats_payload
    profile._season_stats_payload = stat_split.athlete_stats_payload
    defense_v1._team_stats_payload = stat_split.team_stats_payload
    try:
        away = _resolve_side("TB", "Tampa Bay Buccaneers")
        home = _resolve_side("CIN", "Cincinnati Bengals")

        away_qb = away.get("qb1") or {}
        home_qb = home.get("qb1") or {}
        if "baker mayfield" not in str(away_qb.get("name") or "").lower():
            raise AssertionError(f"Expected Baker Mayfield as TB QB1, got {away_qb}")
        if "joe burrow" not in str(home_qb.get("name") or "").lower():
            raise AssertionError(f"Expected Joe Burrow as CIN QB1, got {home_qb}")

        away_profile = profile.build_qb_profile(
            str(away_qb.get("athlete_id") or ""),
            str(away_qb.get("name") or ""),
            TARGET_YEAR,
            SEASON_TYPE,
        )
        home_profile = profile.build_qb_profile(
            str(home_qb.get("athlete_id") or ""),
            str(home_qb.get("name") or ""),
            TARGET_YEAR,
            SEASON_TYPE,
        )

        if not away_profile.get("ready") or not home_profile.get("ready"):
            raise AssertionError(
                "Step 2 live profile bridge failed: "
                + json.dumps(
                    {
                        "away": _summary_profile(away_profile),
                        "home": _summary_profile(home_profile),
                    },
                    indent=2,
                    default=str,
                )
            )

        # Step 3 matchup defense uses the opposing team.
        away_defense = defense_v2.build_pass_defense_profile(
            str(home.get("team_id") or ""),
            str(home.get("team") or "Cincinnati Bengals"),
            TARGET_YEAR,
            SEASON_TYPE,
            CUTOFF_DATE,
        )
        home_defense = defense_v2.build_pass_defense_profile(
            str(away.get("team_id") or ""),
            str(away.get("team") or "Tampa Bay Buccaneers"),
            TARGET_YEAR,
            SEASON_TYPE,
            CUTOFF_DATE,
        )

        away_pace = _build_pace(str(away.get("team_id") or ""))
        home_pace = _build_pace(str(home.get("team_id") or ""))
        env = {
            "away_pace": away_pace,
            "home_pace": home_pace,
            "environment_label": "CHECK",
            "weather_label": "CHECK",
        }

        neutral_pressure = {"pressure_label": "CHECK"}
        neutral_personnel = {"personnel_label": "CHECK"}
        away_base = projection.build_baseline_projection(
            away,
            away_profile,
            away_defense,
            neutral_pressure,
            neutral_personnel,
            env,
            "away",
            preseason=False,
        )
        home_base = projection.build_baseline_projection(
            home,
            home_profile,
            home_defense,
            neutral_pressure,
            neutral_personnel,
            env,
            "home",
            preseason=False,
        )

        failures = []
        for label, row in (("Baker Mayfield", away_base), ("Joe Burrow", home_base)):
            for field in ("expected_attempts", "expected_ypa", "projection_yards"):
                if not _finite(row.get(field)):
                    failures.append(f"{label} {field}={row.get(field)!r}")
            if not row.get("ready"):
                failures.append(
                    f"{label} baseline not ready: {row.get('reason')} "
                    f"attempt_coverage={row.get('attempt_coverage')} ypa_coverage={row.get('ypa_coverage')}"
                )
        if failures:
            raise AssertionError(
                "Step 7 live baseline certification failed: "
                + " | ".join(failures)
                + "\nDETAILS="
                + json.dumps(
                    {
                        "away_profile": _summary_profile(away_profile),
                        "home_profile": _summary_profile(home_profile),
                        "away_defense": _summary_defense(away_defense),
                        "home_defense": _summary_defense(home_defense),
                        "away_pace": away_pace,
                        "home_pace": home_pace,
                        "away_base": away_base,
                        "home_base": home_base,
                    },
                    indent=2,
                    default=str,
                )
            )

        identity_result = {"ready": True, "away": away, "home": home}
        matchup_html = ui_v16._matchup_html(identity_result, [away_base, home_base])
        if not matchup_html or ">—<" in matchup_html:
            raise AssertionError("Matchup Spotlight still renders a dash for a certified Step 7 mini value")

        result = {
            "status": "GREEN",
            "matchup": "Tampa Bay Buccaneers @ Cincinnati Bengals",
            "cutoff_date": CUTOFF_DATE,
            "sportsbook_projection_influence": 0.0,
            "away": {
                "qb": away_qb.get("name"),
                "athlete_id": away_qb.get("athlete_id"),
                "profile": _summary_profile(away_profile),
                "defense": _summary_defense(away_defense),
                "expected_attempts": away_base.get("expected_attempts"),
                "expected_ypa": away_base.get("expected_ypa"),
                "step7_base": away_base.get("projection_yards"),
            },
            "home": {
                "qb": home_qb.get("name"),
                "athlete_id": home_qb.get("athlete_id"),
                "profile": _summary_profile(home_profile),
                "defense": _summary_defense(home_defense),
                "expected_attempts": home_base.get("expected_attempts"),
                "expected_ypa": home_base.get("expected_ypa"),
                "step7_base": home_base.get("projection_yards"),
            },
        }
        print("NFL_PASSING_YARDS_LIVE_SOURCE_CERT_GREEN")
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
        return result
    finally:
        profile._season_stats_payload = original_profile_loader
        defense_v1._team_stats_payload = original_team_loader


if __name__ == "__main__":
    run_live_certification()
