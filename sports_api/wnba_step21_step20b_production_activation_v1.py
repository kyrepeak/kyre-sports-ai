"""WNBA Step 21 — certified Step20B production activation contract.

Step 20B already proved the performance repairs on an exact candidate while
temporarily disabling the always-on runtime and restoring Step19N afterward.

Step 21 is the controlled production handoff:
- deploy the exact certified Step20B candidate,
- leave the existing Step17B single-leader runtime enabled,
- keep 5,000,000 simulations and 250,000 batch size unchanged,
- keep projection/readiness/provider/persistence/wagering semantics unchanged,
- require healthy completed production cycles,
- roll back to the exact Step19N production revision on any activation failure.

This module is certification/orchestration policy only. It is not imported by
the production runtime candidate and changes no basketball/model behavior.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping

SOURCE = "Kyre Sports API WNBA Step21 Step20B production activation"
MODEL_VERSION = "wnba_step21_step20b_production_activation_v1"

STEP20B_CANDIDATE_SHA = "b2c5b10c05036131dea5dee55370ca6498d3c3d8"
STEP19N_ROLLBACK_SHA = "aaf8b8a5425ea6e1b0ab33e6c42f35c95e8905ab"

CERTIFIED_SIMULATIONS = 5_000_000
CERTIFIED_BATCH_SIZE = 250_000
MAX_COMPLETED_CYCLE_SECONDS = 600.0
MIN_SAFE_COMPLETED_CYCLES = 2

STEP20B_RUNTIME_BLOBS = {
    "sports_api/api/wnba_step17b_runtime.py": "5abc347cffc532d28a3c12f5296db6d2b91cad79",
    "sports_api/wnba_step20b_runtime_acceleration.py": "286c480da3b135de8122b1f6c8436e10b03904dc",
    "sports_api/wnba_step20b_optional_workload_compat.py": "1ea92b933047fa4da37044afd69e23b3f49d0339",
    "sports_api/wnba_step20b_monte_carlo_acceleration.py": "41b8810fb47345733cd8a2a4aca75e85bf98ad60",
    "sports_api/wnba_step20b_monte_carlo_cdf_compat.py": "bb00759b9051873601e5d0cdcf108c2951d93845",
    "sports_api/wnba_step20b_step4w_cycle_cache.py": "25bd231b3f408476be52abb3fc70bcf9273c8d57",
    "sports_api/wnba_step20b_rollover_stage_trace.py": "97e6fb2550e0631904f85c3ccce1509bbf7c5ff8",
    "sports_api/wnba_step12b_live_runtime_assembly.py": "fa6f1651a811ce76350f8b88ba5d6a9a6dcaf1ad",
    "sports_api/wnba_step8_joint_monte_carlo.py": "2720aa506cceda55c3ca32dac01d6d6de9fb86c7",
}

_REQUIRED_FALSE_GUARDS = (
    "projection_math_modified",
    "readiness_relaxed",
    "sportsbook_transport_modified",
    "persistence_modified",
    "wagering_enabled",
)

_REQUIRED_STEP20B_STATUS_KEYS = (
    "runtime_acceleration",
    "optional_workload",
    "monte_carlo",
    "monte_carlo_cdf",
    "step4w_cache",
)


class WNBAStep21ActivationError(RuntimeError):
    pass


def _iso(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def completed_cycle_seconds(runtime: Mapping[str, Any]) -> float | None:
    started = _iso(runtime.get("last_cycle_started_at_utc"))
    finished = _iso(runtime.get("last_cycle_finished_at_utc"))
    if started is None or finished is None:
        return None
    seconds = (finished - started).total_seconds()
    return float(seconds) if seconds >= 0 else None


def _require_false_guards(status: Mapping[str, Any], *, label: str) -> None:
    guards = status.get("guardrails") or {}
    if not isinstance(guards, Mapping):
        raise WNBAStep21ActivationError(f"{label} guardrails are unavailable.")
    for key in _REQUIRED_FALSE_GUARDS:
        if guards.get(key) is not False:
            raise WNBAStep21ActivationError(f"{label} guardrail changed: {key}.")


def validate_step20b_statuses(statuses: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    missing = [key for key in _REQUIRED_STEP20B_STATUS_KEYS if key not in statuses]
    if missing:
        raise WNBAStep21ActivationError(
            "Step20B activation status missing: " + ", ".join(missing)
        )

    runtime_accel = statuses["runtime_acceleration"]
    if runtime_accel.get("installed") is not True or runtime_accel.get("all_bindings_active") is not True:
        raise WNBAStep21ActivationError("Step20B runtime acceleration is not fully active.")
    _require_false_guards(runtime_accel, label="runtime acceleration")

    workload = statuses["optional_workload"]
    if workload.get("installed") is not True or workload.get("binding_active") is not True:
        raise WNBAStep21ActivationError("Step20B optional workload compatibility is not active.")
    _require_false_guards(workload, label="optional workload")

    mc = statuses["monte_carlo"]
    if mc.get("installed") is not True or mc.get("binding_active") is not True:
        raise WNBAStep21ActivationError("Step20B Monte Carlo acceleration is not active.")
    _require_false_guards(mc, label="Monte Carlo acceleration")
    mc_guards = mc.get("guardrails") or {}
    for key in (
        "same_pcg64_random_stream",
        "same_latent_gaussian_draws",
        "same_marginal_cdf_tables",
        "same_discrete_count_mapping_required",
    ):
        if mc_guards.get(key) is not True:
            raise WNBAStep21ActivationError(f"Monte Carlo equivalence guard failed: {key}.")
    if mc_guards.get("simulations_modified") is not False:
        raise WNBAStep21ActivationError("Monte Carlo simulation count was modified.")
    if mc_guards.get("batch_size_modified") is not False:
        raise WNBAStep21ActivationError("Monte Carlo batch size was modified.")

    cdf = statuses["monte_carlo_cdf"]
    if cdf.get("installed") is not True or cdf.get("binding_active") is not True:
        raise WNBAStep21ActivationError("Step20B CDF compatibility is not active.")
    _require_false_guards(cdf, label="CDF compatibility")

    cache = statuses["step4w_cache"]
    if cache.get("installed") is not True or cache.get("all_bindings_active") is not True:
        raise WNBAStep21ActivationError("Step20B Step4W cache is not fully active.")
    _require_false_guards(cache, label="Step4W cache")
    cache_guards = cache.get("guardrails") or {}
    if cache_guards.get("cache_scope") != "single_step12b_call_only":
        raise WNBAStep21ActivationError("Step4W cache escaped the single-cycle scope.")
    if cache_guards.get("cached_values_returned_by_deepcopy") is not True:
        raise WNBAStep21ActivationError("Step4W cache deep-copy isolation is not active.")
    if cache_guards.get("raised_exceptions_cached") is not False:
        raise WNBAStep21ActivationError("Step4W cache began caching exceptions.")
    if cache_guards.get("optional_unavailable_results_cached") is not False:
        raise WNBAStep21ActivationError("Step4W cache began caching unavailable optional results.")

    return {
        "step20b_runtime_acceleration_active": True,
        "step20b_optional_workload_active": True,
        "step20b_monte_carlo_acceleration_active": True,
        "step20b_monte_carlo_cdf_compat_active": True,
        "step20b_step4w_cache_active": True,
    }


def validate_live_activation(
    *,
    build: Mapping[str, Any],
    runtime: Mapping[str, Any],
    statuses: Mapping[str, Mapping[str, Any]],
    consumer: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    provider_commit = str(build.get("provider_reported_commit") or "").strip().lower()
    if provider_commit != STEP20B_CANDIDATE_SHA:
        raise WNBAStep21ActivationError(
            f"Live provider commit mismatch: {provider_commit or 'missing'}."
        )
    if build.get("provider_commit_authoritative") is not False:
        raise WNBAStep21ActivationError("Runtime fingerprint provider-authority contract changed.")

    if runtime.get("enabled") is not True or runtime.get("running") is not True:
        raise WNBAStep21ActivationError("Step17B always-on runtime is not running.")
    if runtime.get("role") != "leader" or runtime.get("leadership_acquired") is not True:
        raise WNBAStep21ActivationError("Step17B single-leader ownership is not active.")
    if int(runtime.get("failure_count") or 0) != 0:
        raise WNBAStep21ActivationError("Step17B production failure_count is nonzero.")
    if runtime.get("last_status") != "cycle_completed":
        raise WNBAStep21ActivationError("Latest Step17B cycle is not completed.")
    if int(runtime.get("success_count") or 0) < MIN_SAFE_COMPLETED_CYCLES:
        raise WNBAStep21ActivationError("Not enough safe Step21 production cycles completed.")

    elapsed = completed_cycle_seconds(runtime)
    if elapsed is None:
        raise WNBAStep21ActivationError("Completed cycle timing is unavailable.")
    if elapsed >= MAX_COMPLETED_CYCLE_SECONDS:
        raise WNBAStep21ActivationError(
            f"Completed production cycle exceeded Step20B budget: {elapsed:.3f}s."
        )

    step20b = validate_step20b_statuses(statuses)

    if isinstance(consumer, Mapping):
        nested = consumer.get("runtime") or {}
        if isinstance(nested, Mapping) and nested:
            if nested.get("circuit_state") not in {None, "closed"}:
                raise WNBAStep21ActivationError("WNBA consumer circuit is not closed.")
            if int(nested.get("consecutive_failures") or 0) != 0:
                raise WNBAStep21ActivationError("WNBA consumer has consecutive failures.")
            if nested.get("cycle_outcome") not in {
                None,
                "market_board_not_ready",
                "shadow_board_ready",
                "not_executed",
            }:
                raise WNBAStep21ActivationError("WNBA consumer cycle outcome is unsafe.")

    result = {
        "data_type": "wnba_step21_production_activation_validation",
        "model_version": MODEL_VERSION,
        "candidate_sha": STEP20B_CANDIDATE_SHA,
        "rollback_sha": STEP19N_ROLLBACK_SHA,
        "production_runtime_enabled": True,
        "production_role": runtime.get("role"),
        "success_count": int(runtime.get("success_count") or 0),
        "failure_count": int(runtime.get("failure_count") or 0),
        "latest_completed_cycle_seconds": elapsed,
        "certified_simulations": CERTIFIED_SIMULATIONS,
        "certified_batch_size": CERTIFIED_BATCH_SIZE,
        "projection_math_modified": False,
        "readiness_relaxed": False,
        "sportsbook_transport_modified": False,
        "persistence_behavior_modified": False,
        "wagering_enabled": False,
        **step20b,
    }
    return deepcopy(result)


__all__ = [
    "CERTIFIED_BATCH_SIZE",
    "CERTIFIED_SIMULATIONS",
    "MAX_COMPLETED_CYCLE_SECONDS",
    "MIN_SAFE_COMPLETED_CYCLES",
    "MODEL_VERSION",
    "SOURCE",
    "STEP19N_ROLLBACK_SHA",
    "STEP20B_CANDIDATE_SHA",
    "STEP20B_RUNTIME_BLOBS",
    "WNBAStep21ActivationError",
    "completed_cycle_seconds",
    "validate_live_activation",
    "validate_step20b_statuses",
]
