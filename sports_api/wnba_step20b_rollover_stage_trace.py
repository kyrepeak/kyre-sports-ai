"""WNBA Step20B: sanitized in-flight stage trace for rollover projection assembly.

This diagnostic wraps the high-level Step8 call boundaries used by Step12B and
selected Step8A/Step4W input-construction boundaries beneath the handoff. It
deliberately does not patch any frozen Step7G/source seam. Arguments, return
values, exceptions, ordering, projections, simulations, provider behavior,
readiness, persistence, and wagering remain unchanged.
"""
from __future__ import annotations

from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
from functools import wraps
import threading
import time
from typing import Any, Callable, Mapping

from sports_api import wnba_step8_projection_handoff as step8a
from sports_api import wnba_model_input_readiness as step4x
from sports_api import wnba_projection_input_snapshot as step4w
from sports_api import wnba_step8_official_box_baseline as step8b
from sports_api import wnba_step8_context_adjustment as step8c
from sports_api import wnba_step8_joint_monte_carlo as step8d
from sports_api import wnba_step12b_live_runtime_assembly as step12b

SOURCE = "Kyre Sports API WNBA Step20B rollover in-flight stage trace"
MODEL_VERSION = "wnba_step20b_rollover_stage_trace_v3"

_STAGE_TARGETS: tuple[tuple[str, Any, str], ...] = (
    ("step8a_handoff", step8a, "get_player_game_step8_projection_handoff"),
    ("step8a_readiness_gate", step8a, "get_player_game_model_input_readiness"),
    ("step4x_snapshot_build", step4x, "get_player_game_projection_input_snapshot"),
    ("step4w_player_opportunity", step4w, "get_player_opportunity_context"),
    ("step4w_rest_travel", step4w, "get_game_rest_travel_context"),
    ("step4w_game_availability", step4w, "get_game_availability_context_dataset"),
    ("step4w_player_shot_chart", step4w, "get_player_shot_chart_dataset"),
    ("step4w_opponent_zone_defense", step4w, "get_opponent_defense_by_shot_zone_dataset"),
    ("step4w_player_advanced", step4w, "get_player_advanced_stats_dataset"),
    ("step4w_team_advanced", step4w, "get_team_advanced_stats_dataset"),
    ("step4w_game_whistle_context", step4w, "get_game_whistle_context"),
    ("step4w_matchup_source_status", step4w, "get_matchup_source_status"),
    ("step8b_baseline", step8b, "build_step8_official_box_baseline"),
    ("step8c_context_adjustment", step8c, "build_step8_context_adjusted_projection"),
    ("step8d_monte_carlo_5m", step8d, "simulate_step8_joint_distribution"),
    ("projection_distribution_total", step12b, "_build_frozen_step8_distribution"),
)

