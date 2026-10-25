"""API2 Step 2D global data-truth / zero-false-blank gate."""
from __future__ import annotations
from typing import Any, Mapping

VERSION = "API2_STEP2D_DATA_TRUTH_GATE_V1"
_FAILURE_STATES = {
    "PROVIDER_FETCH_FAILURE", "PARSER_FAILURE", "MAPPING_FAILURE",
    "EVENT_MAPPING_FAILURE", "PLAYER_MAPPING_FAILURE", "MARKET_MAPPING_FAILURE",
    "STALE_DATA", "SOURCE_CONFLICT", "ALL_SOURCES_UNAVAILABLE",
}


def negative_cache_allowed(state: str) -> bool:
    """Only proven absence may be cached as a negative market result."""
    return str(state) == "VERIFIED_NOT_POSTED"


def _failure_state(obs: Mapping[str, Any]) -> str | None:
    if obs.get("reachable") is not True:
        return "PROVIDER_FETCH_FAILURE"
    if obs.get("parsed") is not True:
        return "PARSER_FAILURE"
    if obs.get("matched") is not True:
        return "MAPPING_FAILURE"
    if obs.get("fresh") is not True:
        return "STALE_DATA"
    return None


def evaluate_field(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed unless source truth survives through API and frontend.

    Observations are ordered primary then approved fallbacks. A failed primary may
    be bypassed only by an explicitly approved fallback with a complete, fresh,
    matched observation. Failures never prove market absence.
    """
    observations = list(payload.get("source_observations") or [])
    if not observations:
        return {"allowed": False, "state": "ALL_SOURCES_UNAVAILABLE"}

    first_failure = None
    resolved = None
    verified_absent = None
    for index, raw in enumerate(observations):
        obs = dict(raw)
        failure = _failure_state(obs)
        if failure:
            first_failure = first_failure or failure
            continue
        if index > 0 and obs.get("approved_fallback") is not True:
            continue
        if obs.get("present") is True:
            resolved = obs
            break
        if obs.get("present") is False:
            verified_absent = obs
            # Absence at one source does not prevent an already-supplied approved
            # fallback observation from proving availability later in the chain.
            continue

    if resolved is not None:
        source_value = resolved.get("value")
        api_value = payload.get("api_value")
        frontend_value = payload.get("frontend_value")
        if source_value is None or api_value != source_value or frontend_value != source_value:
            return {"allowed": False, "state": "DATA_TRUTH_MISMATCH", "resolved_provider": resolved.get("provider")}
        return {"allowed": True, "state": "AVAILABLE", "resolved_provider": resolved.get("provider"), "value": source_value}

    if first_failure is not None:
        # A technical failure is never allowed to collapse into NOT_POSTED even
        # when a different source reported absence; the failure still needs
        # fallback/verification or explicit all-source proof.
        return {"allowed": False, "state": first_failure}

    if verified_absent is not None:
        api_state = str(payload.get("api_state") or "")
        if api_state != "VERIFIED_NOT_POSTED":
            return {"allowed": False, "state": "FALSE_EMPTY_STATE"}
        return {"allowed": True, "state": "VERIFIED_NOT_POSTED", "resolved_provider": verified_absent.get("provider")}

    return {"allowed": False, "state": "ALL_SOURCES_UNAVAILABLE"}
