from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy
from pathlib import Path

TOKEN = "WNBA_PRA_REPAIR_V1_STEP3_FROZEN"
THAW = "THAW-API2-WNBA-DATA-STEP3-PLAYER-SHELL-HANDOFF-R1"
INPUT = Path("registry_input.json")
EXPECTED_REVISION = 182
EXPECTED_HASH = "d0fb9193ca76394e7537bf3779fc2476c61841db8af17d937c6d76601e279218"
EXPECTED_SOURCE = "14fb065eee664a798764a50a4dc2cfb124f273c8"
HANDOFF_PATH = "streamlit_memory_lazy_router_wnba_pra_repair_v1_step7_final_integration.py"
HANDOFF_FROM = "6aeb31c68c9e4637aa87d50a70e381e283fc08f7"
HANDOFF_TO = "a82a0d374c0fc1de9346e0d62f92831e39ddd9f7"
HANDOFF_TARGET = "72fb0ca7eaad3827f7a9721c193cd59a5acb7f99"
RETARGET = (
    "WNBA_PRA_REPAIR_V1_STEP7_FROZEN",
    "WNBA_PUSHSTATE_REPAIR_V1_STEP3_FROZEN",
    "WNBA_PUSHSTATE_REPAIR_V1_STEP4_FROZEN",
)
CHUNK = 6000


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _state_hash(state: dict) -> str:
    payload = deepcopy(state)
    payload.pop("state_hash", None)
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _build_candidate(state: dict) -> dict:
    assert state["revision"] == EXPECTED_REVISION, "REGISTRY_REVISION_DRIFT"
    assert state["state_hash"] == EXPECTED_HASH, "REGISTRY_HASH_DRIFT"
    assert state["source_main_sha"] == EXPECTED_SOURCE, "SOURCE_MAIN_DRIFT"
    assert TOKEN not in state["entries"], "FREEZE_TOKEN_ALREADY_PRESENT"
    matching = [x for x in state["active_thaws"] if x.get("thaw_id") == THAW]
    assert len(matching) == 1, "HANDOFF_THAW_IDENTITY_DRIFT"
    thaw = matching[0]
    pair = thaw["files"][HANDOFF_PATH]
    assert pair["from_blob"] == HANDOFF_FROM, "HANDOFF_FROM_DRIFT"
    assert pair["to_blob"] == HANDOFF_TO, "HANDOFF_TO_DRIFT"
    assert thaw["target_head_sha"] == HANDOFF_TARGET, "HANDOFF_TARGET_DRIFT"

    out = deepcopy(state)
    for checkpoint in RETARGET:
        entry = out["entries"][checkpoint]
        assert entry["artifacts"][HANDOFF_PATH] == HANDOFF_FROM, (checkpoint, "BASELINE_DRIFT")
        entry["artifacts"][HANDOFF_PATH] = HANDOFF_TO
    out["active_thaws"] = [x for x in out["active_thaws"] if x.get("thaw_id") != THAW]
    assert len(out["active_thaws"]) == len(state["active_thaws"]) - 1
    out["entries"][TOKEN] = {
        "artifacts": {
            "streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness.py": "84ae2e8eacd785e29547cbc92b435c9483994417",
            "tests/test_wnba_pra_repair_v1_step3.py": "98b2809c31b6b012331c18dc977a54add259ab07",
            "wnba_pra_repair_v1_step3_data.py": "d7c90bda07a5a32a53e14f87973ca6d1596fd1a5",
        },
        "checkpoint_id": TOKEN,
        "source_main_sha": EXPECTED_SOURCE,
        "status": "FROZEN",
    }
    out["revision"] = EXPECTED_REVISION + 1
    out["source_main_sha"] = EXPECTED_SOURCE
    out["state_hash"] = _state_hash(out)
    return out


def pytest_sessionstart(session) -> None:  # pragma: no cover
    state = json.loads(INPUT.read_text(encoding="utf-8"))
    candidate = _build_candidate(state)
    from devsystem.frozen_artifact_registry_v1 import validate_registry
    validation = validate_registry(candidate)
    candidate_text = json.dumps(candidate, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    candidate_bytes = candidate_text.encode("utf-8")
    Path("registry_candidate.json").write_bytes(candidate_bytes)
    encoded = base64.b64encode(candidate_bytes).decode("ascii")
    total = (len(encoded) + CHUNK - 1) // CHUNK
    print("WNBA_PRA_REPAIR_V1_STEP3_REGISTRY_CANDIDATE_GREEN", flush=True)
    print(f"REGISTRY_CANDIDATE_FILE_SHA256={hashlib.sha256(candidate_bytes).hexdigest()}", flush=True)
    print(f"REGISTRY_B64_TOTAL={total}", flush=True)
    for index in range(total):
        piece = encoded[index * CHUNK:(index + 1) * CHUNK]
        print(f"REGISTRY_B64_{index:03d}_OF_{total:03d}={piece}", flush=True)
    meta = {
        "status": "GREEN",
        "revision": candidate["revision"],
        "state_hash": candidate["state_hash"],
        "freeze_token": TOKEN,
        "source_main_sha": candidate["source_main_sha"],
        "retired_thaw": THAW,
        "retargeted_checkpoints": list(RETARGET),
        "active_thaw_count": len(candidate["active_thaws"]),
        "validator_status": validation["status"],
        "entry_count": validation["entry_count"],
        "artifact_count": validation["artifact_count"],
    }
    print("REGISTRY_TRANSPORT_META=" + json.dumps(meta, sort_keys=True), flush=True)
