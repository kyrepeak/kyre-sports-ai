"""Step 7G one-shot production scheduler activation.

This operator authorizes exactly one owned-feed refresh + frozen Step 5P cycle.
It does not start the recurring worker.  All process/global runtime switches must
begin OFF and remain OFF; direct/reconciled write gates exist only in a private
environment mapping for the single DraftKings GET -> reconciled staged feed.

Durability:
- the current canonical feed is backed up byte-for-byte in Supabase first;
- the refresh is staged locally so frozen Step 5O can consume the exact bytes;
- those exact staged bytes are copied to the Step 6R Supabase durable object;
- provider snapshots/attempts, publication/run history, and the scheduler mutex
  use the Step 7G Supabase schema;
- publication + scheduler run are committed atomically;
- any downstream failure restores the exact pre-cycle feed bytes before failing.
"""
from __future__ import annotations

import argparse
from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from sports_api.collectors.wnba_kyre_market_feed import (
    KYRE_MARKET_FEED_PATH_ENV,
    MARKET_PROVIDER_MODE_ENV,
    collect_kyre_market_feed,
    validate_kyre_market_feed,
)
from sports_api.wnba_pregame_board_scheduler import (
    AUTO_ARCHIVE_ENABLED_ENV,
    BOARD_STORE_PATH_ENV,
    FEED_STORE_PATH_ENV,
    SCHEDULER_ENABLED_ENV,
    run_pregame_board_cycle,
)
from sports_api.wnba_production_runtime_readiness import ACTIVATION_ENV as PRODUCTION_RUNTIME_ENV
from sports_api.wnba_reconciled_direct_sync import (
    RECONCILED_SYNC_ENABLED_ENV,
    persistent_feed_sha256,
    sync_reconciled_draftkings_to_kyre_feed,
)
from sports_api.wnba_schedule import verify_daily_slate_dataset
import sports_api.wnba_step6d_direct_integration as step6d
from sports_api.wnba_step6d_direct_integration import (
    DIRECT_SYNC_ENABLED_ENV,
    DIRECT_SYNC_PROVIDER_ENV,
    SUPPORTED_DIRECT_PROVIDER,
)
from sports_api.wnba_step6j_canary_activation import CANARY_ENABLED_ENV
from sports_api.wnba_step6l_production_feed_refresh import PRODUCTION_REFRESH_ENABLED_ENV
from sports_api.wnba_step6m_scheduler_orchestration import _run_frozen_cycle_with_scoped_refresh
from sports_api.wnba_step6q_durable_storage import (
    FEED_OBJECT_KEY,
    STORAGE_BACKEND_ENV,
    SUPABASE_BACKEND,
)
from sports_api.wnba_step6r_supabase_storage import build_step6r_durable_storage
from sports_api.wnba_step7g_supabase_scheduler_storage import Step7GSupabaseSchedulerStore
from sports_api.wnba_step7g_transactional_scheduler_commit import Step7GTransactionalSchedulerCommit

MODEL_SOURCE = "Kyre Sports API WNBA Step 7G one-shot production scheduler activation"
MODEL_VERSION = "wnba_step_7g_one_shot_scheduler_activation_v1"
SCHEMA_VERSION = MODEL_VERSION
ACTIVATION_ID = "step7g-20260827-one-shot-v1"
ACTIVATION_MARKER_KEY = ".wnba-step7g-one-shot.json"
PRE_CYCLE_BACKUP_KEY = ".wnba-step7g-precycle-feed.bin"
EXPECTED_PRE_CYCLE_FEED_SHA256 = "7d6363bc12e6ee2351938eb83eb636d89ec25e559fc199b6a904cdeec816b00e"
EXPECTED_STEP6J_MARKER_SHA256 = "64cf7739cdb095546b7954c35f14d7a4244672c3a8ef999f6cc25a93168f46d2"
STEP6J_MARKER_KEY = ".wnba-step6j-canary-state.json"
ALLOWED_SUCCESS_OUTCOMES = {
    "published_new_board",
    "publication_idempotent_replay",
    "feed_unchanged_model_refresh_not_due",
}


class WNBAStep7GActivationError(RuntimeError):
    pass


