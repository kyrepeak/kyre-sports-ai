"""Passing Yards slate successor overlay for Page 2 completeness.

The verified slate remains the model/data owner. This layer only adds a
current-season game log from the NFLverse rows already loaded by the slate.
Exact source player ID + team identity is mandatory.
"""
from __future__ import annotations

import importlib.util
from concurrent.futures import ThreadPoolExecutor, wait
import sys
from pathlib import Path
from typing import Any

_LEGACY_PATH = Path(__file__).resolve().parent.parent / "nfl_passing_yards_slate_v1.py"
_SPEC = importlib.util.spec_from_file_location("sports_api.api._nfl_passing_yards_slate_v1_verified", _LEGACY_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError("NFL Passing Yards verified slate implementation unavailable")
_legacy = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _legacy
_SPEC.loader.exec_module(_legacy)

for _name, _value in vars(_legacy).items():
    if _name not in {"__name__", "__package__", "__loader__", "__spec__", "__file__", "__cached__"}:
        globals().setdefault(_name, _value)

_ORIGINAL_BUILD_SLATE_BUNDLE = _legacy.build_slate_bundle
MARKET_PREFETCH_DEADLINE_SECONDS = 6.0


def _bounded_market_prefetch(
    games: list[dict[str, Any]],
    *,
    max_workers: int = 4,
    deadline_seconds: float = MARKET_PREFETCH_DEADLINE_SECONDS,
) -> dict[str, list[dict[str, Any]]]:
    if not games:
        return {}
    worker_count = max(1, min(int(max_workers), len(games)))
    results = {_legacy._text(game.get("game_id")): [] for game in games}
    pool = ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="passing-yards-market")
    futures = {
        pool.submit(_legacy._collect_market_observations, game): _legacy._text(game.get("game_id"))
        for game in games
    }
    try:
        done, pending = wait(futures, timeout=max(0.01, float(deadline_seconds)))
        for future in done:
            game_id = futures[future]
            try:
                results[game_id] = future.result()
            except Exception:
                results[game_id] = []
        for future in pending:
            future.cancel()
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return results


def _game_id_context(game_id: Any, team: Any) -> tuple[int | None, str | None]:
    parts = str(game_id or "").strip().split("_")
    team_abbr = _legacy.base._legacy.canonical_team_abbr(team)
    try:
        week = int(parts[1]) if len(parts) >= 2 else None
    except (TypeError, ValueError):
        week = None
    home_away = None
    if len(parts) >= 4:
        away = _legacy.base._legacy.canonical_team_abbr(parts[-2])
        home = _legacy.base._legacy.canonical_team_abbr(parts[-1])
        if team_abbr and team_abbr == home:
            home_away = "HOME"
        elif team_abbr and team_abbr == away:
            home_away = "AWAY"
    return week, home_away


def _season_game_log_for_player(player: dict[str, Any], current_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    visuals = player.get("identity_visuals") or {}
    source_player_id = str(visuals.get("source_player_id") or "").strip()
    team = _legacy._text(player.get("team_abbr")).upper()
    if not source_player_id or not team:
        return []
    output: list[dict[str, Any]] = []
    for raw in current_rows:
        row = dict(raw)
        if _legacy._text(row.get("player_source_id")) != source_player_id:
            continue
        if _legacy._text(row.get("team")).upper() != team:
            continue
        game_id = _legacy._text(row.get("game_id"))
        if not game_id:
            continue
        week, home_away = _game_id_context(game_id, team)
        output.append({
            "game_id": game_id,
            "week": week,
            "home_away": home_away,
            "team": team,
            "opponent": _legacy._text(row.get("opponent")).upper() or None,
            "player_source_id": source_player_id,
            "attempts": row.get("attempts"),
            "completions": row.get("completions"),
            "passing_yards": row.get("passing_yards"),
            "pass_tds": row.get("pass_tds"),
            "interceptions": row.get("interceptions"),
        })
    output.sort(key=lambda row: (int(row["week"]) if row.get("week") is not None else 999, str(row.get("game_id") or "")))
    return output


def build_game_bundles(target_date: str | None = None):
    resolved_date, games = _legacy._schedule_games(target_date)
    provenance = {
        "provider": "NFLverse",
        "market_primary": "FanDuel",
        "market_secondary": "The Odds API when configured and needed",
        "page2_game_log": "NFLverse exact player/team identity",
    }
    if not resolved_date or not games:
        return resolved_date, [], provenance
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="passing-yards-fields") as field_pool:
        contexts_future = field_pool.submit(_legacy._prefetch_season_contexts, games)
        markets_future = field_pool.submit(_bounded_market_prefetch, games)
        contexts = contexts_future.result()
        markets_by_game = markets_future.result()
    bundles: list[dict[str, Any]] = []
    for game in games:
        season = int(game["season"])
        game_date = _legacy._text(game.get("date")) or str(resolved_date or "")
        ctx = contexts.get((season, game_date)) or {"frame": None, "current_rows": [], "defenses": {}, "history": []}
        frame = ctx.get("frame")
        if frame is None:
            continue
        observations = markets_by_game.get(_legacy._text(game.get("game_id")), [])
        players: list[dict[str, Any]] = []
        for team, opponent, side in ((game["away"], game["home"], "away"), (game["home"], game["away"], "home")):
            defense = (ctx.get("defenses") or {}).get(opponent) or {
                "team_id": _legacy.base._legacy._canonical_team_id(opponent),
                "team_abbr": opponent,
                "team_name": _legacy.base._legacy.TEAM_NAMES.get(opponent, opponent),
                "rank": None,
                "grade": "CHECK",
                "pass_yards_allowed_per_game": None,
                "passing_attempts_allowed_per_game": None,
                "completion_pct_allowed": None,
                "yards_per_attempt_allowed": None,
                "recent3_pass_yards_allowed": None,
                "recent3_ypa_allowed": None,
                "sack_rate_generated": None,
            }
            current_rows = _legacy._current_rows_for_market_qb(team, ctx.get("current_rows") or [], observations)
            row = _legacy.base._legacy._player_bundle(
                team=team, opponent=opponent, side=side, current_rows=current_rows,
                all_history=ctx.get("history") or [], defense=defense, frame=frame,
                markets=observations, season=season, week=game.get("week"),
            )
            if row:
                source = dict(row)
                source["season_game_log"] = _season_game_log_for_player(source, current_rows)
                players.append(_legacy._enrich_player(source, game=game, observations=observations))
        bundles.append({"game": game, "players": players})
    return resolved_date, bundles, provenance


def build_slate_bundle(target_date: str | None = None):
    # Preserve the verified module's dependency-injection behavior: consumers may
    # replace this package-level build_game_bundles during tests or controlled runs.
    _legacy.build_game_bundles = globals()["build_game_bundles"]
    return _ORIGINAL_BUILD_SLATE_BUNDLE(target_date)


_legacy.build_game_bundles = build_game_bundles
_legacy.build_slate_bundle = build_slate_bundle
router = _legacy.router
slate = _legacy.slate
status = _legacy.status

__all__ = sorted(set(getattr(_legacy, "__all__", [])) | {
    "_season_game_log_for_player", "build_game_bundles", "build_slate_bundle", "router", "slate", "status",
})
