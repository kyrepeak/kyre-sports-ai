from collections import defaultdict
from datetime import date as date_type
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/v1/mlb", tags=["mlb-bullpen"])

MLB_SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"
MLB_LIVE_FEED_URL = "https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
ARIZONA_TZ = ZoneInfo("America/Phoenix")

FINAL_STATES = {"Final", "Game Over", "Completed Early"}


def _to_number(value, default=0.0):
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _ip_to_outs(value):
    if value is None or value == "":
        return 0

    text = str(value)
    if "." in text:
        whole_text, fraction_text = text.split(".", 1)
    else:
        whole_text, fraction_text = text, "0"

    try:
        whole = int(whole_text)
        fraction = int(fraction_text[:1] or "0")
    except (TypeError, ValueError):
        return 0

    if fraction not in (0, 1, 2):
        fraction = 0

    return (whole * 3) + fraction


def _outs_to_ip(outs: int):
    whole, remainder = divmod(max(int(outs), 0), 3)
    return f"{whole}.{remainder}"


def _parse_date(value: str):
    return datetime.strptime(value, "%Y-%m-%d").date()


def _fetch_recent_schedule(team_id: int, start_date: date_type, end_date: date_type):
    params = {
        "sportId": 1,
        "teamId": team_id,
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "gameTypes": "R",
    }

    try:
        response = httpx.get(MLB_SCHEDULE_URL, params=params, timeout=20.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"MLB upstream schedule request failed: {exc}",
        ) from exc

    payload = response.json()
    games = []
    for date_block in payload.get("dates", []):
        games.extend(date_block.get("games", []))

    return games


def _is_completed_game(game):
    status = game.get("status", {})
    return (
        status.get("abstractGameState") == "Final"
        or status.get("detailedState") in FINAL_STATES
    )


def _fetch_live_feed(game_pk: int):
    url = MLB_LIVE_FEED_URL.format(game_pk=game_pk)

    try:
        response = httpx.get(url, timeout=15.0)
        if response.status_code == 404:
            return None
        response.raise_for_status()
    except httpx.HTTPError:
        return None

    return response.json()


def _team_side(payload, team_id: int):
    teams = payload.get("gameData", {}).get("teams", {})

    if teams.get("away", {}).get("id") == team_id:
        return "away"
    if teams.get("home", {}).get("id") == team_id:
        return "home"
    return None


def _relief_appearances_from_game(payload, team_id: int, game_date: str, game_pk: int):
    side = _team_side(payload, team_id)
    if side is None:
        return []

    team_box = payload.get("liveData", {}).get("boxscore", {}).get("teams", {}).get(side, {})
    pitcher_ids = team_box.get("pitchers", [])
    players = team_box.get("players", {})

    if len(pitcher_ids) <= 1:
        return []

    appearances = []
    for pitcher_id in pitcher_ids[1:]:
        player = players.get(f"ID{pitcher_id}", {})
        person = player.get("person", {})
        pitching = player.get("stats", {}).get("pitching", {})

        appearances.append(
            {
                "game_pk": game_pk,
                "date": game_date,
                "player_id": person.get("id") or pitcher_id,
                "player_name": person.get("fullName"),
                "innings_pitched": pitching.get("inningsPitched"),
                "outs_recorded": _ip_to_outs(pitching.get("inningsPitched")),
                "pitches": int(_to_number(pitching.get("numberOfPitches"))),
                "strikes": int(_to_number(pitching.get("strikes"))),
                "batters_faced": int(_to_number(pitching.get("battersFaced"))),
                "hits_allowed": int(_to_number(pitching.get("hits"))),
                "earned_runs": int(_to_number(pitching.get("earnedRuns"))),
                "walks": int(_to_number(pitching.get("baseOnBalls"))),
                "strikeouts": int(_to_number(pitching.get("strikeOuts"))),
                "home_runs_allowed": int(_to_number(pitching.get("homeRuns"))),
            }
        )

    return appearances


def _window_sum(appearances, target_date: date_type, days: int, field: str):
    start = target_date - timedelta(days=days)
    return sum(
        appearance.get(field) or 0
        for appearance in appearances
        if start <= _parse_date(appearance["date"]) < target_date
    )


