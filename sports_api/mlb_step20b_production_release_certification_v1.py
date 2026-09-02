"""MLB Step 20B — production-release certification.

Step 20B promotes the already-green Step 20A end-to-end proof into a release
candidate certificate. It deliberately does not deploy, mutate Render, start a
scheduler, call providers, write production data, emit actionable output, or
enable wagering. Merge and any later production activation remain manual.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import os
import re
from typing import Any

from sports_api import mlb_step17a_production_host_contract_v1 as step17a
from sports_api import mlb_step20a_end_to_end_certification_v1 as step20a

DATA_TYPE = "mlb_step20b_production_release_certification_v1"
SCHEMA_VERSION = 1
STEP20B_BASE_MAIN_SHA = "6c616cfa19a3c5fdadda2781694654c8f6d2db59"
CERTIFICATION_STATUS = "STEP20B_PRODUCTION_RELEASE_CERTIFICATION_READY"
FINAL_CERTIFICATION_MARKER = "MLB_STEP20B_PRODUCTION_RELEASE_CERTIFICATION_GREEN"
RELEASE_MODE = "CERTIFICATION_ONLY"
ROLLBACK_EXECUTION_MODE = "manual_only"
CERTIFIED_ROLLBACK_REVISION = "ece3cd2d15d091728fdbe30be774dd9c15e4fe8e"

_FORBIDDEN_TRUE_ENV_KEYS = (
    "MLB_PRODUCTION_RUNTIME_ENABLED",
    "MLB_PRODUCTION_SCHEDULER_ENABLED",
    "MLB_ACTIONABLE_OUTPUT_ENABLED",
    "MLB_WAGERING_ENABLED",
    "MLB_SUPABASE_REST_WRITE_ENABLED",
    "MLB_STEP16C_LIVE_POSTGRESQL_CANARY_ENABLED",
    "MLB_STEP16D_CONTROLLED_PRODUCTION_ACTIVATION_ENABLED",
    "MLB_STEP16E_FINAL_PRODUCTION_FREEZE_ENABLED",
)
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class MLBStep20BProductionReleaseCertificationError(ValueError):
    """Raised when a Step 20B release candidate cannot fail closed."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "",
        "0",
        "false",
        "no",
        "off",
        "disabled",
    }


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MLBStep20BProductionReleaseCertificationError(
            f"{field} must be a mapping"
        )
    return value


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise MLBStep20BProductionReleaseCertificationError(
            f"{field} must be a non-negative integer"
        )
    return value


def _positive_int(value: Any, field: str) -> int:
    result = _nonnegative_int(value, field)
    if result <= 0:
        raise MLBStep20BProductionReleaseCertificationError(
            f"{field} must be a positive integer"
        )
    return result


def _assert_host_release_boundary() -> None:
    checks = {
        "render_service": (
            step17a.EXPECTED_RENDER_SERVICE_ID == "srv-da84q6ifngtc73bdbm6g"
        ),
        "render_auto_deploy": step17a.EXPECTED_RENDER_AUTO_DEPLOY == "no",
        "auto_deploy_must_remain_disabled": (
            step17a.AUTO_DEPLOY_MUST_REMAIN_DISABLED is True
        ),
        "render_mutation_allowed": step17a.RENDER_SERVICE_MUTATION_ALLOWED is False,
        "render_deploy_allowed": step17a.RENDER_DEPLOY_ALLOWED is False,
        "wagering_allowed": step17a.WAGERING_ALLOWED is False,
        "actionable_output_allowed": step17a.ACTIONABLE_OUTPUT_ALLOWED is False,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise MLBStep20BProductionReleaseCertificationError(
            "frozen host release boundary drift: " + ", ".join(failed)
        )


def _assert_step20a_certification(source: Mapping[str, Any]) -> list[int]:
    if source.get("data_type") != step20a.DATA_TYPE:
        raise MLBStep20BProductionReleaseCertificationError(
            "source is not a Step 20A certification"
        )
    if source.get("schema_version") != step20a.SCHEMA_VERSION:
        raise MLBStep20BProductionReleaseCertificationError(
            "Step 20A schema version drift"
        )
    if source.get("certification_status") != "certified":
        raise MLBStep20BProductionReleaseCertificationError(
            "Step 20A certification is not green"
        )
    if source.get("final_certification_marker") != step20a.FINAL_CERTIFICATION_MARKER:
        raise MLBStep20BProductionReleaseCertificationError(
            "Step 20A final certification marker drift"
        )
    if source.get("consumer_api_path") != step20a.EXISTING_CONSUMER_PATH:
        raise MLBStep20BProductionReleaseCertificationError(
            "Step 20A consumer API path drift"
        )
    if source.get("consumer_api_data_type") != step20a.EXISTING_API_DATA_TYPE:
        raise MLBStep20BProductionReleaseCertificationError(
            "Step 20A consumer API data type drift"
        )

    game_count = _positive_int(source.get("consumer_game_count"), "consumer_game_count")
    card_count = _positive_int(source.get("consumer_card_count"), "consumer_card_count")
    if card_count != game_count:
        raise MLBStep20BProductionReleaseCertificationError(
            "Step 20A consumer cards do not match certified games"
        )

    raw_ids = source.get("consumer_official_game_ids")
    if not isinstance(raw_ids, list):
        raise MLBStep20BProductionReleaseCertificationError(
            "consumer_official_game_ids must be a list"
        )
    game_ids = [
        _positive_int(game_id, f"consumer_official_game_ids[{index}]")
        for index, game_id in enumerate(raw_ids)
    ]
    if len(game_ids) != game_count:
        raise MLBStep20BProductionReleaseCertificationError(
            "consumer game IDs do not match certified game count"
        )
    if len(set(game_ids)) != len(game_ids):
        raise MLBStep20BProductionReleaseCertificationError(
            "consumer official game IDs must be unique"
        )

    zero_fields = (
        "provider_network_calls_added_by_step20a",
        "database_reads_added_by_step20a",
        "database_writes_added_by_step20a",
    )
    for field in zero_fields:
        if _nonnegative_int(source.get(field), field) != 0:
            raise MLBStep20BProductionReleaseCertificationError(
                f"Step 20A safety counter {field} must be zero"
            )

    false_fields = (
        "production_runtime_wiring",
        "production_scheduler_mutation",
        "model_probability_mutation",
        "projection_mutation",
        "actionable_output",
        "wagering",
        "fuzzy_matching_used",
        "synthetic_game_id_used",
        "synthetic_player_id_used",
        "price_fabrication_used",
    )
    for field in false_fields:
        if source.get(field) is not False:
            raise MLBStep20BProductionReleaseCertificationError(
                f"Step 20A safety flag {field} must be false"
            )
    return game_ids


def certification_manifest() -> dict[str, Any]:
    """Return the immutable non-deploying Step 20B release contract."""
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step20b_base_main_sha": STEP20B_BASE_MAIN_SHA,
        "certification_status": CERTIFICATION_STATUS,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "release_mode": RELEASE_MODE,
        "step20a_required": True,
        "step20a_final_marker": step20a.FINAL_CERTIFICATION_MARKER,
        "existing_consumer_path": step20a.EXISTING_CONSUMER_PATH,
        "render_service_id": step17a.EXPECTED_RENDER_SERVICE_ID,
        "render_auto_deploy_required": "no",
        "pull_request_deploy_allowed": False,
        "pull_request_activation_allowed": False,
        "render_mutation_allowed": False,
        "automatic_rollback_allowed": False,
        "rollback_execution_mode": ROLLBACK_EXECUTION_MODE,
        "certified_rollback_revision": CERTIFIED_ROLLBACK_REVISION,
        "manual_merge_required": True,
        "manual_post_merge_activation_required": True,
        "provider_calls_added_by_step20b": False,
        "production_database_writes_added_by_step20b": False,
        "model_probability_mutation_enabled": False,
        "projection_mutation_enabled": False,
        "actionable_output_enabled": False,
        "wagering_enabled": False,
    }


