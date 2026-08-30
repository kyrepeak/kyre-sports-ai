"""WNBA Step20B: sanitized in-flight stage trace for rollover projection assembly.

This module is diagnostic-only. It wraps already-certified callable seams without
changing arguments, return values, exceptions, ordering, projections, simulation
counts, provider behavior, readiness, persistence, or wagering. The purpose is
to identify which pre-model/projection component consumes wall-clock time while
a hosted Step12B cycle is in progress.
"""
from __future__ import annotations

from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
from functools import wraps
import threading
import time
from typing import Any, Callable

from sports_api import wnba_projection_input_snapshot as snapshot
from sports_api import wnba_step12b_live_runtime_assembly as step12b

SOURCE = "Kyre Sports API WNBA Step20B rollover in-flight stage trace"
MODEL_VERSION = "wnba_step20b_rollover_stage_trace_v1"

_STAGE_TARGETS: tuple[tuple[str, Any, str], ...] = (
    ("player_opportunity_context", snapshot, "get_player_opportunity_context"),
    ("game_rest_travel_context", snapshot, "get_game_rest_travel_context"),
    ("game_availability", snapshot, "get_game_availability_context_dataset"),
    ("player_recent_or_vs_opponent_shot", snapshot, "get_player_shot_chart_dataset"),
    ("opponent_defense_by_shot_zone", snapshot, "get_opponent_defense_by_shot_zone_dataset"),
    ("player_advanced", snapshot, "get_player_advanced_stats_dataset"),
    ("team_or_opponent_advanced", snapshot, "get_team_advanced_stats_dataset"),
    ("game_whistle_context", snapshot, "get_game_whistle_context"),
    ("matchup_source_status", snapshot, "get_matchup_source_status"),
    ("projection_distribution_total", step12b, "_build_frozen_step8_distribution"),
)

_LOCK = threading.RLock()
_INSTALLED = False
_UPSTREAM: dict[str, Callable[..., Any]] = {}
_WRAPPERS: dict[str, Callable[..., Any]] = {}
_COUNTS: dict[str, int] = {}
_COMPLETED: deque[dict[str, Any]] = deque(maxlen=80)
_ACTIVE: dict[str, Any] | None = None
_SEQUENCE = 0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_call_shape(stage: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
    """Expose only numeric/string identity hints needed to correlate repeated work."""
    result: dict[str, Any] = {}
    if stage == "projection_distribution_total":
        result["game_id"] = str(kwargs.get("game_id") or "") or None
        player = kwargs.get("player_id")
        result["player_id"] = int(player) if isinstance(player, int) and not isinstance(player, bool) else None
    elif stage in {"game_rest_travel_context", "game_availability", "game_whistle_context"}:
        result["game_id"] = str(args[0]) if args else None
    elif stage in {"player_opportunity_context", "player_recent_or_vs_opponent_shot"}:
        player = args[0] if args else kwargs.get("player_id")
        result["player_id"] = int(player) if isinstance(player, int) and not isinstance(player, bool) else None
    elif stage == "player_advanced":
        player = kwargs.get("player_id")
        result["player_id"] = int(player) if isinstance(player, int) and not isinstance(player, bool) else None
    elif stage in {"opponent_defense_by_shot_zone", "team_or_opponent_advanced"}:
        team = args[0] if stage == "opponent_defense_by_shot_zone" and args else kwargs.get("team_key")
        result["team_key"] = str(team) if team else None
    return result


def _make_wrapper(stage: str, upstream: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(upstream)
    def traced(*args: Any, **kwargs: Any) -> Any:
        global _ACTIVE, _SEQUENCE
        started_perf = time.perf_counter()
        started_utc = _now()
        with _LOCK:
            _SEQUENCE += 1
            sequence = _SEQUENCE
            _COUNTS[stage] = int(_COUNTS.get(stage, 0)) + 1
            _ACTIVE = {
                "sequence": sequence,
                "stage": stage,
                "started_at_utc": started_utc,
                **_safe_call_shape(stage, args, kwargs),
            }
        status = "returned"
        error_type: str | None = None
        try:
            return upstream(*args, **kwargs)
        except Exception as exc:
            status = "raised"
            error_type = type(exc).__name__
            raise
        finally:
            elapsed = round(time.perf_counter() - started_perf, 3)
            event = {
                "sequence": sequence,
                "stage": stage,
                "started_at_utc": started_utc,
                "finished_at_utc": _now(),
                "elapsed_seconds": elapsed,
                "status": status,
                "error_type": error_type,
                **_safe_call_shape(stage, args, kwargs),
            }
            with _LOCK:
                _COMPLETED.append(event)
                if isinstance(_ACTIVE, dict) and _ACTIVE.get("sequence") == sequence:
                    _ACTIVE = None
    return traced


def install_step20b_rollover_stage_trace() -> dict[str, Any]:
    global _INSTALLED
    with _LOCK:
        for stage, module, attr in _STAGE_TARGETS:
            current = getattr(module, attr)
            known_wrapper = _WRAPPERS.get(stage)
            if known_wrapper is not None:
                if current is not known_wrapper:
                    raise RuntimeError(f"Step20B refuses unknown override after installation for {stage}.")
                continue
            _UPSTREAM[stage] = current
            wrapper = _make_wrapper(stage, current)
            _WRAPPERS[stage] = wrapper
            setattr(module, attr, wrapper)
        _INSTALLED = True
    return installation_status()


def installation_status() -> dict[str, Any]:
    with _LOCK:
        active = deepcopy(_ACTIVE)
        if active is not None:
            try:
                started = datetime.fromisoformat(str(active["started_at_utc"]))
                active["elapsed_seconds_now"] = round((datetime.now(timezone.utc) - started).total_seconds(), 3)
            except Exception:
                active["elapsed_seconds_now"] = None
        recent = deepcopy(list(_COMPLETED))
        counts = deepcopy(_COUNTS)
        installed = bool(_INSTALLED)
    active_bindings = {}
    for stage, module, attr in _STAGE_TARGETS:
        wrapper = _WRAPPERS.get(stage)
        active_bindings[stage] = bool(wrapper is not None and getattr(module, attr) is wrapper)
    return {
        "data_type": "wnba_step20b_rollover_stage_trace_status",
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _now(),
        "installed": installed,
        "all_stage_wrappers_active": installed and all(active_bindings.values()),
        "active_bindings": active_bindings,
        "active_call": active,
        "call_counts": counts,
        "recent_completed": recent[-40:],
        "guardrails": {
            "diagnostic_only": True,
            "arguments_modified": False,
            "return_values_modified": False,
            "exceptions_reclassified": False,
            "execution_order_modified": False,
            "projection_math_modified": False,
            "monte_carlo_simulation_count_modified": False,
            "monte_carlo_batch_size_modified": False,
            "sportsbook_transport_modified": False,
            "readiness_relaxed": False,
            "persistence_modified": False,
            "wagering_enabled": False,
        },
    }


__all__ = ["MODEL_VERSION", "SOURCE", "install_step20b_rollover_stage_trace", "installation_status"]
