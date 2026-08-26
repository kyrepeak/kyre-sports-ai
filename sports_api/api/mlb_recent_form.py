from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query

from sports_api.api.mlb_game_logs import (
    HITTING_LOG_FIELDS,
    PITCHING_LOG_FIELDS,
    _fetch_game_log_splits,
    _latest_first,
    _normalize_game_log,
)

router = APIRouter(prefix="/api/v1/mlb", tags=["mlb-recent-form"])

ARIZONA_TZ = ZoneInfo("America/Phoenix")
WINDOWS = (5, 10, 20)


def _number(value, default=0.0):
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _round(value, digits=3):
    return round(value, digits)


def _rate(count: int, games: int):
    if games <= 0:
        return None
    return _round(count / games, 4)


def _avg(total: float, games: int):
    if games <= 0:
        return None
    return _round(total / games, 3)


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
    except ValueError:
        return 0

    try:
        fraction = int(fraction_text[:1] or "0")
    except ValueError:
        fraction = 0

    if fraction not in (0, 1, 2):
        fraction = 0

    return (whole * 3) + fraction


def _outs_to_ip(outs: int):
    whole, remainder = divmod(max(outs, 0), 3)
    return f"{whole}.{remainder}"


def _hitting_window(logs, requested_window: int):
    sample = logs[:requested_window]
    games = len(sample)

    if games == 0:
        return {
            "requested_window": requested_window,
            "games_available": 0,
            "complete_window": False,
            "metrics": None,
        }

    hits = [_number(game["stats"].get("hits")) for game in sample]
    home_runs = [_number(game["stats"].get("homeRuns")) for game in sample]
    strikeouts = [_number(game["stats"].get("strikeOuts")) for game in sample]

    totals = {
        "plate_appearances": sum(_number(game["stats"].get("plateAppearances")) for game in sample),
        "at_bats": sum(_number(game["stats"].get("atBats")) for game in sample),
        "hits": sum(hits),
        "runs": sum(_number(game["stats"].get("runs")) for game in sample),
        "home_runs": sum(home_runs),
        "rbi": sum(_number(game["stats"].get("rbi")) for game in sample),
        "walks": sum(_number(game["stats"].get("baseOnBalls")) for game in sample),
        "strikeouts": sum(strikeouts),
        "total_bases": sum(_number(game["stats"].get("totalBases")) for game in sample),
    }

    hit_1plus = sum(1 for value in hits if value >= 1)
    hit_2plus = sum(1 for value in hits if value >= 2)
    hit_3plus = sum(1 for value in hits if value >= 3)
    hr_1plus = sum(1 for value in home_runs if value >= 1)
    strikeout_1plus = sum(1 for value in strikeouts if value >= 1)

    return {
        "requested_window": requested_window,
        "games_available": games,
        "complete_window": games >= requested_window,
        "date_range": {
            "most_recent": sample[0].get("date"),
            "oldest": sample[-1].get("date"),
        },
        "metrics": {
            "totals": {key: _round(value, 3) for key, value in totals.items()},
            "per_game": {
                "plate_appearances": _avg(totals["plate_appearances"], games),
                "at_bats": _avg(totals["at_bats"], games),
                "hits": _avg(totals["hits"], games),
                "runs": _avg(totals["runs"], games),
                "home_runs": _avg(totals["home_runs"], games),
                "rbi": _avg(totals["rbi"], games),
                "walks": _avg(totals["walks"], games),
                "strikeouts": _avg(totals["strikeouts"], games),
                "total_bases": _avg(totals["total_bases"], games),
            },
            "event_rates": {
                "hit_1plus_games": hit_1plus,
                "hit_1plus_rate": _rate(hit_1plus, games),
                "hit_2plus_games": hit_2plus,
                "hit_2plus_rate": _rate(hit_2plus, games),
                "hit_3plus_games": hit_3plus,
                "hit_3plus_rate": _rate(hit_3plus, games),
                "home_run_1plus_games": hr_1plus,
                "home_run_1plus_rate": _rate(hr_1plus, games),
                "strikeout_1plus_games": strikeout_1plus,
                "strikeout_1plus_rate": _rate(strikeout_1plus, games),
            },
        },
    }


