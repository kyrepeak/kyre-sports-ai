"""Step 6T storage-aware durable-canary evidence verification.

Step 6T bridges the frozen Step 6K filesystem-only preflight and the frozen
Step 6S storage-aware canary without modifying either one.  The public status
report is configuration-only and network-free.  Explicit evidence verification
is read-only: filesystem selection reads the frozen Step 6J files, while
Supabase selection reads the Step 6R durable objects.  No Step 6T function
writes feed/marker/backup state, starts a scheduler, or authorizes production.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

from sports_api.collectors.wnba_kyre_market_feed import (
    resolve_kyre_market_feed_path,
    validate_kyre_market_feed,
)
from sports_api.wnba_production_runtime_readiness import ACTIVATION_ENV as PRODUCTION_RUNTIME_ENV
from sports_api.wnba_reconciled_direct_sync import (
    RECONCILED_SYNC_ENABLED_ENV,
    persistent_feed_sha256,
)
from sports_api.wnba_step6d_direct_integration import DIRECT_SYNC_ENABLED_ENV
from sports_api.wnba_step6j_canary_activation import (
    BACKUP_PREFIX,
    CANARY_ENABLED_ENV,
    MARKER_FILENAME,
)
from sports_api.wnba_step6q_durable_storage import (
    CANARY_MARKER_OBJECT_KEY,
    FEED_OBJECT_KEY,
    FILESYSTEM_BACKEND,
    STORAGE_BACKEND_ENV,
    SUPABASE_BACKEND,
    WNBADurableStorageBackend,
    WNBADurableStorageError,
    WNBADurableStorageModelInputError,
    WNBADurableStorageNotReadyError,
    resolve_storage_backend_name,
)
from sports_api.wnba_step6r_supabase_storage import (
    build_step6r_durable_storage,
    get_step6r_supabase_storage_status,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 6T durable canary evidence verifier"
MODEL_VERSION = "wnba_step_6t_durable_canary_evidence_v1"
SCHEMA_VERSION = MODEL_VERSION
_ACTIVATION_ID_RE = re.compile(r"^[A-Za-z0-9._-]{6,160}$")
_HEX_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class WNBAStep6TEvidenceError(RuntimeError):
    pass


def _environment(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _truthy(environment: Mapping[str, str], name: str, default: bool = False) -> bool:
    raw = environment.get(name)
    if raw is None:
        return default
    return str(raw).strip().casefold() not in {"", "0", "false", "no", "off", "disabled"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _stable_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return _sha256(payload)


def _backup_key(activation_id: str) -> str:
    return f"{BACKUP_PREFIX}{activation_id}.bin"


def _require_safe_completed_environment(environment: Mapping[str, str]) -> None:
    enabled = [
        name
        for name in (CANARY_ENABLED_ENV, DIRECT_SYNC_ENABLED_ENV, RECONCILED_SYNC_ENABLED_ENV)
        if _truthy(environment, name, False)
    ]
    if enabled:
        raise WNBAStep6TEvidenceError(
            "Step 6T evidence verification requires all temporary Step 6J write switches to be OFF."
        )
    if _truthy(environment, PRODUCTION_RUNTIME_ENV, False):
        raise WNBAStep6TEvidenceError(
            "Step 6T evidence verification requires the WNBA production runtime to remain OFF."
        )


def _read_json_bytes(raw: bytes, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WNBAStep6TEvidenceError(f"{label} is not valid UTF-8 JSON.") from exc
    if not isinstance(value, dict):
        raise WNBAStep6TEvidenceError(f"{label} must be a JSON object.")
    return value


def _validate_completed_evidence(
    *,
    backend_id: str,
    marker: Mapping[str, Any],
    marker_raw: bytes,
    feed_raw: bytes,
    backup_exists: bool,
    backup_raw: bytes | None,
) -> dict[str, Any]:
    if marker.get("status") != "completed":
        raise WNBAStep6TEvidenceError("Step 6T requires a completed durable Step 6J canary marker.")

    activation_id = _clean(marker.get("activation_id"))
    if not activation_id or not _ACTIVATION_ID_RE.fullmatch(activation_id):
        raise WNBAStep6TEvidenceError("Step 6T durable canary marker has no valid activation identity.")

    if marker.get("rollback_verified") is not True:
        raise WNBAStep6TEvidenceError("Step 6T requires the durable canary rollback path to be verified.")

    if backend_id == SUPABASE_BACKEND and marker.get("storage_backend") != SUPABASE_BACKEND:
        raise WNBAStep6TEvidenceError("Step 6T Supabase evidence marker is not bound to the Supabase backend.")

    post_write_sha = (_clean(marker.get("post_write_sha256")) or "").casefold()
    if not _HEX_SHA256_RE.fullmatch(post_write_sha):
        raise WNBAStep6TEvidenceError("Step 6T durable canary marker has an invalid post-write SHA-256.")
    feed_content_sha = _sha256(feed_raw)
    if feed_content_sha != post_write_sha:
        raise WNBAStep6TEvidenceError(
            "Step 6T durable feed bytes do not match the completed canary post-write SHA-256."
        )

    feed_document = _read_json_bytes(feed_raw, label="Step 6T durable feed")
    try:
        validated_feed = validate_kyre_market_feed(feed_document)
    except Exception as exc:
        raise WNBAStep6TEvidenceError("Step 6T durable feed failed the Kyre market-feed contract.") from exc

    canonical_sha = persistent_feed_sha256(validated_feed)
    marker_canonical_sha = (_clean(marker.get("verified_persistent_feed_sha256")) or "").casefold()
    if not _HEX_SHA256_RE.fullmatch(marker_canonical_sha) or canonical_sha != marker_canonical_sha:
        raise WNBAStep6TEvidenceError(
            "Step 6T durable feed canonical identity does not match the completed canary marker."
        )

    marker_date = _clean(marker.get("date"))
    try:
        marker_season = int(marker.get("season"))
    except (TypeError, ValueError) as exc:
        raise WNBAStep6TEvidenceError("Step 6T durable canary marker has an invalid season.") from exc
    if marker_date != validated_feed.get("date") or marker_season != int(validated_feed.get("season")):
        raise WNBAStep6TEvidenceError("Step 6T durable feed date/season does not match the canary marker.")

    offer_count = len(validated_feed.get("offers") or [])
    try:
        marker_offer_count = int(marker.get("offer_side_count"))
    except (TypeError, ValueError) as exc:
        raise WNBAStep6TEvidenceError("Step 6T durable canary marker has an invalid offer count.") from exc
    if marker_offer_count != offer_count:
        raise WNBAStep6TEvidenceError("Step 6T durable feed offer count does not match the canary marker.")

    preexisting = marker.get("preexisting_feed") is True
    pre_write_sha = (_clean(marker.get("pre_write_sha256")) or "").casefold() or None
    backup_present_marker = marker.get("backup_present") is True
    rollback_mode: str
    backup_sha: str | None = None
    if preexisting:
        if not pre_write_sha or not _HEX_SHA256_RE.fullmatch(pre_write_sha):
            raise WNBAStep6TEvidenceError("Step 6T preexisting-feed canary has no valid pre-write SHA-256.")
        if not backup_present_marker or not backup_exists or backup_raw is None:
            raise WNBAStep6TEvidenceError("Step 6T preexisting-feed rollback backup is missing.")
        backup_sha = _sha256(backup_raw)
        if backup_sha != pre_write_sha:
            raise WNBAStep6TEvidenceError("Step 6T rollback backup bytes do not match the pre-write SHA-256.")
        rollback_mode = "restore_exact_backup_bytes"
    else:
        if pre_write_sha is not None:
            raise WNBAStep6TEvidenceError("Step 6T new-feed canary unexpectedly contains a pre-write SHA-256.")
        rollback_mode = "delete_new_feed"

    identity = {
        "storage_backend": backend_id,
        "activation_id": activation_id,
        "status": "completed",
        "date": marker_date,
        "season": marker_season,
        "completed_at_utc": marker.get("completed_at_utc"),
        "preexisting_feed": preexisting,
        "pre_write_sha256": pre_write_sha,
        "post_write_sha256": post_write_sha,
        "verified_persistent_feed_sha256": canonical_sha,
        "offer_side_count": offer_count,
        "rollback_verified": True,
        "rollback_mode": rollback_mode,
        "backup_content_sha256": backup_sha,
        "feed_size_bytes": len(feed_raw),
        "marker_content_sha256": _sha256(marker_raw),
    }
    evidence_payload = {
        "model_version": MODEL_VERSION,
        "canary_identity": identity,
    }
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6t_canary_evidence",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _now_iso(),
        "evidence_verified": True,
        "scheduler_authorized": False,
        "canary_identity": identity,
        "evidence_sha256": _stable_hash(evidence_payload),
        "safety": {
            "storage_read_performed": True,
            "storage_write_performed": False,
            "remote_storage_read_performed": backend_id == SUPABASE_BACKEND,
            "remote_storage_write_performed": False,
            "production_runtime_enabled": False,
            "scheduler_started": False,
            "scheduler_authorized_by_step6t": False,
            "sportsbook_called": False,
            "monte_carlo_run": False,
            "wager_action_performed": False,
            "secret_value_returned": False,
        },
        "handoff": {
            "step6k_modified": False,
            "step6k_network_free_contract_preserved": True,
            "step6k_scheduler_authority_bypassed": False,
            "later_storage_aware_activation_integration_required": True,
        },
    }


def _verify_filesystem(environment: Mapping[str, str]) -> dict[str, Any]:
    target = resolve_kyre_market_feed_path(env=environment)
    marker_path = target.parent / MARKER_FILENAME
    if not target.is_file():
        raise WNBAStep6TEvidenceError("Step 6T filesystem durable feed does not exist.")
    if not marker_path.is_file():
        raise WNBAStep6TEvidenceError("Step 6T filesystem durable canary marker does not exist.")
    try:
        feed_raw = target.read_bytes()
        marker_raw = marker_path.read_bytes()
    except OSError as exc:
        raise WNBAStep6TEvidenceError("Step 6T filesystem evidence could not be read.") from exc
    marker = _read_json_bytes(marker_raw, label="Step 6T filesystem canary marker")
    activation_id = _clean(marker.get("activation_id")) or "invalid"
    backup_path = target.parent / _backup_key(activation_id)
    backup_exists = backup_path.is_file()
    backup_raw = None
    if backup_exists:
        try:
            backup_raw = backup_path.read_bytes()
        except OSError as exc:
            raise WNBAStep6TEvidenceError("Step 6T filesystem rollback backup could not be read.") from exc
    return _validate_completed_evidence(
        backend_id=FILESYSTEM_BACKEND,
        marker=marker,
        marker_raw=marker_raw,
        feed_raw=feed_raw,
        backup_exists=backup_exists,
        backup_raw=backup_raw,
    )


def _verify_supabase(environment: Mapping[str, str]) -> dict[str, Any]:
    try:
        storage = build_step6r_durable_storage(env=environment)
    except (WNBADurableStorageError, WNBADurableStorageNotReadyError, WNBADurableStorageModelInputError) as exc:
        raise WNBAStep6TEvidenceError("Step 6T Supabase durable storage is not ready.") from exc
    if storage.backend_id != SUPABASE_BACKEND:
        raise WNBAStep6TEvidenceError("Step 6T Supabase verifier received the wrong storage backend.")
    return _verify_storage_backend(storage)


def _verify_storage_backend(storage: WNBADurableStorageBackend) -> dict[str, Any]:
    try:
        if not storage.exists(FEED_OBJECT_KEY):
            raise WNBAStep6TEvidenceError("Step 6T durable feed object does not exist.")
        if not storage.exists(CANARY_MARKER_OBJECT_KEY):
            raise WNBAStep6TEvidenceError("Step 6T durable canary marker object does not exist.")
        feed_raw = storage.read_bytes(FEED_OBJECT_KEY)
        marker_raw = storage.read_bytes(CANARY_MARKER_OBJECT_KEY)
        marker = _read_json_bytes(marker_raw, label="Step 6T durable canary marker")
        activation_id = _clean(marker.get("activation_id")) or "invalid"
        backup_key = _backup_key(activation_id)
        backup_exists = storage.exists(backup_key)
        backup_raw = storage.read_bytes(backup_key) if backup_exists else None
    except WNBAStep6TEvidenceError:
        raise
    except (WNBADurableStorageError, WNBADurableStorageNotReadyError) as exc:
        raise WNBAStep6TEvidenceError("Step 6T durable evidence read failed.") from exc
    return _validate_completed_evidence(
        backend_id=storage.backend_id,
        marker=marker,
        marker_raw=marker_raw,
        feed_raw=feed_raw,
        backup_exists=backup_exists,
        backup_raw=backup_raw,
    )


def verify_step6t_canary_evidence(
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Explicitly verify completed canary evidence using read-only storage access."""
    environment = _environment(env)
    _require_safe_completed_environment(environment)
    try:
        backend_name = resolve_storage_backend_name(environment)
    except WNBADurableStorageModelInputError as exc:
        raise WNBAStep6TEvidenceError(str(exc)) from exc
    if backend_name == FILESYSTEM_BACKEND:
        return _verify_filesystem(environment)
    if backend_name == SUPABASE_BACKEND:
        return _verify_supabase(environment)
    raise WNBAStep6TEvidenceError(f"Unsupported Step 6T storage backend {backend_name!r}.")


