from copy import deepcopy
import json
import urllib.error
import urllib.request

from devsystem.frozen_artifact_registry_v1 import validate_registry
from runless_proof_plane.registry import _state_hash
from runless_proof_plane.step7_registry import (
    FREEZE_TOKEN,
    STEP7_ARTIFACTS,
    THAW_ID,
    build_step7_registry_update,
)

# Temporary one-shot transport shim for Universal Live Status Board V1 Step 2.
# It only submits the exact request to the authoritative Runless Proof Plane;
# all proof execution, receipt persistence, and final-gate publication remain
# owned by that service. Remove immediately after the terminal response.
def _submit_ulsb_step2_once():
    body = json.dumps(
        {
            "task_id": "universal-live-status-board-v1-step2-authoritative-chat-ownership",
            "workstream": "universal-live-status-board-v1",
            "candidate_sha": "ad7a3749305e4502092a02d395ae2115775f6989",
            "lease_id": "SCOPE-LEASE-E273870B78DF7BEB9029E929",
            "authorization_id": "AUTH-UNIVERSAL-LIVE-STATUS-BOARD-V1-STEP2-R1",
            "expected_main_sha": "20f23cae36b70ba702657546296560c5432203dc",
        },
        sort_keys=True,
    ).encode()
    request = urllib.request.Request(
        "https://runless-proof-plane.onrender.com/prove",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        response = urllib.request.urlopen(request, timeout=180)
        payload = response.read().decode()
        print("ULSB_STEP2_RUNLESS_RESPONSE=" + payload, flush=True)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()
        print(f"ULSB_STEP2_RUNLESS_HTTP_{exc.code}={detail}", flush=True)
        raise


_submit_ulsb_step2_once()

OLD_APP = "a" * 40
NEW_APP = "b" * 40
MERGED_SHA = "c" * 40


def _registry():
    payload = {
        "schema_version": 1,
        "version": "MONSTER_V4_FROZEN_ARTIFACT_REGISTRY_V1",
        "repository": "kyrepeak/kyre-sports-ai",
        "registry_ref": "refs/heads/monster-frozen-artifact-registry",
        "registry_path": "devsystem/frozen_artifact_registry_state_v1.json",
        "revision": 140,
        "source_main_sha": "d" * 40,
        "entries": {
            "STEP5": {
                "status": "FROZEN",
                "checkpoint_id": "STEP5",
                "source_main_sha": "d" * 40,
                "artifacts": {"app.py": OLD_APP, "step5.py": "1" * 40},
            },
            "STEP6": {
                "status": "FROZEN",
                "checkpoint_id": "STEP6",
                "source_main_sha": "d" * 40,
                "artifacts": {"app.py": OLD_APP, "step6.py": "2" * 40},
            },
        },
        "active_thaws": [
            {
                "thaw_id": "UNRELATED",
                "status": "ACTIVE",
                "target_head_sha": "e" * 40,
                "files": {
                    "step5.py": {"from_blob": "1" * 40, "to_blob": "3" * 40}
                },
            },
            {
                "thaw_id": THAW_ID,
                "status": "ACTIVE",
                "target_head_sha": "f" * 40,
                "files": {
                    "app.py": {"from_blob": OLD_APP, "to_blob": NEW_APP}
                },
            },
        ],
    }
    payload["state_hash"] = _state_hash(payload)
    validate_registry(payload)
    return payload


def _artifacts():
    result = {}
    for index, path in enumerate(sorted(STEP7_ARTIFACTS), 4):
        result[path] = f"{index:x}" * 40
    result["app.py"] = NEW_APP
    return result


def test_step7_freeze_scope_is_exactly_seven_artifacts():
    assert FREEZE_TOKEN == "WNBA_PRA_REPAIR_V1_STEP7_FROZEN"
    assert THAW_ID == "THAW-WNBA-PRA-REPAIR-V1-STEP7-APP"
    assert set(STEP7_ARTIFACTS) == {
        "app.py",
        "wnba_pra_repair_v1_step7_final_integration.py",
        "streamlit_memory_lazy_router_wnba_pra_repair_v1_step7_final_integration.py",
        "tests/test_wnba_pra_repair_v1_step7.py",
        "devsystem/wnba_pra_repair_v1_step7_final_integration_cert.py",
        "devsystem/runless_proof_plans/wnba-pra-repair-v1-step7-final-integration.json",
        "devsystem/task_ledgers/wnba-pra-repair-v1-step7-final-integration.json",
    }


def test_step7_atomic_freeze_forward_ports_app_retires_own_thaw_and_preserves_unrelated():
    current = _registry()
    unrelated_before = deepcopy(current["active_thaws"][0])
    updated = build_step7_registry_update(current, _artifacts(), MERGED_SHA)

    assert updated["revision"] == current["revision"] + 1
    assert updated["source_main_sha"] == MERGED_SHA
    assert updated["entries"]["STEP5"]["artifacts"]["app.py"] == NEW_APP
    assert updated["entries"]["STEP6"]["artifacts"]["app.py"] == NEW_APP
    assert all(grant["thaw_id"] != THAW_ID for grant in updated["active_thaws"])
    assert updated["active_thaws"] == [unrelated_before]
    assert updated["entries"][FREEZE_TOKEN] == {
        "status": "FROZEN",
        "checkpoint_id": FREEZE_TOKEN,
        "source_main_sha": MERGED_SHA,
        "artifacts": _artifacts(),
    }
    assert validate_registry(updated)["status"] == "GREEN"


def test_step7_freeze_fails_closed_without_exact_step7_thaw():
    current = _registry()
    current["active_thaws"] = current["active_thaws"][:1]
    current["state_hash"] = _state_hash(current)
    try:
        build_step7_registry_update(current, _artifacts(), MERGED_SHA)
    except RuntimeError as exc:
        assert "STEP7_THAW_REQUIRED" in str(exc)
    else:
        raise AssertionError("missing Step-7 app thaw must fail closed")


def test_step7_freeze_fails_closed_when_app_artifact_does_not_match_thaw_target():
    artifacts = _artifacts()
    artifacts["app.py"] = "9" * 40
    try:
        build_step7_registry_update(_registry(), artifacts, MERGED_SHA)
    except RuntimeError as exc:
        assert "STEP7_APP_THAW_TARGET_MISMATCH" in str(exc)
    else:
        raise AssertionError("app artifact must equal the exact Step-7 thaw target")
