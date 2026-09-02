#!/usr/bin/env python3
"""Step 17B Render activation v2 with network-free WNBA continuity checks.

The underlying v1 operator retains the full exact-revision activation, restart,
and rollback transaction. This wrapper changes only the WNBA continuity smoke:
it verifies the shared host's liveness plus the internal network-free WNBA Step 5S
deployment contract, rather than calling the upstream-dependent public schedule.
"""
from __future__ import annotations

import json
from typing import Any, Mapping

from sports_api.tools import mlb_step17b_render_activation as base

MODEL_VERSION = "mlb_step17b_render_controlled_activation_v2_network_free_wnba"
EXPECTED_WNBA_DATA_TYPE = "wnba_deployment_and_smoke_readiness"


def verify_wnba_network_free() -> dict[str, Any]:
    health = base._get_json("/health")
    if health.get("status") != "ok":
        raise base.Step17BRenderActivationError("Hosted /health is not ok.")

    deployment = base._get_json("/api/v1/wnba/runtime/deployment")
    semantics = (
        deployment.get("semantics")
        if isinstance(deployment.get("semantics"), Mapping)
        else {}
    )
    if deployment.get("data_type") != EXPECTED_WNBA_DATA_TYPE:
        raise base.Step17BRenderActivationError(
            "Hosted WNBA deployment contract shape drifted."
        )
    if semantics.get("deployment_gate_does_not_call_sportsbook") is not True:
        raise base.Step17BRenderActivationError(
            "WNBA deployment continuity gate crossed sportsbook boundary."
        )
    if semantics.get("deployment_gate_does_not_run_monte_carlo") is not True:
        raise base.Step17BRenderActivationError(
            "WNBA deployment continuity gate crossed Monte Carlo boundary."
        )
    if semantics.get("live_smoke_is_read_only") is not True:
        raise base.Step17BRenderActivationError(
            "WNBA deployment continuity gate is no longer read-only."
        )
    return {
        "health": "ok",
        "season": None,
        "game_count": None,
        "data_type": deployment.get("data_type"),
        "deployment_ready": deployment.get("deployment_ready"),
        "configuration_fingerprint_sha256": deployment.get(
            "configuration_fingerprint_sha256"
        ),
        "network_free_contract_checked": True,
    }


def activate(*, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    original = base._verify_wnba
    base._verify_wnba = verify_wnba_network_free
    try:
        evidence = base.activate(env=env)
    finally:
        base._verify_wnba = original
    evidence["model_version"] = MODEL_VERSION
    evidence["wnba"]["continuity_gate"] = "network_free_step5s_deployment_contract"
    evidence["wnba"]["upstream_schedule_called"] = False
    evidence["safety"]["upstream_wnba_schedule_called"] = False
    return evidence


def main() -> int:
    print(json.dumps(activate(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