def _pitching_window(logs, requested_window: int):
    sample = logs[:requested_window]
    games = len(sample)

    if games == 0:
        return {
            "requested_window": requested_window,
            "games_available": 0,
            "complete_window": False,
            "metrics": None,
        }

    strikeouts = [_number(game["stats"].get("strikeOuts")) for game in sample]
    outs = sum(_ip_to_outs(game["stats"].get("inningsPitched")) for game in sample)

    totals = {
        "batters_faced": sum(_number(game["stats"].get("battersFaced")) for game in sample),
        "strikeouts": sum(strikeouts),
        "walks": sum(_number(game["stats"].get("baseOnBalls")) for game in sample),
        "hits_allowed": sum(_number(game["stats"].get("hits")) for game in sample),
        "earned_runs": sum(_number(game["stats"].get("earnedRuns")) for game in sample),
        "home_runs_allowed": sum(_number(game["stats"].get("homeRuns")) for game in sample),
        "pitches": sum(_number(game["stats"].get("numberOfPitches")) for game in sample),
        "strikes": sum(_number(game["stats"].get("strikes")) for game in sample),
    }

    starts = sum(1 for game in sample if _number(game["stats"].get("gamesStarted")) >= 1)

    threshold_rates = {}
    for threshold in (4, 5, 6, 7, 8, 9, 10):
        count = sum(1 for value in strikeouts if value >= threshold)
        threshold_rates[f"strikeouts_{threshold}plus_games"] = count
        threshold_rates[f"strikeouts_{threshold}plus_rate"] = _rate(count, games)

    return {
        "requested_window": requested_window,
        "games_available": games,
        "complete_window": games >= requested_window,
        "date_range": {
            "most_recent": sample[0].get("date"),
            "oldest": sample[-1].get("date"),
        },
        "metrics": {
            "starts": starts,
            "total_innings_pitched": _outs_to_ip(outs),
            "total_outs_recorded": outs,
            "averages": {
                "innings_pitched_decimal": _avg(outs / 3, games),
                "batters_faced": _avg(totals["batters_faced"], games),
                "strikeouts": _avg(totals["strikeouts"], games),
                "walks": _avg(totals["walks"], games),
                "hits_allowed": _avg(totals["hits_allowed"], games),
                "earned_runs": _avg(totals["earned_runs"], games),
                "home_runs_allowed": _avg(totals["home_runs_allowed"], games),
                "pitches": _avg(totals["pitches"], games),
                "strikes": _avg(totals["strikes"], games),
            },
            "totals": {key: _round(value, 3) for key, value in totals.items()},
            "strikeout_thresholds": threshold_rates,
        },
    }


@router.get("/players/{player_id}/recent-form")
def get_mlb_player_recent_form(
    player_id: int,
    season: int | None = Query(
        default=None,
        ge=1876,
        le=2100,
        description="MLB season year. Defaults to the current Arizona calendar year.",
    ),
):
    target_season = season or datetime.now(ARIZONA_TZ).year

    hitting_splits = _fetch_game_log_splits(player_id, target_season, "hitting")
    pitching_splits = _fetch_game_log_splits(player_id, target_season, "pitching")

    hitting_logs = [
        _normalize_game_log(split, HITTING_LOG_FIELDS)
        for split in hitting_splits
    ]
    pitching_logs = [
        _normalize_game_log(split, PITCHING_LOG_FIELDS)
        for split in pitching_splits
    ]

    hitting_logs.sort(key=_latest_first, reverse=True)
    pitching_logs.sort(key=_latest_first, reverse=True)

    player_name = None
    if hitting_logs:
        player_name = hitting_logs[0].get("player_name")
    elif pitching_logs:
        player_name = pitching_logs[0].get("player_name")

    return {
        "source": "MLB Stats API",
        "calculated_by": "Kyre Sports API",
        "player_id": player_id,
        "player_name": player_name,
        "season": target_season,
        "windows": list(WINDOWS),
        "hitting_games_available": len(hitting_logs),
        "pitching_games_available": len(pitching_logs),
        "hitting": {
            f"last_{window}": _hitting_window(hitting_logs, window)
            for window in WINDOWS
        },
        "pitching": {
            f"last_{window}": _pitching_window(pitching_logs, window)
            for window in WINDOWS
        },
    }
