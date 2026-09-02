"""WNBA Step 11B: one-shot network refresh orchestration into frozen Step 10.

Step 11A owns the read-only DraftKings connector. Step 11B executes that connector
with a bounded immediate retry policy, converts real connector outcomes into the
exact caller-supplied attempt shape expected by frozen Step 10D, then delegates
freshness/reconciliation/last-good decisions to the frozen Step-10 controller.

This is deliberately *not* a scheduler. It never sleeps, loops forever, persists
state, writes Supabase, calls Step 9, enables production, or changes projections.
A caller must explicitly invoke one refresh cycle.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import json
import math
import os
import re
from typing import Any

from sports_api import wnba_step10_refresh_controller as step10d
from sports_api import wnba_step10_release_freeze as step10_freeze
from sports_api import wnba_step11_draftkings_provider as step11a

SOURCE = "Kyre Sports API WNBA Step 11B one-shot network refresh orchestrator"
SCHEMA_VERSION = "wnba_step_11b_network_refresh_orchestrator_v1"
MODEL_VERSION = "wnba_step11b_bounded_provider_refresh_to_step10d_2026_regular_v1"
RELEASE_ID = "wnba_step11b_network_refresh_orchestrator_2026_regular_season_v1"
STEP11B_NETWORK_REFRESH_ENABLED_ENV = "WNBA_STEP11B_NETWORK_REFRESH_ENABLED"
STEP11A_FROZEN_HEAD_SHA = "695e7b45bd74fcb70c4f4fa6a886b4a054d06810"
STEP10_FROZEN_HEAD_SHA = "4341d178aa65806e9bc001c8759eccb4a003ea63"

DEFAULT_PROVIDER_ATTEMPTS = 3
MAX_PROVIDER_ATTEMPTS = 5
MAX_ERROR_CODE_LENGTH = step10d.MAX_ERROR_CODE_LENGTH
_PROVIDER_ERROR_RE = re.compile(r"[^A-Za-z0-9_.:-]+")

_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


class WNBAStep11NetworkRefreshDisabledError(RuntimeError):
    """Raised when the one-shot network orchestrator is not safely enabled."""


class WNBAStep11NetworkRefreshInputError(ValueError):
    """Raised for malformed orchestration policy or unsafe connector output."""


class WNBAStep11NetworkRefreshIntegrityError(ValueError):
    """Raised when the frozen Step-11A connector result fails lineage/hash checks."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step11b_network_refresh_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP11B_NETWORK_REFRESH_ENABLED_ENV))


def _assert_safe_environment(env: Mapping[str, str] | None = None) -> None:
    source = os.environ if env is None else env
    bad = [name for name in _OFF_ENV_KEYS if _truthy(source.get(name))]
    if bad:
        raise WNBAStep11NetworkRefreshDisabledError(
            "Step 11B refuses production/scheduler/sync switches: " + ", ".join(bad)
        )
    if not _truthy(source.get(STEP11B_NETWORK_REFRESH_ENABLED_ENV)):
        raise WNBAStep11NetworkRefreshDisabledError(
            f"Step 11B requires {STEP11B_NETWORK_REFRESH_ENABLED_ENV}=true."
        )
    if not step11a.step11a_draftkings_provider_enabled(source):
        raise WNBAStep11NetworkRefreshDisabledError(
            "Step 11B requires the frozen Step-11A DraftKings provider gate."
        )
    if not step10d.step10d_refresh_controller_enabled(source):
        raise WNBAStep11NetworkRefreshDisabledError(
            "Step 11B requires the frozen Step-10D refresh-controller gate."
        )
    if step10_freeze.DEFAULT_ENABLED is not False:
        raise WNBAStep11NetworkRefreshDisabledError(
            "Step 11B requires frozen Step 10 to remain default-OFF."
        )
    if step10_freeze.PRODUCTION_ACTIVATION_ALLOWED is not False:
        raise WNBAStep11NetworkRefreshDisabledError(
            "Step 11B requires frozen Step 10 production activation to remain disallowed."
        )
    if step11a.STEP10_FROZEN_SHA != STEP10_FROZEN_HEAD_SHA:
        raise WNBAStep11NetworkRefreshDisabledError("Step 11A frozen Step-10 lineage drift.")


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _evaluation_time(value: datetime | None) -> datetime:
    result = datetime.now(timezone.utc) if value is None else value
    if result.tzinfo is None or result.utcoffset() is None:
        raise WNBAStep11NetworkRefreshInputError(
            "WNBA Step 11B evaluated_at must be timezone-aware."
        )
    return result.astimezone(timezone.utc)


