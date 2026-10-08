from __future__ import annotations

from devsystem import closeout_event_consumer_v1 as consumer


PACKET_HASH = "a" * 64
PROOF_HASH = "b" * 64
ACTION_FP = "c" * 64


def _resume(action: str = "VERIFY_DEPLOYMENT_TERMINAL"):
    return {
        "decision": "RUNLESS_RESUME_CONSUMED",
        "next_legal_action": action,
        "step_2a_required": True,
        "mutation_authority_granted": False,
    }


def _step2a(action: str = "VERIFY_DEPLOYMENT_TERMINAL", target: str = "deployment:dep-123"):
    return {
        "decision": "GLOBAL_EXECUTION_AUTHORIZED",
        "allowed": True,
        "execution_authorized": True,
        "action_type": action,
        "target": target,
        "execution_proof_hash": PROOF_HASH,
        "action_fingerprint": ACTION_FP,
        "execution_proof": {"payload": {"execution_authorized": True}},
    }


def _action(action: str = "VERIFY_DEPLOYMENT_TERMINAL", target: str = "deployment:dep-123"):
    return {
        "task_id": "api2-finalization-authority-v1-step4-closeout-event-consumer",
        "checkpoint_id": "API2_FINALIZATION_AUTHORITY_V1_STEP4",
        "action_type": action,
        "target": target,
    }


def _open_latch():
    return {
        "decision": "TERMINAL_LATCH_OPEN",
        "short_circuit": False,
        "canonical_completion": {"complete": False},
    }


def _terminal_latch():
    return {
        "decision": "TERMINAL_LATCH_ALREADY_COMPLETE",
        "short_circuit": True,
        "canonical_completion": {"complete": True},
        "terminal_digest": "d" * 64,
    }


def test_module_is_side_effect_free_by_default():
    assert consumer.NETWORK_CALLS is False
    assert consumer.AUTO_MUTATE is False
    assert consumer.MAY_MODIFY_PRODUCT_RUNTIME is False
    assert consumer.MUTATION_AUTHORITY_GRANTED is False
    assert consumer.POLLING_REQUIRED is False
    assert consumer.GITHUB_ACTIONS_FALLBACK == 0


def test_terminal_canonical_truth_short_circuits_before_executor():
    calls = []

    def execute(action):
        calls.append(action)
        return {"status": "SUCCESS"}

    out = consumer.consume_closeout_event(
        workstream_id="api2-finalization-authority-v1-step4",
        continuation_packet_hash=PACKET_HASH,
        resume_claim=_resume(),
        step2a_result=_step2a(),
        action=_action(),
        terminal_latch=_terminal_latch(),
        consumer_ledger={},
        execute_action=execute,
        telemetry={"tail_sla_state": "BREACHED"},
    )
    assert out["result"]["decision"] == "CLOSEOUT_ALREADY_TERMINAL"
    assert out["result"]["action_executed"] is False
    assert out["result"]["next_legal_action"] == "MOVE_TO_NEXT_STEP"
    assert calls == []


def test_resume_must_be_consumed_before_closeout_action_can_execute():
    calls = []

    def execute(action):
        calls.append(action)
        return {"status": "SUCCESS"}

    resume = _resume()
    resume["decision"] = "RUNLESS_EVENT_RESUME_READY"
    out = consumer.consume_closeout_event(
        workstream_id="api2-finalization-authority-v1-step4",
        continuation_packet_hash=PACKET_HASH,
        resume_claim=resume,
        step2a_result=_step2a(),
        action=_action(),
        terminal_latch=_open_latch(),
        consumer_ledger={},
        execute_action=execute,
    )
    assert out["result"]["decision"] == "CLOSEOUT_RESUME_NOT_CONSUMED"
    assert out["result"]["retry_allowed_now"] is False
    assert calls == []


def test_final_step2a_global_authority_is_required_and_bound_to_same_action():
    calls = []

    def execute(action):
        calls.append(action)
        return {"status": "SUCCESS"}

    denied = _step2a()
    denied["decision"] = "TRIPWIRE_BLOCKED_CONTINUE"
    denied["allowed"] = False
    denied["execution_authorized"] = False
    out = consumer.consume_closeout_event(
        workstream_id="api2-finalization-authority-v1-step4",
        continuation_packet_hash=PACKET_HASH,
        resume_claim=_resume(),
        step2a_result=denied,
        action=_action(),
        terminal_latch=_open_latch(),
        consumer_ledger={},
        execute_action=execute,
    )
    assert out["result"]["decision"] == "CLOSEOUT_STEP2A_REQUIRED"
    assert calls == []

    mismatched = consumer.consume_closeout_event(
        workstream_id="api2-finalization-authority-v1-step4",
        continuation_packet_hash=PACKET_HASH,
        resume_claim=_resume(),
        step2a_result=_step2a(target="deployment:other"),
        action=_action(),
        terminal_latch=_open_latch(),
        consumer_ledger={},
        execute_action=execute,
    )
    assert mismatched["result"]["decision"] == "CLOSEOUT_STEP2A_SCOPE_MISMATCH"
    assert calls == []


