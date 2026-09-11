"""CFB Over/Under performance Step 4 — parallel analysis source prewarm.

This module does not project, rank, qualify, select, or modify any CFB result.
It only warms the already-certified Streamlit/provider caches that frozen Slate
V14 will consume moments later for the selected matchup.

The work is intentionally overlapped with the live sportsbook request by Clean
Page V34. That turns independent network waits into one shared wall-clock wait
without changing data-source semantics or frozen model behavior.

Permanent protections:
- frozen V14 projection math is untouched;
- sportsbook projection influence remains 0.0%;
- official ESPN identity is required for game-specific ESPN warmups;
- no fuzzy game matching or synthetic IDs are introduced;
- every warmup is best-effort and fail-open to the existing certified path.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Callable, Mapping

import cfb_over_under_data_recovery_v1 as recovery
import cfb_over_under_environment_engine_v1 as environment
import cfb_over_under_explosive_engine_v1 as explosive
import cfb_over_under_history_engine_v1 as history
import cfb_over_under_matchup_engine_v1 as matchup
import cfb_over_under_pace_engine_v1 as pace
import cfb_over_under_red_zone_engine_v1 as red_zone
import cfb_over_under_runtime_team_data_v1 as runtime_team_data
import cfb_over_under_third_down_engine_v1 as third_down
import cfb_over_under_turnover_engine_v1 as turnover

MODEL_VERSION = "CFB O/U ANALYSIS PREWARM V1 • PERFORMANCE STEP 4"
PROJECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False
MAX_WORKERS = 8
HISTORY_WORKERS = 6


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _season(game: Mapping[str, Any], day: Any) -> int:
    for candidate in (_clean(game.get("game_date")), _clean(day)):
        try:
            return int(candidate[:4])
        except Exception:
            pass
    return datetime.now(timezone.utc).year


def _timed(label: str, fn: Callable[[], Any]) -> tuple[str, Any, dict[str, Any]]:
    started = perf_counter()
    try:
        value = fn()
        return label, value, {
            "stage": label,
            "status": "GREEN",
            "elapsed_ms": round((perf_counter() - started) * 1000.0, 1),
            "error": "",
        }
    except Exception as exc:
        return label, None, {
            "stage": label,
            "status": "UNAVAILABLE",
            "elapsed_ms": round((perf_counter() - started) * 1000.0, 1),
            "error": f"{type(exc).__name__}: {exc}"[:400],
        }


def _warm_runtime_foundation(
    game: Mapping[str, Any],
    day: Any,
) -> dict[str, Any]:
    game2, away, home, diag = runtime_team_data.reconcile_runtime(
        dict(game),
        day,
    )
    return {
        "game": dict(game2),
        "away": dict(away),
        "home": dict(home),
        "diag": dict(diag),
    }


def _warm_matchup_tables(foundation: Mapping[str, Any]) -> dict[str, Any]:
    away = foundation.get("away") or {}
    home = foundation.get("home") or {}
    away_division = matchup._profile_division(away)
    home_division = matchup._profile_division(home)
    if away_division != home_division:
        return {
            "warmed": False,
            "reason": "mixed-division Step 3 intentionally skips shared rank tables",
            "away_division": away_division,
            "home_division": home_division,
        }
    division = away_division if away_division in {"FBS", "FCS"} else "FBS"
    stats_index = (
        matchup.NCAA_FCS_STATS_INDEX
        if division == "FCS"
        else matchup.NCAA_FBS_STATS_INDEX
    )
    matchup._load_division_tables(stats_index, division)
    return {
        "warmed": True,
        "division": division,
    }


def _warm_pair(loader: Callable[[str], Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for division in ("FBS", "FCS"):
        loader(division)
        out[division] = True
    return out


def _warm_environment_history(
    game: Mapping[str, Any],
    day: Any,
) -> dict[str, Any]:
    event_id = _clean(game.get("espn_event_id") or game.get("game_id"))
    away_id = _clean(game.get("away_espn_team_id"))
    home_id = _clean(game.get("home_espn_team_id"))
    season = _season(game, day)

    jobs: list[tuple[str, Callable[..., Any], tuple[Any, ...]]] = [
        ("env_scoreboard", environment._fetch_scoreboard, (_clean(day)[:10],)),
    ]
    if event_id.isdigit():
        jobs.append(("env_summary", environment._fetch_summary, (event_id,)))
    if away_id.isdigit():
        jobs.append(("env_away_roster", environment._fetch_roster, (away_id,)))
    if home_id.isdigit():
        jobs.append(("env_home_roster", environment._fetch_roster, (home_id,)))

    # Step 10 requests six seasons for the away side and three for the home
    # side. Step 11 reuses the current-season entries from the same cache.
    if away_id.isdigit():
        for year in range(season, season - history.H2H_LOOKBACK_SEASONS, -1):
            jobs.append((f"away_schedule_{year}", history._fetch_team_schedule, (away_id, year)))
    if home_id.isdigit():
        for year in range(season, season - history.LOOKBACK_SEASONS, -1):
            jobs.append((f"home_schedule_{year}", history._fetch_team_schedule, (home_id, year)))

    if not (away_id.isdigit() and home_id.isdigit()):
        jobs.append(("espn_team_directory", recovery._fetch_espn_teams, ()))

    completed = 0
    errors: list[str] = []
    with ThreadPoolExecutor(
        max_workers=max(1, min(HISTORY_WORKERS, len(jobs) or 1))
    ) as pool:
        futures = {
            pool.submit(fn, *args): label
            for label, fn, args in jobs
        }
        for future in as_completed(futures):
            label = futures[future]
            try:
                future.result()
                completed += 1
            except Exception as exc:
                errors.append(f"{label}: {type(exc).__name__}: {exc}"[:300])

    return {
        "jobs": len(jobs),
        "completed": completed,
        "errors": errors,
        "official_event_id": event_id,
        "away_team_id": away_id,
        "home_team_id": home_id,
        "season": season,
    }


def _warm_h2h_context(game: Mapping[str, Any]) -> dict[str, Any]:
    away = _clean(game.get("away_team"))
    home = _clean(game.get("home_team"))
    if not away or not home:
        return {"warmed": False, "reason": "team names unavailable"}
    recovery._fetch_winsipedia_games(away, home)
    return {"warmed": True, "away": away, "home": home}


def warm_selected_game(
    game: Mapping[str, Any] | None,
    day: Any,
) -> dict[str, Any]:
    """Warm independent certified inputs for one selected game in parallel.

    Failures are diagnostics only. The caller always continues into the normal
    certified analysis path, which retains its existing provider fallbacks.
    """
    selected = dict(game or {})
    started = perf_counter()
    if not selected:
        return {
            "version": MODEL_VERSION,
            "status": "SKIPPED",
            "elapsed_ms": 0.0,
            "stages": [],
            "projection_weight": PROJECTION_WEIGHT,
            "may_modify_projection": MAY_MODIFY_PROJECTION,
        }

    stages: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        foundation_future = pool.submit(
            _timed,
            "runtime_team_foundation",
            lambda: _warm_runtime_foundation(selected, day),
        )
        futures = {
            pool.submit(_timed, "pace_sources", lambda: _warm_pair(pace._load_pace_division)): "pace_sources",
            pool.submit(_timed, "explosive_sources", lambda: _warm_pair(explosive._load_explosive_division)): "explosive_sources",
            pool.submit(_timed, "red_zone_sources", lambda: _warm_pair(red_zone._load_red_zone_division)): "red_zone_sources",
            pool.submit(_timed, "third_down_sources", lambda: _warm_pair(third_down._load_third_down_division)): "third_down_sources",
            pool.submit(_timed, "turnover_sources", lambda: _warm_pair(turnover._load_turnover_division)): "turnover_sources",
            pool.submit(_timed, "environment_history_sources", lambda: _warm_environment_history(selected, day)): "environment_history_sources",
            pool.submit(_timed, "h2h_context", lambda: _warm_h2h_context(selected)): "h2h_context",
        }

        foundation = None
        try:
            _, foundation, foundation_diag = foundation_future.result()
            stages.append(foundation_diag)
        except Exception as exc:
            stages.append({
                "stage": "runtime_team_foundation",
                "status": "UNAVAILABLE",
                "elapsed_ms": 0.0,
                "error": f"{type(exc).__name__}: {exc}"[:400],
            })

        if isinstance(foundation, Mapping):
            futures[
                pool.submit(
                    _timed,
                    "step3_matchup_tables",
                    lambda: _warm_matchup_tables(foundation),
                )
            ] = "step3_matchup_tables"

        for future in as_completed(futures):
            try:
                _, _, diag = future.result()
            except Exception as exc:
                diag = {
                    "stage": futures[future],
                    "status": "UNAVAILABLE",
                    "elapsed_ms": 0.0,
                    "error": f"{type(exc).__name__}: {exc}"[:400],
                }
            stages.append(diag)

    unavailable = sum(row.get("status") != "GREEN" for row in stages)
    return {
        "version": MODEL_VERSION,
        "status": "GREEN" if unavailable == 0 else "PARTIAL",
        "elapsed_ms": round((perf_counter() - started) * 1000.0, 1),
        "stages": sorted(
            stages,
            key=lambda row: (-float(row.get("elapsed_ms") or 0.0), str(row.get("stage") or "")),
        ),
        "unavailable_stages": int(unavailable),
        "projection_weight": PROJECTION_WEIGHT,
        "may_modify_projection": MAY_MODIFY_PROJECTION,
        "sportsbook_input_used": False,
        "fuzzy_matching": False,
        "synthetic_ids": False,
    }


__all__ = [
    "HISTORY_WORKERS",
    "MAX_WORKERS",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PROJECTION_WEIGHT",
    "warm_selected_game",
]
