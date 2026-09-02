from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from typing import Any, Mapping

from sports_api import wnba_step12_release_freeze as release
from sports_api import wnba_step12c_live_board_runtime as step12c
from sports_api import wnba_step13a_bounded_scheduler as scheduler


OUTPUT = Path("step13a-bounded-scheduler-cert.json")
BASE = datetime(2026, 8, 28, 16, 40, tzinfo=timezone.utc)


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


def _parent_result(request: Mapping[str, Any], tick: int) -> dict[str, Any]:
    evaluated = datetime.fromisoformat(str(request["evaluated_at_utc"]))
    delay = 180 if tick == 2 else 60
    circuit = "open" if tick == 2 else "closed"
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
        "source": "Step 13A certification frozen Step-12C fixture",
        "model_version": step12c.MODEL_VERSION,
        "generated_at_utc": evaluated.isoformat(),
        "request_content_sha256": request["request_content_sha256"],
        "status": "healthy" if circuit == "closed" else "circuit_open",
        "health": "healthy" if circuit == "closed" else "blocked",
        "slate_date": request["slate_date"],
        "runtime": {
            "status": "healthy" if circuit == "closed" else "circuit_open",
            "health": "healthy" if circuit == "closed" else "blocked",
            "evaluated_at_utc": evaluated.isoformat(),
            "cycle_due": True,
            "cycle_executed": True,
            "cycle_outcome": "shadow_board_ready" if circuit == "closed" else "provider_transient_not_ready",
            "skip_reason": None,
            "circuit_state": circuit,
            "consecutive_failures": 0 if circuit == "closed" else 3,
            "next_refresh_due_at_utc": next_due.isoformat(),
            "circuit_open_until_utc": next_due.isoformat() if circuit == "open" else None,
            "controller_state_content_sha256": state["state_content_sha256"],
        },
        "board": {
            "available": circuit == "closed",
            "requested_top_card_count": 5,
            "qualified_prop_count": 1 if circuit == "closed" else 0,
            "top_card_count": 1 if circuit == "closed" else 0,
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
        "guardrails": {
            "shadow_only": True,
            "scheduler_started": False,
            "state_persisted": False,
        },
    }
    surface = {
        key: deepcopy(value)
        for key, value in result.items()
        if key not in {"generated_at_utc", "board_content_sha256"}
    }
    result["board_content_sha256"] = scheduler._canonical_hash(surface)
    return result


def main() -> None:
    env = _env()
    clock = CertClock()
    calls: list[dict[str, Any]] = []

    def runner(request: Mapping[str, Any], **kwargs: Any) -> Mapping[str, Any]:
        snapshot = deepcopy(dict(request))
        calls.append(snapshot)
        tick = len(calls)
        if tick == 1:
            if request.get("previous_state") is not None:
                raise RuntimeError("Certification expected no initial controller state.")
        else:
            previous = request.get("previous_state") or {}
            if previous.get("tick") != tick - 1:
                raise RuntimeError("Certification detected broken in-memory state chaining.")
        return _parent_result(request, tick)

    request = scheduler.build_step13a_request(
        season=2026,
        slate_date="2026-08-28",
        max_cycles=3,
        max_total_sleep_seconds=300,
        controller_policy={
            "refresh_interval_seconds": 60,
            "failure_threshold": 3,
            "circuit_cooldown_seconds": 180,
        },
    )
    result = scheduler.run_step13a_bounded_scheduler(
        request,
        env=env,
        clock=clock.now,
        sleeper=clock.sleep,
        step12c_runner=runner,
    )

    summary = result["scheduler_summary"]
    guards = result["guardrails"]
    lineage = result["lineage"]
    if summary["executed_ticks"] != 3:
        raise RuntimeError("Step 13A certification did not execute exactly three ticks.")
    if clock.sleeps != [60.0, 180.0]:
        raise RuntimeError(f"Step 13A certification sleep schedule drift: {clock.sleeps!r}")
    if summary["total_sleep_seconds"] != 240.0:
        raise RuntimeError("Step 13A certification total sleep drift.")
    if result["final_controller_state_for_next_process"].get("tick") != 3:
        raise RuntimeError("Step 13A certification final controller state drift.")
    if lineage["step12d_frozen_sha"] != scheduler.STEP12D_FROZEN_SHA:
        raise RuntimeError("Step 13A certification frozen Step-12D lineage drift.")
    if guards["bounded_foreground_scheduler_started"] is not True:
        raise RuntimeError("Step 13A certification bounded scheduler guard missing.")
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
            raise RuntimeError(f"Unsafe Step 13A certification guard drift: {key}")

    cert = {
        "data_type": "wnba_step13a_bounded_scheduler_certification",
        "schema_version": scheduler.SCHEMA_VERSION,
        "certified": True,
        "certified_at_utc": datetime.now(timezone.utc).isoformat(),
        "branch": "wnba-step13a-bounded-scheduler-20260828",
        "certified_head_sha": os.environ.get("GITHUB_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "step12d_frozen_sha": scheduler.STEP12D_FROZEN_SHA,
        "step12_release_id": release.RELEASE_ID,
        "request_content_sha256": request["request_content_sha256"],
        "scheduler_content_sha256": result["scheduler_content_sha256"],
        "scheduler_summary": summary,
        "sleep_schedule_seconds": clock.sleeps,
        "tick_history": result["tick_history"],
        "lineage": lineage,
        "guardrails": guards,
        "phase_boundary": {
            "step13a_complete": True,
            "durable_persistence_not_started": True,
            "production_deployment_not_started": True,
            "wagering_not_started": True,
        },
    }
    OUTPUT.write_text(json.dumps(cert, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("STEP13A_BOUNDED_SCHEDULER_OK")
    print(json.dumps(cert, sort_keys=True))


if __name__ == "__main__":
    main()
