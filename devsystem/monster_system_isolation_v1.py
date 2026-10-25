"""MONSTER hard system isolation V1.

Fail closed when MONSTER control input contains an API 2-owned identity or
state reference. The shared repository name is intentionally allowed; branch,
task, proof, lease, evidence, checkpoint, recovery, or other runtime state that
identifies API 2 is not.

This module is read-only and performs no network or product/runtime mutation.
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

VERSION = "MONSTER_SYSTEM_ISOLATION_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False

_FOREIGN_SYSTEM = re.compile(r"(?<![a-z0-9])api(?:[\s_-]*)2(?![a-z0-9])", re.IGNORECASE)


class MonsterSystemIsolationFailure(RuntimeError):
    pass


def _walk(value: Any, path: str = "root"):
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            yield from _walk(key_text, f"{path}.<key>")
            yield from _walk(item, f"{path}.{key_text}")
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            yield from _walk(item, f"{path}[{index}]")
        return
    if isinstance(value, str):
        yield path, value


def assert_monster_only(payload: Any) -> dict[str, Any]:
    """Reject any control payload carrying API 2-owned identity/state."""
    violations: list[dict[str, str]] = []
    for path, text in _walk(payload):
        match = _FOREIGN_SYSTEM.search(text)
        if match:
            violations.append({"path": path, "value": match.group(0)})
    if violations:
        detail = ", ".join(item["path"] for item in violations[:8])
        raise MonsterSystemIsolationFailure(
            "MONSTER hard isolation rejected foreign API 2 state at: " + detail
        )
    return {
        "status": "GREEN",
        "version": VERSION,
        "monster_only": True,
        "foreign_state_rejected": True,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }


def contract_self_test() -> dict[str, Any]:
    clean = {
        "task_id": "monster-isolation-self-test",
        "authoritative_path": {
            "repository": "kyrepeak/kyre-sports-ai",
            "branch": "monster-main",
            "target": "monster:control-plane",
            "proof_path": "monster-runless-v2",
        },
        "evidence": {"source": "monster-ledger", "fingerprint": "m1"},
    }
    assert_monster_only(clean)

    blocked = 0
    for foreign in (
        {**clean, "task_id": "api2-foreign-task"},
        {**clean, "evidence": {"source": "API 2 ledger"}},
        {**clean, "authoritative_path": {**clean["authoritative_path"], "branch": "api_2-live"}},
        {**clean, "authoritative_path": {**clean["authoritative_path"], "proof_path": "api-2-proof"}},
    ):
        try:
            assert_monster_only(foreign)
        except MonsterSystemIsolationFailure:
            blocked += 1

    if blocked != 4:
        raise MonsterSystemIsolationFailure("MONSTER isolation self-test did not fail closed")

    return {
        "status": "GREEN",
        "version": VERSION,
        "monster_only": True,
        "foreign_state_rejected": True,
        "foreign_cases_blocked": blocked,
        "shared_repository_name_allowed": True,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }


if __name__ == "__main__":
    print("MONSTER_SYSTEM_ISOLATION_V1_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
