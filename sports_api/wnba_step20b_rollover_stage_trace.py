"""WNBA Step20B: sanitized in-flight stage trace for rollover projection assembly.

This diagnostic wraps the high-level Step8 call boundaries used by Step12B and
identity-safe Step8A/Step4W input-construction boundaries beneath the handoff.
Step4W optional components are timed through its dispatcher rather than by
replacing Step7G-protected provider aliases. V5 also traces safe Step4V, Step4R,
Step4U, and Step4N boundaries so slow observed-data construction can be split
without touching protected first-party seams. Arguments, return values,
exceptions, ordering, projections, simulations, provider behavior, readiness,
persistence, and wagering remain unchanged.
"""
from __future__ import annotations

from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
from functools import wraps
import threading
import time
import traceback
from typing import Any, Callable, Mapping

from sports_api import wnba_player_event_features as step4u
from sports_api import wnba_player_opportunity_context as step4v
from sports_api import wnba_projection_input_snapshot as step4w
from sports_api import wnba_rotation_context as step4r
from sports_api import wnba_schedule_context as step4n
from sports_api import wnba_model_input_readiness as step4x
from sports_api import wnba_step8_projection_handoff as step8a
from sports_api import wnba_step8_official_box_baseline as step8b
from sports_api import wnba_step8_context_adjustment as step8c
from sports_api import wnba_step8_joint_monte_carlo as step8d
from sports_api import wnba_step12b_live_runtime_assembly as step12b

SOURCE = "Kyre Sports API WNBA Step20B rollover in-flight stage trace"
MODEL_VERSION = "wnba_step20b_rollover_stage_trace_v5"

# Step7G identity-guards these Step4W aliases. Never wrap them here: doing so
# makes the next Step7G install/revalidation look like an unknown override.
_STEP7G_PROTECTED_STEP4W_ATTRS: tuple[str, ...] = (
    "get_player_shot_chart_dataset",
    "get_opponent_defense_by_shot_zone_dataset",
    "get_player_advanced_stats_dataset",
    "get_team_advanced_stats_dataset",
    "get_game_whistle_context",
)

# The Step4W optional dispatcher receives every optional component call,
# including the protected providers above, so it gives us per-component timing
# without changing any protected provider identity.
_OPTIONAL_DISPATCH_STAGE = "step4w_optional_component_dispatch"