def _window_count(appearances, target_date: date_type, days: int):
    start = target_date - timedelta(days=days)
    return sum(
        1
        for appearance in appearances
        if start <= _parse_date(appearance["date"]) < target_date
    )


def _fatigue_level(appearances, target_date: date_type):
    yesterday = target_date - timedelta(days=1)
    two_days_ago = target_date - timedelta(days=2)

    dates_used = {_parse_date(appearance["date"]) for appearance in appearances}
    used_yesterday = yesterday in dates_used
    used_two_days_ago = two_days_ago in dates_used

    pitches_1d = _window_sum(appearances, target_date, 1, "pitches")
    pitches_3d = _window_sum(appearances, target_date, 3, "pitches")
    appearances_3d = _window_count(appearances, target_date, 3)

    if (
        pitches_1d >= 30
        or (used_yesterday and used_two_days_ago)
        or pitches_3d >= 50
        or appearances_3d >= 3
    ):
        return "high"

    if used_yesterday or pitches_3d >= 30 or appearances_3d >= 2:
        return "moderate"

    return "low"


def _summarize_pitcher(player_id: int, appearances, target_date: date_type):
    appearances = sorted(
        appearances,
        key=lambda appearance: (appearance.get("date") or "", appearance.get("game_pk") or 0),
        reverse=True,
    )

    latest = appearances[0] if appearances else None
    latest_date = _parse_date(latest["date"]) if latest else None

    dates_used = {_parse_date(appearance["date"]) for appearance in appearances}
    yesterday = target_date - timedelta(days=1)
    two_days_ago = target_date - timedelta(days=2)

    total_outs = sum(appearance.get("outs_recorded") or 0 for appearance in appearances)

    return {
        "player_id": player_id,
        "player_name": latest.get("player_name") if latest else None,
        "fatigue_level": _fatigue_level(appearances, target_date),
        "days_since_last_appearance": (
            (target_date - latest_date).days if latest_date is not None else None
        ),
        "used_yesterday": yesterday in dates_used,
        "used_two_days_ago": two_days_ago in dates_used,
        "used_on_back_to_back_previous_days": (
            yesterday in dates_used and two_days_ago in dates_used
        ),
        "last_1_day": {
            "appearances": _window_count(appearances, target_date, 1),
            "pitches": _window_sum(appearances, target_date, 1, "pitches"),
            "outs_recorded": _window_sum(appearances, target_date, 1, "outs_recorded"),
        },
        "last_3_days": {
            "appearances": _window_count(appearances, target_date, 3),
            "pitches": _window_sum(appearances, target_date, 3, "pitches"),
            "outs_recorded": _window_sum(appearances, target_date, 3, "outs_recorded"),
        },
        "last_7_days": {
            "appearances": _window_count(appearances, target_date, 7),
            "pitches": _window_sum(appearances, target_date, 7, "pitches"),
            "outs_recorded": _window_sum(appearances, target_date, 7, "outs_recorded"),
        },
        "lookback_totals": {
            "appearances": len(appearances),
            "pitches": sum(appearance.get("pitches") or 0 for appearance in appearances),
            "outs_recorded": total_outs,
            "innings_pitched": _outs_to_ip(total_outs),
            "batters_faced": sum(appearance.get("batters_faced") or 0 for appearance in appearances),
            "hits_allowed": sum(appearance.get("hits_allowed") or 0 for appearance in appearances),
            "earned_runs": sum(appearance.get("earned_runs") or 0 for appearance in appearances),
            "walks": sum(appearance.get("walks") or 0 for appearance in appearances),
            "strikeouts": sum(appearance.get("strikeouts") or 0 for appearance in appearances),
            "home_runs_allowed": sum(appearance.get("home_runs_allowed") or 0 for appearance in appearances),
        },
        "appearances": appearances,
    }


