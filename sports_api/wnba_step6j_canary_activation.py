"""Step 6J one-shot canary activation for the reconciled DraftKings -> Kyre feed.

Step 6J is the first intentional durable market-feed write. It does not start
or approve the WNBA production scheduler. The canary is fail-closed, requires
all Step 6I write gates plus a one-time activation id, backs up the exact prior
feed bytes on the persistent disk, verifies the exact Step 6I-approved payload
after the atomic Step 6C write, and restores the prior bytes automatically if
post-write verification fails.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

from sports_api.collectors.wnba_kyre_market_feed import (
    resolve_kyre_market_feed_path,
    validate_kyre_market_feed,
)
from sports_api.wnba_production_runtime_readiness import ACTIVATION_ENV as PRODUCTION_RUNTIME_ENV
from sports_api.wnba_reconciled_direct_sync import (
    RECONCILED_SYNC_ENABLED_ENV,
    persistent_feed_sha256,
    sync_reconciled_draftkings_to_kyre_feed,
)
from sports_api.wnba_step6d_direct_integration import (
    DIRECT_SYNC_ENABLED_ENV,
    DIRECT_SYNC_PROVIDER_ENV,
    SUPPORTED_DIRECT_PROVIDER,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 6J controlled canary activation"
MODEL_VERSION = "wnba_step_6j_controlled_canary_activation_v1"
SCHEMA_VERSION = MODEL_VERSION

CANARY_ENABLED_ENV = "WNBA_STEP6J_CANARY_ENABLED"
ACTIVATION_ID_ENV = "WNBA_STEP6J_ACTIVATION_ID"
MARKER_FILENAME = ".wnba-step6j-canary-state.json"
LOCK_FILENAME = ".wnba-step6j-canary.lock"
BACKUP_PREFIX = ".wnba-step6j-backup-"
_ACTIVATION_ID_RE = re.compile(r"^[A-Za-z0-9._-]{6,160}$")


class WNBAStep6JCanaryError(RuntimeError):
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


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _valid_activation_id(value: Any) -> str:
    activation_id = _clean(value)
    if not activation_id or not _ACTIVATION_ID_RE.fullmatch(activation_id):
        raise WNBAStep6JCanaryError("Step 6J requires a valid one-time activation id.")
    return activation_id


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(temporary_name, 0o600)
        except OSError:
            pass
        os.replace(temporary_name, path)
    finally:
        try:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
        except OSError:
            pass


def _write_json(path: Path, document: Mapping[str, Any]) -> None:
    payload = (json.dumps(dict(document), indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    _atomic_write_bytes(path, payload)


def _read_marker(path: Path) -> dict[str, Any] | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise WNBAStep6JCanaryError("Step 6J canary state could not be read.") from exc
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise WNBAStep6JCanaryError("Step 6J canary state is invalid JSON.") from exc
    if not isinstance(document, dict):
        raise WNBAStep6JCanaryError("Step 6J canary state must be an object.")
    return document


def _backup_path(target: Path, activation_id: str) -> Path:
    return target.parent / f"{BACKUP_PREFIX}{activation_id}.bin"


def _marker_path(target: Path) -> Path:
    return target.parent / MARKER_FILENAME


def _lock_path(target: Path) -> Path:
    return target.parent / LOCK_FILENAME


def _restore_prewrite_state(*, target: Path, backup: Path, preexisting: bool, pre_sha256: str | None) -> dict[str, Any]:
    if preexisting:
        if not backup.is_file():
            raise WNBAStep6JCanaryError("Step 6J rollback backup is missing.")
        raw = backup.read_bytes()
        if pre_sha256 and _sha256_bytes(raw) != pre_sha256:
            raise WNBAStep6JCanaryError("Step 6J rollback backup hash does not match the frozen pre-write feed.")
        _atomic_write_bytes(target, raw)
        restored = target.read_bytes()
        restored_sha = _sha256_bytes(restored)
        if pre_sha256 and restored_sha != pre_sha256:
            raise WNBAStep6JCanaryError("Step 6J rollback verification failed after restoring the prior feed.")
        return {"restored": True, "preexisting_feed_restored": True, "restored_sha256": restored_sha}
    try:
        target.unlink()
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise WNBAStep6JCanaryError("Step 6J rollback could not remove the newly created feed.") from exc
    return {"restored": True, "preexisting_feed_restored": False, "restored_sha256": None}


def _require_canary_gate(environment: Mapping[str, str], supplied_activation_id: str) -> str:
    if not _truthy(environment, CANARY_ENABLED_ENV, False):
        raise WNBAStep6JCanaryError(f"{CANARY_ENABLED_ENV}=true is required for the one-shot canary.")
    configured_activation_id = _valid_activation_id(environment.get(ACTIVATION_ID_ENV))
    supplied = _valid_activation_id(supplied_activation_id)
    if supplied != configured_activation_id:
        raise WNBAStep6JCanaryError("Step 6J activation id does not match the configured canary id.")
    if _truthy(environment, PRODUCTION_RUNTIME_ENV, False):
        raise WNBAStep6JCanaryError("Step 6J refuses to run while the WNBA production runtime is enabled.")
    if not _truthy(environment, DIRECT_SYNC_ENABLED_ENV, False):
        raise WNBAStep6JCanaryError(f"{DIRECT_SYNC_ENABLED_ENV}=true is required.")
    provider = (_clean(environment.get(DIRECT_SYNC_PROVIDER_ENV)) or SUPPORTED_DIRECT_PROVIDER).casefold()
    if provider != SUPPORTED_DIRECT_PROVIDER:
        raise WNBAStep6JCanaryError(f"{DIRECT_SYNC_PROVIDER_ENV} must be {SUPPORTED_DIRECT_PROVIDER}.")
    if not _truthy(environment, RECONCILED_SYNC_ENABLED_ENV, False):
        raise WNBAStep6JCanaryError(f"{RECONCILED_SYNC_ENABLED_ENV}=true is required.")
    return configured_activation_id


def get_step6j_canary_status(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Network-free, read-only status for the durable canary state."""
    environment = _environment(env)
    target = resolve_kyre_market_feed_path(env=environment)
    marker = _read_marker(_marker_path(target))
    current_sha = None
    current_size = 0
    if target.is_file():
        raw = target.read_bytes()
        current_sha = _sha256_bytes(raw)
        current_size = len(raw)
    marker_summary = None
    if marker:
        marker_summary = {
            key: marker.get(key)
            for key in (
                "activation_id", "status", "started_at_utc", "completed_at_utc", "rolled_back_at_utc",
                "date", "season", "preexisting_feed", "pre_write_sha256", "post_write_sha256",
                "verified_persistent_feed_sha256", "offer_side_count", "rollback_verified",
            )
        }
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6j_canary_status",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _now_iso(),
        "canary_enabled": _truthy(environment, CANARY_ENABLED_ENV, False),
        "activation_id_configured": bool(_clean(environment.get(ACTIVATION_ID_ENV))),
        "direct_sync_enabled": _truthy(environment, DIRECT_SYNC_ENABLED_ENV, False),
        "reconciled_sync_enabled": _truthy(environment, RECONCILED_SYNC_ENABLED_ENV, False),
        "production_runtime_enabled": _truthy(environment, PRODUCTION_RUNTIME_ENV, False),
        "feed_exists": target.is_file(),
        "feed_size_bytes": current_size,
        "feed_content_sha256": current_sha,
        "canary_state": marker_summary,
        "safety": {
            "network_used_by_status": False,
            "feed_write_performed_by_status": False,
            "scheduler_started_by_step6j": False,
            "monte_carlo_run": False,
            "paid_odds_vendor_used": False,
            "wager_action_performed": False,
            "rollback_backup_persisted": bool(marker and marker.get("backup_present")),
        },
    }