_STAGE_TARGETS: tuple[tuple[str, Any, str], ...] = (
    ("step8a_handoff", step8a, "get_player_game_step8_projection_handoff"),
    ("step8a_readiness_gate", step8a, "get_player_game_model_input_readiness"),
    ("step4x_snapshot_build", step4x, "get_player_game_projection_input_snapshot"),
    ("step4w_player_opportunity", step4w, "get_player_opportunity_context"),
    ("step4v_recent_rotation", step4v, "get_player_recent_rotation_context"),
    ("step4r_game_rotation", step4r, "get_game_rotation"),
    ("step4v_recent_event_features", step4v, "get_player_recent_event_feature_context"),
    ("step4u_game_event_lineups", step4u, "get_game_event_lineups"),
    ("step4u_game_possession_context", step4u, "get_game_possession_event_context"),
    ("step4w_rest_travel", step4w, "get_game_rest_travel_context"),
    ("step4n_team_rest_travel", step4n, "get_team_rest_travel_context"),
    ("step4n_observed_workload", step4n, "_observed_workload"),
    (_OPTIONAL_DISPATCH_STAGE, step4w, "_optional_component"),
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
_COMPLETED: deque[dict[str, Any]] = deque(maxlen=300)
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


def _event_stage(stage: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    if stage != _OPTIONAL_DISPATCH_STAGE:
        return stage
    raw = args[0] if args else kwargs.get("name")
    name = str(raw).strip() if raw is not None else "unknown"
    safe_name = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in name)
    return f"step4w_optional_{safe_name or 'unknown'}"


def _explicit_call_shape(stage: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
    game_id: str | None = None
    player_id: int | None = None

    if stage == "projection_distribution_total":
        game_id = str(kwargs.get("game_id") or "") or None
        player_id = _int_or_none(kwargs.get("player_id"))
    elif stage in {"step8a_handoff", "step8a_readiness_gate", "step4x_snapshot_build"}:
        p = args[0] if args else kwargs.get("player_id")
        g = args[1] if len(args) > 1 else kwargs.get("game_id")
        player_id = _int_or_none(p)
        game_id = str(g) if g is not None else None
    elif stage in {"step4w_player_opportunity", "step4v_recent_rotation", "step4v_recent_event_features"}:
        p = args[0] if args else kwargs.get("player_id")
        player_id = _int_or_none(p)
    elif stage in {
        "step4w_rest_travel",
        "step4r_game_rotation",
        "step4u_game_event_lineups",
        "step4u_game_possession_context",
    }:
        g = args[0] if args else kwargs.get("game_id")
        game_id = str(g) if g is not None else None
    elif stage in {"step8b_baseline", "step8c_context_adjustment", "step8d_monte_carlo_5m"} and args:
        game_id, player_id = _ids_from_mapping(args[0])

    return {"game_id": game_id, "player_id": player_id}


def _parent_for_thread_locked(thread_id: int) -> dict[str, Any] | None:
    for row in reversed(_ACTIVE_STACK):
        if row.get("_thread_id") == thread_id:
            return row
    return None


def _error_metadata(exc: BaseException) -> dict[str, Any]:
    frames = traceback.extract_tb(exc.__traceback__)
    tail = [
        {
            "file": str(frame.filename).replace("\\", "/").rsplit("/", 1)[-1],
            "line": int(frame.lineno),
            "function": str(frame.name),
        }
        for frame in frames[-8:]
    ]
    return {
        "error_type": type(exc).__name__,
        "error_message": str(exc)[:1000],
        "error_repr": repr(exc)[:1000],
        "traceback_tail": tail,
    }


def _make_wrapper(stage: str, upstream: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(upstream)
    def traced(*args: Any, **kwargs: Any) -> Any:
        global _SEQUENCE
        started_perf = time.perf_counter()
        started_utc = _now()
        thread_id = threading.get_ident()
        event_stage = _event_stage(stage, args, kwargs)
        explicit_shape = _explicit_call_shape(event_stage, args, kwargs)

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
            _COUNTS[event_stage] = int(_COUNTS.get(event_stage, 0)) + 1
            active = {
                "sequence": sequence,
                "parent_sequence": parent_sequence,
                "stage": event_stage,
                "started_at_utc": started_utc,
                **safe_shape,
                "_thread_id": thread_id,
            }
            _ACTIVE_STACK.append(active)

        status = "returned"
        error: dict[str, Any] = {
            "error_type": None,
            "error_message": None,
            "error_repr": None,
            "traceback_tail": [],
        }
        try:
            return upstream(*args, **kwargs)
        except Exception as exc:
            status = "raised"
            error = _error_metadata(exc)
            raise
        finally:
            elapsed = round(time.perf_counter() - started_perf, 3)
            event = {
                "sequence": sequence,
                "parent_sequence": parent_sequence,
                "stage": event_stage,
                "started_at_utc": started_utc,
                "finished_at_utc": _now(),
                "elapsed_seconds": elapsed,
                "status": status,
                **error,
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

    protected_attrs_in_targets = [
        attr
        for _, module, attr in _STAGE_TARGETS
        if module is step4w and attr in _STEP7G_PROTECTED_STEP4W_ATTRS
    ]
    return {
        "data_type": "wnba_step20b_rollover_stage_trace_status",
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _now(),
        "installed": installed,
        "all_stage_wrappers_active": installed and all(active_bindings.values()),
        "active_bindings": active_bindings,
        "protected_step7g_step4w_bindings_untouched": not protected_attrs_in_targets,
        "protected_step7g_step4w_bindings_wrapped": protected_attrs_in_targets,
        "active_calls": active,
        "call_counts": counts,
        "recent_completed": recent[-150:],
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
