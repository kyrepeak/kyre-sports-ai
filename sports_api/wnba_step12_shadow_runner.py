"""WNBA Step 12A: deployment-ready one-shot shadow runner over frozen Step 11E.

This is an external execution boundary, not a scheduler. A caller supplies one versioned
JSON request and receives one versioned JSON response. The runner may invoke exactly one
frozen Step-11E controlled-automation tick. It does not persist state, start a background
worker, expose a public FastAPI route, mutate Supabase, enable production, authenticate to
a sportsbook, use cookies, or perform a wager action.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime, timezone
import hashlib
import json
import os
from typing import Any

from sports_api import wnba_step11_controlled_automation as step11e
from sports_api import wnba_step11_release_freeze as release

SOURCE = "Kyre Sports API WNBA Step 12A deployment-ready shadow runner"
SCHEMA_VERSION = "wnba_step_12a_shadow_runner_v1"
REQUEST_SCHEMA_VERSION = "wnba_step_12a_shadow_runner_request_v1"
MODEL_VERSION = "wnba_step12a_external_one_shot_shadow_runner_2026_regular_v1"
RELEASE_ID = release.RELEASE_ID
STEP11E_FROZEN_SHA = "f96d580e398aaa199c424e3b70b7a8f1386a8452"
STEP12A_SHADOW_RUNNER_ENABLED_ENV = "WNBA_STEP12A_SHADOW_RUNNER_ENABLED"

DEFAULT_ENABLED = False
PRODUCTION_ACTIVATION_ALLOWED = False
BACKGROUND_SCHEDULER_ALLOWED = False
PERSISTENCE_ALLOWED = False
SUPABASE_WRITE_ALLOWED = False
PUBLIC_FASTAPI_ACTIVATION_ALLOWED = False
WAGERING_ALLOWED = False

_FORBIDDEN_TRUE_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
    "WNBA_PERSISTENCE_ENABLED",
    "WNBA_SUPABASE_WRITE_ENABLED",
    "WNBA_WAGERING_ENABLED",
    "WNBA_PUBLIC_STEP11E_FASTAPI_ENABLED",
    "WNBA_STEP12_SCHEDULER_ENABLED",
)

_REQUEST_REQUIRED_FIELDS = {
    "data_type",
    "schema_version",
    "season",
    "slate_date",
    "step8_distributions",
}
_REQUEST_OPTIONAL_FIELDS = {
    "evaluated_at_utc",
    "previous_state",
    "policy",
    "request_content_sha256",
}
_POLICY_FIELDS = {
    "refresh_interval_seconds",
    "failure_threshold",
    "circuit_cooldown_seconds",
    "provider_attempts",
}

_UNSAFE_DOWNSTREAM_FALSE_GUARDS = (
    "background_scheduler_started",
    "sleep_performed",
    "state_persisted",
    "public_fastapi_route_added",
    "supabase_mutated",
    "persistence_mutated",
    "production_runtime_enabled",
    "production_activation_allowed",
    "wager_action_performed",
    "authentication_used",
    "cookies_used",
    "paid_odds_vendor_used",
    "basketball_projection_changed",
    "step8_distribution_changed",
)


class WNBAStep12ShadowRunnerDisabledError(RuntimeError):
    """Raised when the one-shot shadow runner is not isolated behind every safety gate."""


class WNBAStep12ShadowRunnerInputError(ValueError):
    """Raised when the external request envelope is malformed."""


class WNBAStep12ShadowRunnerIntegrityError(ValueError):
    """Raised when request or downstream frozen-lineage integrity fails."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step12a_shadow_runner_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP12A_SHADOW_RUNNER_ENABLED_ENV))


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _assert_safe_environment(env: Mapping[str, str] | None = None) -> None:
    source = os.environ if env is None else env
    if not step12a_shadow_runner_enabled(source):
        raise WNBAStep12ShadowRunnerDisabledError(
            f"Step 12A requires {STEP12A_SHADOW_RUNNER_ENABLED_ENV}=true."
        )
    if not step11e.step11e_controlled_automation_enabled(source):
        raise WNBAStep12ShadowRunnerDisabledError(
            f"Step 12A requires {release.STEP11E_CONTROLLED_AUTOMATION_ENABLED_ENV}=true."
        )
    bad = [name for name in _FORBIDDEN_TRUE_ENV_KEYS if _truthy(source.get(name))]
    if bad:
        raise WNBAStep12ShadowRunnerDisabledError(
            "Step 12A refuses production/scheduler/persistence/write switches: "
            + ", ".join(bad)
        )
    safety_constants = {
        "Step11 default": release.DEFAULT_ENABLED,
        "Step11 production": release.PRODUCTION_ACTIVATION_ALLOWED,
        "Step11 scheduler": release.BACKGROUND_SCHEDULER_ALLOWED,
        "Step11 persistence": release.PERSISTENCE_ALLOWED,
        "Step11 Supabase write": release.SUPABASE_WRITE_ALLOWED,
        "Step11 public FastAPI": release.PUBLIC_FASTAPI_ACTIVATION_ALLOWED,
        "Step11 wagering": release.WAGERING_ALLOWED,
        "Step12 default": DEFAULT_ENABLED,
        "Step12 production": PRODUCTION_ACTIVATION_ALLOWED,
        "Step12 scheduler": BACKGROUND_SCHEDULER_ALLOWED,
        "Step12 persistence": PERSISTENCE_ALLOWED,
        "Step12 Supabase write": SUPABASE_WRITE_ALLOWED,
        "Step12 public FastAPI": PUBLIC_FASTAPI_ACTIVATION_ALLOWED,
        "Step12 wagering": WAGERING_ALLOWED,
    }
    enabled = [name for name, value in safety_constants.items() if value is not False]
    if enabled:
        raise WNBAStep12ShadowRunnerDisabledError(
            "Step 12A safety constant drift: " + ", ".join(enabled)
        )


