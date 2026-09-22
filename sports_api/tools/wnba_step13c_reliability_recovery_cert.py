from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from typing import Any, Mapping

from sports_api import wnba_step13b_runtime_supervisor as step13b
from sports_api import wnba_step13c_reliability_recovery as recovery


OUTPUT = Path("step13c-reliability-recovery-cert.json")
BASE = datetime(2026, 8, 28, 17, 0, tzinfo=timezone.utc)


class CertClock:
    def __init__(self) -> None:
        self.current = BASE
        self.sleeps: list[float] = []

    def now(self) -> datetime:
        return self.current

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.current += timedelta(seconds=seconds)


def _env() -> dict[str, str]:
    result = dict(os.environ)
    result.update(
        {
            "WNBA_STEP13C_RELIABILITY_RECOVERY_ENABLED": "true",
            "WNBA_STEP13B_RUNTIME_SUPERVISOR_ENABLED": "true",
            "WNBA_STEP13A_BOUNDED_SCHEDULER_ENABLED": "true",
            "WNBA_STEP12D_FINAL_RUNTIME_FREEZE_ENABLED": "true",
            "WNBA_STEP12C_LIVE_BOARD_RUNTIME_ENABLED": "true",
            "WNBA_STEP12B_LIVE_RUNTIME_ASSEMBLY_ENABLED": "true",
            "WNBA_STEP12A_SHADOW_RUNNER_ENABLED": "true",
            "WNBA_STEP11E_CONTROLLED_AUTOMATION_ENABLED": "true",
            "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
            "WNBA_BOARD_SCHEDULER_ENABLED": "false",
            "WNBA_KYRE_DIRECT_SYNC_ENABLED": "false",
            "WNBA_KYRE_RECONCILED_SYNC_ENABLED": "false",
            "WNBA_STEP6J_CANARY_ENABLED": "false",
            "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED": "false",
            "WNBA_PERSISTENCE_ENABLED": "false",
            "WNBA_SUPABASE_WRITE_ENABLED": "false",
            "WNBA_WAGERING_ENABLED": "false",
            "WNBA_PUBLIC_STEP11E_FASTAPI_ENABLED": "false",
            "WNBA_STEP12_SCHEDULER_ENABLED": "false",
        }
    )
    return result


def _parent_result(request: Mapping[str, Any]) -> dict[str, Any]:
    state = {
        "data_type": "wnba_step11e_controlled_automation_state",
        "state_content_sha256": "9" * 64,
        "next_refresh_due_at_utc": (BASE + timedelta(seconds=60)).isoformat(),
    }
    result: dict[str, Any] = {
        "data_type": "wnba_step13b_runtime_supervisor_response",
        "schema_version": step13b.SCHEMA_VERSION,
        "source": "Step 13C certification frozen Step-13B fixture",
        "model_version": step13b.MODEL_VERSION,
        "generated_at_utc": BASE.isoformat(),
        "request_content_sha256": request["request_content_sha256"],
        "status": "stopped",
        "health": "healthy",
        "active_slate_date": request["initial_slate_date"],
        "supervisor_summary": {
            "requested_max_sessions": 1,
            "completed_sessions": 1,
            "stop_reason": "max_sessions_reached",
            "started_at_utc": BASE.isoformat(),
            "ended_at_utc": BASE.isoformat(),
        },
        "lifecycle": [],
        "session_history": [],
        "rollover_history": [],
        "latest_scheduler": None,
        "final_controller_state_for_restart_handoff": state,
        "lineage": {
            "step13a_frozen_sha": recovery.STEP13A_FROZEN_SHA,
            "latest_step13a_scheduler_content_sha256": "8" * 64,
            "step12d_frozen_sha": recovery.STEP12D_FROZEN_SHA,
        },
        "guardrails": {
            "shadow_only": True,
            "foreground_runtime_supervisor_started": True,
            "background_daemon_started": False,
            "background_thread_spawned": False,
            "step13a_scheduler_reused_without_modification": True,
            "frozen_controller_owns_refresh_cadence": True,
            "intersession_wait_uses_frozen_next_refresh_due": True,
            "graceful_shutdown_hook_supported": True,
            "slate_rollover_protected": True,
            "cross_slate_controller_state_reuse": False,
            "advance_rollover_resets_controller_state": True,
            "state_carried_forward_in_memory": True,
            "state_persisted": False,
            "process_restart_state_recovery_available": False,
            "persistence_deferred_to_step14": True,
            "supabase_mutated": False,
            "public_fastapi_route_added": False,
            "production_runtime_enabled": False,
            "production_activation_allowed": False,
            "wager_action_performed": False,
            "authentication_used": False,
            "cookies_used": False,
            "paid_odds_vendor_used": False,
            "basketball_projection_changed": False,
            "step8_distribution_changed": False,
            "step9_ranking_changed": False,
            "step9_qualification_changed": False,
            "step12_presentation_changed": False,
        },
    }
    surface = {
        key: deepcopy(value)
        for key, value in result.items()
        if key not in {"generated_at_utc", "supervisor_content_sha256"}
    }
    result["supervisor_content_sha256"] = recovery._canonical_hash(surface)
    return result


