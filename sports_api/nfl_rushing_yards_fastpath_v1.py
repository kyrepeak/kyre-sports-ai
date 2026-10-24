"""Bounded NFL Rushing Yards request-time data path.

The canonical slate builder remains authoritative. This module replaces only its
expensive request-time transport helpers:

* weekly player summary stats replace full play-by-play downloads for workload,
  defense and matchup-history aggregation;
* current stats, current roster and prior-season summaries prewarm concurrently;
* historical enrichment is best-effort behind a small total budget;
* direct-book market collection is best-effort behind a hard slate-wide budget.

No numeric value is invented. If enrichment misses its budget, the existing
canonical builder emits its semantic empty states instead of blocking Page 1.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait
from functools import lru_cache
from io import BytesIO
import math
from typing import Any, Mapping

import pandas as pd
import requests

from sports_api.collectors import nfl_fanduel_rushing_yards_nflverse_v1 as direct_book
from sports_api.nfl_data_nflverse_v1 import canonical_team_abbr

PLAYER_STATS_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "stats_player/stats_player_week_{season}.csv"
)
WEEKLY_ROSTER_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "weekly_rosters/roster_weekly_{season}.csv"
)
PLAYER_STATS_TIMEOUT_SECONDS = 6
ROSTER_TIMEOUT_SECONDS = 6
PREFETCH_BUDGET_SECONDS = 6.5
MARKET_CALL_TIMEOUT_SECONDS = 2
MARKET_BUDGET_SECONDS = 4.0
HISTORY_BUDGET_SECONDS = 3.0

_PLAYER_STATS_COLUMNS = {
    "season",
    "week",
    "season_type",
    "game_id",
    "game_date",
    "player_id",
    "gsis_id",
    "player_name",
    "player_display_name",
    "position",
    "team",
    "opponent_team",
    "carries",
    "rushing_attempts",
    "rushing_yards",
    "rushing_tds",
    "rushing_touchdowns",
}


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _number(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _first(row: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value is not None and _text(value):
            return value
    return None


@lru_cache(maxsize=8)
def load_player_stats(season: int) -> pd.DataFrame:
    """Load compact weekly player summaries instead of full season PBP."""
    response = requests.get(
        PLAYER_STATS_URL.format(season=int(season)),
        timeout=PLAYER_STATS_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return pd.read_csv(
        BytesIO(response.content),
        usecols=lambda name: name in _PLAYER_STATS_COLUMNS,
        low_memory=False,
    )


@lru_cache(maxsize=4)
def load_weekly_roster(season: int) -> pd.DataFrame:
    """Load the verified weekly roster with the same bounded request policy."""
    response = requests.get(
        WEEKLY_ROSTER_URL.format(season=int(season)),
        timeout=ROSTER_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return pd.read_csv(BytesIO(response.content), low_memory=False)


def prewarm_season_inputs(
    season: int,
    *,
    budget_seconds: float = PREFETCH_BUDGET_SECONDS,
) -> dict[str, bool]:
    """Warm independent season inputs concurrently before the canonical build."""
    season = int(season)
    labels = {
        "current_stats": (load_player_stats, season),
        "current_roster": (load_weekly_roster, season),
        f"history_{season - 1}": (load_player_stats, season - 1),
        f"history_{season - 2}": (load_player_stats, season - 2),
    }
    state = {label: False for label in labels}
    pool = ThreadPoolExecutor(max_workers=len(labels))
    futures = {
        pool.submit(func, value): label
        for label, (func, value) in labels.items()
    }
    done, pending = wait(futures, timeout=max(0.0, float(budget_seconds)))
    for future in done:
        label = futures[future]
        try:
            future.result()
            state[label] = True
        except Exception:
            state[label] = False
    for future in pending:
        future.cancel()
    pool.shutdown(wait=False, cancel_futures=True)
    return state


def prewarm_request_inputs(
    legacy: Any,
    *,
    target_date: str | None = None,
    now_et: Any = None,
    budget_seconds: float = PREFETCH_BUDGET_SECONDS,
) -> dict[str, bool]:
    """Resolve the upcoming season and prewarm only the inputs that build needs."""
    try:
        games_frame = legacy._load_games_csv()
        games = legacy.select_upcoming_week(games_frame, now_et=now_et)
        if target_date:
            games = [game for game in games if game.get("game_date") == str(target_date)[:10]]
        if not games:
            return {}
        season = int(games[0]["season"])
    except Exception:
        return {}
    return prewarm_season_inputs(season, budget_seconds=budget_seconds)


def completed_rush_rows(frame: pd.DataFrame, cutoff_day: str) -> pd.DataFrame:
    """Return completed regular-season player-game rushing summaries."""
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return pd.DataFrame()
    rows = frame.copy()
    if "season_type" in rows.columns:
        rows = rows[rows["season_type"].astype(str).str.upper().eq("REG")]
    if "game_date" in rows.columns:
        rows = rows[rows["game_date"].astype(str).str[:10] < str(cutoff_day)[:10]]
    carries_key = "carries" if "carries" in rows.columns else "rushing_attempts" if "rushing_attempts" in rows.columns else None
    if carries_key is None or "rushing_yards" not in rows.columns:
        return pd.DataFrame()
    carries = pd.to_numeric(rows[carries_key], errors="coerce")
    yards = pd.to_numeric(rows["rushing_yards"], errors="coerce")
    return rows[carries.gt(0) & yards.notna()].copy()


def player_game_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Normalize one weekly-stat row into the canonical player-game shape."""
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return []
    out: list[dict[str, Any]] = []
    for raw in frame.to_dict(orient="records"):
        source_id = _text(_first(raw, "player_id", "gsis_id"))
        name = _text(_first(raw, "player_display_name", "player_name"))
        team = canonical_team_abbr(raw.get("team"))
        opponent = canonical_team_abbr(raw.get("opponent_team"))
        attempts = _number(_first(raw, "carries", "rushing_attempts"))
        yards = _number(raw.get("rushing_yards"))
        touchdowns = _number(_first(raw, "rushing_tds", "rushing_touchdowns")) or 0.0
        week_num = int(_number(raw.get("week")) or 0)
        season_num = int(_number(raw.get("season")) or 0)
        if not source_id or not name or not team or not opponent or attempts is None or attempts <= 0 or yards is None:
            continue
        source_game_id = _text(raw.get("game_id")) or f"{season_num}_{week_num:02d}_{team}_{opponent}"
        out.append({
            "source_game_id": source_game_id,
            "game_date": _text(raw.get("game_date"))[:10],
            "week": week_num,
            "team_abbr": team,
            "opponent_abbr": opponent,
            "player_source_id": source_id,
            "player_name": name,
            "attempts": int(attempts) if float(attempts).is_integer() else float(attempts),
            "rushing_yards": float(yards),
            "rushing_touchdowns": int(touchdowns),
        })
    out.sort(key=lambda row: (row.get("game_date") or "", int(row.get("week") or 0), row.get("source_game_id") or ""))
    return out