def _strict_season(value: Any) -> int:
    if isinstance(value, bool):
        raise WNBAStep12ShadowRunnerInputError("Step 12A season must be integer 2026.")
    try:
        season = int(value)
    except (TypeError, ValueError) as exc:
        raise WNBAStep12ShadowRunnerInputError(
            "Step 12A season must be integer 2026."
        ) from exc
    if season != release.SEASON or str(season) != str(value).strip():
        raise WNBAStep12ShadowRunnerInputError(
            "Step 12A is certified for the 2026 Regular Season only."
        )
    return season


def _strict_slate_date(value: Any) -> str:
    text = str(value or "").strip()
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise WNBAStep12ShadowRunnerInputError(
            "Step 12A slate_date must be YYYY-MM-DD."
        ) from exc
    if parsed.isoformat() != text:
        raise WNBAStep12ShadowRunnerInputError(
            "Step 12A slate_date must be canonical YYYY-MM-DD."
        )
    return text


def _evaluated_at(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        result = value
    else:
        text = str(value).strip()
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        try:
            result = datetime.fromisoformat(text)
        except ValueError as exc:
            raise WNBAStep12ShadowRunnerInputError(
                "Step 12A evaluated_at_utc must be ISO-8601 with timezone."
            ) from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise WNBAStep12ShadowRunnerInputError(
            "Step 12A evaluated_at_utc must be timezone-aware."
        )
    return result.astimezone(timezone.utc)


def _validate_request(request: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(request, Mapping):
        raise WNBAStep12ShadowRunnerInputError("Step 12A request must be a JSON object.")
    keys = set(request)
    missing = _REQUEST_REQUIRED_FIELDS - keys
    unknown = keys - _REQUEST_REQUIRED_FIELDS - _REQUEST_OPTIONAL_FIELDS
    if missing:
        raise WNBAStep12ShadowRunnerInputError(
            "Step 12A request missing fields: " + ", ".join(sorted(missing))
        )
    if unknown:
        raise WNBAStep12ShadowRunnerInputError(
            "Step 12A request has unknown fields: " + ", ".join(sorted(unknown))
        )
    if request.get("data_type") != "wnba_step12a_shadow_runner_request":
        raise WNBAStep12ShadowRunnerInputError("Step 12A request data_type mismatch.")
    if request.get("schema_version") != REQUEST_SCHEMA_VERSION:
        raise WNBAStep12ShadowRunnerInputError("Step 12A request schema_version mismatch.")

    request_hash = request.get("request_content_sha256")
    surface = {k: v for k, v in request.items() if k != "request_content_sha256"}
    canonical_hash = _canonical_hash(surface)
    if request_hash is not None and request_hash != canonical_hash:
        raise WNBAStep12ShadowRunnerIntegrityError(
            "Step 12A request content hash mismatch."
        )

    distributions = request.get("step8_distributions")
    if (
        isinstance(distributions, (str, bytes))
        or not isinstance(distributions, Sequence)
        or not distributions
        or any(not isinstance(item, Mapping) for item in distributions)
    ):
        raise WNBAStep12ShadowRunnerInputError(
            "Step 12A step8_distributions must be a non-empty JSON array of objects."
        )

    previous_state = request.get("previous_state")
    if previous_state is not None and not isinstance(previous_state, Mapping):
        raise WNBAStep12ShadowRunnerInputError(
            "Step 12A previous_state must be null or an object."
        )

    policy = request.get("policy") or {}
    if not isinstance(policy, Mapping):
        raise WNBAStep12ShadowRunnerInputError("Step 12A policy must be an object.")
    unknown_policy = set(policy) - _POLICY_FIELDS
    if unknown_policy:
        raise WNBAStep12ShadowRunnerInputError(
            "Step 12A policy has unknown fields: " + ", ".join(sorted(unknown_policy))
        )

    return {
        "season": _strict_season(request.get("season")),
        "slate_date": _strict_slate_date(request.get("slate_date")),
        "step8_distributions": list(distributions),
        "previous_state": dict(previous_state) if previous_state is not None else None,
        "evaluated_at": _evaluated_at(request.get("evaluated_at_utc")),
        "policy": dict(policy),
        "request_content_sha256": canonical_hash,
    }


def build_step12a_request(
    *,
    season: int,
    slate_date: str,
    step8_distributions: Sequence[Mapping[str, Any]],
    previous_state: Mapping[str, Any] | None = None,
    evaluated_at: datetime | str | None = None,
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a canonical external request envelope with a tamper-evident content hash."""
    request: dict[str, Any] = {
        "data_type": "wnba_step12a_shadow_runner_request",
        "schema_version": REQUEST_SCHEMA_VERSION,
        "season": season,
        "slate_date": slate_date,
        "step8_distributions": list(step8_distributions),
        "evaluated_at_utc": (
            evaluated_at.isoformat() if isinstance(evaluated_at, datetime) else evaluated_at
        ),
        "previous_state": dict(previous_state) if previous_state is not None else None,
        "policy": dict(policy or {}),
    }
    request["request_content_sha256"] = _canonical_hash(request)
    _validate_request(request)
    return request


def _assert_frozen_tick(tick: Mapping[str, Any]) -> None:
    if not isinstance(tick, Mapping):
        raise WNBAStep12ShadowRunnerIntegrityError(
            "Step 12A downstream Step 11E tick must be an object."
        )
    lineage = tick.get("lineage")
    expected_lineage = {
        "step11_release_id": release.RELEASE_ID,
        "step11a_frozen_sha": release.STEP11A_FROZEN_SHA,
        "step11b_frozen_sha": release.STEP11B_FROZEN_SHA,
        "step11c_frozen_sha": release.STEP11C_FROZEN_SHA,
        "step11d_frozen_sha": release.STEP11D_FROZEN_SHA,
        "step10_frozen_sha": release.STEP10_FROZEN_SHA,
        "step9_frozen_sha": release.STEP9_FROZEN_SHA,
        "step8_frozen_sha": release.STEP8_FROZEN_SHA,
    }
    if lineage != expected_lineage:
        raise WNBAStep12ShadowRunnerIntegrityError(
            "Step 12A downstream frozen lineage mismatch."
        )
    guardrails = tick.get("guardrails")
    if not isinstance(guardrails, Mapping):
        raise WNBAStep12ShadowRunnerIntegrityError(
            "Step 12A downstream Step 11E guardrails missing."
        )
    if guardrails.get("caller_driven_tick_only") is not True:
        raise WNBAStep12ShadowRunnerIntegrityError(
            "Step 12A requires caller-driven Step 11E tick semantics."
        )
    for key in _UNSAFE_DOWNSTREAM_FALSE_GUARDS:
        if guardrails.get(key) is not False:
            raise WNBAStep12ShadowRunnerIntegrityError(
                f"Step 12A downstream safety guard drift: {key}."
            )


def run_step12a_shadow_job(
    request: Mapping[str, Any],
    *,
    env: Mapping[str, str] | None = None,
    tick_runner: Callable[..., Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run exactly one externally-invoked Step 12A job and at most one frozen Step 11E tick."""
    _assert_safe_environment(env)
    normalized = _validate_request(request)
    runner = step11e.run_step11e_controlled_automation_tick if tick_runner is None else tick_runner
    policy = normalized["policy"]

    tick = runner(
        season=normalized["season"],
        slate_date=normalized["slate_date"],
        step8_distributions=normalized["step8_distributions"],
        previous_state=normalized["previous_state"],
        evaluated_at=normalized["evaluated_at"],
        refresh_interval_seconds=policy.get(
            "refresh_interval_seconds", step11e.DEFAULT_REFRESH_INTERVAL_SECONDS
        ),
        failure_threshold=policy.get(
            "failure_threshold", step11e.DEFAULT_FAILURE_THRESHOLD
        ),
        circuit_cooldown_seconds=policy.get(
            "circuit_cooldown_seconds", step11e.DEFAULT_CIRCUIT_COOLDOWN_SECONDS
        ),
        provider_attempts=policy.get(
            "provider_attempts", step11e.step11d.DEFAULT_PROVIDER_ATTEMPTS
        ),
        env=env,
    )
    _assert_frozen_tick(tick)
    _assert_safe_environment(env)

    automation_state = tick.get("automation_state")
    execution = tick.get("execution") or {}
    response = {
        "data_type": "wnba_step12a_shadow_runner_response",
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "release_id": RELEASE_ID,
        "step11e_frozen_sha": STEP11E_FROZEN_SHA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "request_content_sha256": normalized["request_content_sha256"],
        "status": tick.get("status"),
        "health": tick.get("health"),
        "execution_summary": {
            "cycle_due": execution.get("cycle_due"),
            "cycle_executed": execution.get("cycle_executed"),
            "cycle_outcome": execution.get("cycle_outcome"),
            "skip_reason": execution.get("skip_reason"),
            "half_open_probe": execution.get("half_open_probe"),
            "controller_content_sha256": tick.get("controller_content_sha256"),
            "state_content_sha256": (
                automation_state.get("state_content_sha256")
                if isinstance(automation_state, Mapping)
                else None
            ),
        },
        "automation_state": automation_state,
        "shadow_board_result": tick.get("shadow_board_result"),
        "step11e_tick": tick,
        "lineage": {
            "step11e_frozen_sha": STEP11E_FROZEN_SHA,
            **dict(tick["lineage"]),
        },
        "guardrails": {
            "shadow_only": True,
            "external_execution_surface": True,
            "stdin_stdout_cli_supported": True,
            "single_job_invocation_only": True,
            "single_step11e_tick_maximum": True,
            "caller_resupplies_state": True,
            "scheduler_started": False,
            "background_worker_started": False,
            "sleep_performed": False,
            "state_persisted": False,
            "public_fastapi_route_added": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "production_runtime_enabled": False,
            "production_activation_allowed": False,
            "wager_action_performed": False,
            "authentication_used": False,
            "cookies_used": False,
            "paid_odds_vendor_used": False,
            "basketball_projection_changed": False,
            "step8_distribution_changed": False,
        },
    }
    hash_surface = {
        "data_type": response["data_type"],
        "schema_version": response["schema_version"],
        "release_id": response["release_id"],
        "step11e_frozen_sha": response["step11e_frozen_sha"],
        "request_content_sha256": response["request_content_sha256"],
        "status": response["status"],
        "health": response["health"],
        "execution_summary": response["execution_summary"],
        "lineage": response["lineage"],
        "guardrails": response["guardrails"],
    }
    response["runner_content_sha256"] = _canonical_hash(hash_surface)
    return response
