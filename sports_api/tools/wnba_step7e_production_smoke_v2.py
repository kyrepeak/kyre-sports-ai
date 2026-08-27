#!/usr/bin/env python3
"""Step 7E v2: certify hosted API while preserving legacy Step 6U fail-closed state.

The Phase 7 Render Free + Supabase topology intentionally does not satisfy the
legacy Step 5W hosted-staging checkpoint (which was built around the earlier
immutable-image/persistent-host contract). Therefore the correct hosted Step 6U
state before Phase 7 activation is: Supabase selected, Step 6T ready/read-only,
Step 5W blocked, bridge not ready, scheduler unauthorized, production runtime
off. This operator treats only that exact legacy blocker as healthy.
"""
from __future__ import annotations

import json
from typing import Any, Mapping

import httpx

import sports_api.tools.wnba_step7e_production_smoke as base

MODEL_VERSION = "wnba_step_7e_production_smoke_v2"
EXPECTED_LEGACY_STEP6U_BLOCKER = "Step 5W pre-activation checkpoint is not ready."


class Step7EV2SmokeError(base.Step7ESmokeError):
    pass


def validate_step6u_phase7_preactivation(body: Any) -> None:
    doc = base._assert_dict(body, "Step 6U")
    if doc.get("selected_backend") != "supabase":
        raise Step7EV2SmokeError("Hosted Step 6U is not bound to Supabase.")
    if doc.get("configuration_ready") is not False:
        raise Step7EV2SmokeError("Hosted legacy Step 6U should remain blocked under the Phase 7 topology.")
    if doc.get("bridge_ready") is not False or doc.get("verification_required") is not True:
        raise Step7EV2SmokeError("Hosted legacy Step 6U must remain unbridged and verification-required.")
    if doc.get("scheduler_authorized") is not False:
        raise Step7EV2SmokeError("Hosted legacy Step 6U unexpectedly authorizes the scheduler.")

    reasons = doc.get("blocking_reasons")
    if reasons != [EXPECTED_LEGACY_STEP6U_BLOCKER]:
        raise Step7EV2SmokeError(f"Hosted Step 6U has unexpected blockers: {reasons!r}")

    step6t = doc.get("step_6t") if isinstance(doc.get("step_6t"), Mapping) else {}
    if step6t.get("configuration_ready") is not True:
        raise Step7EV2SmokeError("Step 6U reports Step 6T Supabase readiness is not green.")
    if step6t.get("verification_requires_network") is not True or step6t.get("verification_is_read_only") is not True:
        raise Step7EV2SmokeError("Step 6U reports invalid Step 6T verification semantics.")

    step5w = doc.get("step_5w") if isinstance(doc.get("step_5w"), Mapping) else {}
    if step5w.get("phase") != "pre_activation_blocked":
        raise Step7EV2SmokeError("Legacy Step 5W is not in the expected pre_activation_blocked phase.")
    if step5w.get("checkpoint_ready") is not False or step5w.get("live_cycle_allowed") is not False:
        raise Step7EV2SmokeError("Legacy Step 5W must not be checkpoint-ready or allow a live cycle.")

    safety = doc.get("safety") if isinstance(doc.get("safety"), Mapping) else {}
    if safety.get("production_runtime_enabled") is not False:
        raise Step7EV2SmokeError("Hosted production runtime is unexpectedly enabled.")
    if safety.get("scheduler_started") is not False or safety.get("scheduler_authorized_by_step6u") is not False:
        raise Step7EV2SmokeError("Hosted scheduler safety state is invalid.")
    if safety.get("storage_write_performed_by_status") is not False:
        raise Step7EV2SmokeError("Step 6U status unexpectedly performed a storage write.")


def _summary_v2(body: Any) -> dict[str, Any]:
    out = base._safe_summary(body)
    if isinstance(body, Mapping):
        if "blocking_reasons" in body:
            out["blocking_reasons"] = body.get("blocking_reasons")
        step5w = body.get("step_5w") if isinstance(body.get("step_5w"), Mapping) else None
        if step5w is not None:
            out["legacy_step5w"] = {
                "phase": step5w.get("phase"),
                "checkpoint_ready": step5w.get("checkpoint_ready"),
                "live_cycle_allowed": step5w.get("live_cycle_allowed"),
            }
    return out


ENDPOINTS = tuple(
    (name, path, validate_step6u_phase7_preactivation if name == "step6u_bridge_status" else validator)
    for name, path, validator in base.ENDPOINTS
)


def run_production_smoke() -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    with httpx.Client(
        timeout=25.0,
        follow_redirects=True,
        headers={"user-agent": "kyre-sports-api-step7e-smoke-v2/1"},
    ) as client:
        for name, path, validator in ENDPOINTS:
            status, body, attempts, elapsed = base._get_json(client, path)
            validator(body)
            results.append({
                "name": name,
                "path": path.split("?", 1)[0],
                "status_code": status,
                "attempts": attempts,
                "elapsed_seconds": elapsed,
                "passed": True,
                "summary": _summary_v2(body),
                "response_sha256": base._sha256_json(body),
            })

    safety = {
        "http_methods_used": ["GET"],
        "render_mutation_performed": False,
        "supabase_write_performed": False,
        "sportsbook_write_performed": False,
        "scheduler_authorized": False,
        "scheduler_started": False,
        "production_runtime_enabled": False,
        "monte_carlo_run": False,
        "wager_action_performed": False,
        "secret_required": False,
        "secret_value_returned": False,
        "legacy_step6u_fail_closed_preserved": True,
        "legacy_step5w_live_cycle_allowed": False,
    }
    manifest_payload = {
        "model_version": MODEL_VERSION,
        "base_url": base.BASE_URL,
        "expected_release_revision": base.EXPECTED_RELEASE_REVISION,
        "endpoint_results": results,
        "expected_legacy_step6u_blocker": EXPECTED_LEGACY_STEP6U_BLOCKER,
        "safety": safety,
    }
    return {
        "source": "Kyre Sports API WNBA Step 7E v2 production smoke test",
        "model_version": MODEL_VERSION,
        "generated_at_utc": base._utc_now(),
        "state": "wnba_production_smoke_passed",
        "smoke_complete": True,
        "base_url": base.BASE_URL,
        "expected_release_revision": base.EXPECTED_RELEASE_REVISION,
        "checks_total": len(results),
        "checks_passed": len(results),
        "checks_failed": 0,
        "expected_legacy_step6u_blocker": EXPECTED_LEGACY_STEP6U_BLOCKER,
        "endpoint_results": results,
        "smoke_manifest_sha256": base._sha256_json(manifest_payload),
        "safety": safety,
    }


def main() -> int:
    print(json.dumps(run_production_smoke(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
