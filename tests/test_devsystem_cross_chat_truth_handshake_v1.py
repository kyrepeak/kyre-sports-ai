from __future__ import annotations

from copy import deepcopy
import subprocess
import sys
from pathlib import Path

import pytest

from devsystem.cross_chat_truth_handshake_v1 import (
    CrossChatTruthFailure,
    VERSION,
    authorize_handshake,
    bootstrap_view,
    build_truth_packet,
    contract_self_test,
    validate_truth_packet,
)
from devsystem.distributed_execution_lease_v1 import claim_lease, new_lease_state


def _hash(payload):
    import hashlib
    import json
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def _registry():
    payload = {
        "schema_version": 1,
        "version": "MONSTER_V4_FROZEN_ARTIFACT_REGISTRY_V1",
        "repository": "owner/repo",
        "registry_ref": "refs/heads/monster-frozen-artifact-registry",
        "registry_path": "devsystem/frozen_artifact_registry_state_v1.json",
        "revision": 2,
        "source_main_sha": "1" * 40,
        "entries": {
            "MONSTER_V4_STEP1": {
                "status": "FROZEN",
                "checkpoint_id": "MONSTER_V4_STEP1",
                "source_main_sha": "1" * 40,
                "artifacts": {"a.py": "a" * 40},
            },
            "MONSTER_V4_STEP2": {
                "status": "FROZEN",
                "checkpoint_id": "MONSTER_V4_STEP2",
                "source_main_sha": "1" * 40,
                "artifacts": {"b.py": "b" * 40},
            },
            "MONSTER_V4_STEP3": {
                "status": "FROZEN",
                "checkpoint_id": "MONSTER_V4_STEP3",
                "source_main_sha": "1" * 40,
                "artifacts": {"c.py": "c" * 40},
            },
        },
        "active_thaws": [],
    }
    payload["state_hash"] = _hash(payload)
    return payload


def _context():
    lease0 = new_lease_state("owner/repo")
    claimed = claim_lease(
        lease0,
        owner_id="chat:test-owner",
        now_utc="2026-09-30T06:00:00Z",
        current_main_sha="1" * 40,
        current_head_sha="2" * 40,
        expected_revision=0,
        expected_state_hash=lease0["state_hash"],
    )
    registry = _registry()
    packet = build_truth_packet(
        repository="owner/repo",
        truth_epoch=3,
        program_id="MONSTER_V4",
        program_title="MONSTER V4",
        current_step=4,
        total_steps=6,
        step_title="Cross-Chat Truth Handshake",
        step_status="ACTIVE",
        active_checkpoint="MONSTER_V4_STEP4",
        main_sha="1" * 40,
        active_head_sha="2" * 40,
        lease_state=claimed["state"],
        registry_state=registry,
        next_legal_action="PROVE_STEP4",
        active_pr=55,
        active_run=66,
    )
    return claimed["state"], registry, packet


def test_packet_is_hash_valid_and_bootstrap_complete():
    _, _, packet = _context()
    validated = validate_truth_packet(packet)
    view = bootstrap_view(validated)
    assert validated["version"] == VERSION
    assert view["step"] == 4
    assert view["total_steps"] == 6
    assert view["active_pr"] == 55
    assert view["active_run"] == 66
    assert view["next_legal_action"] == "PROVE_STEP4"
    assert view["frozen_checkpoint_count"] == 3


def test_missing_packet_fails_closed_without_user_intervention():
    lease, registry, _ = _context()
    result = authorize_handshake(
        None,
        consumer_id="chat:test-consumer",
        observed_main_sha="1" * 40,
        lease_state=lease,
        registry_state=registry,
    )
    assert result["decision"] == "HANDSHAKE_REQUIRED_CONTINUE"
    assert result["allowed"] is False
    assert result["requires_user_intervention"] is False


def test_stale_main_fails_closed():
    lease, registry, packet = _context()
    result = authorize_handshake(
        packet,
        consumer_id="chat:test-consumer",
        observed_main_sha="9" * 40,
        lease_state=lease,
        registry_state=registry,
    )
    assert result["decision"] == "HANDSHAKE_STALE_CONTINUE"
    assert "main_sha" in result["reason"]


def test_stale_lease_fails_closed():
    lease, registry, packet = _context()
    drift = deepcopy(lease)
    drift["revision"] += 1
    drift["state_hash"] = _hash({k: v for k, v in drift.items() if k != "state_hash"})
    result = authorize_handshake(
        packet,
        consumer_id="chat:test-consumer",
        observed_main_sha="1" * 40,
        lease_state=drift,
        registry_state=registry,
    )
    assert result["decision"] == "HANDSHAKE_STALE_CONTINUE"
    assert "lease.revision" in result["reason"]


def test_stale_registry_fails_closed():
    lease, registry, packet = _context()
    drift = deepcopy(registry)
    drift["revision"] += 1
    drift["state_hash"] = _hash({k: v for k, v in drift.items() if k != "state_hash"})
    result = authorize_handshake(
        packet,
        consumer_id="chat:test-consumer",
        observed_main_sha="1" * 40,
        lease_state=lease,
        registry_state=drift,
    )
    assert result["decision"] == "HANDSHAKE_STALE_CONTINUE"
    assert "frozen_registry.revision" in result["reason"]


def test_packet_tamper_is_rejected():
    lease, registry, packet = _context()
    packet = deepcopy(packet)
    packet["next_legal_action"] = "BYPASS"
    result = authorize_handshake(
        packet,
        consumer_id="chat:test-consumer",
        observed_main_sha="1" * 40,
        lease_state=lease,
        registry_state=registry,
    )
    assert result["decision"] == "HANDSHAKE_INVALID_CONTINUE"
    assert result["allowed"] is False


def test_frozen_checkpoint_count_cannot_lie():
    _, _, packet = _context()
    packet = deepcopy(packet)
    packet["frozen_registry"]["checkpoint_count"] = 99
    packet["state_hash"] = _hash({k: v for k, v in packet.items() if k != "state_hash"})
    with pytest.raises(CrossChatTruthFailure, match="count mismatch"):
        validate_truth_packet(packet)


def test_contract_self_test_is_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["valid_handshake_authorized"] is True
    assert result["missing_packet_blocked"] is True
    assert result["stale_main_blocked"] is True
    assert result["stale_lease_blocked"] is True
    assert result["stale_registry_blocked"] is True
    assert result["tampered_packet_blocked"] is True
    assert result["missing_packet_cannot_reach_execution"] is True
    assert result["raw_semantic_authority_rejected"] is True
    assert result["tampered_handshake_proof_rejected"] is True
    assert result["semantic_chain_preserved"] is True
    assert result["lease_chain_preserved"] is True
    assert result["two_a_chain_preserved"] is True
    assert result["final_authority_valid"] is True
    assert result["product_runtime_mutation"] is False


def test_direct_script_execution_is_green():
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str(root / "devsystem" / "cross_chat_truth_handshake_v1.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "MONSTER_V4_CROSS_CHAT_TRUTH_HANDSHAKE_V1_GREEN" in completed.stdout
