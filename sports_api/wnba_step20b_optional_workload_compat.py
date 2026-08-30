"""WNBA Step20B compatibility for unavailable optional historical workload.

Step4N's required schedule, rest, density, road-trip, and travel context is
independent from its observed team-minutes enrichment. In Step7G first-party
mode, the optional workload enrichment is assembled through Step4J history and
can fail when one historical WNBA.com game page no longer exposes a usable box
score. That missing historical enrichment must not fabricate data and must not
hide failures in the required schedule/rest/travel path.

This overlay changes exactly one case: if the frozen Step4N observed-workload
helper fails and its exception chain contains
``WNBAStep7GFirstPartyNotFoundError``, return an explicit unavailable workload
object with ``None`` metrics. Every other exception is re-raised unchanged.

No required Step4N calculation, projection math, readiness rule, Monte Carlo
configuration, sportsbook transport, persistence behavior, or wagering behavior
is modified.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import re
import threading
from typing import Any, Callable

from sports_api import wnba_schedule_context as schedule_context
from sports_api import wnba_step7g_first_party_history as first_party

SOURCE = "Kyre Sports API WNBA Step20B optional historical workload compatibility"
MODEL_VERSION = "wnba_step20b_optional_historical_workload_not_found_v1"

_ORIGINAL_OBSERVED_WORKLOAD: Callable[..., dict[str, Any]] = schedule_context._observed_workload
_LOCK = threading.RLock()
_INSTALLED = False
_FALLBACK_COUNT = 0
_LAST_FALLBACK: dict[str, Any] | None = None


def _exception_chain(exc: BaseException):
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def _is_first_party_not_found(exc: BaseException) -> bool:
    return any(
        isinstance(item, first_party.WNBAStep7GFirstPartyNotFoundError)
        for item in _exception_chain(exc)
    )


def _historical_game_id(exc: BaseException) -> str | None:
    for item in _exception_chain(exc):
        match = re.search(r"\b(\d{10})\b", str(item))
        if match:
            return match.group(1)
    return None


def _date_text(value: Any) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _unavailable_workload(
    team_key: str,
    season: int,
    target_date: Any,
    *,
    historical_game_id: str | None,
) -> dict[str, Any]:
    return {
        "available": False,
        "included": True,
        "classification": "optional_observed_workload_unavailable",
        "reason": "historical_official_box_score_not_found",
        "source": None,
        "source_endpoint": None,
        "team_key": str(team_key),
        "season": int(season),
        "target_date": _date_text(target_date),
        "historical_game_id": historical_game_id,
        "completed_games_before_target_date": None,
        "completed_games_previous_3_days": None,
        "completed_games_previous_5_days": None,
        "completed_games_previous_7_days": None,
        "team_minutes_previous_7_days": None,
        "team_minutes_above_regulation_previous_7_days": None,
        "games_above_regulation_team_minutes_previous_7_days": None,
        "most_recent_completed_game": None,
        "team_minutes_note": (
            "Optional observed workload is unavailable because an official historical "
            "WNBA.com box score was not found. No workload value is fabricated."
        ),
        "verification": {
            "optional_enrichment_unavailable": True,
            "historical_box_score_not_found": True,
            "required_schedule_rest_travel_preserved": True,
            "values_fabricated": False,
        },
    }


def get_observed_workload_step20b(
    team_key: str,
    season: int,
    target_date: Any,
) -> dict[str, Any]:
    """Run frozen workload logic; fail soft only for first-party NotFound history."""
    global _FALLBACK_COUNT, _LAST_FALLBACK
    try:
        return _ORIGINAL_OBSERVED_WORKLOAD(team_key, season, target_date)
    except Exception as exc:
        if not _is_first_party_not_found(exc):
            raise
        result = _unavailable_workload(
            team_key,
            season,
            target_date,
            historical_game_id=_historical_game_id(exc),
        )
        with _LOCK:
            _FALLBACK_COUNT += 1
            _LAST_FALLBACK = deepcopy(result)
        return result


def _wrapper_chain_contains(current: Callable[..., Any], target: Callable[..., Any]) -> bool:
    seen: set[int] = set()
    value: Any = current
    while callable(value) and id(value) not in seen:
        if value is target:
            return True
        seen.add(id(value))
        value = getattr(value, "__wrapped__", None)
    return False


def install_step20b_optional_workload_compat() -> dict[str, Any]:
    global _INSTALLED
    current = schedule_context._observed_workload
    if not _wrapper_chain_contains(current, get_observed_workload_step20b):
        if current is not _ORIGINAL_OBSERVED_WORKLOAD:
            raise RuntimeError(
                "Step20B optional workload compatibility refuses an unknown "
                "Step4N _observed_workload override."
            )
        schedule_context._observed_workload = get_observed_workload_step20b
    with _LOCK:
        _INSTALLED = True
    return installation_status()


def installation_status() -> dict[str, Any]:
    with _LOCK:
        fallback_count = int(_FALLBACK_COUNT)
        last_fallback = deepcopy(_LAST_FALLBACK)
        installed = bool(_INSTALLED)
    active = _wrapper_chain_contains(
        schedule_context._observed_workload,
        get_observed_workload_step20b,
    )
    return {
        "data_type": "wnba_step20b_optional_workload_compat_status",
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "installed": installed,
        "binding_active": bool(installed and active),
        "fallback_count": fallback_count,
        "last_fallback": last_fallback,
        "guardrails": {
            "first_party_not_found_only": True,
            "other_observed_workload_exceptions_reraised": True,
            "required_schedule_rest_travel_failures_relaxed": False,
            "unavailable_metrics_are_none_not_zero": True,
            "workload_values_fabricated": False,
            "projection_math_modified": False,
            "readiness_relaxed": False,
            "monte_carlo_simulation_count_modified": False,
            "monte_carlo_batch_size_modified": False,
            "sportsbook_transport_modified": False,
            "persistence_modified": False,
            "wagering_enabled": False,
        },
    }


__all__ = [
    "MODEL_VERSION",
    "SOURCE",
    "get_observed_workload_step20b",
    "install_step20b_optional_workload_compat",
    "installation_status",
]