def _team_fatigue_summary(relievers):
    high = sum(1 for reliever in relievers if reliever.get("fatigue_level") == "high")
    moderate = sum(1 for reliever in relievers if reliever.get("fatigue_level") == "moderate")
    low = sum(1 for reliever in relievers if reliever.get("fatigue_level") == "low")

    team_pitches_1d = sum(reliever["last_1_day"]["pitches"] for reliever in relievers)
    team_pitches_3d = sum(reliever["last_3_days"]["pitches"] for reliever in relievers)
    team_appearances_3d = sum(reliever["last_3_days"]["appearances"] for reliever in relievers)

    if high >= 2 or team_pitches_3d >= 120:
        level = "strained"
    elif high >= 1 or moderate >= 2 or team_pitches_3d >= 80:
        level = "watch"
    else:
        level = "fresh"

    return {
        "bullpen_fatigue_level": level,
        "high_fatigue_relievers": high,
        "moderate_fatigue_relievers": moderate,
        "low_fatigue_relievers": low,
        "team_pitches_last_1_day": team_pitches_1d,
        "team_pitches_last_3_days": team_pitches_3d,
        "team_reliever_appearances_last_3_days": team_appearances_3d,
    }


@router.get("/teams/{team_id}/bullpen")
def get_mlb_bullpen_usage(
    team_id: int,
    date: str | None = Query(
        default=None,
        description="Analysis date in YYYY-MM-DD format. Defaults to today's Arizona date.",
    ),
    lookback_days: int = Query(
        default=7,
        ge=3,
        le=14,
        description="Number of calendar days of completed games to inspect.",
    ),
):
    target_text = date or datetime.now(ARIZONA_TZ).date().isoformat()

    try:
        target_date = _parse_date(target_text)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="date must use YYYY-MM-DD format.",
        ) from exc

    start_date = target_date - timedelta(days=lookback_days)
    schedule = _fetch_recent_schedule(team_id, start_date, target_date)

    completed_games = [game for game in schedule if _is_completed_game(game)]
    completed_games.sort(
        key=lambda game: (
            game.get("officialDate") or "",
            game.get("gameDate") or "",
            game.get("gameNumber") or 0,
        ),
        reverse=True,
    )

    by_pitcher = defaultdict(list)
    skipped_game_pks = []
    processed_game_pks = []
    team_name = None

    for game in completed_games:
        game_pk = game.get("gamePk")
        game_date = game.get("officialDate")

        if not isinstance(game_pk, int) or not game_date:
            continue

        payload = _fetch_live_feed(game_pk)
        if payload is None:
            skipped_game_pks.append(game_pk)
            continue

        side = _team_side(payload, team_id)
        if side is None:
            skipped_game_pks.append(game_pk)
            continue

        if team_name is None:
            team_name = payload.get("gameData", {}).get("teams", {}).get(side, {}).get("name")

        appearances = _relief_appearances_from_game(payload, team_id, game_date, game_pk)
        for appearance in appearances:
            player_id = appearance.get("player_id")
            if isinstance(player_id, int):
                by_pitcher[player_id].append(appearance)

        processed_game_pks.append(game_pk)

    relievers = [
        _summarize_pitcher(player_id, appearances, target_date)
        for player_id, appearances in by_pitcher.items()
    ]
    relievers.sort(
        key=lambda reliever: (
            {"high": 2, "moderate": 1, "low": 0}.get(reliever.get("fatigue_level"), 0),
            reliever.get("last_3_days", {}).get("pitches", 0),
            reliever.get("last_1_day", {}).get("pitches", 0),
        ),
        reverse=True,
    )

    return {
        "source": "MLB Stats API",
        "calculated_by": "Kyre Sports API",
        "fatigue_method": "workload heuristic v0.1",
        "fatigue_disclaimer": (
            "Fatigue labels are workload signals for modeling, not medical assessments."
        ),
        "team_id": team_id,
        "team_name": team_name,
        "analysis_date": target_date.isoformat(),
        "lookback_days": lookback_days,
        "lookback_start_date": start_date.isoformat(),
        "completed_games_found": len(completed_games),
        "games_processed": len(processed_game_pks),
        "processed_game_pks": processed_game_pks,
        "skipped_game_pks": skipped_game_pks,
        "relievers_found": len(relievers),
        "team_summary": _team_fatigue_summary(relievers),
        "relievers": relievers,
    }