def test_valid_closeout_executes_exactly_one_legal_action_and_emits_receipt():
    calls = []

    def execute(action):
        calls.append(dict(action))
        return {
            "status": "SUCCESS",
            "action_type": action["action_type"],
            "target": action["target"],
            "receipt_id": "executor-receipt-1",
        }

    out = consumer.consume_closeout_event(
        workstream_id="api2-finalization-authority-v1-step4",
        continuation_packet_hash=PACKET_HASH,
        resume_claim=_resume(),
        step2a_result=_step2a(),
        action=_action(),
        terminal_latch=_open_latch(),
        consumer_ledger={},
        execute_action=execute,
        telemetry={"tail_sla_state": "READY", "mutation_authority": True},
    )
    assert out["result"]["decision"] == "CLOSEOUT_ACTION_CONSUMED"
    assert out["result"]["action_executed"] is True
    assert out["result"]["executor_calls"] == 1
    assert out["result"]["telemetry_detection_only"] is True
    assert out["result"]["next_legal_action"] == "RECONCILE_CANONICAL_COMPLETION"
    assert len(calls) == 1
    assert out["receipt"]["receipt_digest"]
    assert out["receipt"]["execution_proof_hash"] == PROOF_HASH
    assert out["receipt"]["action_fingerprint"] == ACTION_FP
    assert out["receipt"]["executor_receipt"]["receipt_id"] == "executor-receipt-1"
    assert out["receipt"]["consumer_key"] in out["consumer_ledger"]


def test_same_consumption_key_is_duplicate_blocked_without_second_executor_call():
    calls = []

    def execute(action):
        calls.append(dict(action))
        return {
            "status": "SUCCESS",
            "action_type": action["action_type"],
            "target": action["target"],
            "receipt_id": f"executor-{len(calls)}",
        }

    first = consumer.consume_closeout_event(
        workstream_id="api2-finalization-authority-v1-step4",
        continuation_packet_hash=PACKET_HASH,
        resume_claim=_resume(),
        step2a_result=_step2a(),
        action=_action(),
        terminal_latch=_open_latch(),
        consumer_ledger={},
        execute_action=execute,
    )
    second = consumer.consume_closeout_event(
        workstream_id="api2-finalization-authority-v1-step4",
        continuation_packet_hash=PACKET_HASH,
        resume_claim=_resume(),
        step2a_result=_step2a(),
        action=_action(),
        terminal_latch=_open_latch(),
        consumer_ledger=first["consumer_ledger"],
        execute_action=execute,
    )
    assert first["result"]["decision"] == "CLOSEOUT_ACTION_CONSUMED"
    assert second["result"]["decision"] == "CLOSEOUT_DUPLICATE_BLOCKED"
    assert second["result"]["duplicate_action_blocked"] is True
    assert len(calls) == 1


def test_executor_failure_is_single_attempt_and_never_blind_retries():
    calls = []

    def execute(action):
        calls.append(dict(action))
        return {
            "status": "FAILURE",
            "action_type": action["action_type"],
            "target": action["target"],
            "failure_class": "DEPLOYMENT_IDENTITY_MISMATCH",
        }

    out = consumer.consume_closeout_event(
        workstream_id="api2-finalization-authority-v1-step4",
        continuation_packet_hash=PACKET_HASH,
        resume_claim=_resume(),
        step2a_result=_step2a(),
        action=_action(),
        terminal_latch=_open_latch(),
        consumer_ledger={},
        execute_action=execute,
    )
    assert out["result"]["decision"] == "CLOSEOUT_ACTION_FAILED"
    assert out["result"]["executor_calls"] == 1
    assert out["result"]["retry_allowed_now"] is False
    assert out["result"]["next_legal_action"] == "CLASSIFY_CLOSEOUT_ACTION_FAILURE"
    assert len(calls) == 1


def test_telemetry_cannot_create_authority_when_step2a_is_missing():
    calls = []

    def execute(action):
        calls.append(dict(action))
        return {"status": "SUCCESS"}

    out = consumer.consume_closeout_event(
        workstream_id="api2-finalization-authority-v1-step4",
        continuation_packet_hash=PACKET_HASH,
        resume_claim=_resume(),
        step2a_result={"decision": "TAIL_SLA_READY", "allowed": True},
        action=_action(),
        terminal_latch=_open_latch(),
        consumer_ledger={},
        execute_action=execute,
        telemetry={"mutation_authority": True, "tail_sla_state": "READY"},
    )
    assert out["result"]["decision"] == "CLOSEOUT_STEP2A_REQUIRED"
    assert out["result"]["telemetry_detection_only"] is True
    assert calls == []
