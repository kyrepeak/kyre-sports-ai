"""Free/open nflverse adapter for NFL Game Totals canonical football metrics.

This module owns transport and deterministic derivation only. It never consumes
sportsbook data and never performs projection math. Provider-specific rows are
normalized into the canonical metric shapes accepted by nfl_data_router_v1.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from functools import lru_cache
from io import BytesIO
import math
from typing import Any

import pandas as pd
import requests

NFLVERSE_GAMES_CSV = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
NFLVERSE_PBP_CSV = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.csv.gz"
REQUEST_TIMEOUT_SECONDS = 12
PROVIDER = "nflverse"

_TEAM_ALIASES = {
    "JAC": "JAX",
    "JAX": "JAX",
    "STL": "LAR",
    "LA": "LAR",
    "LAR": "LAR",
    "OAK": "LV",
    "LVR": "LV",
    "LV": "LV",
    "WSH": "WAS",
    "WFT": "WAS",
    "WAS": "WAS",
    "SD": "LAC",
    "SDG": "LAC",
    "LAC": "LAC",
}

_PBP_COLUMNS = (
    "game_id",
    "season",
    "season_type",
    "posteam",
    "defteam",
    "drive",
    "qtr",
    "game_seconds_remaining",
    "play_type",
    "rush_attempt",
    "pass_attempt",
    "sack",
    "yards_gained",
    "complete_pass",
    "no_play",
    "yardline_100",
    "touchdown",
    "down",
    "third_down_converted",
    "third_down_failed",
    "first_down",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_team_abbr(value: Any) -> str:
    text = str(value if value is not None else "").strip().upper()
    return _TEAM_ALIASES.get(text, text)


def _num(value: Any) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else math.nan
    except (TypeError, ValueError):
        return math.nan


def _flag(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce").fillna(0.0)
    return numeric.eq(1.0)


def _column(frame: pd.DataFrame, name: str, default: Any = 0.0) -> pd.Series:
    if name in frame.columns:
        return frame[name]
    return pd.Series(default, index=frame.index)


def _regular_team_rows(frame: pd.DataFrame, team_abbr: str) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return pd.DataFrame()
    required = {"game_id", "posteam"}
    if not required.issubset(frame.columns):
        return pd.DataFrame()

    team = canonical_team_abbr(team_abbr)
    rows = frame.copy()
    if "season_type" in rows.columns:
        rows = rows[rows["season_type"].astype(str).str.upper().eq("REG")]
    canonical_posteam = rows["posteam"].map(canonical_team_abbr)
    rows = rows[canonical_posteam.eq(team)]
    return rows.copy()


def _valid_offensive_rows(frame: pd.DataFrame, team_abbr: str) -> pd.DataFrame:
    rows = _regular_team_rows(frame, team_abbr)
    if rows.empty:
        return rows

    no_play = _flag(_column(rows, "no_play"))
    rush = _flag(_column(rows, "rush_attempt"))
    pass_attempt = _flag(_column(rows, "pass_attempt"))
    sack = _flag(_column(rows, "sack"))
    valid = (~no_play) & (rush | pass_attempt | sack)
    return rows[valid].copy()


def _game_count(rows: pd.DataFrame) -> int:
    if rows.empty or "game_id" not in rows.columns:
        return 0
    return int(rows["game_id"].dropna().astype(str).nunique())


def extract_scoring_games(
    frame: pd.DataFrame,
    team_abbr: str,
    season: int,
    cutoff_day: str,
) -> list[dict[str, Any]]:
    """Return completed regular-season scoring rows through an exact cutoff day."""
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return []
    required = {
        "season",
        "game_type",
        "gameday",
        "away_team",
        "home_team",
        "away_score",
        "home_score",
    }
    if not required.issubset(frame.columns):
        return []

    try:
        cutoff = date.fromisoformat(str(cutoff_day)[:10])
        requested_season = int(season)
    except (TypeError, ValueError):
        return []

    team = canonical_team_abbr(team_abbr)
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for _, record in frame.iterrows():
        try:
            row_season = int(record.get("season"))
        except (TypeError, ValueError):
            continue
        if row_season != requested_season:
            continue
        if str(record.get("game_type") or "").upper() != "REG":
            continue

        try:
            game_day = date.fromisoformat(str(record.get("gameday") or "")[:10])
        except ValueError:
            continue
        if game_day > cutoff:
            continue

        away = canonical_team_abbr(record.get("away_team"))
        home = canonical_team_abbr(record.get("home_team"))
        if team not in {away, home}:
            continue

        away_score = _num(record.get("away_score"))
        home_score = _num(record.get("home_score"))
        if not math.isfinite(away_score) or not math.isfinite(home_score):
            continue

        if team == away:
            pf, pa, opponent = away_score, home_score, home
        else:
            pf, pa, opponent = home_score, away_score, away

        key = (game_day.isoformat(), opponent)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "date": game_day.isoformat(),
                "pf": float(pf),
                "pa": float(pa),
                "opponent_abbr": opponent,
            }
        )

    rows.sort(key=lambda item: item["date"])
    return rows


def derive_pace_metrics(frame: pd.DataFrame, team_abbr: str) -> dict[str, Any]:
    """Derive valid offensive plays/game and elapsed unique-drive possession/game."""
    team_rows = _regular_team_rows(frame, team_abbr)
    valid_rows = _valid_offensive_rows(frame, team_abbr)
    games = _game_count(valid_rows)
    if games <= 0:
        return {
            "ready": False,
            "games_played": 0,
            "plays_per_game": math.nan,
            "possession_seconds_per_game": math.nan,
        }

    plays_per_game = float(len(valid_rows) / games)
    possession_total = 0.0
    timed_games: set[str] = set()

    if {"game_id", "drive", "game_seconds_remaining"}.issubset(team_rows.columns):
        grouped = team_rows.dropna(subset=["game_id", "drive"]).groupby(["game_id", "drive"], dropna=True)
        for (game_id, _drive), drive_rows in grouped:
            clocks = pd.to_numeric(drive_rows["game_seconds_remaining"], errors="coerce").dropna()
            if clocks.empty:
                continue
            elapsed = float(clocks.max() - clocks.min())
            if math.isfinite(elapsed) and elapsed >= 0.0:
                possession_total += elapsed
                timed_games.add(str(game_id))

    if len(timed_games) != games:
        return {
            "ready": False,
            "games_played": games,
            "plays_per_game": plays_per_game,
            "possession_seconds_per_game": math.nan,
        }

    return {
        "ready": True,
        "games_played": games,
        "plays_per_game": plays_per_game,
        "possession_seconds_per_game": float(possession_total / games),
    }


def derive_explosive_metrics(frame: pd.DataFrame, team_abbr: str) -> dict[str, Any]:
    """Derive canonical 20+ yard rush/completed-pass explosive plays."""
    rows = _valid_offensive_rows(frame, team_abbr)
    games = _game_count(rows)
    if games <= 0:
        return {
            "ready": False,
            "games_played": 0,
            "rushing_big_plays": math.nan,
            "receiving_big_plays": math.nan,
            "total_big_plays": math.nan,
            "rushing_big_plays_per_game": math.nan,
            "receiving_big_plays_per_game": math.nan,
            "explosive_plays_per_game": math.nan,
        }

    yards = pd.to_numeric(_column(rows, "yards_gained"), errors="coerce")
    big = yards.ge(20.0)
    rush = _flag(_column(rows, "rush_attempt")) & big
    receiving = _flag(_column(rows, "complete_pass")) & big
    rushing_big = float(rush.sum())
    receiving_big = float(receiving.sum())
    total_big = rushing_big + receiving_big

    return {
        "ready": True,
        "games_played": games,
        "rushing_big_plays": rushing_big,
        "receiving_big_plays": receiving_big,
        "total_big_plays": total_big,
        "rushing_big_plays_per_game": float(rushing_big / games),
        "receiving_big_plays_per_game": float(receiving_big / games),
        "explosive_plays_per_game": float(total_big / games),
    }


def derive_red_zone_drive_metrics(frame: pd.DataFrame, team_abbr: str) -> dict[str, Any]:
    """Derive unique-drive red-zone TD%, third-down%, first downs, and drives/game."""
    rows = _valid_offensive_rows(frame, team_abbr)
    games = _game_count(rows)
    if games <= 0:
        return {
            "ready": False,
            "games_played": 0,
            "red_zone_td_pct": math.nan,
            "third_down_conv_pct": math.nan,
            "first_downs_per_game": math.nan,
            "drives_per_game": math.nan,
        }

    required = {"game_id", "drive"}
    if not required.issubset(rows.columns):
        return {
            "ready": False,
            "games_played": games,
            "red_zone_td_pct": math.nan,
            "third_down_conv_pct": math.nan,
            "first_downs_per_game": math.nan,
            "drives_per_game": math.nan,
        }

    drive_rows = rows.dropna(subset=["game_id", "drive"])
    drives = int(drive_rows[["game_id", "drive"]].drop_duplicates().shape[0])

    red_zone_drives = 0
    red_zone_td_drives = 0
    for (_game_id, _drive), group in drive_rows.groupby(["game_id", "drive"], dropna=True):
        yardline = pd.to_numeric(_column(group, "yardline_100"), errors="coerce")
        reaches_red_zone = bool(yardline.le(20.0).fillna(False).any())
        if not reaches_red_zone:
            continue
        red_zone_drives += 1
        touchdown = _flag(_column(group, "touchdown"))
        if bool(touchdown.any()):
            red_zone_td_drives += 1

    converted = _flag(_column(rows, "third_down_converted"))
    failed = _flag(_column(rows, "third_down_failed"))
    attempts = int((converted | failed).sum())
    conversions = int(converted.sum())
    first_downs = int(_flag(_column(rows, "first_down")).sum())

    if red_zone_drives <= 0 or attempts <= 0 or drives <= 0:
        return {
            "ready": False,
            "games_played": games,
            "red_zone_td_pct": math.nan,
            "third_down_conv_pct": math.nan,
            "first_downs_per_game": float(first_downs / games),
            "drives_per_game": float(drives / games) if drives else math.nan,
        }

    return {
        "ready": True,
        "games_played": games,
        "red_zone_td_pct": float(100.0 * red_zone_td_drives / red_zone_drives),
        "third_down_conv_pct": float(100.0 * conversions / attempts),
        "first_downs_per_game": float(first_downs / games),
        "drives_per_game": float(drives / games),
    }


@lru_cache(maxsize=1)
def _load_games_csv() -> pd.DataFrame:
    response = requests.get(NFLVERSE_GAMES_CSV, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return pd.read_csv(BytesIO(response.content))


@lru_cache(maxsize=4)
def _load_pbp_csv(season: int) -> pd.DataFrame:
    response = requests.get(
        NFLVERSE_PBP_CSV.format(season=int(season)),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return pd.read_csv(
        BytesIO(response.content),
        compression="gzip",
        usecols=lambda name: name in _PBP_COLUMNS,
        low_memory=False,
    )


# Keep a `.clear()` interface compatible with Streamlit cached functions.
_load_games_csv.clear = _load_games_csv.cache_clear  # type: ignore[attr-defined]
_load_pbp_csv.clear = _load_pbp_csv.cache_clear  # type: ignore[attr-defined]


def _provider_result(
    *,
    data: dict[str, Any],
    fields_verified: list[str],
    ready: bool,
    diagnostics: list[str] | None = None,
    source_timestamp: str = "",
) -> dict[str, Any]:
    fetched_at = _utc_now()
    return {
        "ready": bool(ready),
        "provider": PROVIDER,
        "data": data if ready else {},
        "fields_verified": list(fields_verified) if ready else [],
        "quality": "HIGH" if ready else "UNAVAILABLE",
        "data_freshness": source_timestamp or fetched_at,
        "source_timestamp": source_timestamp,
        "fetched_at": fetched_at,
        "diagnostics": list(diagnostics or []),
    }


def _request_value(request: dict[str, Any], key: str, default: Any = None) -> Any:
    return request.get(key, default) if isinstance(request, dict) else default


def fetch_scoring_games(request: dict[str, Any]) -> dict[str, Any]:
    team = canonical_team_abbr(_request_value(request, "team_abbr", ""))
    try:
        season = int(_request_value(request, "season"))
    except (TypeError, ValueError):
        return _provider_result(data={}, fields_verified=[], ready=False, diagnostics=["invalid season"])
    cutoff_day = str(_request_value(request, "cutoff_day", "") or "")[:10]
    if not team or not cutoff_day:
        return _provider_result(data={}, fields_verified=[], ready=False, diagnostics=["missing team or cutoff day"])

    try:
        frame = _load_games_csv()
        games = extract_scoring_games(frame, team, season, cutoff_day)
    except Exception as exc:
        return _provider_result(
            data={},
            fields_verified=[],
            ready=False,
            diagnostics=[f"{type(exc).__name__}: {str(exc)[:180]}"],
        )

    if not games:
        return _provider_result(
            data={},
            fields_verified=[],
            ready=False,
            diagnostics=["no completed regular-season scoring games available through cutoff"],
        )
    freshness = max(row["date"] for row in games)
    return _provider_result(
        data={"games": games},
        fields_verified=["date", "pf", "pa", "opponent_abbr"],
        ready=True,
        source_timestamp=freshness,
    )


def _fetch_pbp_metric(request: dict[str, Any], derive) -> tuple[dict[str, Any] | None, list[str], str]:
    team = canonical_team_abbr(_request_value(request, "team_abbr", ""))
    try:
        season = int(_request_value(request, "season"))
    except (TypeError, ValueError):
        return None, ["invalid season"], ""
    if not team:
        return None, ["missing team abbreviation"], ""

    try:
        frame = _load_pbp_csv(season)
        metrics = derive(frame, team)
    except Exception as exc:
        return None, [f"{type(exc).__name__}: {str(exc)[:180]}"], ""

    if metrics.get("ready") is not True:
        return None, ["no complete canonical nflverse metric available"], ""
    return metrics, [], _utc_now()


def fetch_pace(request: dict[str, Any]) -> dict[str, Any]:
    metrics, diagnostics, freshness = _fetch_pbp_metric(request, derive_pace_metrics)
    if metrics is None:
        return _provider_result(data={}, fields_verified=[], ready=False, diagnostics=diagnostics)
    return _provider_result(
        data={
            "games_played": int(metrics["games_played"]),
            "plays_per_game": float(metrics["plays_per_game"]),
            "possession_seconds_per_game": float(metrics["possession_seconds_per_game"]),
        },
        fields_verified=["games_played", "plays_per_game", "possession_seconds_per_game"],
        ready=True,
        source_timestamp=freshness,
    )


def fetch_explosive(request: dict[str, Any]) -> dict[str, Any]:
    metrics, diagnostics, freshness = _fetch_pbp_metric(request, derive_explosive_metrics)
    if metrics is None:
        return _provider_result(data={}, fields_verified=[], ready=False, diagnostics=diagnostics)
    return _provider_result(
        data={key: metrics[key] for key in (
            "games_played",
            "rushing_big_plays",
            "receiving_big_plays",
            "total_big_plays",
            "rushing_big_plays_per_game",
            "receiving_big_plays_per_game",
            "explosive_plays_per_game",
        )},
        fields_verified=[
            "games_played",
            "rushing_big_plays",
            "receiving_big_plays",
            "total_big_plays",
            "explosive_plays_per_game",
        ],
        ready=True,
        source_timestamp=freshness,
    )


def fetch_red_zone_drive(request: dict[str, Any]) -> dict[str, Any]:
    metrics, diagnostics, freshness = _fetch_pbp_metric(request, derive_red_zone_drive_metrics)
    if metrics is None:
        return _provider_result(data={}, fields_verified=[], ready=False, diagnostics=diagnostics)
    return _provider_result(
        data={key: metrics[key] for key in (
            "games_played",
            "red_zone_td_pct",
            "third_down_conv_pct",
            "first_downs_per_game",
            "drives_per_game",
        )},
        fields_verified=[
            "games_played",
            "red_zone_td_pct",
            "third_down_conv_pct",
            "first_downs_per_game",
            "drives_per_game",
        ],
        ready=True,
        source_timestamp=freshness,
    )


def clear_caches() -> None:
    _load_games_csv.cache_clear()
    _load_pbp_csv.cache_clear()


__all__ = [
    "NFLVERSE_GAMES_CSV",
    "NFLVERSE_PBP_CSV",
    "PROVIDER",
    "REQUEST_TIMEOUT_SECONDS",
    "canonical_team_abbr",
    "clear_caches",
    "derive_explosive_metrics",
    "derive_pace_metrics",
    "derive_red_zone_drive_metrics",
    "extract_scoring_games",
    "fetch_explosive",
    "fetch_pace",
    "fetch_red_zone_drive",
    "fetch_scoring_games",
]
