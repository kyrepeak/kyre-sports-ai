"""Final OFF-only release/freeze certification for WNBA Step 7G.

The certificate binds the declarative release manifest to the promoted v11
integration, exercises the real public readiness route twice with no query
overrides, and requires stable critical readiness across both calls. It never
enables production runtime, schedulers, market sync, persistence, Supabase, or
sportsbook access.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from sports_api import wnba_step7g_release_freeze as freeze

REPORT_PATH = Path("step7g-final-release-freeze-cert.json")
_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def _assert_safe() -> None:
    bad = [name for name in _OFF_ENV_KEYS if _truthy(os.getenv(name))]
    if bad:
        raise RuntimeError(
            "Final Step 7G freeze cert refuses to run with production switches enabled: "
            + ", ".join(bad)
        )
    if not _truthy(os.getenv("WNBA_STEP7G_FIRST_PARTY_ENABLED")):
        raise RuntimeError("Final Step 7G freeze cert requires first-party mode ON only in CI.")


def _check_by_id(body: dict[str, Any], check_id: str) -> dict[str, Any] | None:
    rows = body.get("checks")
    if not isinstance(rows, list):
        return None
    for row in rows:
        if isinstance(row, dict) and row.get("check_id") == check_id:
            return row
    return None


def _assert_release_response(body: dict[str, Any], *, call_label: str) -> dict[str, Any]:
    summary = body.get("summary") or {}
    readiness = body.get("readiness")
    if readiness not in {"READY", "READY_WITH_WARNINGS"}:
        raise RuntimeError(f"{call_label} readiness is not startable: {readiness!r}.")
    if body.get("can_start_projection") is not True:
        raise RuntimeError(f"{call_label} cannot start projection.")
    if summary.get("blocker_count") != 0 or list(summary.get("blocker_ids") or []):
        raise RuntimeError(f"{call_label} has blockers: {summary!r}.")

    warning_ids = list(summary.get("warning_ids") or [])
    if not set(warning_ids).issubset(freeze.ALLOWED_NON_BLOCKING_WARNING_IDS):
        raise RuntimeError(f"{call_label} has unexpected warnings: {warning_ids!r}.")

    required: dict[str, dict[str, Any]] = {}
    for check_id in freeze.REQUIRED_RELEASE_DEFAULT_CHECKS:
        row = _check_by_id(body, check_id)
        if not isinstance(row, dict):
            raise RuntimeError(f"{call_label} is missing required check {check_id!r}.")
        if row.get("severity") != "pass" or row.get("blocking") is not False:
            raise RuntimeError(f"{call_label} check {check_id!r} did not pass: {row!r}.")
        required[check_id] = {
            "severity": row.get("severity"),
            "blocking": row.get("blocking"),
            "observed": row.get("observed"),
        }

    return {
        "readiness": readiness,
        "can_start_projection": body.get("can_start_projection"),
        "blocker_ids": list(summary.get("blocker_ids") or []),
        "warning_ids": warning_ids,
        "required_checks": required,
        "check_count": summary.get("check_count"),
        "pass_count": summary.get("pass_count"),
        "warning_count": summary.get("warning_count"),
    }


def main() -> int:
    _assert_safe()
    started = datetime.now(timezone.utc)

    import sports_api.wnba_step7g_first_party_integration as integration

    status = integration.get_step7g_first_party_status()
    if freeze.DEFAULT_ENABLED is not False or freeze.PRODUCTION_ACTIVATION_ALLOWED is not False:
        raise RuntimeError("Frozen release manifest does not preserve default-OFF safety.")
    if freeze.SEASON != 2026 or freeze.SEASON_TYPE != "Regular Season":
        raise RuntimeError("Frozen release manifest season scope changed unexpectedly.")
    if status.get("model_version") != freeze.INTEGRATION_VERSION:
        raise RuntimeError("Frozen release manifest and integration version disagree.")
    if status.get("candidate_scope") != {}:
        raise RuntimeError(f"Frozen release still exposes candidate scope: {status.get('candidate_scope')!r}.")
    if status.get("all_core_seams_installed") is not True:
        raise RuntimeError("Frozen release does not have all core seams installed in CI.")

    scope = status.get("certified_scope") or {}
    for key, expected in freeze.CERTIFIED_SCOPE.items():
        if scope.get(key) is not expected:
            raise RuntimeError(f"Frozen release certified scope mismatch for {key!r}.")

    # Reinstall once to prove the finalized integration remains idempotent.
    second_install = integration.install_step7g_first_party_integration()
    if second_install.get("installed") is not True:
        raise RuntimeError("Final Step 7G integration is not idempotently installed.")
    if second_install.get("model_version") != freeze.INTEGRATION_VERSION:
        raise RuntimeError("Idempotent reinstall changed the integration version.")
    if second_install.get("candidate_scope") != {}:
        raise RuntimeError("Idempotent reinstall reintroduced candidate scope.")

    from sports_api.main import app
    from sports_api.tools import wnba_step7g_pregame_readiness_cert as selector

    selector.MIN_TIP_BUFFER_HOURS = 0.5
    selected_game, selected_player, _ = selector._select_live_pregame_case()
    game_id = str(selected_game["game_id"])
    player_id = int(selected_player["player_id"])
    path = f"/api/v1/wnba/games/{game_id}/players/{player_id}/model-input-readiness"

    results: list[dict[str, Any]] = []
    with TestClient(app, raise_server_exceptions=True) as client:
        for index in (1, 2):
            response = client.get(path)
            if response.status_code != 200:
                raise RuntimeError(
                    f"Final Step 7G release call {index} returned HTTP {response.status_code}."
                )
            body = response.json()
            if not isinstance(body, dict):
                raise RuntimeError(f"Final Step 7G release call {index} returned non-object JSON.")
            critical = _assert_release_response(body, call_label=f"release call {index}")
            critical["http_status"] = response.status_code
            results.append(critical)

    if results[0] != results[1]:
        raise RuntimeError(
            "Final Step 7G release produced inconsistent critical readiness across repeated calls."
        )

    safety = status.get("safety") or {}
    for key in (
        "production_runtime_enabled_by_this_module",
        "scheduler_started_by_this_module",
        "sportsbook_called_by_this_module",
        "supabase_mutation_supported_by_this_module",
        "persistence_supported_by_this_module",
        "frozen_step4x_source_modified",
        "frozen_step4j_source_modified",
        "frozen_step4n_source_modified",
        "frozen_step4i_source_modified",
        "frozen_step4l_source_modified",
        "frozen_step4f_source_modified",
        "frozen_step4o_source_modified",
    ):
        if safety.get(key) is not False:
            raise RuntimeError(f"Final Step 7G safety flag {key!r} is not false.")

    report = {
        "data_type": "wnba_step7g_final_release_freeze_cert_v1",
        "certification_result": "STEP7G_FIRST_PARTY_RELEASE_FROZEN_CERTIFIED",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "release": {
            "release_id": freeze.RELEASE_ID,
            "integration_version": freeze.INTEGRATION_VERSION,
            "certified_baseline_sha": freeze.CERTIFIED_BASELINE_SHA,
            "certified_baseline_branch": freeze.CERTIFIED_BASELINE_BRANCH,
            "season": freeze.SEASON,
            "season_type": freeze.SEASON_TYPE,
            "github_head_sha": os.getenv("GITHUB_SHA"),
            "candidate_scope": status.get("candidate_scope"),
            "certified_scope": scope,
            "all_core_seams_installed": status.get("all_core_seams_installed"),
        },
        "selected_game": selected_game,
        "selected_player": selected_player,
        "fastapi": {
            "endpoint": path,
            "request_query_overrides": {},
            "repeat_call_count": 2,
            "critical_results_identical": True,
            "critical_result": results[0],
        },
        "safety": {
            "default_enabled": False,
            "production_activation_allowed": False,
            "production_runtime_enabled": False,
            "scheduler_started": False,
            "sportsbook_called": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "step7g_enabled_for_isolated_ci_only": True,
        },
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    print("STEP7G_FIRST_PARTY_RELEASE_FROZEN_CERTIFIED")
    _assert_safe()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
