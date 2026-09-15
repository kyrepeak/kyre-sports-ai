"""Official ESPN team scoring profiles for NFL Game Totals V1.

Sportsbook-free football data only. The collector uses exact official ESPN team
IDs, completed regular-season scores, and leakage-safe date cutoffs. It creates
team scoring/allowance profiles for the separate Game Totals feature firewall;
it does not create a game projection or consume market data.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import math
from typing import Any, Mapping

from sports_api.collectors import nfl_fanduel_passing_yards as transport
from sports_api.collectors.nfl_game_totals_schedule_v1 import ESPN_SITE_BASES

SCHEMA_VERSION = "nfl_game_totals_team_profile_v1"
PRIOR_GAMES_WEIGHT = 6.0
MIN_PRIOR_GAMES = 12
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
SPORTSBOOK_INPUTS: tuple[str, ...] = ()


class NFLGameTotalsTeamProfileError(RuntimeError):
    """An exact football-only team profile could not be proven safely."""


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _aware_utc(value: Any, field: str) -> datetime:
    text = _text(value).replace("Z", "+00:00")
    if not text:
        raise NFLGameTotalsTeamProfileError(f"{field} is required")
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError as exc:
        raise NFLGameTotalsTeamProfileError(f"{field} is not valid ISO-8601") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise NFLGameTotalsTeamProfileError(f"{field} must be timezone-aware")
    return stamp.astimezone(timezone.utc)


def _game_date(value: date | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(_text(value))
    except ValueError as exc:
        raise NFLGameTotalsTeamProfileError("game_date must be YYYY-MM-DD") from exc


def _season_year(value: date | str) -> int:
    d = _game_date(value)
    return d.year - 1 if d.month <= 2 else d.year


def _score(value: Any, field: str) -> float:
    raw = value
    if isinstance(value, Mapping):
        raw = value.get("value")
        if raw is None:
            raw = value.get("displayValue")
    try:
        number = float(raw)
    except (TypeError, ValueError) as exc:
        raise NFLGameTotalsTeamProfileError(f"{field} is not numeric") from exc
    if not math.isfinite(number) or number < 0 or number > 100:
        raise NFLGameTotalsTeamProfileError(f"{field} is outside the supported NFL score range")
    return number


def parse_completed_regular_schedule(
    payload: Mapping[str, Any],
    official_team_id: str,
    *,
    before_utc: datetime | None = None,
) -> list[dict[str, Any]]:
    """Normalize completed exact-team regular-season games before the cutoff."""
    team_id = _text(official_team_id)
    if not team_id.isdigit():
        raise NFLGameTotalsTeamProfileError("official ESPN team ID must be numeric")
    if before_utc is not None:
        if before_utc.tzinfo is None or before_utc.utcoffset() is None:
            raise ValueError("before_utc must be timezone-aware")
        cutoff = before_utc.astimezone(timezone.utc)
    else:
        cutoff = None

    events = payload.get("events") if isinstance(payload, Mapping) else None
    if not isinstance(events, list):
        raise NFLGameTotalsTeamProfileError("ESPN team schedule events payload is invalid")

    rows: list[dict[str, Any]] = []
    eligible_completed = 0
    for event in events:
        if not isinstance(event, Mapping):
            continue
        competitions = event.get("competitions") or []
        if not competitions or not isinstance(competitions[0], Mapping):
            continue
        competition = competitions[0]
        status = event.get("status") if isinstance(event.get("status"), Mapping) else competition.get("status")
        status_type = (status or {}).get("type") if isinstance(status, Mapping) and isinstance((status or {}).get("type"), Mapping) else {}
        completed = bool((status_type or {}).get("completed")) or _text((status_type or {}).get("state")).lower() == "post"
        if not completed:
            continue

        kickoff = _aware_utc(competition.get("date") or event.get("date"), "ESPN team game kickoff")
        if cutoff is not None and kickoff >= cutoff:
            continue
        eligible_completed += 1

        ours = None
        opponent = None
        for competitor in competition.get("competitors") or []:
            if not isinstance(competitor, Mapping):
                continue
            team = competitor.get("team") if isinstance(competitor.get("team"), Mapping) else {}
            candidate_id = _text((team or {}).get("id"))
            if candidate_id == team_id:
                if ours is not None:
                    raise NFLGameTotalsTeamProfileError("ESPN schedule duplicated the official team in one game")
                ours = competitor
            elif candidate_id.isdigit():
                opponent = competitor
        if ours is None or opponent is None:
            continue

        event_id = _text(event.get("id") or competition.get("id"))
        if not event_id.isdigit():
            raise NFLGameTotalsTeamProfileError("ESPN completed team game is missing a numeric event ID")
        pf = _score(ours.get("score"), "points_for")
        pa = _score(opponent.get("score"), "points_against")
        opp_team = opponent.get("team") if isinstance(opponent.get("team"), Mapping) else {}
        rows.append(
            {
                "official_event_id": event_id,
                "official_team_id": team_id,
                "opponent_team_id": _text((opp_team or {}).get("id")),
                "kickoff_utc": kickoff.isoformat(),
                "pf": pf,
                "pa": pa,
            }
        )

    if eligible_completed and not rows:
        raise NFLGameTotalsTeamProfileError(
            "completed ESPN schedule rows did not contain the requested exact official team ID"
        )
    rows.sort(key=lambda row: (row["kickoff_utc"], row["official_event_id"]))
    ids = [row["official_event_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise NFLGameTotalsTeamProfileError("ESPN team schedule produced duplicate event IDs")
    return rows


def summarize_completed_games(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    clean: list[tuple[float, float]] = []
    for row in rows or []:
        if not isinstance(row, Mapping):
            continue
        pf = _score(row.get("pf"), "points_for")
        pa = _score(row.get("pa"), "points_against")
        clean.append((pf, pa))
    if not clean:
        return {
            "games": 0,
            "ppg": None,
            "papg": None,
            "recent6_pf_pg": None,
            "recent6_pa_pg": None,
        }
    recent = clean[-6:]
    return {
        "games": len(clean),
        "ppg": sum(pf for pf, _ in clean) / len(clean),
        "papg": sum(pa for _, pa in clean) / len(clean),
        "recent6_pf_pg": sum(pf for pf, _ in recent) / len(recent),
        "recent6_pa_pg": sum(pa for _, pa in recent) / len(recent),
    }


def blend_scoring_profiles(prior: Mapping[str, Any], current: Mapping[str, Any]) -> dict[str, Any]:
    prior_games = int(prior.get("games") or 0)
    current_games = int(current.get("games") or 0)
    if prior_games < MIN_PRIOR_GAMES:
        raise NFLGameTotalsTeamProfileError(
            f"prior-season scoring profile requires at least {MIN_PRIOR_GAMES} completed games"
        )

    def finite(profile: Mapping[str, Any], key: str) -> float:
        try:
            number = float(profile.get(key))
        except (TypeError, ValueError) as exc:
            raise NFLGameTotalsTeamProfileError(f"profile field {key} is unavailable") from exc
        if not math.isfinite(number):
            raise NFLGameTotalsTeamProfileError(f"profile field {key} is unavailable")
        return number

    if current_games <= 0:
        return {
            "ppg": finite(prior, "ppg"),
            "papg": finite(prior, "papg"),
            "recent6_pf_pg": finite(prior, "recent6_pf_pg"),
            "recent6_pa_pg": finite(prior, "recent6_pa_pg"),
            "current_weight": 0.0,
        }

    weight = current_games / (PRIOR_GAMES_WEIGHT + current_games)
    ppg = (PRIOR_GAMES_WEIGHT * finite(prior, "ppg") + current_games * finite(current, "ppg")) / (PRIOR_GAMES_WEIGHT + current_games)
    papg = (PRIOR_GAMES_WEIGHT * finite(prior, "papg") + current_games * finite(current, "papg")) / (PRIOR_GAMES_WEIGHT + current_games)
    if current_games >= 3:
        recent_pf = finite(current, "recent6_pf_pg")
        recent_pa = finite(current, "recent6_pa_pg")
    else:
        recent_pf = finite(prior, "recent6_pf_pg")
        recent_pa = finite(prior, "recent6_pa_pg")
    return {
        "ppg": ppg,
        "papg": papg,
        "recent6_pf_pg": recent_pf,
        "recent6_pa_pg": recent_pa,
        "current_weight": weight,
    }


def fetch_espn_team_schedule_hosted(
    official_team_id: str,
    season: int,
    *,
    timeout: int = transport.DEFAULT_TIMEOUT_SECONDS,
) -> tuple[dict[str, Any], str]:
    team_id = _text(official_team_id)
    if not team_id.isdigit():
        raise NFLGameTotalsTeamProfileError("official ESPN team ID must be numeric")
    for root in ESPN_SITE_BASES:
        try:
            payload = transport._get_json(
                f"{root}/teams/{team_id}/schedule",
                {"season": int(season), "seasontype": 2},
                headers=transport.ESPN_HEADERS,
                timeout=timeout,
            )
            return payload, root
        except transport.NFLPassingYardsCollectorError:
            continue
    raise NFLGameTotalsTeamProfileError(
        "official ESPN team schedule transport failed closed across site.api + site.web.api"
    )


def collect_team_scoring_profile(
    team: Mapping[str, Any],
    game_date: date | str,
    *,
    fetcher=None,
) -> dict[str, Any]:
    team_id = _text((team or {}).get("team_id"))
    abbr = _text((team or {}).get("abbr")).upper()
    name = _text((team or {}).get("name"))
    if not team_id.isdigit() or not abbr or not name:
        raise NFLGameTotalsTeamProfileError("official team identity is incomplete")

    requested = _game_date(game_date)
    season = _season_year(requested)
    prior_season = season - 1
    cutoff = datetime(requested.year, requested.month, requested.day, tzinfo=timezone.utc)
    load = fetcher or fetch_espn_team_schedule_hosted

    prior_result = load(team_id, prior_season)
    current_result = load(team_id, season)
    prior_payload, prior_source = prior_result if isinstance(prior_result, tuple) else (prior_result, "injected-test-source")
    current_payload, current_source = current_result if isinstance(current_result, tuple) else (current_result, "injected-test-source")

    prior_rows = parse_completed_regular_schedule(prior_payload, team_id)
    current_rows = parse_completed_regular_schedule(current_payload, team_id, before_utc=cutoff)
    prior = summarize_completed_games(prior_rows)
    current = summarize_completed_games(current_rows)
    blended = blend_scoring_profiles(prior, current)

    return {
        "schema_version": SCHEMA_VERSION,
        "ready": True,
        "official_authority": "ESPN",
        "official_team_id": team_id,
        "abbr": abbr,
        "name": name,
        "season": season,
        "prior_season": prior_season,
        "prior_games": int(prior["games"]),
        "current_games": int(current["games"]),
        "current_weight": float(blended["current_weight"]),
        "ppg": float(blended["ppg"]),
        "papg": float(blended["papg"]),
        "recent6_pf_pg": float(blended["recent6_pf_pg"]),
        "recent6_pa_pg": float(blended["recent6_pa_pg"]),
        "sources": {
            "prior": prior_source,
            "current": current_source,
        },
        "identity_policy": {
            "exact_official_team_id": True,
            "fuzzy_matching": False,
            "synthetic_team_ids": False,
        },
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        "sportsbook_inputs": list(SPORTSBOOK_INPUTS),
        "projection_generated": False,
    }


__all__ = [
    "MIN_PRIOR_GAMES",
    "NFLGameTotalsTeamProfileError",
    "PRIOR_GAMES_WEIGHT",
    "SCHEMA_VERSION",
    "SPORTSBOOK_INPUTS",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "blend_scoring_profiles",
    "collect_team_scoring_profile",
    "fetch_espn_team_schedule_hosted",
    "parse_completed_regular_schedule",
    "summarize_completed_games",
]
