from __future__ import annotations

import pytest

import devsystem.api2_anti_loop_v1 as anti
import devsystem.api2_execution_controller_v3 as controller
import devsystem.api2_step2a_authority_v1 as step2a


PROBLEM_ID = "api2-step2a-anti-loop-hard-guard-v2"
BRANCH = "api2-step2a-anti-loop-hard-guard-v2"
PROOF_PATH = "api2-step2a-anti-loop-hard-guard-v2-proof"
REPOSITORY = "kyrepeak/kyre-sports-ai"
BASE_REF = "refs/heads/api2-main"
BASE_SHA = "a" * 40
DEPLOYMENT_ID = "dpl_" + "A" * 28


def _identity(**overrides):
    payload = {
        "repository": REPOSITORY,
        "base_ref": BASE_REF,
        "base_sha": BASE_SHA,
        "pr_number": 1796,
        "run_id": "api2-proof-run-1796-r1",
        "deployment_id": DEPLOYMENT_ID,
    }
    payload.update(overrides)
    return payload


def _begin(**overrides):
    identity = _identity(**overrides)
    return step2a.begin_problem(
        {},
        problem_id=PROBLEM_ID,
        branch=BRANCH,
        proof_path=PROOF_PATH,
        **identity,
    )


def test_step2a_binds_complete_authoritative_path_identity():
    state = _begin()
    active = state["active_problem"]
    assert active == {
        "system": "api2",
        "problem_id": PROBLEM_ID,
        "repository": REPOSITORY,
        "base_ref": BASE_REF,
        "base_sha": BASE_SHA,
        "branch": BRANCH,
        "pr_number": 1796,
        "run_id": "api2-proof-run-1796-r1",
        "deployment_id": DEPLOYMENT_ID,
        "proof_path": PROOF_PATH,
    }
    assert state["authority_digest"].startswith("sha256:")


def test_step2a_rejects_truncated_or_noncanonical_authority_ids():
    with pytest.raises(step2a.Step2AError, match="API2_BASE_SHA_INVALID"):
        _begin(base_sha="74210717")
    with pytest.raises(step2a.Step2AError, match="API2_DEPLOYMENT_ID_INVALID"):
        _begin(deployment_id="dpl_FHwX")


def test_step2a_existing_authority_cannot_be_reset_to_another_path():
    state = _begin()
    with pytest.raises(step2a.Step2AError, match="API2_MULTIPLE_ACTIVE_PROBLEMS_OR_PATHS_FORBIDDEN"):
        step2a.begin_problem(
            state,
            problem_id=PROBLEM_ID,
            branch=BRANCH,
            proof_path=PROOF_PATH,
            **_identity(deployment_id="dpl_" + "B" * 28),
        )


def test_step2a_resume_requires_exact_snapshot_identity():
    state = _begin()
    snapshot = step2a.authority_snapshot(state)
    resumed = step2a.restore_authority(snapshot)
    assert resumed["authority_digest"] == state["authority_digest"]

    tampered = dict(snapshot)
    tampered["active_problem"] = dict(snapshot["active_problem"])
    tampered["active_problem"]["deployment_id"] = "dpl_" + "C" * 28
    with pytest.raises(step2a.Step2AError, match="API2_AUTHORITY_SNAPSHOT_DIGEST_MISMATCH"):
        step2a.restore_authority(tampered)


def test_anti_loop_failed_action_is_not_reauthorized_by_rewording_evidence():
    action = {
        "type": "READBACK",
        "target": "production-rushing-values",
        "method": "vercel-web-fetch",
        "deployment_id": DEPLOYMENT_ID,
    }
    state = anti.record_failure(
        {},
        action=action,
        evidence=["preview authentication redirected"],
        hypothesis="protected deployment access path",
        classification="ACCESS_PATH_FAILURE",
    )
    decision = anti.authorize_retry(
        state,
        action=action,
        evidence=["different wording and another login response"],
        hypothesis="different wording for the same protected deployment access path",
    )
    assert decision["allowed"] is False
    assert decision["decision"] == "FAILED_ACTION_PERMANENTLY_EXCLUDED"


