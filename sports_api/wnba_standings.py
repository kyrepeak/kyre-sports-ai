"""WNBA standings, conference position, and playoff/seeding context.

Step 4M is descriptive standings context only. It does not estimate playoff
probabilities, future wins, clinch odds, or postseason series outcomes.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from sports_api.wnba_league import get_wnba_teams
from sports_api.wnba_rosters import (
    WNBA_LEAGUE_ID,
    WNBA_STATS_SOURCE,
    WNBA_STATS_SOURCE_URL,
    WNBAStatsUpstreamError,
    _request_stats_json,
    _result_rows,
)

STANDINGS_ENDPOINT = "leaguestandingsv3"
ALLOWED_STANDINGS_SEASON_TYPES = ("Regular Season",)
PLAYOFF_TEAM_COUNT = 8

# Season-scoped because expansion and postseason rules can change.
REGULAR_SEASON_GAMES_BY_SEASON = {2026: 44}
PLAYOFF_RULES_BY_SEASON: dict[int, dict[str, Any]] = {
    2026: {
        "qualification": "Top eight teams in the league regardless of conference",
        "playoff_team_count": 8,
        "seeding": "Regular-season record, subject to official WNBA tiebreak procedures",
        "reseed_after_first_round": False,
        "first_round": {"best_of": 3, "home_pattern": "1-1-1"},
        "semifinals": {"best_of": 5, "home_pattern": "2-2-1"},
        "finals": {"best_of": 7, "home_pattern": "2-2-1-1-1"},
        "official_source_url": "https://www.wnba.com/webview/news/2026-schedule-release",
    }
}
TIEBREAK_RULES_BY_SEASON: dict[int, dict[str, Any]] = {
    2026: {
        "criteria_in_order": [
            "Better record in head-to-head games",
            "Better winning percentage against all teams with .500 or better record at the end of the season",
            "Better head-to-head point differential",
            "Better overall point differential",
        ],
        "multi_team_reset_rule": (
            "For multi-team ties, after one or more teams are eliminated at a step, "
            "restart the procedure from the first criterion."
        ),
        "official_source_url": "https://www.wnba.com/standings",
    }
}


class WNBAStandingsUpstreamError(RuntimeError):
    """Raised when official WNBA standings cannot be consumed safely."""


class WNBAStandingsNotFoundError(LookupError):
    """Raised when a requested team or conference is not available."""


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_int(value: Any) -> int | None:
    text = _clean_text(value)
    if text is None:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    text = _clean_text(value)
    if text is None:
        return None
    if text in {"--", "-"}:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _flag(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "y", "x"}:
        return True
    if text in {"0", "false", "no", "n", ""}:
        return False
    return None


def _choice(value: str, allowed: Iterable[str], label: str) -> str:
    text = str(value).strip()
    lookup = {item.casefold(): item for item in allowed}
    resolved = lookup.get(text.casefold())
    if resolved is None:
        raise ValueError(
            f"Unsupported WNBA {label} {value!r}. Allowed values: "
            + ", ".join(allowed)
            + "."
        )
    return resolved


def _conference_name(value: Any) -> str | None:
    text = (_clean_text(value) or "").casefold()
    if text in {"east", "eastern", "e"}:
        return "Eastern"
    if text in {"west", "western", "w"}:
        return "Western"
    return None


def _require_team_key(team_key: str, season: int) -> dict[str, Any]:
    key = str(team_key).strip().casefold()
    for team in get_wnba_teams(season):
        if team["team_key"].casefold() == key:
            return team
    raise WNBAStandingsNotFoundError(
        f"WNBA team key {team_key!r} was not found for the {season} season."
    )


def _registry_team_from_row(row: dict[str, Any], season: int) -> dict[str, Any] | None:
    values = {
        (_clean_text(row.get("TeamCity")) or "").casefold(),
        (_clean_text(row.get("TeamName")) or "").casefold(),
        (_clean_text(row.get("TeamSlug")) or "").casefold(),
    }
    city = _clean_text(row.get("TeamCity"))
    name = _clean_text(row.get("TeamName"))
    if city and name:
        values.add(f"{city} {name}".casefold())
    values.discard("")

    # Official WNBA surfaces can use PDX for Portland while our stable
    # 2026 registry deliberately owns POR as its abbreviation.
    if "pdx" in values:
        values.add("por")
        values.add("portland-fire")
    if "gs" in values:
        values.add("gsv")
        values.add("golden-state-valkyries")

    for team in get_wnba_teams(season):
        candidates = {
            team["team_key"].casefold(),
            team["slug"].casefold(),
            team["abbreviation"].casefold(),
            team["city"].casefold(),
            team["nickname"].casefold(),
            team["full_name"].casefold(),
        }
        if values & candidates:
            return team
    return None


def _parse_record(value: Any) -> dict[str, Any]:
    text = _clean_text(value)
    wins = losses = None
    if text and "-" in text:
        left, right = text.split("-", 1)
        wins = _to_int(left)
        losses = _to_int(right)
    return {"raw": text, "wins": wins, "losses": losses}


def _normalize_standing(row: dict[str, Any], season: int) -> dict[str, Any]:
    registry = _registry_team_from_row(row, season)
    source_conference = _conference_name(row.get("Conference"))
    registry_conference = registry["conference"] if registry else None

    wins = _to_int(row.get("WINS"))
    losses = _to_int(row.get("LOSSES"))
    games_played = wins + losses if wins is not None and losses is not None else None
    schedule_games = REGULAR_SEASON_GAMES_BY_SEASON.get(season)
    games_remaining = (
        max(schedule_games - games_played, 0)
        if schedule_games is not None and games_played is not None
        else None
    )

    clinch_indicator = _clean_text(row.get("ClinchIndicator"))
    indicator = (clinch_indicator or "").casefold()
    eliminated_indicator = indicator in {"o", "e"}

    return {
        "official_team_id": _to_int(row.get("TeamID")),
        "team_key": registry["team_key"] if registry else None,
        "team_full_name": registry["full_name"] if registry else None,
        "team_abbreviation": registry["abbreviation"] if registry else None,
        "team_city": _clean_text(row.get("TeamCity")),
        "team_name": _clean_text(row.get("TeamName")),
        "team_slug": _clean_text(row.get("TeamSlug")),
        "conference": registry_conference,
        "source_conference": source_conference,
        "conference_consistent": (
            source_conference is None
            or registry_conference is None
            or source_conference == registry_conference
        ),
        "conference_record": _parse_record(row.get("ConferenceRecord")),
        "official_playoff_rank": _to_int(row.get("PlayoffRank")),
        "official_league_rank": _to_int(row.get("LeagueRank")),
        "clinch_indicator": clinch_indicator,
        "official_clinch_flags": {
            "clinched_playoff_berth": _flag(row.get("ClinchedPlayoffBirth")),
            "clinched_conference_title": _flag(row.get("ClinchedConferenceTitle")),
            "clinched_division_title": _flag(row.get("ClinchedDivisionTitle")),
            "eliminated_conference": _flag(row.get("EliminatedConference")),
            "eliminated_division": _flag(row.get("EliminatedDivision")),
            "eliminated_playoff_indicator": eliminated_indicator,
        },
        "wins": wins,
        "losses": losses,
        "win_percentage": _to_float(row.get("WinPCT")),
        "record": _clean_text(row.get("Record")),
        "games_played": games_played,
        "scheduled_regular_season_games": schedule_games,
        "games_remaining": games_remaining,
        "max_possible_wins": (
            wins + games_remaining
            if wins is not None and games_remaining is not None
            else None
        ),
        "home_record": _parse_record(row.get("HOME")),
        "road_record": _parse_record(row.get("ROAD")),
        "last_10_record": _parse_record(row.get("L10")),
        "last_10_home_record": _parse_record(row.get("Last10Home")),
        "last_10_road_record": _parse_record(row.get("Last10Road")),
        "overtime_record": _parse_record(row.get("OT")),
        "three_points_or_less_record": _parse_record(row.get("ThreePTSOrLess")),
        "ten_points_or_more_record": _parse_record(row.get("TenPTSOrMore")),
        "current_streak": {
            "count": _to_int(row.get("CurrentStreak")),
            "display": _clean_text(row.get("strCurrentStreak")),
        },
        "current_home_streak": {
            "count": _to_int(row.get("CurrentHomeStreak")),
            "display": _clean_text(row.get("strCurrentHomeStreak")),
        },
        "current_road_streak": {
            "count": _to_int(row.get("CurrentRoadStreak")),
            "display": _clean_text(row.get("strCurrentRoadStreak")),
        },
        "conference_games_back": _to_float(row.get("ConferenceGamesBack")),
        "points_per_game": _to_float(row.get("PointsPG")),
        "opponent_points_per_game": _to_float(row.get("OppPointsPG")),
        "point_differential_per_game": _to_float(row.get("DiffPointsPG")),
        "record_vs_east": _parse_record(row.get("vsEast")),
        "record_vs_west": _parse_record(row.get("vsWest")),
        "record_vs_500_or_better": _parse_record(row.get("OppOver500")),
        "monthly_records": {
            month: _parse_record(row.get(month))
            for month in ("May", "Jun", "Jul", "Aug", "Sep")
        },
        "mapped_to_registry": registry is not None,
        # Filled after the full league table is validated and ordered.
        "current_league_seed": None,
        "league_seed_source": None,
        "conference_rank": None,
        "playoff_context": None,
    }


def _games_back(team: dict[str, Any], reference: dict[str, Any]) -> float | None:
    tw, tl = team.get("wins"), team.get("losses")
    rw, rl = reference.get("wins"), reference.get("losses")
    if None in {tw, tl, rw, rl}:
        return None
    return round(((rw - tw) + (tl - rl)) / 2.0, 1)


def _ordered_standings(standings: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    official = [team.get("official_league_rank") for team in standings]
    count = len(standings)
    if (
        all(isinstance(rank, int) for rank in official)
        and len(set(official)) == count
        and set(official) == set(range(1, count + 1))
    ):
        ordered = sorted(standings, key=lambda team: team["official_league_rank"])
        return ordered, "official_LeagueRank"

    ordered = sorted(
        standings,
        key=lambda team: (
            -(team.get("win_percentage") if team.get("win_percentage") is not None else -1.0),
            -(team.get("wins") if team.get("wins") is not None else -1),
            team.get("losses") if team.get("losses") is not None else 10_000,
            team.get("team_key") or "",
        ),
    )
    return ordered, "derived_win_pct_order_tiebreak_not_resolved"


def _apply_ranks_and_playoff_context(standings: list[dict[str, Any]], season: int) -> str:
    ordered, source = _ordered_standings(standings)
    for seed, team in enumerate(ordered, start=1):
        team["current_league_seed"] = seed
        team["league_seed_source"] = source

    by_conference: dict[str, list[dict[str, Any]]] = {"Eastern": [], "Western": []}
    for team in ordered:
        if team["conference"] in by_conference:
            by_conference[team["conference"]].append(team)
    for conference_teams in by_conference.values():
        for rank, team in enumerate(conference_teams, start=1):
            team["conference_rank"] = rank

    if len(ordered) < PLAYOFF_TEAM_COUNT:
        raise WNBAStandingsUpstreamError(
            "Official WNBA standings returned fewer teams than the playoff field."
        )

    eighth = ordered[PLAYOFF_TEAM_COUNT - 1]
    ninth = ordered[PLAYOFF_TEAM_COUNT] if len(ordered) > PLAYOFF_TEAM_COUNT else None

    for team in ordered:
        seed = team["current_league_seed"]
        clinched = team["official_clinch_flags"]["clinched_playoff_berth"] is True
        eliminated = team["official_clinch_flags"]["eliminated_playoff_indicator"] is True

        if clinched:
            status = "clinched_playoff_berth"
        elif eliminated:
            status = "eliminated_from_playoff_contention"
        elif seed <= PLAYOFF_TEAM_COUNT:
            status = "inside_current_playoff_field"
        else:
            status = "outside_current_playoff_field"

        behind_eighth = _games_back(team, eighth) if seed > PLAYOFF_TEAM_COUNT else None
        ahead_ninth = None
        if seed <= PLAYOFF_TEAM_COUNT and ninth is not None:
            ninth_behind_team = _games_back(ninth, team)
            ahead_ninth = max(ninth_behind_team, 0.0) if ninth_behind_team is not None else None

        cutoff_tied = False
        if team.get("win_percentage") is not None:
            comparison = eighth if seed > PLAYOFF_TEAM_COUNT else ninth
            if comparison and comparison.get("win_percentage") is not None:
                cutoff_tied = team["win_percentage"] == comparison["win_percentage"]

        team["playoff_context"] = {
            "qualification_rule": PLAYOFF_RULES_BY_SEASON[season]["qualification"],
            "current_status": status,
            "currently_in_playoff_field": seed <= PLAYOFF_TEAM_COUNT,
            "current_seed": seed,
            "playoff_cutoff_seed": PLAYOFF_TEAM_COUNT,
            "games_behind_eighth_seed": (
                max(behind_eighth, 0.0) if behind_eighth is not None else None
            ),
            "games_ahead_of_ninth_seed": ahead_ninth,
            "cutoff_tied_on_win_percentage": cutoff_tied,
            "tiebreak_note": (
                "Official league order is used when supplied. Games-back values do "
                "not independently resolve WNBA tiebreak criteria."
            ),
            "projection_or_probability": False,
        }

    standings[:] = ordered
    return source


def _standings_params(season: int, season_type: str) -> list[tuple[str, Any]]:
    return [
        ("LeagueID", WNBA_LEAGUE_ID),
        ("Season", str(season)),
        ("SeasonType", season_type),
        ("SeasonYear", ""),
    ]


def get_standings_dataset(
    season: int,
    *,
    season_type: str = "Regular Season",
) -> dict[str, Any]:
    registry = get_wnba_teams(season)
    if season not in PLAYOFF_RULES_BY_SEASON or season not in REGULAR_SEASON_GAMES_BY_SEASON:
        raise ValueError(f"WNBA standings rules are not configured for season {season}.")
    season_type = _choice(
        season_type, ALLOWED_STANDINGS_SEASON_TYPES, "standings season_type"
    )

    params = _standings_params(season, season_type)
    try:
        payload, retrieved_at_utc, cache_hit = _request_stats_json(
            STANDINGS_ENDPOINT, params
        )
        rows = _result_rows(payload, "Standings")
    except WNBAStatsUpstreamError as exc:
        raise WNBAStandingsUpstreamError(str(exc)) from exc

    if not rows:
        raise WNBAStandingsUpstreamError("Official WNBA standings returned no teams.")

    required = {"LeagueID", "TeamID", "TeamCity", "TeamName", "WINS", "LOSSES", "WinPCT"}
    missing = sorted(required - set(rows[0]))
    if missing:
        raise WNBAStandingsUpstreamError(
            "Official WNBA standings schema is missing required field(s): "
            + ", ".join(missing)
        )

    standings = [_normalize_standing(row, season) for row in rows]
    if len(standings) != len(registry):
        raise WNBAStandingsUpstreamError(
            f"Official WNBA standings returned {len(standings)} teams; "
            f"expected {len(registry)} for {season}."
        )

    wrong_league = sorted(
        {
            str(row.get("LeagueID"))
            for row in rows
            if _clean_text(row.get("LeagueID")) not in {None, WNBA_LEAGUE_ID}
        }
    )
    if wrong_league:
        raise WNBAStandingsUpstreamError(
            "Official WNBA standings returned unexpected LeagueID value(s): "
            + ", ".join(wrong_league)
        )

    unmapped = [team for team in standings if not team["mapped_to_registry"]]
    if unmapped:
        names = ", ".join(
            sorted(
                f"{team.get('team_city') or ''} {team.get('team_name') or ''}".strip()
                for team in unmapped
            )
        )
        raise WNBAStandingsUpstreamError(
            f"Official WNBA standings contain unmapped team identity: {names}."
        )

    inconsistent = [
        team["team_key"] for team in standings if not team["conference_consistent"]
    ]
    if inconsistent:
        raise WNBAStandingsUpstreamError(
            "Official WNBA standings conference disagrees with the season registry for: "
            + ", ".join(sorted(inconsistent))
        )

    team_ids = [team["official_team_id"] for team in standings]
    if any(team_id is None for team_id in team_ids) or len(set(team_ids)) != len(team_ids):
        raise WNBAStandingsUpstreamError(
            "Official WNBA standings contain missing or duplicate team IDs."
        )
    team_keys = [team["team_key"] for team in standings]
    if len(set(team_keys)) != len(team_keys):
        raise WNBAStandingsUpstreamError(
            "Official WNBA standings map more than one row to the same team."
        )

    seed_source = _apply_ranks_and_playoff_context(standings, season)

    eighth = standings[PLAYOFF_TEAM_COUNT - 1]
    ninth = standings[PLAYOFF_TEAM_COUNT] if len(standings) > PLAYOFF_TEAM_COUNT else None

    return {
        "source": WNBA_STATS_SOURCE,
        "source_url": WNBA_STATS_SOURCE_URL,
        "source_endpoint": STANDINGS_ENDPOINT,
        "league_id": WNBA_LEAGUE_ID,
        "season": season,
        "season_type": season_type,
        "retrieved_at_utc": retrieved_at_utc,
        "cache_hit": cache_hit,
        "team_count": len(standings),
        "league_seed_source": seed_source,
        "playoff_rules": deepcopy(PLAYOFF_RULES_BY_SEASON[season]),
        "tiebreak_rules": deepcopy(TIEBREAK_RULES_BY_SEASON[season]),
        "playoff_cut_line": {
            "eighth_seed": {
                "team_key": eighth["team_key"],
                "record": eighth["record"],
                "win_percentage": eighth["win_percentage"],
            },
            "ninth_seed": (
                {
                    "team_key": ninth["team_key"],
                    "record": ninth["record"],
                    "win_percentage": ninth["win_percentage"],
                }
                if ninth
                else None
            ),
        },
        "standings": standings,
        "verification": {
            "team_count_matches_registry": len(standings) == len(registry),
            "team_ids_unique": len(set(team_ids)) == len(team_ids),
            "team_keys_unique": len(set(team_keys)) == len(team_keys),
            "all_teams_mapped_to_registry": True,
            "conference_alignment_matches_registry": True,
            "playoff_context_is_descriptive_not_predictive": True,
        },
    }


def get_conference_standings_dataset(
    conference: str,
    season: int,
    *,
    season_type: str = "Regular Season",
) -> dict[str, Any]:
    resolved = _choice(conference, ("Eastern", "Western", "East", "West"), "conference")
    resolved = _conference_name(resolved)
    if resolved is None:
        raise ValueError(f"Unsupported WNBA conference {conference!r}.")

    dataset = get_standings_dataset(season, season_type=season_type)
    teams = [team for team in dataset["standings"] if team["conference"] == resolved]
    expected = sum(team["conference"] == resolved for team in get_wnba_teams(season))
    if len(teams) != expected:
        raise WNBAStandingsUpstreamError(
            f"WNBA {resolved} standings returned {len(teams)} teams; expected {expected}."
        )
    return {
        "source": dataset["source"],
        "source_url": dataset["source_url"],
        "source_endpoint": dataset["source_endpoint"],
        "league_id": dataset["league_id"],
        "season": season,
        "season_type": dataset["season_type"],
        "retrieved_at_utc": dataset["retrieved_at_utc"],
        "cache_hit": dataset["cache_hit"],
        "conference": resolved,
        "team_count": len(teams),
        "standings": teams,
        "playoff_note": (
            "Conference rank is descriptive only. WNBA playoff qualification uses "
            "the top eight teams league-wide regardless of conference."
        ),
    }


def get_team_standings_context_dataset(
    team_key: str,
    season: int,
    *,
    season_type: str = "Regular Season",
) -> dict[str, Any]:
    registry_team = _require_team_key(team_key, season)
    dataset = get_standings_dataset(season, season_type=season_type)
    standing = next(
        (team for team in dataset["standings"] if team["team_key"] == registry_team["team_key"]),
        None,
    )
    if standing is None:
        raise WNBAStandingsNotFoundError(
            f"WNBA team {registry_team['team_key']!r} was not found in official standings."
        )

    seed = standing["current_league_seed"]
    above = dataset["standings"][seed - 2] if seed and seed > 1 else None
    below = dataset["standings"][seed] if seed and seed < len(dataset["standings"]) else None

    return {
        "source": dataset["source"],
        "source_url": dataset["source_url"],
        "source_endpoint": dataset["source_endpoint"],
        "season": season,
        "season_type": dataset["season_type"],
        "retrieved_at_utc": dataset["retrieved_at_utc"],
        "cache_hit": dataset["cache_hit"],
        "team": standing,
        "adjacent_seeds": {
            "one_seed_above": (
                {"seed": above["current_league_seed"], "team_key": above["team_key"], "record": above["record"]}
                if above else None
            ),
            "one_seed_below": (
                {"seed": below["current_league_seed"], "team_key": below["team_key"], "record": below["record"]}
                if below else None
            ),
        },
        "playoff_cut_line": deepcopy(dataset["playoff_cut_line"]),
        "playoff_rules": deepcopy(dataset["playoff_rules"]),
        "tiebreak_rules": deepcopy(dataset["tiebreak_rules"]),
    }