def _positive_int(value: Any, label: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise WNBAStep11NetworkRefreshInputError(f"WNBA Step 11B {label} must be an integer.")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise WNBAStep11NetworkRefreshInputError(
            f"WNBA Step 11B {label} must be an integer."
        ) from exc
    if isinstance(value, float) and not value.is_integer():
        raise WNBAStep11NetworkRefreshInputError(f"WNBA Step 11B {label} must be an integer.")
    if not minimum <= result <= maximum:
        raise WNBAStep11NetworkRefreshInputError(
            f"WNBA Step 11B {label} must be from {minimum} through {maximum}."
        )
    return result


def _error_code(exc: Exception) -> str:
    text = type(exc).__name__
    text = _PROVIDER_ERROR_RE.sub("_", text).strip("_") or "provider_error"
    return text[:MAX_ERROR_CODE_LENGTH]


def _verify_step11a_bridge(bridge: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(bridge, Mapping):
        raise WNBAStep11NetworkRefreshIntegrityError("Step 11A connector result must be an object.")
    expected = {
        "data_type": "wnba_step11a_draftkings_provider_bridge",
        "schema_version": step11a.SCHEMA_VERSION,
        "model_version": step11a.MODEL_VERSION,
        "release_id": step11a.RELEASE_ID,
        "provider": step11a.PROVIDER,
    }
    for key, value in expected.items():
        if bridge.get(key) != value:
            raise WNBAStep11NetworkRefreshIntegrityError(
                f"Frozen Step-11A connector {key} drift."
            )
    lineage = bridge.get("lineage") or {}
    if lineage.get("step10_frozen_git_sha") != STEP10_FROZEN_HEAD_SHA:
        raise WNBAStep11NetworkRefreshIntegrityError("Step-11A connector Step-10 lineage drift.")
    if lineage.get("step10b_frozen_git_sha") != step10_freeze.STEP10B_FROZEN_SHA:
        raise WNBAStep11NetworkRefreshIntegrityError("Step-11A connector Step-10B lineage drift.")
    guardrails = bridge.get("guardrails") or {}
    required_false = (
        "authentication_used",
        "cookies_used",
        "wager_action_performed",
        "paid_odds_vendor_used",
        "basketball_projection_changed",
        "step8_distribution_changed",
        "supabase_mutated",
        "persistence_mutated",
        "scheduler_started",
        "production_runtime_enabled",
        "production_activation_allowed",
    )
    if not all(guardrails.get(key) is False for key in required_false):
        raise WNBAStep11NetworkRefreshIntegrityError(
            "Step-11A connector safety guardrail drift."
        )
    if guardrails.get("sportsbook_network_fetch_performed") is not True:
        raise WNBAStep11NetworkRefreshIntegrityError(
            "Step 11B requires a live-wrapper Step-11A result that records sportsbook GET execution."
        )
    if guardrails.get("sportsbook_http_methods") != ["GET"]:
        raise WNBAStep11NetworkRefreshIntegrityError(
            "Step 11B accepts GET-only Step-11A sportsbook transport."
        )
    surface = {
        key: value for key, value in bridge.items()
        if key not in {"generated_at_utc", "provider_bridge_content_sha256"}
    }
    if bridge.get("provider_bridge_content_sha256") != _canonical_hash(surface):
        raise WNBAStep11NetworkRefreshIntegrityError(
            "Step-11A connector content hash mismatch."
        )
    provider_refresh = bridge.get("provider_refresh")
    if not isinstance(provider_refresh, Mapping):
        raise WNBAStep11NetworkRefreshIntegrityError(
            "Step-11A connector omitted provider_refresh."
        )
    if set(provider_refresh) != {"provider", "adapter_type", "attempts"}:
        raise WNBAStep11NetworkRefreshIntegrityError(
            "Step-11A provider_refresh shape drift."
        )
    if provider_refresh.get("provider") != step11a.PROVIDER:
        raise WNBAStep11NetworkRefreshIntegrityError("Step-11A provider identity drift.")
    if provider_refresh.get("adapter_type") != step11a.ADAPTER_TYPE:
        raise WNBAStep11NetworkRefreshIntegrityError("Step-11A adapter type drift.")
    attempts = provider_refresh.get("attempts")
    if not isinstance(attempts, list) or len(attempts) != 1:
        raise WNBAStep11NetworkRefreshIntegrityError(
            "Step-11A successful bridge must contain exactly one Step-10 success attempt."
        )
    attempt = attempts[0]
    if not isinstance(attempt, Mapping) or attempt.get("ok") is not True or "payload" not in attempt:
        raise WNBAStep11NetworkRefreshIntegrityError(
            "Step-11A successful bridge contains malformed Step-10 payload attempt."
        )
    return dict(attempt["payload"])


def _refresh_options(refresh_policy: Mapping[str, Any] | None) -> dict[str, Any]:
    options = dict(refresh_policy or {})
    allowed = {
        "refresh_interval_seconds",
        "retry_base_seconds",
        "retry_multiplier",
        "retry_max_seconds",
        "allow_last_good_fallback",
        "max_last_good_age_seconds",
        "max_quote_age_seconds",
        "max_market_sync_seconds",
        "max_board_sync_seconds",
        "require_board_synchronized",
    }
    unknown = sorted(set(options) - allowed)
    if unknown:
        raise WNBAStep11NetworkRefreshInputError(
            "Unknown Step-11B refresh policy fields: " + ", ".join(unknown)
        )
    return options


def run_step11b_network_refresh_cycle(
    *,
    season: int,
    slate_date: str,
    evaluated_at: datetime | None = None,
    cycle_started_at: datetime | None = None,
    provider_attempts: int = DEFAULT_PROVIDER_ATTEMPTS,
    last_good_snapshot: Mapping[str, Any] | None = None,
    expected_sportsbooks: Sequence[str] | None = None,
    refresh_policy: Mapping[str, Any] | None = None,
    provider_fetcher: Callable[..., Mapping[str, Any]] | None = None,
    provider_requester: Callable[..., Any] | None = None,
    roster_loader: Callable[[int], Mapping[str, Any]] | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Execute one bounded real-provider refresh and hand its attempts to frozen Step 10D.

    Retry attempts are immediate: Step 11B intentionally performs no sleep. The
    frozen Step-10D controller still records retry/backoff metadata and owns
    last-good/freshness/synchronization behavior.
    """
    _assert_safe_environment(env)
    evaluated = _evaluation_time(evaluated_at)
    attempts_limit = _positive_int(
        provider_attempts,
        "provider_attempts",
        minimum=1,
        maximum=MAX_PROVIDER_ATTEMPTS,
    )
    options = _refresh_options(refresh_policy)
    fetcher = provider_fetcher or step11a.fetch_step11a_draftkings_provider_bridge

    attempt_rows: list[dict[str, Any]] = []
    bridge: Mapping[str, Any] | None = None
    success_payload: dict[str, Any] | None = None
    retryable_failures = 0

    for attempt_number in range(1, attempts_limit + 1):
        try:
            candidate = fetcher(
                season=int(season),
                slate_date=str(slate_date),
                evaluated_at=evaluated,
                requester=provider_requester,
                roster_loader=roster_loader,
                env=env,
            )
            payload = _verify_step11a_bridge(candidate)
        except (
            step11a.WNBAStep11DraftKingsProviderUpstreamError,
            step11a.WNBAStep11DraftKingsProviderNotReadyError,
        ) as exc:
            retryable_failures += 1
            attempt_rows.append({"ok": False, "error_code": _error_code(exc)})
            continue
        except (
            step11a.WNBAStep11DraftKingsProviderDisabledError,
            step11a.WNBAStep11DraftKingsProviderIdentityError,
            WNBAStep11NetworkRefreshIntegrityError,
            ValueError,
        ):
            # Identity/configuration/integrity failures must never be hidden as a
            # transient provider outage or silently converted into last-good fallback.
            raise
        bridge = candidate
        success_payload = payload
        attempt_rows.append({"ok": True, "payload": payload})
        break

    provider_refresh = {
        "provider": step11a.PROVIDER,
        "adapter_type": step11a.ADAPTER_TYPE,
        "attempts": attempt_rows,
    }

    cycle = step10d.run_step10d_refresh_cycle(
        [provider_refresh],
        evaluated_at=evaluated,
        cycle_started_at=cycle_started_at,
        last_good_snapshot=last_good_snapshot,
        expected_sportsbooks=(expected_sportsbooks if expected_sportsbooks is not None else [step11a.PROVIDER]),
        max_attempts_per_provider=attempts_limit,
        env=env,
        **options,
    )

    result = {
        "data_type": "wnba_step11b_network_refresh_orchestration",
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "release_id": RELEASE_ID,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "evaluated_at_utc": evaluated.isoformat(),
        "provider": step11a.PROVIDER,
        "network_refresh": {
            "attempt_limit": attempts_limit,
            "attempts_executed": len(attempt_rows),
            "retryable_failures": retryable_failures,
            "succeeded": success_payload is not None,
            "sleep_performed": False,
            "scheduler_invoked": False,
            "step11a_provider_bridge_content_sha256": (
                bridge.get("provider_bridge_content_sha256") if bridge is not None else None
            ),
            "step11a_step10b_adapter_content_sha256": (
                bridge.get("step10_validation", {}).get("adapter_content_sha256")
                if bridge is not None else None
            ),
        },
        "provider_refresh": provider_refresh,
        "step10d_cycle": cycle,
        "lineage": {
            "step11a_release_id": step11a.RELEASE_ID,
            "step11a_schema_version": step11a.SCHEMA_VERSION,
            "step11a_model_version": step11a.MODEL_VERSION,
            "step11a_frozen_head_sha": STEP11A_FROZEN_HEAD_SHA,
            "step10_frozen_head_sha": STEP10_FROZEN_HEAD_SHA,
            "step10d_release_id": step10d.RELEASE_ID,
            "step10d_schema_version": step10d.SCHEMA_VERSION,
            "step10d_model_version": step10d.MODEL_VERSION,
            "step10d_frozen_head_sha": step10_freeze.STEP10D_FROZEN_SHA,
            "refresh_cycle_id": cycle.get("refresh_cycle_id"),
            "refresh_cycle_content_sha256": cycle.get("refresh_cycle_content_sha256"),
            "served_step10c_snapshot_content_sha256": (
                cycle.get("lineage", {}).get("served_step10c_snapshot_content_sha256")
            ),
        },
        "guardrails": {
            "sportsbook_network_fetch_attempted": True,
            "sportsbook_network_fetch_performed": success_payload is not None,
            "sportsbook_http_methods": ["GET"],
            "authentication_used": False,
            "cookies_used": False,
            "wager_action_performed": False,
            "paid_odds_vendor_used": False,
            "retry_sleep_performed": False,
            "scheduler_started": False,
            "step9_called": False,
            "basketball_projection_changed": False,
            "step8_distribution_changed": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "production_runtime_enabled": False,
            "production_activation_allowed": False,
        },
    }
    surface = {
        key: value for key, value in result.items()
        if key not in {"generated_at_utc", "orchestration_content_sha256"}
    }
    result["orchestration_content_sha256"] = _canonical_hash(surface)
    _assert_safe_environment(env)
    return result
