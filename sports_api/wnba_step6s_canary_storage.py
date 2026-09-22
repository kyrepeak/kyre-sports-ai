"""Step 6S storage-aware Step 6J canary orchestration.

Step 6R is frozen. Step 6S migrates the *transported* Step 6J canary onto the
Step 6Q durable-storage contract without rewriting the proven filesystem core:
filesystem selection delegates byte-for-byte behavior to Step 6J, while the
Supabase selection stores the feed, canary marker, rollback backup, and lock in
the Step 6R backend.

The Supabase path is intentionally not activated by this module. It requires an
explicit Supabase backend configuration plus the existing Step 6J write gates.
The public readiness report is network-free and performs no storage mutation.
"""
from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from sports_api.collectors.wnba_kyre_market_feed import validate_kyre_market_feed
from sports_api.wnba_reconciled_direct_sync import (
    persistent_feed_sha256,
    sync_reconciled_draftkings_to_kyre_feed,
)
from sports_api.wnba_step6j_canary_activation import (
    BACKUP_PREFIX,
    WNBAStep6JCanaryError,
    _clean,
    _now_iso,
    _require_canary_gate,
    rollback_step6j_canary as _legacy_rollback_step6j_canary,
    run_step6j_canary as _legacy_run_step6j_canary,
)
from sports_api.wnba_step6q_durable_storage import (
    CANARY_LOCK_OBJECT_KEY,
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

MODEL_SOURCE = "Kyre Sports API WNBA Step 6S storage-aware Step 6J canary"
MODEL_VERSION = "wnba_step_6s_storage_aware_step6j_canary_v1"
SCHEMA_VERSION = MODEL_VERSION

_TERMINAL_REPLAY_BLOCKED = {"rolled_back", "manually_rolled_back"}
_RECOVERABLE_INTERRUPTED = {"started", "verification_failed"}


class WNBAStep6SCanaryStorageError(WNBAStep6JCanaryError):
    """Step 6S failures remain compatible with the Step 6J transport error type."""


def _environment(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _backend_name(environment: Mapping[str, str]) -> str:
    try:
        return resolve_storage_backend_name(environment)
    except WNBADurableStorageModelInputError as exc:
        raise WNBAStep6SCanaryStorageError(str(exc)) from exc


def _backup_key(activation_id: str) -> str:
    return f"{BACKUP_PREFIX}{activation_id}.bin"


def _marker_bytes(document: Mapping[str, Any]) -> bytes:
    return (json.dumps(dict(document), indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _read_marker(storage: WNBADurableStorageBackend) -> dict[str, Any] | None:
    try:
        if not storage.exists(CANARY_MARKER_OBJECT_KEY):
            return None
        raw = storage.read_bytes(CANARY_MARKER_OBJECT_KEY)
    except (WNBADurableStorageError, WNBADurableStorageNotReadyError) as exc:
        raise WNBAStep6SCanaryStorageError("Step 6S canary state could not be read from durable storage.") from exc
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WNBAStep6SCanaryStorageError("Step 6S canary state is invalid UTF-8 JSON.") from exc
    if not isinstance(document, dict):
        raise WNBAStep6SCanaryStorageError("Step 6S canary state must be a JSON object.")
    return document


def _write_marker(storage: WNBADurableStorageBackend, document: Mapping[str, Any]) -> None:
    payload = _marker_bytes(document)
    try:
        metadata = storage.write_bytes_atomic(CANARY_MARKER_OBJECT_KEY, payload)
        stored = storage.read_bytes(CANARY_MARKER_OBJECT_KEY)
    except (WNBADurableStorageError, WNBADurableStorageNotReadyError) as exc:
        raise WNBAStep6SCanaryStorageError("Step 6S canary state could not be durably written and verified.") from exc
    expected = _sha256_bytes(payload)
    if metadata.content_sha256 != expected or stored != payload or _sha256_bytes(stored) != expected:
        raise WNBAStep6SCanaryStorageError("Step 6S durable canary marker failed byte-integrity verification.")


def _build_supabase_storage(environment: Mapping[str, str]) -> WNBADurableStorageBackend:
    try:
        storage = build_step6r_durable_storage(env=environment)
    except (WNBADurableStorageError, WNBADurableStorageNotReadyError, WNBADurableStorageModelInputError) as exc:
        raise WNBAStep6SCanaryStorageError("Step 6S Supabase durable storage is not ready.") from exc
    if storage.backend_id != SUPABASE_BACKEND:
        raise WNBAStep6SCanaryStorageError("Step 6S Supabase canary requires the Supabase durable-storage backend.")
    return storage


def _restore_prewrite_state(
    *,
    storage: WNBADurableStorageBackend,
    backup_key: str,
    preexisting: bool,
    pre_sha256: str | None,
) -> dict[str, Any]:
    try:
        if preexisting:
            if not storage.exists(backup_key):
                raise WNBAStep6SCanaryStorageError("Step 6S rollback backup is missing.")
            raw = storage.read_bytes(backup_key)
            if pre_sha256 and _sha256_bytes(raw) != pre_sha256:
                raise WNBAStep6SCanaryStorageError(
                    "Step 6S rollback backup hash does not match the frozen pre-write feed."
                )
            metadata = storage.write_bytes_atomic(FEED_OBJECT_KEY, raw)
            restored = storage.read_bytes(FEED_OBJECT_KEY)
            restored_sha = _sha256_bytes(restored)
            if metadata.content_sha256 != restored_sha or (pre_sha256 and restored_sha != pre_sha256):
                raise WNBAStep6SCanaryStorageError(
                    "Step 6S rollback verification failed after restoring the prior feed."
                )
            return {
                "restored": True,
                "preexisting_feed_restored": True,
                "restored_sha256": restored_sha,
            }
        storage.delete(FEED_OBJECT_KEY)
        if storage.exists(FEED_OBJECT_KEY):
            raise WNBAStep6SCanaryStorageError("Step 6S rollback could not remove the newly created feed.")
        return {
            "restored": True,
            "preexisting_feed_restored": False,
            "restored_sha256": None,
        }
    except WNBAStep6SCanaryStorageError:
        raise
    except (WNBADurableStorageError, WNBADurableStorageNotReadyError) as exc:
        raise WNBAStep6SCanaryStorageError("Step 6S rollback storage operation failed.") from exc


def _completed_replay(marker: Mapping[str, Any], activation_id: str) -> dict[str, Any]:
    if marker.get("activation_id") != activation_id:
        raise WNBAStep6SCanaryStorageError(
            "Step 6S has already reached a terminal state under another activation id."
        )
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6j_canary_result",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "activation_id": activation_id,
        "status": "completed",
        "already_completed": True,
        "date": marker.get("date"),
        "season": marker.get("season"),
        "offer_side_count": marker.get("offer_side_count"),
        "pre_write_sha256": marker.get("pre_write_sha256"),
        "post_write_sha256": marker.get("post_write_sha256"),
        "verified_persistent_feed_sha256": marker.get("verified_persistent_feed_sha256"),
        "rollback_available": bool(marker.get("backup_present") or not marker.get("preexisting_feed")),
        "storage_backend": SUPABASE_BACKEND,
        "step6s_storage_migration": True,
        "safety": {
            "feed_write_performed": False,
            "idempotent_replay_blocked": True,
            "production_runtime_enabled": False,
            "scheduler_started_by_step6j": False,
            "monte_carlo_run": False,
            "wager_action_performed": False,
        },
    }


def _run_supabase_step6j_canary(
    *,
    date: str,
    season: int,
    activation_id: str,
    environment: Mapping[str, str],
) -> dict[str, Any]:
    configured_activation_id = _require_canary_gate(environment, activation_id)
    storage = _build_supabase_storage(environment)
    backup_key = _backup_key(configured_activation_id)

    try:
        lock_context = storage.exclusive_lock(CANARY_LOCK_OBJECT_KEY)
        with lock_context:
            marker = _read_marker(storage)
            if marker:
                marker_activation = _clean(marker.get("activation_id"))
                marker_status = _clean(marker.get("status"))
                if marker_status == "completed":
                    return _completed_replay(marker, configured_activation_id)
                if marker_status in _TERMINAL_REPLAY_BLOCKED:
                    if marker_activation != configured_activation_id:
                        raise WNBAStep6SCanaryStorageError(
                            "Step 6S has already reached a terminal state under another activation id."
                        )
                    raise WNBAStep6SCanaryStorageError(
                        "Step 6S canary already rolled back; this one-shot activation id cannot be replayed."
                    )
                if marker_activation and marker_activation != configured_activation_id:
                    raise WNBAStep6SCanaryStorageError(
                        "Step 6S found durable canary state owned by another activation id."
                    )
                if marker_status in _RECOVERABLE_INTERRUPTED:
                    _restore_prewrite_state(
                        storage=storage,
                        backup_key=backup_key,
                        preexisting=bool(marker.get("preexisting_feed")),
                        pre_sha256=_clean(marker.get("pre_write_sha256")),
                    )
                elif marker_status:
                    raise WNBAStep6SCanaryStorageError(
                        f"Step 6S refuses unknown durable canary state {marker_status!r}."
                    )

            preexisting = storage.exists(FEED_OBJECT_KEY)
            pre_raw = storage.read_bytes(FEED_OBJECT_KEY) if preexisting else b""
            pre_sha = _sha256_bytes(pre_raw) if preexisting else None
            if preexisting:
                backup_metadata = storage.write_bytes_atomic(backup_key, pre_raw)
                verified_backup = storage.read_bytes(backup_key)
                if (
                    backup_metadata.content_sha256 != pre_sha
                    or verified_backup != pre_raw
                    or _sha256_bytes(verified_backup) != pre_sha
                ):
                    raise WNBAStep6SCanaryStorageError(
                        "Step 6S could not verify the pre-write rollback backup."
                    )
            else:
                storage.delete(backup_key)

            started = {
                "source": MODEL_SOURCE,
                "schema_version": SCHEMA_VERSION,
                "model_version": MODEL_VERSION,
                "activation_id": configured_activation_id,
                "status": "started",
                "started_at_utc": _now_iso(),
                "date": str(date),
                "season": int(season),
                "preexisting_feed": preexisting,
                "pre_write_sha256": pre_sha,
                "backup_present": bool(preexisting),
                "rollback_verified": False,
                "storage_backend": SUPABASE_BACKEND,
                "step6s_storage_migration": True,
            }
            _write_marker(storage, started)

            stage_write_attempted = False
            durable_feed_write_attempted = False
            try:
                with tempfile.TemporaryDirectory(prefix="wnba-step6s-stage-") as temporary_root:
                    stage_path = Path(temporary_root) / FEED_OBJECT_KEY
                    stage_write_attempted = True
                    sync_result = sync_reconciled_draftkings_to_kyre_feed(
                        date=str(date),
                        season=int(season),
                        env=environment,
                        path=str(stage_path),
                    )
                    if sync_result.get("synced") is not True or sync_result.get("feed_write_performed") is not True:
                        raise WNBAStep6SCanaryStorageError(
                            "Step 6I did not report a completed staging write for Step 6S."
                        )
                    if not stage_path.is_file():
                        raise WNBAStep6SCanaryStorageError(
                            "Step 6S staging feed is missing after the Step 6I write."
                        )
                    post_raw = stage_path.read_bytes()

                post_sha = _sha256_bytes(post_raw)
                step6i_storage = sync_result.get("storage") or {}
                if step6i_storage.get("content_sha256") != post_sha:
                    raise WNBAStep6SCanaryStorageError(
                        "Step 6S staging-byte hash does not match the Step 6I writer result."
                    )
                try:
                    stored_document = json.loads(post_raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise WNBAStep6SCanaryStorageError(
                        "Step 6S staged feed is not valid UTF-8 JSON."
                    ) from exc
                validated = validate_kyre_market_feed(stored_document)
                verified_persistent_sha = persistent_feed_sha256(validated)
                expected_persistent_sha = _clean(sync_result.get("persistent_feed_sha256"))
                if not expected_persistent_sha or verified_persistent_sha != expected_persistent_sha:
                    raise WNBAStep6SCanaryStorageError(
                        "Step 6S staged feed identity does not match the Step 6I approved snapshot."
                    )
                if validated["date"] != str(date) or int(validated["season"]) != int(season):
                    raise WNBAStep6SCanaryStorageError(
                        "Step 6S staged feed date/season does not match the approved canary request."
                    )
                offer_count = len(validated["offers"])
                if int(sync_result.get("offer_side_count") or -1) != offer_count:
                    raise WNBAStep6SCanaryStorageError(
                        "Step 6S staged offer count does not match the Step 6I attestation."
                    )

                durable_feed_write_attempted = True
                metadata = storage.write_bytes_atomic(FEED_OBJECT_KEY, post_raw)
                durable_raw = storage.read_bytes(FEED_OBJECT_KEY)
                durable_sha = _sha256_bytes(durable_raw)
                if (
                    metadata.content_sha256 != post_sha
                    or durable_raw != post_raw
                    or durable_sha != post_sha
                ):
                    raise WNBAStep6SCanaryStorageError(
                        "Step 6S Supabase durable feed failed exact post-write byte verification."
                    )

                completed = dict(started)
                completed.update(
                    {
                        "status": "completed",
                        "completed_at_utc": _now_iso(),
                        "post_write_sha256": durable_sha,
                        "verified_persistent_feed_sha256": verified_persistent_sha,
                        "snapshot_sha256": sync_result.get("snapshot_sha256"),
                        "reconciliation_fingerprint_sha256": sync_result.get(
                            "reconciliation_fingerprint_sha256"
                        ),
                        "attestation_sha256": sync_result.get("attestation_sha256"),
                        "offer_side_count": offer_count,
                        "rollback_verified": True,
                    }
                )
                _write_marker(storage, completed)
                return {
                    "source": MODEL_SOURCE,
                    "data_type": "wnba_step6j_canary_result",
                    "schema_version": SCHEMA_VERSION,
                    "model_version": MODEL_VERSION,
                    "activation_id": configured_activation_id,
                    "status": "completed",
                    "already_completed": False,
                    "date": str(date),
                    "season": int(season),
                    "offer_side_count": offer_count,
                    "pre_write_sha256": pre_sha,
                    "post_write_sha256": durable_sha,
                    "snapshot_sha256": sync_result.get("snapshot_sha256"),
                    "verified_persistent_feed_sha256": verified_persistent_sha,
                    "reconciliation_fingerprint_sha256": sync_result.get(
                        "reconciliation_fingerprint_sha256"
                    ),
                    "attestation_sha256": sync_result.get("attestation_sha256"),
                    "rollback_available": True,
                    "storage_backend": SUPABASE_BACKEND,
                    "step6s_storage_migration": True,
                    "safety": {
                        "feed_write_performed": True,
                        "exact_step6i_snapshot_verified_before_remote_write": True,
                        "exact_remote_bytes_verified_after_write": True,
                        "prewrite_backup_verified": True,
                        "production_runtime_enabled": False,
                        "scheduler_started_by_step6j": False,
                        "paid_odds_vendor_used": False,
                        "monte_carlo_run": False,
                        "wager_action_performed": False,
                    },
                }
            except Exception as exc:
                try:
                    rollback = _restore_prewrite_state(
                        storage=storage,
                        backup_key=backup_key,
                        preexisting=preexisting,
                        pre_sha256=pre_sha,
                    )
                    failed = dict(started)
                    failed.update(
                        {
                            "status": "rolled_back",
                            "rolled_back_at_utc": _now_iso(),
                            "failure_type": type(exc).__name__,
                            "stage_write_attempted": stage_write_attempted,
                            "write_attempted": durable_feed_write_attempted,
                            "rollback_verified": bool(rollback.get("restored")),
                        }
                    )
                    _write_marker(storage, failed)
                except Exception as rollback_exc:
                    raise WNBAStep6SCanaryStorageError(
                        "Step 6S Supabase canary failed and rollback verification also failed "
                        f"({type(exc).__name__}; {type(rollback_exc).__name__})."
                    ) from rollback_exc
                raise WNBAStep6SCanaryStorageError(
                    "Step 6S Supabase canary failed closed and restored the pre-write feed "
                    f"({type(exc).__name__})."
                ) from exc
    except WNBAStep6SCanaryStorageError:
        raise
    except (WNBADurableStorageError, WNBADurableStorageNotReadyError) as exc:
        raise WNBAStep6SCanaryStorageError(
            "Step 6S could not acquire or release the Supabase durable canary lock."
        ) from exc


def run_storage_aware_step6j_canary(
    *,
    date: str,
    season: int,
    activation_id: str,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Dispatch Step 6J to its frozen filesystem path or the Step 6S Supabase path."""
    environment = _environment(env)
    backend_name = _backend_name(environment)
    if backend_name == FILESYSTEM_BACKEND:
        return _legacy_run_step6j_canary(
            date=str(date),
            season=int(season),
            activation_id=activation_id,
            env=environment,
        )
    if backend_name == SUPABASE_BACKEND:
        return _run_supabase_step6j_canary(
            date=str(date),
            season=int(season),
            activation_id=activation_id,
            environment=environment,
        )
    raise WNBAStep6SCanaryStorageError(
        f"Unsupported Step 6S durable-storage backend {backend_name!r}."
    )


def _rollback_supabase_step6j_canary(
    *,
    activation_id: str,
    environment: Mapping[str, str],
) -> dict[str, Any]:
    configured_activation_id = _require_canary_gate(environment, activation_id)
    storage = _build_supabase_storage(environment)
    backup_key = _backup_key(configured_activation_id)
    try:
        with storage.exclusive_lock(CANARY_LOCK_OBJECT_KEY):
            marker = _read_marker(storage)
            if not marker or marker.get("activation_id") != configured_activation_id:
                raise WNBAStep6SCanaryStorageError(
                    "No matching Step 6S Supabase canary state exists for rollback."
                )
            if marker.get("status") not in {"completed", "rolled_back", "manually_rolled_back"}:
                raise WNBAStep6SCanaryStorageError(
                    "Step 6S Supabase canary is not in a rollback-safe terminal state."
                )
            rollback = _restore_prewrite_state(
                storage=storage,
                backup_key=backup_key,
                preexisting=bool(marker.get("preexisting_feed")),
                pre_sha256=_clean(marker.get("pre_write_sha256")),
            )
            updated = dict(marker)
            updated.update(
                {
                    "status": "manually_rolled_back",
                    "rolled_back_at_utc": _now_iso(),
                    "rollback_verified": bool(rollback.get("restored")),
                }
            )
            _write_marker(storage, updated)
            return {
                "source": MODEL_SOURCE,
                "data_type": "wnba_step6j_canary_rollback_result",
                "schema_version": SCHEMA_VERSION,
                "model_version": MODEL_VERSION,
                "activation_id": configured_activation_id,
                "status": "manually_rolled_back",
                "rollback_verified": bool(rollback.get("restored")),
                "restored_sha256": rollback.get("restored_sha256"),
                "storage_backend": SUPABASE_BACKEND,
                "step6s_storage_migration": True,
                "safety": {
                    "production_runtime_enabled": False,
                    "scheduler_started_by_step6j": False,
                    "monte_carlo_run": False,
                    "wager_action_performed": False,
                },
            }
    except WNBAStep6SCanaryStorageError:
        raise
    except (WNBADurableStorageError, WNBADurableStorageNotReadyError) as exc:
        raise WNBAStep6SCanaryStorageError(
            "Step 6S could not acquire or release the Supabase durable rollback lock."
        ) from exc


def rollback_storage_aware_step6j_canary(
    *,
    activation_id: str,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Dispatch rollback to the selected Step 6J/6S durable-storage backend."""
    environment = _environment(env)
    backend_name = _backend_name(environment)
    if backend_name == FILESYSTEM_BACKEND:
        return _legacy_rollback_step6j_canary(
            activation_id=activation_id,
            env=environment,
        )
    if backend_name == SUPABASE_BACKEND:
        return _rollback_supabase_step6j_canary(
            activation_id=activation_id,
            environment=environment,
        )
    raise WNBAStep6SCanaryStorageError(
        f"Unsupported Step 6S durable-storage backend {backend_name!r}."
    )


def get_step6s_canary_storage_status(
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Network-free, read-only report of the Step 6J -> Step 6S storage dispatch."""
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

    configuration_ready = bool(
        configuration_error is None
        and selected_backend in {FILESYSTEM_BACKEND, SUPABASE_BACKEND}
    )
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6s_canary_storage_status",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "selected_backend": selected_backend,
        "configuration_ready": configuration_ready,
        "configuration_error": configuration_error,
        "filesystem_delegates_to_step6j_unchanged": selected_backend == FILESYSTEM_BACKEND,
        "supabase_canary_supported": True,
        "supabase_configuration": supabase_configuration,
        "migration": {
            "step6j_post_transport_storage_aware": True,
            "feed_object_key": FEED_OBJECT_KEY,
            "marker_object_key": CANARY_MARKER_OBJECT_KEY,
            "lock_object_key": CANARY_LOCK_OBJECT_KEY,
            "rollback_backup_object_prefix": BACKUP_PREFIX,
            "step6k_remote_canary_preflight_migrated": False,
            "step6k_remains_fail_closed_for_supabase_until_later_step": True,
        },
        "safety": {
            "network_used_by_status": False,
            "remote_storage_read_performed_by_status": False,
            "storage_write_performed_by_status": False,
            "live_supabase_canary_executed_by_status": False,
            "scheduler_started": False,
            "render_provisioned": False,
            "sportsbook_called": False,
            "monte_carlo_run": False,
            "wager_action_performed": False,
            "secret_value_returned": False,
        },
    }