def run_step6j_canary(*, date: str, season: int, activation_id: str, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Perform exactly one guarded durable write and verify/rollback it."""
    environment = _environment(env)
    configured_activation_id = _require_canary_gate(environment, activation_id)
    target = resolve_kyre_market_feed_path(env=environment)
    target.parent.mkdir(parents=True, exist_ok=True)
    marker_path = _marker_path(target)
    backup = _backup_path(target, configured_activation_id)

    with _lock_path(target).open("a+b") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        marker = _read_marker(marker_path)
        if marker and marker.get("status") in {"completed", "manually_rolled_back"}:
            if marker.get("activation_id") != configured_activation_id:
                raise WNBAStep6JCanaryError("Step 6J has already reached a terminal state under another activation id.")
            if marker.get("status") == "manually_rolled_back":
                raise WNBAStep6JCanaryError("Step 6J canary was already manually rolled back; this activation id cannot be replayed.")
            return {
                "source": MODEL_SOURCE,
                "data_type": "wnba_step6j_canary_result",
                "schema_version": SCHEMA_VERSION,
                "model_version": MODEL_VERSION,
                "activation_id": configured_activation_id,
                "status": "completed",
                "already_completed": True,
                "date": marker.get("date"),
                "season": marker.get("season"),
                "offer_side_count": marker.get("offer_side_count"),
                "pre_write_sha256": marker.get("pre_write_sha256"),
                "post_write_sha256": marker.get("post_write_sha256"),
                "verified_persistent_feed_sha256": marker.get("verified_persistent_feed_sha256"),
                "rollback_available": bool(marker.get("backup_present") or not marker.get("preexisting_feed")),
                "safety": {
                    "feed_write_performed": False,
                    "idempotent_replay_blocked": True,
                    "production_runtime_enabled": False,
                    "scheduler_started_by_step6j": False,
                    "monte_carlo_run": False,
                    "wager_action_performed": False,
                },
            }
        if marker and marker.get("activation_id") == configured_activation_id and marker.get("status") in {"started", "verification_failed"}:
            _restore_prewrite_state(
                target=target,
                backup=backup,
                preexisting=bool(marker.get("preexisting_feed")),
                pre_sha256=_clean(marker.get("pre_write_sha256")),
            )

        preexisting = target.is_file()
        pre_raw = target.read_bytes() if preexisting else b""
        pre_sha = _sha256_bytes(pre_raw) if preexisting else None
        if preexisting:
            _atomic_write_bytes(backup, pre_raw)
            if _sha256_bytes(backup.read_bytes()) != pre_sha:
                raise WNBAStep6JCanaryError("Step 6J could not verify the pre-write rollback backup.")
        else:
            try:
                backup.unlink()
            except FileNotFoundError:
                pass

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
        }
        _write_json(marker_path, started)

        write_attempted = False
        try:
            write_attempted = True
            sync_result = sync_reconciled_draftkings_to_kyre_feed(
                date=str(date), season=int(season), env=environment, path=str(target)
            )
            if sync_result.get("synced") is not True or sync_result.get("feed_write_performed") is not True:
                raise WNBAStep6JCanaryError("Step 6I did not report a completed durable write.")
            if not target.is_file():
                raise WNBAStep6JCanaryError("Step 6J durable feed is missing after the Step 6I write.")

            post_raw = target.read_bytes()
            post_sha = _sha256_bytes(post_raw)
            storage = sync_result.get("storage") or {}
            if storage.get("content_sha256") != post_sha:
                raise WNBAStep6JCanaryError("Step 6J stored-byte hash does not match the Step 6C writer result.")
            try:
                stored_document = json.loads(post_raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise WNBAStep6JCanaryError("Step 6J stored feed is not valid UTF-8 JSON.") from exc
            validated = validate_kyre_market_feed(stored_document)
            verified_persistent_sha = persistent_feed_sha256(validated)
            expected_persistent_sha = _clean(sync_result.get("persistent_feed_sha256"))
            if not expected_persistent_sha or verified_persistent_sha != expected_persistent_sha:
                raise WNBAStep6JCanaryError("Step 6J post-write feed identity does not match the Step 6I approved snapshot.")
            if validated["date"] != str(date) or int(validated["season"]) != int(season):
                raise WNBAStep6JCanaryError("Step 6J stored feed date/season does not match the approved canary request.")
            offer_count = len(validated["offers"])
            if int(sync_result.get("offer_side_count") or -1) != offer_count:
                raise WNBAStep6JCanaryError("Step 6J stored offer count does not match the Step 6I attestation.")

            completed = dict(started)
            completed.update({
                "status": "completed",
                "completed_at_utc": _now_iso(),
                "post_write_sha256": post_sha,
                "verified_persistent_feed_sha256": verified_persistent_sha,
                "snapshot_sha256": sync_result.get("snapshot_sha256"),
                "reconciliation_fingerprint_sha256": sync_result.get("reconciliation_fingerprint_sha256"),
                "attestation_sha256": sync_result.get("attestation_sha256"),
                "offer_side_count": offer_count,
                "rollback_verified": True,
            })
            _write_json(marker_path, completed)
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
                "post_write_sha256": post_sha,
                "snapshot_sha256": sync_result.get("snapshot_sha256"),
                "verified_persistent_feed_sha256": verified_persistent_sha,
                "reconciliation_fingerprint_sha256": sync_result.get("reconciliation_fingerprint_sha256"),
                "attestation_sha256": sync_result.get("attestation_sha256"),
                "rollback_available": True,
                "safety": {
                    "feed_write_performed": True,
                    "exact_step6i_snapshot_verified_after_write": True,
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
                rollback = _restore_prewrite_state(target=target, backup=backup, preexisting=preexisting, pre_sha256=pre_sha)
                failed = dict(started)
                failed.update({
                    "status": "rolled_back",
                    "rolled_back_at_utc": _now_iso(),
                    "failure_type": type(exc).__name__,
                    "write_attempted": write_attempted,
                    "rollback_verified": bool(rollback.get("restored")),
                })
                _write_json(marker_path, failed)
            except Exception as rollback_exc:
                raise WNBAStep6JCanaryError(
                    f"Step 6J canary failed ({type(exc).__name__}) and rollback verification also failed ({type(rollback_exc).__name__})."
                ) from rollback_exc
            raise WNBAStep6JCanaryError(
                f"Step 6J canary failed closed and restored the pre-write feed ({type(exc).__name__})."
            ) from exc


def rollback_step6j_canary(*, activation_id: str, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Restore the exact pre-canary bytes while the Step 6J gate is explicitly enabled."""
    environment = _environment(env)
    configured_activation_id = _require_canary_gate(environment, activation_id)
    target = resolve_kyre_market_feed_path(env=environment)
    marker_path = _marker_path(target)
    backup = _backup_path(target, configured_activation_id)
    with _lock_path(target).open("a+b") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        marker = _read_marker(marker_path)
        if not marker or marker.get("activation_id") != configured_activation_id:
            raise WNBAStep6JCanaryError("No matching Step 6J canary state exists for rollback.")
        if marker.get("status") not in {"completed", "rolled_back", "manually_rolled_back"}:
            raise WNBAStep6JCanaryError("Step 6J canary is not in a rollback-safe terminal state.")
        rollback = _restore_prewrite_state(
            target=target,
            backup=backup,
            preexisting=bool(marker.get("preexisting_feed")),
            pre_sha256=_clean(marker.get("pre_write_sha256")),
        )
        updated = dict(marker)
        updated.update({
            "status": "manually_rolled_back",
            "rolled_back_at_utc": _now_iso(),
            "rollback_verified": bool(rollback.get("restored")),
        })
        _write_json(marker_path, updated)
        return {
            "source": MODEL_SOURCE,
            "data_type": "wnba_step6j_canary_rollback_result",
            "schema_version": SCHEMA_VERSION,
            "model_version": MODEL_VERSION,
            "activation_id": configured_activation_id,
            "status": "manually_rolled_back",
            "rollback_verified": bool(rollback.get("restored")),
            "restored_sha256": rollback.get("restored_sha256"),
            "safety": {
                "production_runtime_enabled": False,
                "scheduler_started_by_step6j": False,
                "monte_carlo_run": False,
                "wager_action_performed": False,
            },
        }
