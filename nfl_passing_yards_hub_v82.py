"""NFL Passing Yards V82 — concurrent cold evidence prefetch.

Speed Phase Step 6 reduces selected-QB full-analysis latency without changing
any certified football value. The frozen V8 pipeline consumes independent
profile, defense, pressure, personnel, and environment evidence sequentially.
On a cold cache those independent verified ESPN builders dominate server time.

V82 keeps the frozen render order and exact builders, but once Step 1 identity
is resolved it launches those independent frozen builders concurrently. The
normal frozen pipeline then consumes the exact future results at the same call
sites. If a future is absent or fails, the original certified builder is called
synchronously. No formula, provider, projection, probability, market, sportsbook,
widget, navigation, or stake behavior changes.
"""
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from time import perf_counter
import threading
from threading import RLock
from typing import Any, Callable

import streamlit as st

import nfl_passing_yards_hub_v8 as step7_ui
import nfl_passing_yards_hub_v58 as selection
import nfl_passing_yards_hub_v80 as cache_v80
import nfl_passing_yards_hub_v81 as prior

try:
    from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
except Exception:  # pragma: no cover - compatibility fallback
    add_script_run_ctx = None
    get_script_run_ctx = None

MODEL_VERSION = "NFL PASSING YARDS V82 • SPEED STEP 6 CONCURRENT COLD EVIDENCE"
FROZEN_PRIOR = "nfl_passing_yards_hub_v81"
SPEED_PHASE_STEP = 6
CONCURRENCY_VERSION = "v82"
MAX_PREFETCH_WORKERS = 10
BASELINE_FULL_READY_SECONDS = 42.594
FULL_READY_TARGET_SECONDS = 24.0
REDUCTION_TARGET_PCT = 40.0
PRESENTATION_ONLY = False
TRANSPORT_SCHEDULING_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_CONTEXT_MATH = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_SPORTSBOOK_BEHAVIOR = False
MAY_MODIFY_DATA_PROVIDER_BEHAVIOR = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_NAVIGATION_STATE = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_PROCESS_STEP6_RLOCK = RLock()