_LOCK = threading.RLock()
_INSTALLED = False
_UPSTREAM: dict[str, Callable[..., Any]] = {}
_WRAPPERS: dict[str, Callable[..., Any]] = {}
_COUNTS: dict[str, int] = {}
_COMPLETED: deque[dict[str, Any]] = deque(maxlen=200)
_ACTIVE_STACK: list[dict[str, Any]] = []
_SEQUENCE = 0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ids_from_mapping(value: Any) -> tuple[str | None, int | None]:
    if not isinstance(value, Mapping):
        return None, None
    game = value.get("game_id")
    player = value.get("player_id")
    ref = value.get("snapshot_reference")
    if isinstance(ref, Mapping):
        game = game or ref.get("game_id")
        player = player or ref.get("player_id")
    try:
        player_id = int(player) if player is not None and not isinstance(player, bool) else None
    except (TypeError, ValueError):
        player_id = None
    return (str(game) if game is not None else None), player_id


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _explicit_call_shape(stage: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
    game_id: str | None = None
    player_id: int | None = None
    variant: str | None = None
    subject_key: str | None = None

    if stage == "projection_distribution_total":
        game_id = str(kwargs.get("game_id") or "") or None
        player_id = _int_or_none(kwargs.get("player_id"))
    elif stage in {"step8a_handoff", "step8a_readiness_gate", "step4x_snapshot_build"}:
        p = args[0] if args else kwargs.get("player_id")
        g = args[1] if len(args) > 1 else kwargs.get("game_id")
        player_id = _int_or_none(p)
        game_id = str(g) if g is not None else None
    elif stage == "step4w_player_opportunity":
        p = args[0] if args else kwargs.get("player_id")
        player_id = _int_or_none(p)
    elif stage in {"step4w_rest_travel", "step4w_game_availability", "step4w_game_whistle_context"}:
        g = args[0] if args else kwargs.get("game_id")
        game_id = str(g) if g is not None else None
    elif stage == "step4w_player_shot_chart":
        p = args[0] if args else kwargs.get("player_id")
        player_id = _int_or_none(p)
        variant = "vs_opponent" if kwargs.get("opponent_team_key") else "recent"
    elif stage == "step4w_player_advanced":
        player_id = _int_or_none(kwargs.get("player_id"))
    elif stage in {"step4w_opponent_zone_defense", "step4w_team_advanced"}:
        if stage == "step4w_opponent_zone_defense":
            raw_key = args[0] if args else kwargs.get("team_key")
        else:
            raw_key = kwargs.get("team_key")
        subject_key = str(raw_key) if raw_key is not None else None
    elif stage in {"step8b_baseline", "step8c_context_adjustment", "step8d_monte_carlo_5m"} and args:
        game_id, player_id = _ids_from_mapping(args[0])

    result: dict[str, Any] = {"game_id": game_id, "player_id": player_id}
    if variant is not None:
        result["variant"] = variant
    if subject_key is not None:
        result["subject_key"] = subject_key
    return result


def _parent_for_thread_locked(thread_id: int) -> dict[str, Any] | None:
    for row in reversed(_ACTIVE_STACK):
        if row.get("_thread_id") == thread_id:
            return row
    return None


def _make_wrapper(stage: str, upstream: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(upstream)
    def traced(*args: Any, **kwargs: Any) -> Any:
        global _SEQUENCE
        started_perf = time.perf_counter()
        started_utc = _now()
        thread_id = threading.get_ident()
        explicit_shape = _explicit_call_shape(stage, args, kwargs)
        with _LOCK:
            parent = _parent_for_thread_locked(thread_id)
            parent_sequence = parent.get("sequence") if parent is not None else None
            safe_shape = dict(explicit_shape)
            if parent is not None:
                if safe_shape.get("game_id") is None:
                    safe_shape["game_id"] = parent.get("game_id")
                if safe_shape.get("player_id") is None:
                    safe_shape["player_id"] = parent.get("player_id")
            _SEQUENCE += 1
            sequence = _SEQUENCE
            _COUNTS[stage] = int(_COUNTS.get(stage, 0)) + 1
            active = {
                "sequence": sequence,
                "parent_sequence": parent_sequence,
                "stage": stage,
                "started_at_utc": started_utc,
                **safe_shape,
                "_thread_id": thread_id,
            }
            _ACTIVE_STACK.append(active)
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
                "parent_sequence": parent_sequence,
                "stage": stage,
                "started_at_utc": started_utc,
                "finished_at_utc": _now(),
                "elapsed_seconds": elapsed,
                "status": status,
                "error_type": error_type,
                **safe_shape,
            }
            with _LOCK:
                _COMPLETED.append(event)
                for idx in range(len(_ACTIVE_STACK) - 1, -1, -1):
                    if _ACTIVE_STACK[idx].get("sequence") == sequence:
                        del _ACTIVE_STACK[idx]
                        break
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
        active = deepcopy(_ACTIVE_STACK)
        now = datetime.now(timezone.utc)
        for row in active:
            row.pop("_thread_id", None)
            try:
                started = datetime.fromisoformat(str(row["started_at_utc"]))
                row["elapsed_seconds_now"] = round((now - started).total_seconds(), 3)
            except Exception:
                row["elapsed_seconds_now"] = None
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
        "active_calls": active,
        "call_counts": counts,
        "recent_completed": recent[-100:],
        "guardrails": {
            "diagnostic_only": True,
            "frozen_step7g_source_seams_patched": False,
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
