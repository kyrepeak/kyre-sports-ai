"""WNBA Step 12B: live market-driven runtime assembly over frozen Step 12A.

Step 12A proved that an external caller can safely execute one frozen Step-11E
shadow tick when Step-8 distributions are supplied. Step 12B removes that manual
Step-8 handoff.

One caller-driven Step-12B job now:
  1. performs one bounded current DraftKings discovery and one bounded current
     FanDuel discovery through the already-certified Step-11A/11C GET-only bridges;
  2. identifies only exact same-line two-book market groups using official
     WNBA game/player identities already reconciled by those frozen bridges;
  3. automatically builds the frozen 5,000,000-draw Step-8A -> 8B -> 8C -> 8D
     probability distribution for each unique player needed by those groups;
  4. passes those distributions into frozen Step 12A; and
  5. reuses the already-fetched provider bridges inside the Step-11E/11D tick,
     so sportsbook discovery is not performed twice.

This module is still shadow-only and caller-driven. It does not start a scheduler,
persist controller state, mutate Supabase, expose a public FastAPI route, enable
production runtime, authenticate to a sportsbook, use cookies, or perform a wager.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
import json
import math
import os
from typing import Any

from sports_api import wnba_step11_controlled_automation as step11e
from sports_api import wnba_step11_draftkings_provider as draftkings
from sports_api import wnba_step11_fanduel_provider as fanduel
from sports_api import wnba_step11_multibook_shadow_board as step11d
from sports_api import wnba_step11_release_freeze as release
from sports_api import wnba_step12_shadow_runner as step12a
from sports_api import wnba_step8_context_adjustment as step8c
from sports_api import wnba_step8_core_projection as step8core
from sports_api import wnba_step8_joint_monte_carlo as step8d
from sports_api import wnba_step8_official_box_baseline as step8b
from sports_api import wnba_step8_projection_handoff as step8a

SOURCE = "Kyre Sports API WNBA Step 12B live market-driven runtime assembly"
SCHEMA_VERSION = "wnba_step_12b_live_runtime_assembly_v1"
REQUEST_SCHEMA_VERSION = "wnba_step_12b_live_runtime_request_v1"
MODEL_VERSION = "wnba_step12b_market_discovery_step8_assembly_shadow_2026_regular_v1"
STEP12A_FROZEN_SHA = "4523abb8b230e8e29d9f9d298232dfb8948fc883"
STEP11E_FROZEN_SHA = step12a.STEP11E_FROZEN_SHA
STEP8_FROZEN_SHA = release.STEP8_FROZEN_SHA
STEP12B_LIVE_RUNTIME_ASSEMBLY_ENABLED_ENV = "WNBA_STEP12B_LIVE_RUNTIME_ASSEMBLY_ENABLED"

DEFAULT_ENABLED = False
PRODUCTION_ACTIVATION_ALLOWED = False
BACKGROUND_SCHEDULER_ALLOWED = False
PERSISTENCE_ALLOWED = False
SUPABASE_WRITE_ALLOWED = False
PUBLIC_FASTAPI_ACTIVATION_ALLOWED = False
WAGERING_ALLOWED = False

CERTIFIED_SIMULATIONS = step8d.DEFAULT_SIMULATIONS
CERTIFIED_BATCH_SIZE = step8d.DEFAULT_BATCH_SIZE
MAX_PROJECTION_TARGETS = 120

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

_REQUIRED_TRUE_ENV_KEYS = (
    "WNBA_STEP12A_SHADOW_RUNNER_ENABLED",
    "WNBA_STEP11E_CONTROLLED_AUTOMATION_ENABLED",
    "WNBA_STEP11D_MULTIBOOK_SHADOW_ENABLED",
    "WNBA_STEP11C_FANDUEL_PROVIDER_ENABLED",
    "WNBA_STEP11B_NETWORK_REFRESH_ENABLED",
    "WNBA_STEP11A_DRAFTKINGS_PROVIDER_ENABLED",
    "WNBA_STEP10_FASTAPI_ENABLED",
    "WNBA_STEP10A_LIVE_MARKET_INPUT_ENABLED",
    "WNBA_STEP10B_MARKET_ADAPTER_ENABLED",
    "WNBA_STEP10C_MARKET_SNAPSHOT_ENABLED",
    "WNBA_STEP10D_REFRESH_CONTROLLER_ENABLED",
    "WNBA_STEP9_FASTAPI_ENABLED",
    "WNBA_STEP9_THRESHOLD_PRICING_ENABLED",
    "WNBA_STEP9B_MARKET_COMPARISON_ENABLED",
    "WNBA_STEP9C_MULTIBOOK_CONSENSUS_ENABLED",
    "WNBA_STEP9D_QUALIFICATION_RANKING_ENABLED",
    "WNBA_STEP8_PROJECTION_HANDOFF_ENABLED",
    "WNBA_STEP8_CORE_PROJECTION_ENABLED",
    "WNBA_STEP8_CONTEXT_ADJUSTMENT_ENABLED",
    "WNBA_STEP8_MONTE_CARLO_ENABLED",
    "WNBA_STEP7G_FIRST_PARTY_ENABLED",
)

_REQUEST_REQUIRED_FIELDS = {
    "data_type",
    "schema_version",
    "season",
    "slate_date",
}
_REQUEST_OPTIONAL_FIELDS = {
    "evaluated_at_utc",
    "previous_state",
    "controller_policy",
    "refresh_policy",
    "qualification_policy",
    "request_content_sha256",
}
_CONTROLLER_POLICY_FIELDS = {
    "refresh_interval_seconds",
    "failure_threshold",
    "circuit_cooldown_seconds",
    "provider_attempts",
}

_UNSAFE_RESPONSE_FALSE_GUARDS = (
    "scheduler_started",
    "background_worker_started",
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
    "basketball_model_modified",
    "step8_distribution_modified_after_generation",
)


class WNBAStep12LiveRuntimeDisabledError(RuntimeError):
    """Raised when Step 12B is not isolated behind every required safety gate."""


class WNBAStep12LiveRuntimeInputError(ValueError):
    """Raised when the Step-12B request or bounded policy is malformed."""


class WNBAStep12LiveRuntimeIntegrityError(ValueError):
    """Raised when frozen bridge/distribution/lineage integrity fails."""


class WNBAStep12LiveRuntimeNotReadyError(RuntimeError):
    """Raised when the current market/projection slate cannot form a shadow board."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step12b_live_runtime_assembly_enabled(
    env: Mapping[str, str] | None = None,
) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP12B_LIVE_RUNTIME_ASSEMBLY_ENABLED_ENV))


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
    if not step12b_live_runtime_assembly_enabled(source):
        raise WNBAStep12LiveRuntimeDisabledError(
            f"Step 12B requires {STEP12B_LIVE_RUNTIME_ASSEMBLY_ENABLED_ENV}=true."
        )
    bad = [name for name in _FORBIDDEN_TRUE_ENV_KEYS if _truthy(source.get(name))]
    if bad:
        raise WNBAStep12LiveRuntimeDisabledError(
            "Step 12B refuses production/scheduler/persistence/write switches: "
            + ", ".join(bad)
        )
    missing = [name for name in _REQUIRED_TRUE_ENV_KEYS if not _truthy(source.get(name))]
    if missing:
        raise WNBAStep12LiveRuntimeDisabledError(
            "Step 12B requires isolated frozen gates: " + ", ".join(missing)
        )
    constants = {
        "step12b_default": DEFAULT_ENABLED,
        "step12b_production": PRODUCTION_ACTIVATION_ALLOWED,
        "step12b_scheduler": BACKGROUND_SCHEDULER_ALLOWED,
        "step12b_persistence": PERSISTENCE_ALLOWED,
        "step12b_supabase": SUPABASE_WRITE_ALLOWED,
        "step12b_public_api": PUBLIC_FASTAPI_ACTIVATION_ALLOWED,
        "step12b_wagering": WAGERING_ALLOWED,
        "step12a_default": step12a.DEFAULT_ENABLED,
        "step12a_production": step12a.PRODUCTION_ACTIVATION_ALLOWED,
        "step12a_scheduler": step12a.BACKGROUND_SCHEDULER_ALLOWED,
        "step12a_persistence": step12a.PERSISTENCE_ALLOWED,
        "step12a_supabase": step12a.SUPABASE_WRITE_ALLOWED,
        "step12a_public_api": step12a.PUBLIC_FASTAPI_ACTIVATION_ALLOWED,
        "step12a_wagering": step12a.WAGERING_ALLOWED,
    }
    drift = [name for name, value in constants.items() if value is not False]
    if drift:
        raise WNBAStep12LiveRuntimeDisabledError(
            "Step 12B safety constant drift: " + ", ".join(drift)
        )
    if step12a.STEP11E_FROZEN_SHA != "f96d580e398aaa199c424e3b70b7a8f1386a8452":
        raise WNBAStep12LiveRuntimeDisabledError("Step 12A frozen Step-11E lineage drift.")
    if release.STEP8_FROZEN_SHA != "8faf468b770f7a31244914df75390fc788f859a1":
        raise WNBAStep12LiveRuntimeDisabledError("Frozen Step-8 lineage drift.")