def _safe(value: object, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _profile_key(athlete_id: str, qb_name: str, year: int, season_type: int = 2):
    return (_safe(athlete_id), _safe(qb_name), int(year), int(season_type))


def _defense_key(team_id: str, team_name: str, year: int, season_type: int, cutoff_date: str):
    return (_safe(team_id), _safe(team_name), int(year), int(season_type), _safe(cutoff_date))


def _pressure_key(
    offense_team_id: str,
    offense_team_name: str,
    defense_team_id: str,
    defense_team_name: str,
    year: int,
    season_type: int,
    cutoff_date: str,
):
    return (
        _safe(offense_team_id), _safe(offense_team_name),
        _safe(defense_team_id), _safe(defense_team_name),
        int(year), int(season_type), _safe(cutoff_date),
    )


def _personnel_key(offense_ctx: dict, defense_ctx: dict, year: int, season_type: int):
    return (
        _safe((offense_ctx or {}).get("team_id")),
        _safe((defense_ctx or {}).get("team_id")),
        int(year), int(season_type),
    )


def _environment_key(
    game: dict,
    away_ctx: dict,
    home_ctx: dict,
    year: int,
    season_type: int,
    cutoff_date: str,
):
    return (
        _safe((game or {}).get("game_id")),
        _safe((away_ctx or {}).get("team_id")),
        _safe((home_ctx or {}).get("team_id")),
        int(year), int(season_type), _safe(cutoff_date),
    )


def _worker_initializer(ctx) -> Callable[[], None]:
    def init() -> None:
        if ctx is not None and add_script_run_ctx is not None:
            try:
                add_script_run_ctx(threading.current_thread(), ctx)
            except Exception:
                pass
    return init


def render_nfl_passing_yards_hub() -> None:
    st.markdown(
        '<span data-passing-yards-concurrent-prefetch-owner="v82" '
        'data-passing-yards-speed-step="6" style="display:none" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )

    with _PROCESS_STEP6_RLOCK:
        original_identity = step7_ui.identity.resolve_matchup_identity
        original_profile = cache_v80._cached_profile
        original_defense = cache_v80._cached_defense
        original_pressure = cache_v80._cached_pressure
        original_environment = cache_v80._cached_environment
        original_personnel = step7_ui.personnel.build_personnel_matchup

        try:
            script_ctx = get_script_run_ctx() if get_script_run_ctx is not None else None
        except Exception:
            script_ctx = None

        executor = ThreadPoolExecutor(
            max_workers=MAX_PREFETCH_WORKERS,
            thread_name_prefix="passing-yards-step6",
            initializer=_worker_initializer(script_ctx),
        )
        futures: dict[str, dict[tuple, Future]] = {
            "profile": {}, "defense": {}, "pressure": {},
            "personnel": {}, "environment": {},
        }
        stats = {"launched": 0, "hits": 0, "fallbacks": 0}
        render_started = perf_counter()

        def submit(bucket: str, key: tuple, fn: Callable, *args) -> Future:
            existing = futures[bucket].get(key)
            if existing is not None:
                return existing
            future = executor.submit(fn, *args)
            futures[bucket][key] = future
            stats["launched"] += 1
            return future

        def consume(bucket: str, key: tuple, fallback: Callable, *args):
            future = futures[bucket].get(key)
            if future is None:
                stats["fallbacks"] += 1
                return fallback(*args)
            try:
                value = future.result()
                stats["hits"] += 1
                return value
            except Exception:
                stats["fallbacks"] += 1
                return fallback(*args)

        def wrapped_identity(game: dict, year: int):
            resolved = original_identity(game, year)
            away = resolved.get("away") or {}
            home = resolved.get("home") or {}
            day_str = _safe(selection._param("ks_py_date"))
            if len(day_str) != 10:
                return resolved
            season_type = int(step7_ui.step2_ui._season_type_code((game or {}).get("season_type")))

            for ctx in (away, home):
                qb = ctx.get("qb1") or {}
                if ctx.get("identity_verified"):
                    args = (
                        _safe(qb.get("athlete_id")),
                        _safe(qb.get("name")),
                        int(year),
                        season_type,
                    )
                    submit("profile", _profile_key(*args), original_profile, *args)

            for opp in (home, away):
                args = (
                    _safe(opp.get("team_id")),
                    _safe(opp.get("team"), opp.get("abbr")),
                    int(year), season_type, day_str,
                )
                submit("defense", _defense_key(*args), original_defense, *args)

            pressure_futures: list[Future] = []
            for offense_ctx, defense_ctx in ((away, home), (home, away)):
                args = (
                    _safe(offense_ctx.get("team_id")),
                    _safe(offense_ctx.get("team"), offense_ctx.get("abbr")),
                    _safe(defense_ctx.get("team_id")),
                    _safe(defense_ctx.get("team"), defense_ctx.get("abbr")),
                    int(year), season_type, day_str,
                )
                pressure_futures.append(
                    submit("pressure", _pressure_key(*args), original_pressure, *args)
                )

            env_args = (game, away, home, int(year), season_type, day_str)
            submit(
                "environment",
                _environment_key(*env_args),
                original_environment,
                *env_args,
            )

            def personnel_job(offense_ctx: dict, defense_ctx: dict, pressure_future: Future):
                pressure_row = pressure_future.result()
                attempts = (pressure_row.get("offense") or {}).get("passing_attempts")
                return original_personnel(
                    offense_ctx, defense_ctx, int(year), season_type, attempts
                )

            for (offense_ctx, defense_ctx), pressure_future in zip(
                ((away, home), (home, away)), pressure_futures
            ):
                key = _personnel_key(offense_ctx, defense_ctx, int(year), season_type)
                submit(
                    "personnel", key, personnel_job,
                    offense_ctx, defense_ctx, pressure_future,
                )
            return resolved

        def fast_profile(athlete_id: str, qb_name: str, year: int, season_type: int = 2):
            args = (athlete_id, qb_name, year, season_type)
            return consume("profile", _profile_key(*args), original_profile, *args)

        def fast_defense(team_id: str, team_name: str, year: int, season_type: int, cutoff_date: str):
            args = (team_id, team_name, year, season_type, cutoff_date)
            return consume("defense", _defense_key(*args), original_defense, *args)

        def fast_pressure(
            offense_team_id: str,
            offense_team_name: str,
            defense_team_id: str,
            defense_team_name: str,
            year: int,
            season_type: int,
            cutoff_date: str,
        ):
            args = (
                offense_team_id, offense_team_name, defense_team_id,
                defense_team_name, year, season_type, cutoff_date,
            )
            return consume("pressure", _pressure_key(*args), original_pressure, *args)

        def fast_environment(
            game: dict,
            away_ctx: dict,
            home_ctx: dict,
            year: int,
            season_type: int,
            cutoff_date: str,
        ):
            args = (game, away_ctx, home_ctx, year, season_type, cutoff_date)
            return consume(
                "environment", _environment_key(*args), original_environment, *args
            )

        def fast_personnel(
            offense_ctx: dict,
            defense_ctx: dict,
            year: int,
            season_type: int,
            team_pass_attempts: Any,
        ):
            key = _personnel_key(offense_ctx, defense_ctx, year, season_type)
            return consume(
                "personnel", key, original_personnel,
                offense_ctx, defense_ctx, year, season_type, team_pass_attempts,
            )

        step7_ui.identity.resolve_matchup_identity = wrapped_identity
        cache_v80._cached_profile = fast_profile
        cache_v80._cached_defense = fast_defense
        cache_v80._cached_pressure = fast_pressure
        cache_v80._cached_environment = fast_environment
        step7_ui.personnel.build_personnel_matchup = fast_personnel

        try:
            result = prior.render_nfl_passing_yards_hub()
            elapsed_ms = (perf_counter() - render_started) * 1000.0
            st.markdown(
                '<span data-passing-yards-concurrent-prefetch="v82" '
                f'data-step6-prefetch-launched="{stats["launched"]}" '
                f'data-step6-prefetch-hits="{stats["hits"]}" '
                f'data-step6-prefetch-fallbacks="{stats["fallbacks"]}" '
                f'data-step6-wrapper-render-ms="{elapsed_ms:.3f}" '
                'style="display:none" aria-hidden="true"></span>',
                unsafe_allow_html=True,
            )
            return result
        finally:
            step7_ui.identity.resolve_matchup_identity = original_identity
            cache_v80._cached_profile = original_profile
            cache_v80._cached_defense = original_defense
            cache_v80._cached_pressure = original_pressure
            cache_v80._cached_environment = original_environment
            step7_ui.personnel.build_personnel_matchup = original_personnel
            executor.shutdown(wait=False, cancel_futures=True)


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V82 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "BASELINE_FULL_READY_SECONDS","CONCURRENCY_VERSION","FROZEN_PRIOR",
    "FULL_READY_TARGET_SECONDS","MAX_PREFETCH_WORKERS","MAY_MODIFY_CONTEXT_MATH",
    "MAY_MODIFY_DATA_PROVIDER_BEHAVIOR","MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_NAVIGATION_STATE","MAY_MODIFY_PROBABILITY","MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_SPORTSBOOK_BEHAVIOR","MAY_MODIFY_WIDGET_KEYS","MODEL_VERSION",
    "REDUCTION_TARGET_PCT","SPEED_PHASE_STEP","SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED","TRANSPORT_SCHEDULING_ONLY",
    "_defense_key","_environment_key","_personnel_key","_pressure_key","_profile_key",
    "render_nfl_hub","render_nfl_passing_yards_hub",
]