class WNBAStep7GActivationNotReadyError(WNBAStep7GActivationError):
    pass


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() not in {"", "0", "false", "no", "off", "disabled"}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _marker_bytes(document: Mapping[str, Any]) -> bytes:
    return (json.dumps(dict(document), indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _read_json_object(storage: Any, key: str) -> dict[str, Any] | None:
    if not storage.exists(key):
        return None
    raw = storage.read_bytes(key)
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WNBAStep7GActivationError(f"Durable Step 7G object {key!r} is not valid JSON.") from exc
    if not isinstance(document, dict):
        raise WNBAStep7GActivationError(f"Durable Step 7G object {key!r} must be a JSON object.")
    return document


def _write_verified(storage: Any, key: str, payload: bytes) -> str:
    metadata = storage.write_bytes_atomic(key, payload)
    reread = storage.read_bytes(key)
    digest = _sha256(payload)
    if reread != payload or _sha256(reread) != digest or metadata.content_sha256 != digest:
        raise WNBAStep7GActivationError(f"Durable Step 7G write verification failed for {key!r}.")
    return digest


def _write_marker(storage: Any, document: Mapping[str, Any]) -> str:
    return _write_verified(storage, ACTIVATION_MARKER_KEY, _marker_bytes(document))


def _require_base_fail_closed(environment: Mapping[str, str]) -> None:
    required_off = (
        PRODUCTION_RUNTIME_ENV,
        SCHEDULER_ENABLED_ENV,
        DIRECT_SYNC_ENABLED_ENV,
        RECONCILED_SYNC_ENABLED_ENV,
        CANARY_ENABLED_ENV,
        PRODUCTION_REFRESH_ENABLED_ENV,
    )
    active = [name for name in required_off if _truthy(environment.get(name))]
    if active:
        raise WNBAStep7GActivationNotReadyError(
            "Step 7G requires every production/legacy write switch to begin OFF: " + ", ".join(active)
        )
    backend = str(environment.get(STORAGE_BACKEND_ENV) or "").strip().casefold()
    if backend != SUPABASE_BACKEND:
        raise WNBAStep7GActivationNotReadyError(
            f"Step 7G requires {STORAGE_BACKEND_ENV}={SUPABASE_BACKEND}."
        )


def _require_playable_slate(date: str, season: int) -> dict[str, Any]:
    slate = verify_daily_slate_dataset(date, season)
    integrity = bool((slate.get("slate") or {}).get("slate_integrity_pass"))
    playable = int((slate.get("status_summary") or {}).get("playable_pregame_games") or 0)
    if not integrity:
        raise WNBAStep7GActivationNotReadyError(
            "Step 7G refuses activation because official WNBA slate integrity is not green."
        )
    if playable <= 0:
        raise WNBAStep7GActivationNotReadyError(
            "Step 7G requires at least one official playable pregame WNBA game for the one-shot proof."
        )
    return {
        "slate_integrity_pass": True,
        "playable_pregame_games": playable,
        "source_variant": slate.get("source_variant"),
        "source_url": slate.get("source_url"),
        "verified_at_utc": slate.get("verified_at_utc"),
    }


def _private_cycle_environment(base: Mapping[str, str], stage_path: str) -> dict[str, str]:
    environment = dict(base)
    environment[STORAGE_BACKEND_ENV] = SUPABASE_BACKEND
    environment[PRODUCTION_RUNTIME_ENV] = "false"
    environment[SCHEDULER_ENABLED_ENV] = "false"
    environment[AUTO_ARCHIVE_ENABLED_ENV] = "false"
    environment[PRODUCTION_REFRESH_ENABLED_ENV] = "false"
    environment[CANARY_ENABLED_ENV] = "false"
    environment[MARKET_PROVIDER_MODE_ENV] = "kyre"
    environment[DIRECT_SYNC_ENABLED_ENV] = "true"
    environment[DIRECT_SYNC_PROVIDER_ENV] = SUPPORTED_DIRECT_PROVIDER
    environment[RECONCILED_SYNC_ENABLED_ENV] = "true"
    environment[KYRE_MARKET_FEED_PATH_ENV] = stage_path
    # Frozen Step 5P validates these paths even though the injected Step 7G
    # persistence functions never write SQLite in this operator.
    environment[BOARD_STORE_PATH_ENV] = "/tmp/wnba-step7g-board-unused.sqlite3"
    environment[FEED_STORE_PATH_ENV] = "/tmp/wnba-step7g-feed-unused.sqlite3"
    return environment


def _build_failover_wrapper(store: Step7GSupabaseSchedulerStore):
    original = step6d._ORIGINAL_COLLECT_FAILOVER_LINE_BOARD

    def collect(provider_ids=None, **kwargs: Any):
        forwarded = dict(kwargs)
        forwarded["snapshot_persister"] = store.persist_feed_snapshot
        forwarded["attempt_appender"] = store.append_feed_attempt
        # Bypass the Step 6D auto-sync wrapper: Step 7G already performs exactly
        # one reconciled refresh at Step 6M's provider hook.
        forwarded["kyre_market_collector"] = collect_kyre_market_feed
        return original(provider_ids, **forwarded)

    return collect


def _build_cycle_runner(
    store: Step7GSupabaseSchedulerStore,
    transaction: Step7GTransactionalSchedulerCommit,
):
    def cycle(**kwargs: Any):
        forwarded = dict(kwargs)
        forwarded.update(
            {
                "board_store_path": "/tmp/wnba-step7g-board-unused.sqlite3",
                "feed_store_path": "/tmp/wnba-step7g-feed-unused.sqlite3",
                "publication_persister": transaction.persist_publication,
                "run_appender": transaction.append_scheduler_run,
                "latest_publication_getter": store.get_latest_publication,
                "latest_run_getter": store.get_latest_scheduler_run,
                "run_history_getter": store.list_scheduler_runs,
            }
        )
        return run_pregame_board_cycle(**forwarded)

    return cycle


def _build_refresher(*, storage: Any, stage_path: Path):
    def refresh(*, date: str, season: int, env: Mapping[str, str]):
        sync = sync_reconciled_draftkings_to_kyre_feed(
            date=str(date),
            season=int(season),
            env=env,
            path=str(stage_path),
        )
        if sync.get("synced") is not True or sync.get("feed_write_performed") is not True:
            raise WNBAStep7GActivationError("Step 7G reconciled DraftKings refresh did not complete its staging write.")
        if not stage_path.is_file():
            raise WNBAStep7GActivationError("Step 7G staged market feed is missing after refresh.")
        staged = stage_path.read_bytes()
        staged_sha = _sha256(staged)
        if (sync.get("storage") or {}).get("content_sha256") != staged_sha:
            raise WNBAStep7GActivationError("Step 7G staged feed hash does not match Step 6I write evidence.")
        try:
            document = json.loads(staged.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WNBAStep7GActivationError("Step 7G staged feed is not valid UTF-8 JSON.") from exc
        validated = validate_kyre_market_feed(document)
        if validated.get("date") != str(date) or int(validated.get("season") or 0) != int(season):
            raise WNBAStep7GActivationError("Step 7G staged feed date/season drifted from the approved slate.")
        persistent_sha = persistent_feed_sha256(validated)
        if sync.get("persistent_feed_sha256") != persistent_sha:
            raise WNBAStep7GActivationError("Step 7G staged feed identity does not match Step 6I evidence.")
        durable = storage.write_bytes_atomic(FEED_OBJECT_KEY, staged)
        reread = storage.read_bytes(FEED_OBJECT_KEY)
        if reread != staged or durable.content_sha256 != staged_sha or _sha256(reread) != staged_sha:
            raise WNBAStep7GActivationError("Step 7G durable refreshed feed failed exact-byte verification.")
        return {
            "source": MODEL_SOURCE,
            "model_version": MODEL_VERSION,
            "outcome": "refreshed",
            "content_sha256": staged_sha,
            "persistent_feed_sha256": persistent_sha,
            "offer_side_count": len(validated.get("offers") or []),
            "feed_write_performed": True,
            "storage_backend": SUPABASE_BACKEND,
            "sportsbook_http_method": "GET",
            "paid_odds_vendor_used": False,
        }

    return refresh


def _restore_pre_cycle_feed(storage: Any, backup: bytes, expected_sha: str) -> str:
    if _sha256(backup) != expected_sha:
        raise WNBAStep7GActivationError("Step 7G rollback backup no longer matches its frozen pre-cycle hash.")
    metadata = storage.write_bytes_atomic(FEED_OBJECT_KEY, backup)
    restored = storage.read_bytes(FEED_OBJECT_KEY)
    digest = _sha256(restored)
    if restored != backup or digest != expected_sha or metadata.content_sha256 != expected_sha:
        raise WNBAStep7GActivationError("Step 7G could not verify exact pre-cycle feed rollback.")
    return digest


def run_step7g_one_shot(
    *,
    date: str,
    season: int,
    activation_id: str = ACTIVATION_ID,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if activation_id != ACTIVATION_ID:
        raise WNBAStep7GActivationNotReadyError("Step 7G accepts only the frozen one-shot activation id.")
    try:
        datetime.strptime(str(date), "%Y-%m-%d")
    except ValueError as exc:
        raise WNBAStep7GActivationNotReadyError("Step 7G date must use YYYY-MM-DD.") from exc
    if not isinstance(season, int) or isinstance(season, bool) or season <= 0:
        raise WNBAStep7GActivationNotReadyError("Step 7G season must be a positive integer.")

    base = dict(os.environ if env is None else env)
    _require_base_fail_closed(base)
    slate_proof = _require_playable_slate(str(date), season)
    durable_storage = build_step6r_durable_storage(env=base)
    if durable_storage.backend_id != SUPABASE_BACKEND:
        raise WNBAStep7GActivationNotReadyError("Step 7G durable backend is not Supabase.")

    marker = _read_json_object(durable_storage, ACTIVATION_MARKER_KEY)
    if marker:
        if marker.get("activation_id") != activation_id:
            raise WNBAStep7GActivationNotReadyError(
                "Step 7G durable activation state belongs to another activation id."
            )
        if marker.get("status") == "completed":
            current = durable_storage.read_bytes(FEED_OBJECT_KEY)
            current_sha = _sha256(current)
            if current_sha != marker.get("post_cycle_feed_sha256"):
                raise WNBAStep7GActivationError("Completed Step 7G marker no longer matches the durable feed.")
            return {
                "source": MODEL_SOURCE,
                "data_type": "wnba_step7g_one_shot_activation_result",
                "schema_version": SCHEMA_VERSION,
                "model_version": MODEL_VERSION,
                "status": "completed",
                "already_completed": True,
                "activation_id": activation_id,
                "date": marker.get("date"),
                "season": marker.get("season"),
                "pre_cycle_feed_sha256": marker.get("pre_cycle_feed_sha256"),
                "post_cycle_feed_sha256": marker.get("post_cycle_feed_sha256"),
                "cycle_outcome": marker.get("cycle_outcome"),
                "publication_id": marker.get("publication_id"),
                "scheduler_run_id": marker.get("scheduler_run_id"),
                "final_switch_state": {name: False for name in (
                    PRODUCTION_RUNTIME_ENV, SCHEDULER_ENABLED_ENV, DIRECT_SYNC_ENABLED_ENV,
                    RECONCILED_SYNC_ENABLED_ENV, CANARY_ENABLED_ENV, PRODUCTION_REFRESH_ENABLED_ENV,
                )},
                "safety": {"recurring_scheduler_started": False, "secret_value_returned": False},
            }
        raise WNBAStep7GActivationNotReadyError(
            f"Step 7G one-shot activation is not replayable from durable status {marker.get('status')!r}."
        )

    if not durable_storage.exists(FEED_OBJECT_KEY):
        raise WNBAStep7GActivationNotReadyError("Step 7G requires the frozen durable WNBA market feed.")
    pre_feed = durable_storage.read_bytes(FEED_OBJECT_KEY)
    pre_sha = _sha256(pre_feed)
    if pre_sha != EXPECTED_PRE_CYCLE_FEED_SHA256:
        raise WNBAStep7GActivationNotReadyError(
            "Step 7G pre-cycle feed drifted from the frozen Step 7E/6V proof; activation is blocked."
        )
    if not durable_storage.exists(STEP6J_MARKER_KEY):
        raise WNBAStep7GActivationNotReadyError("Step 7G cannot find the frozen Step 6J canary marker.")
    step6j_marker_sha = _sha256(durable_storage.read_bytes(STEP6J_MARKER_KEY))
    if step6j_marker_sha != EXPECTED_STEP6J_MARKER_SHA256:
        raise WNBAStep7GActivationNotReadyError("Step 7G Step 6J canary marker identity drifted.")

    backup_sha = _write_verified(durable_storage, PRE_CYCLE_BACKUP_KEY, pre_feed)
    if backup_sha != pre_sha:
        raise WNBAStep7GActivationError("Step 7G rollback backup SHA does not match the pre-cycle feed.")

    started = {
        "source": MODEL_SOURCE,
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "activation_id": activation_id,
        "status": "started",
        "started_at_utc": _utc_now_iso(),
        "date": str(date),
        "season": season,
        "pre_cycle_feed_sha256": pre_sha,
        "backup_object_key": PRE_CYCLE_BACKUP_KEY,
        "backup_sha256": backup_sha,
        "rollback_verified": False,
        "recurring_scheduler_started": False,
    }
    _write_marker(durable_storage, started)

    store = Step7GSupabaseSchedulerStore(base)
    transaction = Step7GTransactionalSchedulerCommit(store)
    cycle_result: dict[str, Any] | None = None
    feed_write_may_have_occurred = False
    try:
        with store.scheduler_lock(activation_id):
            with tempfile.TemporaryDirectory(prefix="wnba-step7g-cycle-") as tmp:
                stage_path = Path(tmp) / FEED_OBJECT_KEY
                private_env = _private_cycle_environment(base, str(stage_path))
                failover = _build_failover_wrapper(store)
                cycle_runner = _build_cycle_runner(store, transaction)
                refresher = _build_refresher(storage=durable_storage, stage_path=stage_path)
                # Once the provider hook is reached, refresher can mutate the durable
                # feed; set this flag conservatively before entering the scoped cycle.
                feed_write_may_have_occurred = True
                cycle_result = _run_frozen_cycle_with_scoped_refresh(
                    target_date=str(date),
                    season=season,
                    force=True,
                    environment=private_env,
                    refresher=refresher,
                    cycle_runner=cycle_runner,
                    base_failover_collector=failover,
                )
                transaction.assert_clean()

        if not isinstance(cycle_result, dict):
            raise WNBAStep7GActivationError("Step 7G frozen scheduler cycle returned no result.")
        step6m = cycle_result.get("step_6m") or {}
        if step6m.get("owned_feed_refresh_attempted") is not True or step6m.get("owned_feed_refresh_outcome") != "refreshed":
            raise WNBAStep7GActivationNotReadyError(
                "Step 7G did not reach the guarded owned-feed refresh hook; one-shot proof is incomplete."
            )
        if cycle_result.get("outcome") not in ALLOWED_SUCCESS_OUTCOMES:
            raise WNBAStep7GActivationError(
                f"Step 7G frozen cycle ended in unsupported outcome {cycle_result.get('outcome')!r}."
            )
        if cycle_result.get("provider_collection_attempted") is not True:
            raise WNBAStep7GActivationError("Step 7G provider collection was not attempted after refresh.")
        archive = cycle_result.get("archive_summary") or {}
        if archive and archive.get("requested") not in {False, None}:
            raise WNBAStep7GActivationError("Step 7G first cycle unexpectedly enabled historical auto-archive.")

        post_feed = durable_storage.read_bytes(FEED_OBJECT_KEY)
        post_sha = _sha256(post_feed)
        if post_sha == pre_sha:
            raise WNBAStep7GActivationError("Step 7G refreshed feed bytes did not change from the frozen pre-cycle feed.")
        post_doc = validate_kyre_market_feed(json.loads(post_feed.decode("utf-8")))
        if post_doc["date"] != str(date) or int(post_doc["season"]) != season:
            raise WNBAStep7GActivationError("Step 7G durable post-cycle feed date/season is invalid.")

        latest_run = store.get_latest_scheduler_run(date=str(date), season=season)
        latest_publication = store.get_latest_publication(
            date=str(date), season=season, now_utc=datetime.now(timezone.utc), require_current=False
        )
        snapshots = store.list_feed_snapshots(provider_id="kyre", date=str(date), season=season, limit=20)
        locks = store.active_scheduler_locks()
        lock_history = store.lock_history(limit=5)
        if not isinstance(latest_run, dict):
            raise WNBAStep7GActivationError("Step 7G persistent scheduler run history is missing.")
        if latest_run.get("outcome") != cycle_result.get("outcome"):
            raise WNBAStep7GActivationError("Step 7G persistent scheduler run outcome drifted.")
        if cycle_result.get("board_rebuild_attempted") is True and not isinstance(latest_publication, dict):
            raise WNBAStep7GActivationError("Step 7G rebuilt a board but no Supabase publication is readable.")
        if int(snapshots.get("count") or 0) < 1:
            raise WNBAStep7GActivationError("Step 7G Supabase provider snapshot evidence is missing.")
        if locks:
            raise WNBAStep7GActivationError("Step 7G scheduler mutex remained active after the one-shot cycle.")
        if not lock_history or lock_history[0].get("activation_id") != activation_id:
            raise WNBAStep7GActivationError("Step 7G persistent lock-release history is missing.")

        publication = cycle_result.get("publication") or cycle_result.get("current_publication") or {}
        completed = dict(started)
        completed.update(
            {
                "status": "completed",
                "completed_at_utc": _utc_now_iso(),
                "post_cycle_feed_sha256": post_sha,
                "rollback_verified": True,
                "cycle_outcome": cycle_result.get("outcome"),
                "publication_id": publication.get("publication_id"),
                "scheduler_run_id": latest_run.get("run_id"),
                "provider_snapshot_count": int(snapshots.get("count") or 0),
                "offer_side_count": step6m.get("owned_feed_offer_side_count"),
            }
        )
        marker_sha = _write_marker(durable_storage, completed)
        return {
            "source": MODEL_SOURCE,
            "data_type": "wnba_step7g_one_shot_activation_result",
            "schema_version": SCHEMA_VERSION,
            "model_version": MODEL_VERSION,
            "status": "completed",
            "already_completed": False,
            "activation_id": activation_id,
            "date": str(date),
            "season": season,
            "slate": slate_proof,
            "storage_backend": SUPABASE_BACKEND,
            "pre_cycle_feed_sha256": pre_sha,
            "post_cycle_feed_sha256": post_sha,
            "activation_marker_sha256": marker_sha,
            "cycle": {
                "outcome": cycle_result.get("outcome"),
                "provider_collection_attempted": cycle_result.get("provider_collection_attempted"),
                "board_rebuild_attempted": cycle_result.get("board_rebuild_attempted"),
                "selected_provider_id": cycle_result.get("selected_provider_id"),
                "publication_id": publication.get("publication_id"),
                "scheduler_run_id": latest_run.get("run_id"),
                "captured_threshold_snapshot_pair_count": cycle_result.get("captured_threshold_snapshot_pair_count"),
                "owned_feed_offer_side_count": step6m.get("owned_feed_offer_side_count"),
            },
            "persistence": {
                "provider_snapshot_count": int(snapshots.get("count") or 0),
                "active_scheduler_locks": 0,
                "lock_release_recorded": True,
                "publication_run_atomic_commit": True,
                "historical_auto_archive_enabled": False,
                "rollback_backup_sha256": backup_sha,
            },
            "final_switch_state": {name: False for name in (
                PRODUCTION_RUNTIME_ENV, SCHEDULER_ENABLED_ENV, DIRECT_SYNC_ENABLED_ENV,
                RECONCILED_SYNC_ENABLED_ENV, CANARY_ENABLED_ENV, PRODUCTION_REFRESH_ENABLED_ENV,
            )},
            "safety": {
                "base_environment_mutated": False,
                "temporary_write_switches_persisted": False,
                "recurring_scheduler_started": False,
                "production_runtime_enabled": False,
                "sportsbook_http_method": "GET",
                "paid_odds_vendor_used": False,
                "wager_action_performed": False,
                "secret_value_returned": False,
            },
        }
    except Exception as exc:
        rollback_error: str | None = None
        restored_sha: str | None = None
        try:
            if feed_write_may_have_occurred:
                backup = durable_storage.read_bytes(PRE_CYCLE_BACKUP_KEY)
                restored_sha = _restore_pre_cycle_feed(durable_storage, backup, pre_sha)
            else:
                restored_sha = pre_sha
        except Exception as rollback_exc:
            rollback_error = f"{type(rollback_exc).__name__}: {rollback_exc}"
        failed = dict(started)
        failed.update(
            {
                "status": "failed_rolled_back" if rollback_error is None else "failed_rollback_unverified",
                "failed_at_utc": _utc_now_iso(),
                "error_type": type(exc).__name__,
                "rollback_verified": rollback_error is None and restored_sha == pre_sha,
                "restored_feed_sha256": restored_sha,
                "rollback_error": rollback_error,
            }
        )
        try:
            _write_marker(durable_storage, failed)
        except Exception:
            pass
        if rollback_error is not None:
            raise WNBAStep7GActivationError(
                f"Step 7G cycle failed ({type(exc).__name__}) and rollback could not be verified: {rollback_error}"
            ) from exc
        raise


def _write_output(path: str, document: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(dict(document), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the WNBA Step 7G one-shot scheduler activation.")
    parser.add_argument("--date", required=True)
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--activation-id", default=ACTIVATION_ID)
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    result = run_step7g_one_shot(
        date=args.date,
        season=args.season,
        activation_id=args.activation_id,
    )
    if args.output:
        _write_output(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