def test_anti_loop_failure_ledger_is_append_only_and_classified():
    action = {"type": "FETCH", "target": "preview", "method": "raw-http"}
    first = anti.record_failure(
        {},
        action=action,
        evidence=["302 to login"],
        hypothesis="preview auth",
        classification="AUTH_REDIRECT",
    )
    with pytest.raises(anti.AntiLoopError, match="API2_FAILURE_ALREADY_RECORDED"):
        anti.record_failure(
            first,
            action=action,
            evidence=["same operation again"],
            hypothesis="preview auth again",
            classification="AUTH_REDIRECT",
        )


def test_anti_loop_same_state_poll_is_blocked_until_observation_changes():
    state, first = anti.authorize_poll(
        {},
        operation_id=DEPLOYMENT_ID,
        observed_state="BUILDING",
        observed_revision="build-17",
    )
    assert first["allowed"] is True

    _, repeated = anti.authorize_poll(
        state,
        operation_id=DEPLOYMENT_ID,
        observed_state="BUILDING",
        observed_revision="build-17",
    )
    assert repeated["allowed"] is False
    assert repeated["decision"] == "SAME_STATE_POLL_BLOCKED"

    _, changed = anti.authorize_poll(
        state,
        operation_id=DEPLOYMENT_ID,
        observed_state="READY",
        observed_revision="build-18",
    )
    assert changed["allowed"] is True
    assert changed["decision"] == "OBSERVATION_CHANGED"


def test_anti_loop_snapshot_tampering_is_rejected():
    action = {"type": "FETCH", "target": "production", "method": "api"}
    state = anti.record_failure(
        {},
        action=action,
        evidence=["404 truncated deployment id"],
        hypothesis="truncated deployment identity",
        classification="IDENTITY_FAILURE",
    )
    snapshot = anti.state_snapshot(state)
    restored = anti.restore_state(snapshot)
    assert restored["state_digest"] == snapshot["state_digest"]

    tampered = dict(snapshot)
    tampered["failures"] = {}
    with pytest.raises(anti.AntiLoopError, match="API2_ANTI_LOOP_SNAPSHOT_DIGEST_MISMATCH"):
        anti.restore_state(tampered)


def test_controller_handoff_restores_same_authority_and_failed_method_exclusion():
    state = controller.new_state(
        problem_id=PROBLEM_ID,
        branch=BRANCH,
        proof_path=PROOF_PATH,
        acceptance_criteria=["hard authority", "anti loop"],
        authority_identity=_identity(),
    )
    action = {
        "type": "READBACK",
        "target": "production-rushing-values",
        "method": "protected-preview-raw-http",
        "deployment_id": DEPLOYMENT_ID,
    }
    state = controller.record_failure(
        state,
        action=action,
        evidence=["redirected to authentication"],
        hypothesis="protected deployment requires authenticated path",
        classification="ACCESS_PATH_FAILURE",
    )
    snapshot = controller.state_snapshot(state)
    resumed = controller.restore_state(snapshot)

    assert resumed["authority"]["authority_digest"] == state["authority"]["authority_digest"]
    assert resumed["authority"]["active_problem"] == state["authority"]["active_problem"]
    decision = anti.authorize_retry(
        resumed["anti_loop"],
        action=action,
        evidence=["same method with different words"],
        hypothesis="same access failure rephrased",
    )
    assert decision["allowed"] is False
    assert decision["decision"] == "FAILED_ACTION_PERMANENTLY_EXCLUDED"


def test_controller_handoff_rejects_tampered_authority_snapshot():
    state = controller.new_state(
        problem_id=PROBLEM_ID,
        branch=BRANCH,
        proof_path=PROOF_PATH,
        acceptance_criteria=["hard authority"],
        authority_identity=_identity(),
    )
    snapshot = controller.state_snapshot(state)
    snapshot["authority_snapshot"]["active_problem"]["deployment_id"] = "dpl_" + "Z" * 28
    with pytest.raises(controller.ControllerError, match="API2_CONTROLLER_RESUME_AUTHORITY_INVALID"):
        controller.restore_state(snapshot)
