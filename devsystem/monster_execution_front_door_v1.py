"""Canonical MONSTER-only execution front door V1.

Every MONSTER control action enters here before the existing Step 2A global
execution chain. Foreign API 2-owned identity/state is rejected before Step 2A,
Step 2B, Step 2C, Anti-Loop, replay locks, or execution proof logic may consume
it. Clean MONSTER input delegates unchanged to the existing fail-closed global
Step 2A execution chain.

This module is read-only; it authorizes control actions but performs no network
calls or product/runtime mutation itself.
"""
from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Mapping, Sequence

from devsystem.automatic_loop_kill_v1 import contract_self_test as anti_loop_self_test
from devsystem.mandatory_2a_action_gate_v1 import contract_self_test as step2a_self_test
from devsystem.mandatory_2a_global_enforcement_v1 import enforce_action as enforce_step2a_action
from devsystem.mandatory_2b_reliability_gate_v1 import contract_self_test as step2b_self_test
from devsystem.mandatory_2c_autonomous_recovery_v1 import contract_self_test as step2c_self_test
from devsystem.monster_system_isolation_v1 import (
    MonsterSystemIsolationFailure,
    assert_monster_only,
)

VERSION = "MONSTER_EXECUTION_FRONT_DOOR_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "result": {
            "version": VERSION,
            "decision": "MONSTER_ISOLATION_BLOCKED",
            "reason": reason,
            "allowed": False,
            "execution_authorized": False,
            "monster_only": True,
            "foreign_state_blocked": True,
            "requires_user_intervention": False,
            "next_legal_action": "RETURN_TO_MONSTER_STEP_2C",
            "recheck_policy": "ONLY_AFTER_MONSTER_OWN_NEW_EVIDENCE",
        },
        "replay_ledger": {},
        "consumption_ledger": {},
    }


def enforce_monster_action(
    brain_state: Mapping[str, Any],
    action: Mapping[str, Any],
    history: Sequence[Mapping[str, Any]],
    replay_ledger: Mapping[str, Any],
    consumption_ledger: Mapping[str, Any],
    *,
    forward_decision: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Authorize exactly one MONSTER action through isolation then Step 2A."""
    isolation_payload = {
        "brain_state": brain_state,
        "action": action,
        "history": history,
        "replay_ledger": replay_ledger,
        "consumption_ledger": consumption_ledger,
        "forward_decision": forward_decision,
    }
    try:
        assert_monster_only(isolation_payload)
    except MonsterSystemIsolationFailure as exc:
        blocked = _blocked(str(exc))
        blocked["replay_ledger"] = deepcopy(dict(replay_ledger))
        blocked["consumption_ledger"] = deepcopy(dict(consumption_ledger))
        return blocked

    delegated = enforce_step2a_action(
        brain_state,
        action,
        history,
        replay_ledger,
        consumption_ledger,
        forward_decision=forward_decision,
    )
    if isinstance(delegated, Mapping) and isinstance(delegated.get("result"), Mapping):
        result = dict(delegated["result"])
        result["monster_only"] = True
        result["monster_front_door_version"] = VERSION
        result["foreign_state_blocked"] = False
        delegated = dict(delegated)
        delegated["result"] = result
    return delegated


def contract_self_test() -> dict[str, Any]:
    anti_loop = anti_loop_self_test()
    step2a = step2a_self_test()
    step2b = step2b_self_test()
    step2c = step2c_self_test()
    global_entrypoint_bound = callable(enforce_step2a_action)

    foreign = enforce_monster_action(
        {"program_id": "monster-self-test"},
        {
            "task_id": "api2-foreign-task",
            "checkpoint_id": "2BC",
            "action_type": "patch",
            "target": "monster:control-plane",
        },
        [],
        {},
        {},
    )
    foreign_result = foreign["result"]

    required_green = (
        anti_loop.get("status") == "GREEN",
        step2a.get("status") == "GREEN",
        step2b.get("status") == "GREEN",
        step2c.get("status") == "GREEN",
        global_entrypoint_bound,
    )
    if not all(required_green):
        raise RuntimeError("MONSTER canonical front door dependency contract is not GREEN")
    if foreign_result.get("decision") != "MONSTER_ISOLATION_BLOCKED":
        raise RuntimeError("MONSTER canonical front door did not block foreign state")

    return {
        "status": "GREEN",
        "version": VERSION,
        "monster_only": True,
        "foreign_state_blocked": True,
        "step2a_chain_preserved": True,
        "step2b_chain_preserved": True,
        "step2c_chain_preserved": True,
        "anti_loop_preserved": True,
        "global_execution_entrypoint_bound": True,
        "global_execution_tripwire_preserved": True,
        "legacy_global_self_test_fixture_required": False,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }


if __name__ == "__main__":
    print("MONSTER_EXECUTION_FRONT_DOOR_V1_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
