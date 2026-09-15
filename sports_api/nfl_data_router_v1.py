"""Shared free/open NFL data router for Game Totals Steps 3-7.

The router knows canonical metric contracts, provider priority, validation,
provenance, and targeted cache invalidation. Provider adapters remain isolated
from projection math. Sportsbook data is intentionally outside this module.
"""
from __future__ import annotations

from math import isfinite
from typing import Any, Callable

Provider = Callable[[dict[str, Any]], dict[str, Any]]
CacheClearer = Callable[[], Any]

_ACCEPTED_QUALITY = {"HIGH", "MEDIUM"}
_CACHE_CLEARERS: dict[str, CacheClearer] = {}


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _in_range(value: Any, minimum: float, maximum: float) -> bool:
    number = _number(value)
    return number is not None and minimum <= number <= maximum


def _validate_scoring_games(data: dict[str, Any]) -> tuple[bool, list[str]]:
    games = data.get("games")
    if not isinstance(games, list):
        return False, ["scoring_games.games must be a list"]
    for row in games:
        if not isinstance(row, dict):
            return False, ["scoring_games row must be an object"]
        if not str(row.get("date") or "").strip():
            return False, ["scoring_games row missing date"]
        if not _in_range(row.get("pf"), 0.0, 100.0):
            return False, ["scoring_games points-for outside allowed range"]
        if not _in_range(row.get("pa"), 0.0, 100.0):
            return False, ["scoring_games points-against outside allowed range"]
    return True, []