def certify_step20b_production_release_candidate(
    step20a_certification: Mapping[str, Any],
    *,
    candidate_sha: str,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Certify a merge candidate without deploying or activating production."""
    source = _mapping(step20a_certification, "step20a_certification")
    normalized_sha = str(candidate_sha or "").strip().casefold()
    if _GIT_SHA_RE.fullmatch(normalized_sha) is None:
        raise MLBStep20BProductionReleaseCertificationError(
            "candidate_sha must be a full 40-character Git SHA"
        )

    _assert_host_release_boundary()
    game_ids = _assert_step20a_certification(source)

    environment = os.environ if env is None else env
    enabled = [
        key for key in _FORBIDDEN_TRUE_ENV_KEYS if _truthy(environment.get(key))
    ]
    if enabled:
        raise MLBStep20BProductionReleaseCertificationError(
            "release certification refuses activation/mutation gates: "
            + ", ".join(enabled)
        )

    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "certification_status": "certified",
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "step20b_base_main_sha": STEP20B_BASE_MAIN_SHA,
        "candidate_sha": normalized_sha,
        "release_mode": RELEASE_MODE,
        "source_step20a_marker": source.get("final_certification_marker"),
        "source_checkpoint_version": deepcopy(source.get("checkpoint_version")),
        "source_checkpoint_id": deepcopy(source.get("checkpoint_id")),
        "source_checkpoint_envelope_sha256": deepcopy(
            source.get("checkpoint_envelope_sha256")
        ),
        "consumer_api_path": source.get("consumer_api_path"),
        "consumer_api_data_type": source.get("consumer_api_data_type"),
        "consumer_game_count": len(game_ids),
        "consumer_official_game_ids": deepcopy(game_ids),
        "host_release_boundary_verified": True,
        "render_service_id": step17a.EXPECTED_RENDER_SERVICE_ID,
        "render_auto_deploy": step17a.EXPECTED_RENDER_AUTO_DEPLOY,
        "ready_for_merge_decision": True,
        "deployment_performed": False,
        "activation_performed": False,
        "render_mutation_performed": False,
        "production_database_write_performed": False,
        "provider_network_call_performed_by_step20b": False,
        "sportsbook_network_call_performed_by_step20b": False,
        "automatic_rollback_performed": False,
        "rollback_execution_mode": ROLLBACK_EXECUTION_MODE,
        "rollback_revision": CERTIFIED_ROLLBACK_REVISION,
        "manual_merge_required": True,
        "manual_post_merge_activation_required": True,
        "model_probability_mutation": False,
        "projection_mutation": False,
        "actionable_output": False,
        "wagering": False,
    }


__all__ = [
    "CERTIFICATION_STATUS",
    "CERTIFIED_ROLLBACK_REVISION",
    "DATA_TYPE",
    "FINAL_CERTIFICATION_MARKER",
    "MLBStep20BProductionReleaseCertificationError",
    "RELEASE_MODE",
    "ROLLBACK_EXECUTION_MODE",
    "SCHEMA_VERSION",
    "STEP20B_BASE_MAIN_SHA",
    "certification_manifest",
    "certify_step20b_production_release_candidate",
]
