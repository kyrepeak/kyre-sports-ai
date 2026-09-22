"""Season-scoped WNBA league structure used by the API.

Step 4A intentionally contains league/team identity only. It does not contain
player, roster, schedule, standings, betting, or model-derived data.

The 2026 alignment is based on the official WNBA league structure. Internal
``team_key``/``slug`` values are stable API identifiers owned by this project;
they are not represented as official WNBA IDs.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

CURRENT_SUPPORTED_SEASON = 2026
SUPPORTED_SEASONS = (2026,)
ALLOWED_CONFERENCES = frozenset({"Eastern", "Western"})

OFFICIAL_SOURCE = "WNBA.com"
OFFICIAL_SOURCE_URL = "https://www.wnba.com/faq"

# This registry is deliberately season-scoped. Do not reuse one season's
# alignment for another year without explicitly adding and validating it.
_WNBA_TEAMS_BY_SEASON: dict[int, tuple[dict[str, Any], ...]] = {
    2026: (
        {
            "team_key": "atlanta-dream",
            "slug": "atlanta-dream",
            "abbreviation": "ATL",
            "city": "Atlanta",
            "nickname": "Dream",
            "full_name": "Atlanta Dream",
            "conference": "Eastern",
        },
        {
            "team_key": "chicago-sky",
            "slug": "chicago-sky",
            "abbreviation": "CHI",
            "city": "Chicago",
            "nickname": "Sky",
            "full_name": "Chicago Sky",
            "conference": "Eastern",
        },
        {
            "team_key": "connecticut-sun",
            "slug": "connecticut-sun",
            "abbreviation": "CON",
            "city": "Connecticut",
            "nickname": "Sun",
            "full_name": "Connecticut Sun",
            "conference": "Eastern",
        },
        {
            "team_key": "dallas-wings",
            "slug": "dallas-wings",
            "abbreviation": "DAL",
            "city": "Dallas",
            "nickname": "Wings",
            "full_name": "Dallas Wings",
            "conference": "Western",
        },
        {
            "team_key": "golden-state-valkyries",
            "slug": "golden-state-valkyries",
            "abbreviation": "GSV",
            "city": "Golden State",
            "nickname": "Valkyries",
            "full_name": "Golden State Valkyries",
            "conference": "Western",
        },
        {
            "team_key": "indiana-fever",
            "slug": "indiana-fever",
            "abbreviation": "IND",
            "city": "Indiana",
            "nickname": "Fever",
            "full_name": "Indiana Fever",
            "conference": "Eastern",
        },
        {
            "team_key": "las-vegas-aces",
            "slug": "las-vegas-aces",
            "abbreviation": "LVA",
            "city": "Las Vegas",
            "nickname": "Aces",
            "full_name": "Las Vegas Aces",
            "conference": "Western",
        },
        {
            "team_key": "los-angeles-sparks",
            "slug": "los-angeles-sparks",
            "abbreviation": "LAS",
            "city": "Los Angeles",
            "nickname": "Sparks",
            "full_name": "Los Angeles Sparks",
            "conference": "Western",
        },
        {
            "team_key": "minnesota-lynx",
            "slug": "minnesota-lynx",
            "abbreviation": "MIN",
            "city": "Minnesota",
            "nickname": "Lynx",
            "full_name": "Minnesota Lynx",
            "conference": "Western",
        },
        {
            "team_key": "new-york-liberty",
            "slug": "new-york-liberty",
            "abbreviation": "NYL",
            "city": "New York",
            "nickname": "Liberty",
            "full_name": "New York Liberty",
            "conference": "Eastern",
        },
        {
            "team_key": "phoenix-mercury",
            "slug": "phoenix-mercury",
            "abbreviation": "PHX",
            "city": "Phoenix",
            "nickname": "Mercury",
            "full_name": "Phoenix Mercury",
            "conference": "Western",
        },
        {
            "team_key": "portland-fire",
            "slug": "portland-fire",
            "abbreviation": "POR",
            "city": "Portland",
            "nickname": "Fire",
            "full_name": "Portland Fire",
            "conference": "Western",
        },
        {
            "team_key": "seattle-storm",
            "slug": "seattle-storm",
            "abbreviation": "SEA",
            "city": "Seattle",
            "nickname": "Storm",
            "full_name": "Seattle Storm",
            "conference": "Western",
        },
        {
            "team_key": "toronto-tempo",
            "slug": "toronto-tempo",
            "abbreviation": "TOR",
            "city": "Toronto",
            "nickname": "Tempo",
            "full_name": "Toronto Tempo",
            "conference": "Eastern",
        },
        {
            "team_key": "washington-mystics",
            "slug": "washington-mystics",
            "abbreviation": "WAS",
            "city": "Washington",
            "nickname": "Mystics",
            "full_name": "Washington Mystics",
            "conference": "Eastern",
        },
    ),
}

_EXPECTED_TEAM_COUNTS = {2026: 15}
_EXPECTED_CONFERENCE_COUNTS = {
    2026: {"Eastern": 7, "Western": 8},
}


def validate_wnba_registry() -> None:
    """Fail fast if a supported season has an inconsistent team registry."""

    if set(_WNBA_TEAMS_BY_SEASON) != set(SUPPORTED_SEASONS):
        raise RuntimeError("WNBA supported seasons and team registry are out of sync.")

    for season in SUPPORTED_SEASONS:
        teams = _WNBA_TEAMS_BY_SEASON[season]
        expected_total = _EXPECTED_TEAM_COUNTS[season]
        if len(teams) != expected_total:
            raise RuntimeError(
                f"WNBA {season} registry has {len(teams)} teams; expected {expected_total}."
            )

        for field in ("team_key", "slug", "abbreviation", "full_name"):
            values = [str(team[field]).casefold() for team in teams]
            if len(values) != len(set(values)):
                raise RuntimeError(f"WNBA {season} registry contains duplicate {field} values.")

        conference_counts = {conference: 0 for conference in ALLOWED_CONFERENCES}
        for team in teams:
            conference = team.get("conference")
            if conference not in ALLOWED_CONFERENCES:
                raise RuntimeError(
                    f"WNBA {season} registry has invalid conference {conference!r}."
                )
            conference_counts[conference] += 1

        if conference_counts != _EXPECTED_CONFERENCE_COUNTS[season]:
            raise RuntimeError(
                f"WNBA {season} conference counts are {conference_counts}; "
                f"expected {_EXPECTED_CONFERENCE_COUNTS[season]}."
            )


validate_wnba_registry()


def _require_supported_season(season: int) -> None:
    if season not in _WNBA_TEAMS_BY_SEASON:
        supported = ", ".join(str(value) for value in SUPPORTED_SEASONS)
        raise ValueError(
            f"WNBA season {season} is not loaded. Supported season(s): {supported}."
        )


def get_wnba_teams(season: int = CURRENT_SUPPORTED_SEASON) -> list[dict[str, Any]]:
    """Return a defensive copy of the official team alignment for ``season``."""

    _require_supported_season(season)
    return deepcopy(list(_WNBA_TEAMS_BY_SEASON[season]))


def get_wnba_league_structure(
    season: int = CURRENT_SUPPORTED_SEASON,
) -> dict[str, Any]:
    """Return the league/conference summary for a supported season."""

    teams = get_wnba_teams(season)
    conferences = []

    for conference in ("Eastern", "Western"):
        conference_teams = [
            team for team in teams if team["conference"] == conference
        ]
        conferences.append(
            {
                "name": conference,
                "team_count": len(conference_teams),
                "teams": conference_teams,
            }
        )

    return {
        "league": "Women's National Basketball Association",
        "abbreviation": "WNBA",
        "season": season,
        "team_count": len(teams),
        "conference_count": len(conferences),
        "conferences": conferences,
    }