def main() -> None:
    env = _env()
    clock = CertClock()
    calls: list[dict[str, Any]] = []

    parent_request = step13b.build_step13b_request(
        season=2026,
        initial_slate_date="2026-08-28",
        rollover_policy="stop",
        max_supervisor_sessions=1,
        max_supervisor_runtime_seconds=600,
        max_total_intersession_sleep_seconds=0,
        scheduler_cycles_per_session=1,
        scheduler_sleep_budget_seconds_per_session=0,
    )
    request = recovery.build_step13c_request(
        supervisor_request=parent_request,
        max_recovery_attempts=3,
        base_recovery_backoff_seconds=2,
        max_total_recovery_sleep_seconds=10,
    )

    def runner(request: Mapping[str, Any], **kwargs: Any) -> Mapping[str, Any]:
        calls.append(deepcopy(dict(request)))
        if len(calls) == 1:
            raise TimeoutError("certified synthetic transport timeout")
        return _parent_result(request)

    result = recovery.run_step13c_reliability_recovery(
        request,
        env=env,
        clock=clock.now,
        sleeper=clock.sleep,
        step13b_runner=runner,
        active_run_registry=set(),
    )

    summary = result["recovery_summary"]
    guards = result["guardrails"]
    lineage = result["lineage"]
    if result["status"] != "completed" or result["health"] != "healthy":
        raise RuntimeError("Step 13C certification did not recover to healthy completion.")
    if len(calls) != 2 or summary["attempts_executed"] != 2:
        raise RuntimeError("Step 13C certification attempt count drift.")
    if summary["successful_attempt"] != 2 or summary["recoverable_failures"] != 1:
        raise RuntimeError("Step 13C certification recovery accounting drift.")
    if clock.sleeps != [2.0]:
        raise RuntimeError(f"Step 13C certification backoff drift: {clock.sleeps!r}")
    if result["attempt_history"][0]["error_type"] != "TimeoutError":
        raise RuntimeError("Step 13C certification did not classify timeout recovery correctly.")
    if lineage["step13b_frozen_sha"] != recovery.STEP13B_FROZEN_SHA:
        raise RuntimeError("Step 13C certification frozen Step-13B lineage drift.")
    if guards["process_local_duplicate_run_guard"] is not True:
        raise RuntimeError("Step 13C certification process-local lease guard missing.")
    if guards["recovery_only_for_timeout_or_connection_error"] is not True:
        raise RuntimeError("Step 13C certification recovery classification guard missing.")
    for key in (
        "background_daemon_started",
        "background_thread_spawned",
        "cross_process_duplicate_run_guard",
        "durable_distributed_lease_used",
        "state_persisted",
        "durable_restart_recovery_available",
        "supabase_mutated",
        "public_fastapi_route_added",
        "production_runtime_enabled",
        "production_activation_allowed",
        "wager_action_performed",
        "authentication_used",
        "cookies_used",
        "paid_odds_vendor_used",
        "basketball_projection_changed",
        "step8_distribution_changed",
        "step9_ranking_changed",
        "step9_qualification_changed",
        "step12_presentation_changed",
    ):
        if guards[key] is not False:
            raise RuntimeError(f"Unsafe Step 13C certification guard drift: {key}")

    cert = {
        "data_type": "wnba_step13c_reliability_recovery_certification",
        "schema_version": recovery.SCHEMA_VERSION,
        "certified": True,
        "certified_at_utc": datetime.now(timezone.utc).isoformat(),
        "branch": "wnba-step13c-reliability-recovery-20260828",
        "certified_head_sha": os.environ.get("GITHUB_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "step13b_frozen_sha": recovery.STEP13B_FROZEN_SHA,
        "step13a_frozen_sha": recovery.STEP13A_FROZEN_SHA,
        "step12d_frozen_sha": recovery.STEP12D_FROZEN_SHA,
        "request_content_sha256": request["request_content_sha256"],
        "run_identity_sha256": request["run_identity_sha256"],
        "reliability_content_sha256": result["reliability_content_sha256"],
        "recovery_summary": summary,
        "attempt_history": result["attempt_history"],
        "sleep_schedule_seconds": clock.sleeps,
        "lineage": lineage,
        "guardrails": guards,
        "phase_boundary": {
            "step13c_complete": True,
            "step13d_final_freeze_not_started": True,
            "durable_persistence_not_started": True,
            "production_deployment_not_started": True,
            "wagering_not_started": True,
        },
    }
    OUTPUT.write_text(json.dumps(cert, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("STEP13C_RELIABILITY_RECOVERY_OK")
    print(json.dumps(cert, sort_keys=True))


if __name__ == "__main__":
    main()