def get_step6t_canary_evidence_status(
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Network-free, read-only configuration status for Step 6T evidence verification."""
    environment = _environment(env)
    selected_backend: str | None = None
    configuration_error: str | None = None
    supabase_configuration: dict[str, Any] | None = None
    try:
        selected_backend = resolve_storage_backend_name(environment)
    except WNBADurableStorageModelInputError as exc:
        configuration_error = str(exc)

    if selected_backend == SUPABASE_BACKEND:
        supabase_configuration = get_step6r_supabase_storage_status(environment)
        if supabase_configuration.get("configuration_ready") is not True:
            configuration_error = str(
                supabase_configuration.get("configuration_error")
                or "Step 6R Supabase configuration is not ready."
            )

    temporary_write_switches_off = not any(
        _truthy(environment, name, False)
        for name in (CANARY_ENABLED_ENV, DIRECT_SYNC_ENABLED_ENV, RECONCILED_SYNC_ENABLED_ENV)
    )
    production_runtime_off = not _truthy(environment, PRODUCTION_RUNTIME_ENV, False)
    configuration_ready = bool(
        configuration_error is None
        and selected_backend in {FILESYSTEM_BACKEND, SUPABASE_BACKEND}
        and temporary_write_switches_off
        and production_runtime_off
    )
    if configuration_error is None and not temporary_write_switches_off:
        configuration_error = "Temporary Step 6J write switches must all be OFF before evidence verification."
    if configuration_error is None and not production_runtime_off:
        configuration_error = "WNBA production runtime must remain OFF during Step 6T evidence verification."

    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6t_canary_evidence_status",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "selected_backend": selected_backend,
        "configuration_ready": configuration_ready,
        "configuration_error": configuration_error,
        "verification_requires_network": selected_backend == SUPABASE_BACKEND,
        "verification_is_read_only": True,
        "supabase_configuration": supabase_configuration,
        "scheduler_authorized": False,
        "handoff": {
            "step6k_modified": False,
            "step6k_network_free_contract_preserved": True,
            "step6k_scheduler_authority_bypassed": False,
            "later_storage_aware_activation_integration_required": True,
        },
        "safety": {
            "network_used_by_status": False,
            "storage_read_performed_by_status": False,
            "storage_write_performed_by_status": False,
            "scheduler_started": False,
            "scheduler_authorized_by_step6t": False,
            "sportsbook_called": False,
            "monte_carlo_run": False,
            "wager_action_performed": False,
            "secret_value_returned": False,
        },
    }
