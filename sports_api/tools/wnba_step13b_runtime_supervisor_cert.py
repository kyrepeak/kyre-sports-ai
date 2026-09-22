from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from typing import Any, Mapping

from sports_api import wnba_step12_release_freeze as release
from sports_api import wnba_step12c_live_board_runtime as step12c
from sports_api import wnba_step13a_bounded_scheduler as step13a
from sports_api import wnba_step13b_runtime_supervisor as supervisor


OUTPUT = Path("step13b-runtime-supervisor-cert.json")
BASE = datetime(2026, 8, 29, 3, 59, tzinfo=timezone.utc)  # 2026-08-28 23:59 America/New_York


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


def _step12c_result(request: Mapping[str, Any], tick: int) -> dict[str, Any]:
    evaluated = datetime.fromisoformat(str(request["evaluated_at_utc"]))
    delay = 120 if tick == 1 else 60
    next_due = evaluated + timedelta(seconds=delay)
    state = {
        "data_type": "wnba_step11e_controlled_automation_state",
        "state_content_sha256": f"{tick:064x}",
        "next_refresh_due_at_utc": next_due.isoformat(),
        "tick": tick,
    }
    result: dict[str, Any] = {
        "data_type": "wnba_step12c_live_board_runtime_response",
        "schema_version": step12c.SCHEMA_VERSION,
        "source": "Step 13B certification Step-12C fixture",
        "model_version": step12c.MODEL_VERSION,
        "generated_at_utc": evaluated.isoformat(),
        "request_content_sha256": request["request_content_sha256"],
        "status": "healthy",
        "health": "healthy",
        "slate_date": request["slate_date"],
        "runtime": {
            "status": "healthy",
            "health": "healthy",
            "evaluated_at_utc": evaluated.isoformat(),
            "cycle_due": True,
            "cycle_executed": True,
            "cycle_outcome": "shadow_board_ready",
            "skip_reason": None,
            "circuit_state": "closed",
            "consecutive_failures": 0,
            "next_refresh_due_at_utc": next_due.isoformat(),
            "circuit_open_until_utc": None,
            "controller_state_content_sha256": state["state_content_sha256"],
        },
        "board": {
            "available": True,
            "requested_top_card_count": 5,
            "qualified_prop_count": 1,
            "top_card_count": 1,
            "primary_top_cards": [],
            "value_ranking": [],
        },
        "controller_state_for_next_caller_tick": state,
        "diagnostics": {},
        "lineage": {
            "step12b_frozen_sha": release.STEP12B_FROZEN_SHA,
            "step12b_runtime_content_sha256": "a" * 64,
            "step12a_frozen_sha": release.STEP12A_FROZEN_SHA,
            "step11e_frozen_sha": release.STEP11E_FROZEN_SHA,
            "step8_frozen_sha": release.STEP8_FROZEN_SHA,
        },
        "guardrails": {},
    }
    surface = {
        key: deepcopy(value)
        for key, value in result.items()
        if key not in {"generated_at_utc", "board_content_sha256"}
    }
    result["board_content_sha256"] = step13a._canonical_hash(surface)
    return result


def main() -> None:
    env = _env()
    clock = CertClock()
    step12c_calls: list[dict[str, Any]] = []

    def step12c_runner(request: Mapping[str, Any], **kwargs: Any) -> Mapping[str, Any]:
        snapshot = deepcopy(dict(request))
        step12c_calls.append(snapshot)
        tick = len(step12c_calls)
        if request.get("previous_state") is not None:
            raise RuntimeError("Step 13B certification detected cross-slate state reuse.")
        return _step12c_result(request, tick)

    request = supervisor.build_step13b_request(
        season=2026,
        initial_slate_date="2026-08-28",
        slate_timezone="America/New_York",
        rollover_policy="advance_reset",
        max_supervisor_sessions=2,
        max_supervisor_runtime_seconds=600,
        max_total_intersession_sleep_seconds=300,
        scheduler_cycles_per_session=1,
        scheduler_sleep_budget_seconds_per_session=0,
    )
    result = supervisor.run_step13b_runtime_supervisor(
        request,
        env=env,
        clock=clock.now,
        sleeper=clock.sleep,
        step12c_runner=step12c_runner,
    )

    summary = result["supervisor_summary"]
    guards = result["guardrails"]
    lineage = result["lineage"]
    if summary["completed_sessions"] != 2:
        raise RuntimeError("Step 13B certification did not complete exactly two sessions.")
    if [call["slate_date"] for call in step12c_calls] != ["2026-08-28", "2026-08-29"]:
        raise RuntimeError("Step 13B certification slate rollover drift.")
    if clock.sleeps != [120.0]:
        raise RuntimeError(f"Step 13B certification wait schedule drift: {clock.sleeps!r}")
    if summary["rollover_count"] != 1:
        raise RuntimeError("Step 13B certification rollover count drift.")
    if result["rollover_history"][0]["controller_state_reset"] is not True:
        raise RuntimeError("Step 13B certification did not prove controller state reset on rollover.")
    if result["final_controller_state_for_restart_handoff"].get("tick") != 2:
        raise RuntimeError("Step 13B certification final controller state drift.")
    if lineage["step13a_frozen_sha"] != supervisor.STEP13A_FROZEN_SHA:
        raise RuntimeError("Step 13B certification frozen Step-13A lineage drift.")
    if guards["foreground_runtime_supervisor_started"] is not True:
        raise RuntimeError("Step 13B certification foreground supervisor guard missing.")
    if guards["slate_rollover_protected"] is not True:
        raise RuntimeError("Step 13B certification slate protection guard missing.")
    if guards["cross_slate_controller_state_reuse"] is not False:
        raise RuntimeError("Step 13B certification cross-slate state guard drift.")
    for key in (
        "background_daemon_started",
        "background_thread_spawned",
        "state_persisted",
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
            raise RuntimeError(f"Unsafe Step 13B certification guard drift: {key}")

    cert = {
        "data_type": "wnba_step13b_runtime_supervisor_certification",
        "schema_version": supervisor.SCHEMA_VERSION,
        "certified": True,
        "certified_at_utc": datetime.now(timezone.utc).isoformat(),
        "branch": "wnba-step13b-runtime-supervisor-20260828",
        "certified_head_sha": os.environ.get("GITHUB_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "step13a_frozen_sha": supervisor.STEP13A_FROZEN_SHA,
        "step12d_frozen_sha": supervisor.STEP12D_FROZEN_SHA,
        "step12_release_id": release.RELEASE_ID,
        "request_content_sha256": request["request_content_sha256"],
        "supervisor_content_sha256": result["supervisor_content_sha256"],
        "supervisor_summary": summary,
        "session_history": result["session_history"],
        "rollover_history": result["rollover_history"],
        "lifecycle": result["lifecycle"],
        "sleep_schedule_seconds": clock.sleeps,
        "step12c_slate_sequence": [call["slate_date"] for call in step12c_calls],
        "lineage": lineage,
        "guardrails": guards,
        "phase_boundary": {
            "step13b_complete": True,
            "durable_persistence_not_started": True,
            "production_deployment_not_started": True,
            "reliability_recovery_step13c_not_started": True,
            "wagering_not_started": True,
        },
    }
    OUTPUT.write_text(json.dumps(cert, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("STEP13B_RUNTIME_SUPERVISOR_OK")
    print(json.dumps(cert, sort_keys=True))


if __name__ == "__main__":
    main()
