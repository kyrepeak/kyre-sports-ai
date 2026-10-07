from __future__ import annotations

import importlib

import pytest


def _telemetry():
    try:
        return importlib.import_module("runless_proof_plane.tail_sla_telemetry")
    except ModuleNotFoundError:
        pytest.fail("Runless Task 17 Step 6 tail SLA telemetry engine is missing")


def test_records_every_state_timestamp_and_exposes_tail_fields():
    telemetry = _telemetry()
    timeline = []
    timeline = telemetry.record_tail_state(
        timeline,
        state="CERTIFIED_PROOF",
        at_utc="2026-10-07T07:00:00Z",
        blocked_on="MERGE",
        next_event="MERGE_COMMIT",
    )
    timeline = telemetry.record_tail_state(
        timeline,
        state="MERGED",
        at_utc="2026-10-07T07:00:32Z",
        blocked_on="MERGED_MAIN_GATE",
        next_event="RUNLESS_GATE_SUCCESS",
    )
    timeline = telemetry.record_tail_state(
        timeline,
        state="GREEN_FROZEN",
        at_utc="2026-10-07T07:01:41Z",
    )

    result = telemetry.evaluate_tail_sla(timeline, now_utc="2026-10-07T07:01:41Z")

    assert [row["state"] for row in result["state_timestamps"]] == [
        "CERTIFIED_PROOF",
        "MERGED",
        "GREEN_FROZEN",
    ]
    assert result["tail_age_seconds"] == 101
    assert result["blocked_on"] is None
    assert result["next_event"] is None
    assert result["sla_seconds"] == 120
    assert result["within_sla"] is True
    assert result["decision"] == "RUNLESS_TAIL_SLA_GREEN"


def test_normal_tail_boundary_is_inclusive_and_breach_is_explicit():
    telemetry = _telemetry()
    base = telemetry.record_tail_state(
        [],
        state="CERTIFIED_PROOF",
        at_utc="2026-10-07T07:00:00Z",
        blocked_on="FREEZE",
        next_event="REGISTRY_READBACK",
    )

    at_boundary = telemetry.evaluate_tail_sla(base, now_utc="2026-10-07T07:02:00Z")
    breached = telemetry.evaluate_tail_sla(base, now_utc="2026-10-07T07:02:01Z")

    assert at_boundary["tail_age_seconds"] == 120
    assert at_boundary["within_sla"] is True
    assert at_boundary["decision"] == "RUNLESS_TAIL_SLA_TRACKING"
    assert breached["tail_age_seconds"] == 121
    assert breached["within_sla"] is False
    assert breached["decision"] == "RUNLESS_TAIL_SLA_BREACH"
    assert breached["blocked_on"] == "FREEZE"
    assert breached["next_event"] == "REGISTRY_READBACK"


def test_hosted_deployment_wait_is_event_driven_and_wakes_on_identity_change():
    telemetry = _telemetry()
    timeline = telemetry.record_tail_state(
        [],
        state="CERTIFIED_PROOF",
        at_utc="2026-10-07T07:00:00Z",
        blocked_on="HOSTED_DEPLOYMENT",
        next_event="MEANINGFUL_IDENTITY_CHANGE",
    )
    timeline = telemetry.record_tail_state(
        timeline,
        state="WAITING_HOSTED_DEPLOYMENT",
        at_utc="2026-10-07T07:00:05Z",
        blocked_on="HOSTED_DEPLOYMENT",
        next_event="MEANINGFUL_IDENTITY_CHANGE",
        hosted_deployment_wait=True,
        identity="deploy:abc",
    )

    waiting = telemetry.evaluate_tail_sla(
        timeline,
        now_utc="2026-10-07T07:05:00Z",
        meaningful_identity_change=False,
    )
    wake = telemetry.evaluate_tail_sla(
        timeline,
        now_utc="2026-10-07T07:05:00Z",
        meaningful_identity_change=True,
    )

    assert waiting["sla_applicable"] is False
    assert waiting["sla_status"] == "HOSTED_WAIT_EVENT_DRIVEN"
    assert waiting["blocked_on"] == "HOSTED_DEPLOYMENT"
    assert waiting["next_event"] == "MEANINGFUL_IDENTITY_CHANGE"
    assert waiting["event_driven_resume"] is True
    assert waiting["polling_required"] is False
    assert waiting["resume_now"] is False
    assert wake["resume_now"] is True
    assert wake["decision"] == "RUNLESS_TAIL_SLA_RESUME_NOW"


def test_missing_certified_proof_fails_closed_without_mutation_authority():
    telemetry = _telemetry()
    timeline = telemetry.record_tail_state(
        [],
        state="WAITING",
        at_utc="2026-10-07T07:00:00Z",
        blocked_on="CERTIFIED_PROOF",
        next_event="RUNLESS_GATE_SUCCESS",
    )
    result = telemetry.evaluate_tail_sla(timeline, now_utc="2026-10-07T07:00:30Z")

    assert result["decision"] == "RUNLESS_TAIL_SLA_UNARMED"
    assert result["allowed"] is False
    assert result["mutation_authority_granted"] is False
    assert result["network_calls"] is False
    assert result["github_actions_fallback"] == 0


def test_non_monotonic_timestamps_fail_closed():
    telemetry = _telemetry()
    timeline = telemetry.record_tail_state(
        [],
        state="CERTIFIED_PROOF",
        at_utc="2026-10-07T07:00:10Z",
    )
    with pytest.raises(telemetry.TailSLATelemetryFailure, match="NON_MONOTONIC_TIMESTAMP"):
        telemetry.record_tail_state(
            timeline,
            state="MERGED",
            at_utc="2026-10-07T07:00:09Z",
        )


def test_module_is_side_effect_free_and_never_enables_actions_fallback():
    telemetry = _telemetry()
    assert telemetry.NETWORK_CALLS is False
    assert telemetry.AUTO_MUTATE is False
    assert telemetry.MAY_MODIFY_PRODUCT_RUNTIME is False
    assert telemetry.MUTATION_AUTHORITY_GRANTED is False
    assert telemetry.POLLING_REQUIRED is False
    assert telemetry.GITHUB_ACTIONS_FALLBACK == 0