def _load_history_season(season: int) -> list[dict[str, Any]]:
    return player_game_rows(completed_rush_rows(load_player_stats(season), "9999-12-31"))


def history_rows(
    season: int,
    cutoff_day: str,
    current_rows: list[dict[str, Any]],
    *,
    budget_seconds: float = HISTORY_BUDGET_SECONDS,
) -> tuple[list[dict[str, Any]], bool]:
    """Best-effort two-season matchup history without blocking the live slate."""
    rows = list(current_rows)
    prior_seasons = [int(season) - 2, int(season) - 1]
    pool = ThreadPoolExecutor(max_workers=len(prior_seasons))
    futures = {pool.submit(_load_history_season, prior): prior for prior in prior_seasons}
    done, pending = wait(futures, timeout=max(0.0, float(budget_seconds)))
    complete = not pending
    for future in done:
        try:
            rows.extend(list(future.result() or []))
        except Exception:
            complete = False
    for future in pending:
        future.cancel()
    pool.shutdown(wait=False, cancel_futures=True)
    return rows, complete


def collect_markets(
    games: list[dict[str, Any]],
    *,
    budget_seconds: float = MARKET_BUDGET_SECONDS,
    call_timeout_seconds: int = MARKET_CALL_TIMEOUT_SECONDS,
) -> dict[str, list[dict[str, Any]]]:
    """Collect direct-book markets without allowing the provider to block Page 1."""
    results: dict[str, list[dict[str, Any]]] = {
        str(game.get("source_game_id")): [] for game in games or [] if game.get("source_game_id")
    }
    if not games:
        return results
    pool = ThreadPoolExecutor(max_workers=min(12, max(1, len(games))))
    futures = {
        pool.submit(
            direct_book.collect_fanduel_game_markets,
            game,
            timeout=int(call_timeout_seconds),
        ): str(game.get("source_game_id"))
        for game in games
        if game.get("source_game_id")
    }
    done, pending = wait(futures, timeout=max(0.0, float(budget_seconds)))
    for future in done:
        game_id = futures[future]
        try:
            results[game_id] = list(future.result() or [])
        except Exception:
            results[game_id] = []
    for future in pending:
        future.cancel()
    pool.shutdown(wait=False, cancel_futures=True)
    return results


def install(legacy: Any) -> Any:
    """Install the bounded transport helpers into the canonical legacy builder."""
    legacy._load_pbp = load_player_stats
    legacy._load_weekly_roster = load_weekly_roster
    legacy._completed_rush_rows = completed_rush_rows
    legacy._player_game_rows = player_game_rows
    legacy._history_rows = history_rows
    legacy._collect_markets = collect_markets
    return legacy


__all__ = [
    "HISTORY_BUDGET_SECONDS",
    "MARKET_BUDGET_SECONDS",
    "MARKET_CALL_TIMEOUT_SECONDS",
    "PLAYER_STATS_TIMEOUT_SECONDS",
    "PLAYER_STATS_URL",
    "PREFETCH_BUDGET_SECONDS",
    "ROSTER_TIMEOUT_SECONDS",
    "WEEKLY_ROSTER_URL",
    "collect_markets",
    "completed_rush_rows",
    "history_rows",
    "install",
    "load_player_stats",
    "load_weekly_roster",
    "player_game_rows",
    "prewarm_request_inputs",
    "prewarm_season_inputs",
]