def _strict_season(value: Any) -> int:
    if isinstance(value, bool):
        raise WNBAStep12LiveRuntimeInputError("Step 12B season must be integer 2026.")
    try:
        season = int(value)
    except (TypeError, ValueError) as exc:
        raise WNBAStep12LiveRuntimeInputError(
            "Step 12B season must be integer 2026."
        ) from exc
    if season != release.SEASON:
        raise WNBAStep12LiveRuntimeInputError(
            "Step 12B is certified for the 2026 Regular Season only."
        )
    return season


def _strict_slate_date(value: Any) -> str:
    text = str(value or "").strip()
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise WNBAStep12LiveRuntimeInputError(
            "Step 12B slate_date must be YYYY-MM-DD."
        ) from exc
    if parsed.isoformat() != text:
        raise WNBAStep12LiveRuntimeInputError(
            "Step 12B slate_date must be canonical YYYY-MM-DD."
        )
    return text


def _evaluated_at(value: Any) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise WNBAStep12LiveRuntimeInputError(
                "Step 12B evaluated_at_utc must be ISO-8601 with timezone."
            ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise WNBAStep12LiveRuntimeInputError(
            "Step 12B evaluated_at_utc must be timezone-aware."
        )
    return parsed.astimezone(timezone.utc)


def _strict_int(value: Any, label: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise WNBAStep12LiveRuntimeInputError(f"{label} must be an integer.")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise WNBAStep12LiveRuntimeInputError(f"{label} must be an integer.") from exc
    if isinstance(value, float) and not value.is_integer():
        raise WNBAStep12LiveRuntimeInputError(f"{label} must be an integer.")
    if not minimum <= result <= maximum:
        raise WNBAStep12LiveRuntimeInputError(
            f"{label} must be from {minimum} through {maximum}."
        )
    return result


def _validate_request(request: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(request, Mapping):
        raise WNBAStep12LiveRuntimeInputError("Step 12B request must be a JSON object.")
    keys = set(request)
    missing = _REQUEST_REQUIRED_FIELDS - keys
    unknown = keys - _REQUEST_REQUIRED_FIELDS - _REQUEST_OPTIONAL_FIELDS
    if missing:
        raise WNBAStep12LiveRuntimeInputError(
            "Step 12B request missing fields: " + ", ".join(sorted(missing))
        )
    if unknown:
        raise WNBAStep12LiveRuntimeInputError(
            "Step 12B request has unknown fields: " + ", ".join(sorted(unknown))
        )
    if request.get("data_type") != "wnba_step12b_live_runtime_request":
        raise WNBAStep12LiveRuntimeInputError("Step 12B request data_type mismatch.")
    if request.get("schema_version") != REQUEST_SCHEMA_VERSION:
        raise WNBAStep12LiveRuntimeInputError("Step 12B request schema_version mismatch.")

    supplied_hash = request.get("request_content_sha256")
    surface = {key: value for key, value in request.items() if key != "request_content_sha256"}
    canonical_hash = _canonical_hash(surface)
    if supplied_hash is not None and supplied_hash != canonical_hash:
        raise WNBAStep12LiveRuntimeIntegrityError("Step 12B request content hash mismatch.")

    previous_state = request.get("previous_state")
    if previous_state is not None and not isinstance(previous_state, Mapping):
        raise WNBAStep12LiveRuntimeInputError(
            "Step 12B previous_state must be null or an object."
        )
    controller_policy = request.get("controller_policy") or {}
    if not isinstance(controller_policy, Mapping):
        raise WNBAStep12LiveRuntimeInputError("Step 12B controller_policy must be an object.")
    unknown_controller = set(controller_policy) - _CONTROLLER_POLICY_FIELDS
    if unknown_controller:
        raise WNBAStep12LiveRuntimeInputError(
            "Step 12B controller_policy has unknown fields: "
            + ", ".join(sorted(unknown_controller))
        )
    refresh_policy = request.get("refresh_policy") or {}
    qualification_policy = request.get("qualification_policy") or {}
    if not isinstance(refresh_policy, Mapping) or not isinstance(qualification_policy, Mapping):
        raise WNBAStep12LiveRuntimeInputError(
            "Step 12B refresh_policy and qualification_policy must be objects."
        )

    return {
        "season": _strict_season(request.get("season")),
        "slate_date": _strict_slate_date(request.get("slate_date")),
        "evaluated_at": _evaluated_at(request.get("evaluated_at_utc")),
        "previous_state": dict(previous_state) if previous_state is not None else None,
        "controller_policy": dict(controller_policy),
        "refresh_policy": dict(refresh_policy),
        "qualification_policy": dict(qualification_policy),
        "request_content_sha256": canonical_hash,
    }


def build_step12b_request(
    *,
    season: int,
    slate_date: str,
    evaluated_at: datetime | str | None = None,
    previous_state: Mapping[str, Any] | None = None,
    controller_policy: Mapping[str, Any] | None = None,
    refresh_policy: Mapping[str, Any] | None = None,
    qualification_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the tamper-evident Step-12B request; no Step-8 payload is required."""
    request: dict[str, Any] = {
        "data_type": "wnba_step12b_live_runtime_request",
        "schema_version": REQUEST_SCHEMA_VERSION,
        "season": season,
        "slate_date": slate_date,
        "evaluated_at_utc": (
            evaluated_at.isoformat() if isinstance(evaluated_at, datetime) else evaluated_at
        ),
        "previous_state": dict(previous_state) if previous_state is not None else None,
        "controller_policy": dict(controller_policy or {}),
        "refresh_policy": dict(refresh_policy or {}),
        "qualification_policy": dict(qualification_policy or {}),
    }
    request["request_content_sha256"] = _canonical_hash(request)
    _validate_request(request)
    return request


def _fetch_provider_bridge(
    *,
    provider: str,
    fetcher: Callable[..., Mapping[str, Any]],
    season: int,
    slate_date: str,
    evaluated_at: datetime,
    attempts: int,
    requester: Callable[..., Any] | None,
    roster_loader: Callable[[int], Mapping[str, Any]] | None,
    env: Mapping[str, str] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if provider == draftkings.PROVIDER:
        retryable = (
            draftkings.WNBAStep11DraftKingsProviderUpstreamError,
            draftkings.WNBAStep11DraftKingsProviderNotReadyError,
        )
    elif provider == fanduel.PROVIDER:
        retryable = (
            fanduel.WNBAStep11FanDuelProviderUpstreamError,
            fanduel.WNBAStep11FanDuelProviderNotReadyError,
        )
    else:
        raise WNBAStep12LiveRuntimeInputError(f"Unsupported provider {provider!r}.")

    errors: list[dict[str, Any]] = []
    for attempt_number in range(1, attempts + 1):
        try:
            candidate = fetcher(
                season=season,
                slate_date=slate_date,
                evaluated_at=evaluated_at,
                requester=requester,
                roster_loader=roster_loader,
                env=env,
            )
            payload = step11d._verify_bridge(candidate, provider=provider)
        except retryable as exc:
            errors.append(
                {
                    "attempt": attempt_number,
                    "error_type": type(exc).__name__,
                    "error_message": " ".join(str(exc).split())[:300],
                }
            )
            continue
        except step11d.WNBAStep11MultiBookShadowIntegrityError as exc:
            raise WNBAStep12LiveRuntimeIntegrityError(str(exc)) from exc
        return dict(candidate), {
            "provider": provider,
            "attempt_limit": attempts,
            "attempts_executed": attempt_number,
            "retryable_failures": len(errors),
            "record_count": len(payload.get("records") or []),
            "bridge_content_sha256": candidate.get("provider_bridge_content_sha256"),
            "errors": errors,
        }
    raise WNBAStep12LiveRuntimeNotReadyError(
        f"Step 12B {provider} discovery exhausted {attempts} bounded attempts."
    )


def _payload_records(bridge: Mapping[str, Any], provider: str) -> list[dict[str, Any]]:
    try:
        payload = step11d._verify_bridge(bridge, provider=provider)
    except step11d.WNBAStep11MultiBookShadowIntegrityError as exc:
        raise WNBAStep12LiveRuntimeIntegrityError(str(exc)) from exc
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        raise WNBAStep12LiveRuntimeNotReadyError(
            f"Step 12B {provider} bridge contains no current market records."
        )
    return [dict(row) for row in records]


def _market_key(row: Mapping[str, Any]) -> tuple[str, int, str, float]:
    try:
        game_id = str(row["game_id"]).strip()
        player_id = int(row["player_id"])
        stat = str(row["stat"]).strip().casefold()
        line = round(float(row["line"]), 6)
    except (KeyError, TypeError, ValueError) as exc:
        raise WNBAStep12LiveRuntimeIntegrityError(
            "Step 12B provider record has malformed official market identity."
        ) from exc
    if len(game_id) != 10 or not game_id.isdigit() or player_id <= 0:
        raise WNBAStep12LiveRuntimeIntegrityError(
            "Step 12B provider record has invalid official game/player identity."
        )
    if stat not in {"points", "rebounds", "assists", "pra"}:
        raise WNBAStep12LiveRuntimeIntegrityError(
            f"Step 12B provider record has unsupported stat {stat!r}."
        )
    if not math.isfinite(line) or line < 0.0:
        raise WNBAStep12LiveRuntimeIntegrityError("Step 12B provider line must be finite and nonnegative.")
    return game_id, player_id, stat, line


def _exact_multibook_targets(
    draftkings_records: Sequence[Mapping[str, Any]],
    fanduel_records: Sequence[Mapping[str, Any]],
) -> tuple[list[tuple[str, int]], list[dict[str, Any]]]:
    by_provider: dict[str, set[tuple[str, int, str, float]]] = {}
    for provider, records in (
        (draftkings.PROVIDER, draftkings_records),
        (fanduel.PROVIDER, fanduel_records),
    ):
        keys: set[tuple[str, int, str, float]] = set()
        for row in records:
            key = _market_key(row)
            if key in keys:
                raise WNBAStep12LiveRuntimeIntegrityError(
                    f"Step 12B {provider} has duplicate exact market identity {key!r}."
                )
            keys.add(key)
        by_provider[provider] = keys

    overlap = sorted(
        by_provider[draftkings.PROVIDER] & by_provider[fanduel.PROVIDER]
    )
    if not overlap:
        raise WNBAStep12LiveRuntimeNotReadyError(
            "Step 12B found no exact same-line DraftKings/FanDuel player-prop group."
        )
    targets = sorted({(game_id, player_id) for game_id, player_id, _stat, _line in overlap})
    if len(targets) > MAX_PROJECTION_TARGETS:
        raise WNBAStep12LiveRuntimeNotReadyError(
            f"Step 12B exact-line target count {len(targets)} exceeds safety cap {MAX_PROJECTION_TARGETS}."
        )
    groups = [
        {
            "game_id": game_id,
            "player_id": player_id,
            "stat": stat,
            "line": line,
            "sportsbooks": [draftkings.PROVIDER, fanduel.PROVIDER],
            "sportsbook_count": 2,
        }
        for game_id, player_id, stat, line in overlap
    ]
    return targets, groups


def _build_frozen_step8_distribution(
    *,
    game_id: str,
    player_id: int,
    env: Mapping[str, str] | None,
) -> dict[str, Any]:
    handoff = step8a.get_player_game_step8_projection_handoff(
        player_id,
        game_id,
        env=env,
    )
    baseline = step8b.build_step8_official_box_baseline(handoff)
    adjusted = step8c.build_step8_context_adjusted_projection(handoff, baseline)
    return step8d.simulate_step8_joint_distribution(
        adjusted,
        baseline,
        simulations=CERTIFIED_SIMULATIONS,
        batch_size=CERTIFIED_BATCH_SIZE,
        env=env,
    )


def _verify_step8_distribution(
    distribution: Mapping[str, Any],
    *,
    game_id: str,
    player_id: int,
) -> dict[str, Any]:
    if not isinstance(distribution, Mapping):
        raise WNBAStep12LiveRuntimeIntegrityError("Step 12B Step-8 result must be an object.")
    expected = {
        "data_type": "joint_player_stat_probability_distribution",
        "schema_version": step8d.SCHEMA_VERSION,
        "model_version": step8d.MODEL_VERSION,
        "game_id": game_id,
        "player_id": player_id,
    }
    for key, value in expected.items():
        if distribution.get(key) != value:
            raise WNBAStep12LiveRuntimeIntegrityError(
                f"Step 12B Step-8 distribution {key} drift for game={game_id} player={player_id}."
            )
    simulation = distribution.get("simulation")
    convergence = distribution.get("convergence")
    if not isinstance(simulation, Mapping) or not isinstance(convergence, Mapping):
        raise WNBAStep12LiveRuntimeIntegrityError("Step 12B Step-8 simulation/convergence metadata missing.")
    if simulation.get("simulations") != CERTIFIED_SIMULATIONS:
        raise WNBAStep12LiveRuntimeIntegrityError(
            f"Step 12B requires exactly {CERTIFIED_SIMULATIONS:,} frozen simulations."
        )
    if convergence.get("converged") is not True:
        raise WNBAStep12LiveRuntimeNotReadyError(
            f"Step 12B Step-8 distribution did not converge for game={game_id} player={player_id}."
        )
    provided_hash = distribution.get("result_content_sha256")
    surface = {
        key: value for key, value in distribution.items()
        if key not in {"generated_at_utc", "result_content_sha256"}
    }
    if provided_hash != _canonical_hash(surface):
        raise WNBAStep12LiveRuntimeIntegrityError(
            f"Step 12B Step-8 content hash mismatch for game={game_id} player={player_id}."
        )
    distributions = distribution.get("distributions")
    if not isinstance(distributions, Mapping) or not all(
        isinstance(distributions.get(stat), Mapping)
        for stat in ("points", "rebounds", "assists", "points_rebounds_assists")
    ):
        raise WNBAStep12LiveRuntimeIntegrityError(
            "Step 12B Step-8 distribution is missing P/R/A/PRA probability surfaces."
        )
    return dict(distribution)


def _cached_bridge_fetcher(
    bridge: Mapping[str, Any],
    *,
    expected_provider: str,
    season: int,
    slate_date: str,
) -> Callable[..., Mapping[str, Any]]:
    frozen = deepcopy(dict(bridge))

    def fetcher(**kwargs: Any) -> Mapping[str, Any]:
        if int(kwargs.get("season")) != season or str(kwargs.get("slate_date")) != slate_date:
            raise WNBAStep12LiveRuntimeIntegrityError(
                f"Step 12B cached {expected_provider} bridge invoked for different slate identity."
            )
        return deepcopy(frozen)

    return fetcher


def _assert_step12a_result(result: Mapping[str, Any], request_hash: str) -> None:
    if not isinstance(result, Mapping):
        raise WNBAStep12LiveRuntimeIntegrityError("Step 12B frozen Step-12A result must be an object.")
    if result.get("data_type") != "wnba_step12a_shadow_runner_response":
        raise WNBAStep12LiveRuntimeIntegrityError("Step 12B received wrong Step-12A response type.")
    if result.get("schema_version") != step12a.SCHEMA_VERSION:
        raise WNBAStep12LiveRuntimeIntegrityError("Step 12B received wrong Step-12A schema.")
    if result.get("step11e_frozen_sha") != STEP11E_FROZEN_SHA:
        raise WNBAStep12LiveRuntimeIntegrityError("Step 12B Step-12A frozen Step-11E lineage drift.")
    if result.get("request_content_sha256") != request_hash:
        raise WNBAStep12LiveRuntimeIntegrityError("Step 12B Step-12A request lineage mismatch.")
    lineage = result.get("lineage")
    if not isinstance(lineage, Mapping) or lineage.get("step8_frozen_sha") != STEP8_FROZEN_SHA:
        raise WNBAStep12LiveRuntimeIntegrityError("Step 12B frozen Step-8 lineage missing from Step-12A result.")
    guards = result.get("guardrails")
    if not isinstance(guards, Mapping):
        raise WNBAStep12LiveRuntimeIntegrityError("Step 12B Step-12A guardrails missing.")
    for key in (
        "scheduler_started",
        "background_worker_started",
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
    ):
        if guards.get(key) is not False:
            raise WNBAStep12LiveRuntimeIntegrityError(
                f"Step 12B downstream Step-12A safety guard drift: {key}."
            )


def run_step12b_live_runtime_job(
    request: Mapping[str, Any],
    *,
    env: Mapping[str, str] | None = None,
    draftkings_fetcher: Callable[..., Mapping[str, Any]] | None = None,
    fanduel_fetcher: Callable[..., Mapping[str, Any]] | None = None,
    draftkings_requester: Callable[..., Any] | None = None,
    fanduel_requester: Callable[..., Any] | None = None,
    roster_loader: Callable[[int], Mapping[str, Any]] | None = None,
    projection_loader: Callable[..., Mapping[str, Any]] | None = None,
    step12a_runner: Callable[..., Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assemble one live shadow runtime from markets through frozen Step 8/9/10/11/12A."""
    _assert_safe_environment(env)
    normalized = _validate_request(request)
    controller_policy = normalized["controller_policy"]
    provider_attempts = _strict_int(
        controller_policy.get("provider_attempts", step11d.DEFAULT_PROVIDER_ATTEMPTS),
        "provider_attempts",
        1,
        step11d.MAX_PROVIDER_ATTEMPTS,
    )

    dk_fetch = draftkings_fetcher or draftkings.fetch_step11a_draftkings_provider_bridge
    fd_fetch = fanduel_fetcher or fanduel.fetch_step11c_fanduel_provider_bridge
    dk_bridge, dk_discovery = _fetch_provider_bridge(
        provider=draftkings.PROVIDER,
        fetcher=dk_fetch,
        season=normalized["season"],
        slate_date=normalized["slate_date"],
        evaluated_at=normalized["evaluated_at"],
        attempts=provider_attempts,
        requester=draftkings_requester,
        roster_loader=roster_loader,
        env=env,
    )
    fd_bridge, fd_discovery = _fetch_provider_bridge(
        provider=fanduel.PROVIDER,
        fetcher=fd_fetch,
        season=normalized["season"],
        slate_date=normalized["slate_date"],
        evaluated_at=normalized["evaluated_at"],
        attempts=provider_attempts,
        requester=fanduel_requester,
        roster_loader=roster_loader,
        env=env,
    )

    dk_records = _payload_records(dk_bridge, draftkings.PROVIDER)
    fd_records = _payload_records(fd_bridge, fanduel.PROVIDER)
    targets, exact_groups = _exact_multibook_targets(dk_records, fd_records)

    loader = projection_loader or _build_frozen_step8_distribution
    step8_distributions: list[dict[str, Any]] = []
    built_targets: list[dict[str, Any]] = []
    skipped_targets: list[dict[str, Any]] = []
    candidate_not_ready = (
        step8a.WNBAStep8ProjectionHandoffNotReadyError,
        step8b.WNBAStep8OfficialBoxBaselineNotFoundError,
        step8core.WNBAStep8CoreProjectionNotReadyError,
        step8c.WNBAStep8ContextAdjustmentNotReadyError,
    )
    for game_id, player_id in targets:
        try:
            candidate = loader(
                game_id=game_id,
                player_id=player_id,
                env=env,
            )
        except candidate_not_ready as exc:
            skipped_targets.append(
                {
                    "game_id": game_id,
                    "player_id": player_id,
                    "reason": "certified_step8_candidate_not_ready",
                    "error_type": type(exc).__name__,
                }
            )
            continue
        verified = _verify_step8_distribution(
            candidate,
            game_id=game_id,
            player_id=player_id,
        )
        step8_distributions.append(verified)
        built_targets.append(
            {
                "game_id": game_id,
                "player_id": player_id,
                "result_content_sha256": verified["result_content_sha256"],
                "simulations": CERTIFIED_SIMULATIONS,
                "converged": True,
            }
        )
    if not step8_distributions:
        raise WNBAStep12LiveRuntimeNotReadyError(
            "Step 12B could not build any certified converged Step-8 distribution for current exact-line markets."
        )

    step12a_request = step12a.build_step12a_request(
        season=normalized["season"],
        slate_date=normalized["slate_date"],
        step8_distributions=step8_distributions,
        previous_state=normalized["previous_state"],
        evaluated_at=normalized["evaluated_at"],
        policy=controller_policy,
    )
    cached_dk = _cached_bridge_fetcher(
        dk_bridge,
        expected_provider=draftkings.PROVIDER,
        season=normalized["season"],
        slate_date=normalized["slate_date"],
    )
    cached_fd = _cached_bridge_fetcher(
        fd_bridge,
        expected_provider=fanduel.PROVIDER,
        season=normalized["season"],
        slate_date=normalized["slate_date"],
    )

    def frozen_tick_runner(**kwargs: Any) -> Mapping[str, Any]:
        call = dict(kwargs)
        call["draftkings_fetcher"] = cached_dk
        call["fanduel_fetcher"] = cached_fd
        call["refresh_policy"] = normalized["refresh_policy"]
        call["qualification_policy"] = normalized["qualification_policy"]
        return step11e.run_step11e_controlled_automation_tick(**call)

    runner = step12a_runner or step12a.run_step12a_shadow_job
    step12a_result = runner(
        step12a_request,
        env=env,
        tick_runner=frozen_tick_runner,
    )
    _assert_step12a_result(
        step12a_result,
        step12a_request["request_content_sha256"],
    )
    _assert_safe_environment(env)

    tick = step12a_result.get("step11e_tick") or {}
    shadow = tick.get("shadow_board_result") if isinstance(tick, Mapping) else None
    shadow_summary = shadow.get("shadow_summary") if isinstance(shadow, Mapping) else None
    response = {
        "data_type": "wnba_step12b_live_runtime_assembly_response",
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "request_content_sha256": normalized["request_content_sha256"],
        "status": step12a_result.get("status"),
        "health": step12a_result.get("health"),
        "slate_date": normalized["slate_date"],
        "provider_discovery": {
            "sportsbooks": [draftkings.PROVIDER, fanduel.PROVIDER],
            "draftkings": dk_discovery,
            "fanduel": fd_discovery,
            "sportsbook_network_fetches_reused_in_step11_tick": True,
            "duplicate_sportsbook_discovery_performed": False,
        },
        "market_overlap": {
            "draftkings_record_count": len(dk_records),
            "fanduel_record_count": len(fd_records),
            "exact_line_multibook_group_count": len(exact_groups),
            "exact_line_multibook_groups": exact_groups,
            "unique_projection_target_count": len(targets),
            "different_lines_blended": False,
        },
        "projection_assembly": {
            "requested_target_count": len(targets),
            "built_target_count": len(built_targets),
            "skipped_target_count": len(skipped_targets),
            "simulations_per_built_target": CERTIFIED_SIMULATIONS,
            "batch_size": CERTIFIED_BATCH_SIZE,
            "targets": built_targets,
            "skipped_targets": skipped_targets,
            "all_built_distributions_converged": True,
        },
        "runtime_summary": {
            "step8_distribution_count": len(step8_distributions),
            "step11_cycle_executed": ((tick.get("execution") or {}).get("cycle_executed") if isinstance(tick, Mapping) else None),
            "qualified_prop_count": (
                shadow_summary.get("qualified_prop_count")
                if isinstance(shadow_summary, Mapping)
                else None
            ),
            "top_card_count": (
                shadow_summary.get("top_card_count")
                if isinstance(shadow_summary, Mapping)
                else None
            ),
        },
        "step12a_result": step12a_result,
        "lineage": {
            "step12a_frozen_sha": STEP12A_FROZEN_SHA,
            "step11e_frozen_sha": STEP11E_FROZEN_SHA,
            "step8_frozen_sha": STEP8_FROZEN_SHA,
            "step12a_runner_content_sha256": step12a_result.get("runner_content_sha256"),
            "draftkings_bridge_content_sha256": dk_bridge.get("provider_bridge_content_sha256"),
            "fanduel_bridge_content_sha256": fd_bridge.get("provider_bridge_content_sha256"),
            "step8_result_content_sha256": [
                row["result_content_sha256"] for row in built_targets
            ],
        },
        "guardrails": {
            "shadow_only": True,
            "caller_driven_job_only": True,
            "market_driven_projection_target_discovery": True,
            "official_wnba_identity_reconciliation_required": True,
            "exact_line_multibook_overlap_required": True,
            "frozen_step8_projection_generated": True,
            "five_million_simulations_required": True,
            "sportsbook_network_fetch_performed": True,
            "sportsbook_http_methods": ["GET"],
            "sportsbook_discovery_reused_without_second_network_fetch": True,
            "scheduler_started": False,
            "background_worker_started": False,
            "sleep_performed": False,
            "state_persisted": False,
            "caller_resupplies_state": True,
            "public_fastapi_route_added": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "production_runtime_enabled": False,
            "production_activation_allowed": False,
            "wager_action_performed": False,
            "authentication_used": False,
            "cookies_used": False,
            "paid_odds_vendor_used": False,
            "basketball_model_modified": False,
            "step8_distribution_modified_after_generation": False,
        },
    }
    hash_surface = {
        "data_type": response["data_type"],
        "schema_version": response["schema_version"],
        "request_content_sha256": response["request_content_sha256"],
        "status": response["status"],
        "health": response["health"],
        "slate_date": response["slate_date"],
        "provider_discovery": response["provider_discovery"],
        "market_overlap": response["market_overlap"],
        "projection_assembly": response["projection_assembly"],
        "runtime_summary": response["runtime_summary"],
        "lineage": response["lineage"],
        "guardrails": response["guardrails"],
    }
    response["runtime_content_sha256"] = _canonical_hash(hash_surface)
    return response


__all__ = [
    "CERTIFIED_BATCH_SIZE",
    "CERTIFIED_SIMULATIONS",
    "MAX_PROJECTION_TARGETS",
    "MODEL_VERSION",
    "REQUEST_SCHEMA_VERSION",
    "SCHEMA_VERSION",
    "STEP12A_FROZEN_SHA",
    "STEP12B_LIVE_RUNTIME_ASSEMBLY_ENABLED_ENV",
    "WNBAStep12LiveRuntimeDisabledError",
    "WNBAStep12LiveRuntimeInputError",
    "WNBAStep12LiveRuntimeIntegrityError",
    "WNBAStep12LiveRuntimeNotReadyError",
    "build_step12b_request",
    "run_step12b_live_runtime_job",
    "step12b_live_runtime_assembly_enabled",
]