def _validate_pace(data: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not _in_range(data.get("plays_per_game"), 20.0, 100.0):
        errors.append("pace plays_per_game outside allowed range")
    if not _in_range(data.get("possession_seconds_per_game"), 600.0, 3000.0):
        errors.append("pace possession_seconds_per_game outside allowed range")
    return not errors, errors


def _validate_explosive(data: dict[str, Any]) -> tuple[bool, list[str]]:
    if not _in_range(data.get("explosive_plays_per_game"), 0.0, 20.0):
        return False, ["explosive plays-per-game outside allowed range"]
    return True, []


def _validate_red_zone_drive(data: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not _in_range(data.get("red_zone_td_pct"), 0.0, 100.0):
        errors.append("red-zone TD percentage outside allowed range")
    if not _in_range(data.get("third_down_conv_pct"), 0.0, 100.0):
        errors.append("third-down conversion percentage outside allowed range")
    if not _in_range(data.get("first_downs_per_game"), 0.0, 60.0):
        errors.append("first downs per game outside allowed range")
    drives = data.get("drives_per_game")
    if drives is not None and not _in_range(drives, 1.0, 30.0):
        errors.append("drives per game outside allowed range")
    return not errors, errors


def _validate_environment(data: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not str(data.get("venue_name") or "").strip():
        errors.append("environment venue_name missing")
    if not isinstance(data.get("indoor"), bool):
        errors.append("environment indoor flag missing or ambiguous")
        return False, errors
    if bool(data.get("indoor")):
        return not errors, errors
    if not _in_range(data.get("temperature"), -80.0, 140.0):
        errors.append("environment temperature outside allowed range")
    if not _in_range(data.get("precipitation"), 0.0, 100.0):
        errors.append("environment precipitation outside allowed range")
    if not _in_range(data.get("gust"), 0.0, 150.0):
        errors.append("environment gust outside allowed range")
    return not errors, errors


_VALIDATORS: dict[str, Callable[[dict[str, Any]], tuple[bool, list[str]]]] = {
    "scoring_games": _validate_scoring_games,
    "pace": _validate_pace,
    "explosive": _validate_explosive,
    "red_zone_drive": _validate_red_zone_drive,
    "environment": _validate_environment,
}


def validate_result(metric: str, result: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate one normalized provider response against a canonical metric."""
    metric_key = str(metric or "").strip()
    if metric_key not in _VALIDATORS:
        return False, [f"unsupported canonical metric: {metric_key or 'empty'}"]
    if not isinstance(result, dict):
        return False, ["provider result must be an object"]
    if result.get("ready") is not True:
        return False, ["provider result is not ready"]

    quality = str(result.get("quality") or "").upper()
    if quality not in _ACCEPTED_QUALITY:
        return False, [f"provider quality {quality or 'UNAVAILABLE'} is not accepted for projection use"]

    fields = result.get("fields_verified")
    if not isinstance(fields, (list, tuple)) or not fields:
        return False, ["provider result has no verified fields"]

    freshness = str(result.get("data_freshness") or "").strip()
    if not freshness:
        return False, ["provider result has no data freshness timestamp"]

    data = result.get("data")
    if not isinstance(data, dict):
        return False, ["provider result data must be an object"]
    return _VALIDATORS[metric_key](data)


def _attempt_provider_name(provider: Provider, result: dict[str, Any] | None = None) -> str:
    if isinstance(result, dict):
        declared = str(result.get("provider") or "").strip()
        if declared:
            return declared
    return str(getattr(provider, "__name__", "provider") or "provider")


def _fail_closed(metric: str, attempts: list[dict[str, Any]], diagnostics: list[str]) -> dict[str, Any]:
    return {
        "ready": False,
        "metric": metric,
        "data": {},
        "provider_used": "",
        "fallback_rank": 0,
        "data_freshness": "",
        "fields_verified": [],
        "quality": "UNAVAILABLE",
        "diagnostics": diagnostics or ["all certified providers failed"],
        "provider_attempts": attempts,
    }


def route_metric(
    metric: str,
    request: dict[str, Any],
    providers: tuple[Provider, ...],
) -> dict[str, Any]:
    """Try providers in order and return the first validated canonical result."""
    metric_key = str(metric or "").strip()
    attempts: list[dict[str, Any]] = []
    diagnostics: list[str] = []

    if metric_key not in _VALIDATORS:
        return _fail_closed(metric_key, attempts, [f"unsupported canonical metric: {metric_key or 'empty'}"])
    if not isinstance(request, dict):
        return _fail_closed(metric_key, attempts, ["metric request must be an object"])

    for rank, provider in enumerate(tuple(providers or ()), start=1):
        result: dict[str, Any] | None = None
        try:
            candidate = provider(dict(request))
            result = candidate if isinstance(candidate, dict) else None
        except Exception as exc:
            provider_name = _attempt_provider_name(provider)
            message = f"{provider_name}: {type(exc).__name__}: {str(exc)[:180]}"
            diagnostics.append(message)
            attempts.append(
                {
                    "provider": provider_name,
                    "rank": rank,
                    "accepted": False,
                    "diagnostics": [message],
                }
            )
            continue

        provider_name = _attempt_provider_name(provider, result)
        if result is None:
            message = f"{provider_name}: provider returned a non-object result"
            diagnostics.append(message)
            attempts.append(
                {
                    "provider": provider_name,
                    "rank": rank,
                    "accepted": False,
                    "diagnostics": [message],
                }
            )
            continue

        if result.get("ready") is not True:
            provider_diags = [str(item) for item in (result.get("diagnostics") or []) if str(item).strip()]
            if not provider_diags:
                provider_diags = ["provider result unavailable"]
            qualified = [f"{provider_name}: {item}" for item in provider_diags]
            diagnostics.extend(qualified)
            attempts.append(
                {
                    "provider": provider_name,
                    "rank": rank,
                    "accepted": False,
                    "diagnostics": qualified,
                }
            )
            continue

        valid, validation_errors = validate_result(metric_key, result)
        if not valid:
            qualified = [f"{provider_name}: {item}" for item in validation_errors]
            diagnostics.extend(qualified)
            attempts.append(
                {
                    "provider": provider_name,
                    "rank": rank,
                    "accepted": False,
                    "diagnostics": qualified,
                }
            )
            continue

        attempts.append(
            {
                "provider": provider_name,
                "rank": rank,
                "accepted": True,
                "diagnostics": [],
            }
        )
        return {
            "ready": True,
            "metric": metric_key,
            "data": dict(result.get("data") or {}),
            "provider_used": provider_name,
            "fallback_rank": rank,
            "data_freshness": str(result.get("data_freshness") or ""),
            "fields_verified": list(result.get("fields_verified") or []),
            "quality": str(result.get("quality") or "").upper(),
            "diagnostics": diagnostics + [str(item) for item in (result.get("diagnostics") or []) if str(item).strip()],
            "provider_attempts": attempts,
        }

    return _fail_closed(metric_key, attempts, diagnostics)


def register_cache_clearer(name: str, clearer: CacheClearer) -> None:
    """Register one targeted provider/router cache clearer by stable name."""
    key = str(name or "").strip()
    if not key:
        raise ValueError("cache clearer name is required")
    if not callable(clearer):
        raise TypeError("cache clearer must be callable")
    _CACHE_CLEARERS[key] = clearer


def clear_router_caches() -> list[str]:
    """Clear only caches explicitly registered by the NFL data router stack."""
    cleared: list[str] = []
    for name, clearer in tuple(_CACHE_CLEARERS.items()):
        clearer()
        cleared.append(name)
    return cleared


__all__ = [
    "clear_router_caches",
    "register_cache_clearer",
    "route_metric",
    "validate_result",
]
