from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import validate_registry
from runless_proof_plane.registry import _state_hash
from runless_proof_plane.step7_registry import (
    FREEZE_TOKEN,
    STEP7_ARTIFACTS,
    THAW_ID,
    build_step7_registry_update,
)

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


def test_relay_cfb_game_total_step4_runless_proof_once():
    import json
    import urllib.error
    import urllib.request

    payload = {
        "task_id": "cfb-game-total-page1-v2-step4-prediction-market",
        "workstream": "cfb-game-total-page1-v2",
        "candidate_sha": "6ce49ccd5cee2a0b39af9404f6ed413e78e49f1b",
        "lease_id": "SCOPE-LEASE-2FEF82C73C72C46AE97410C9",
        "authorization_id": "AUTH-CFB-GAME-TOTAL-PAGE1-V2-STEP4-6CE49CCD",
        "expected_main_sha": "8ad570f765daf0884fe6f963f10982b05a414b60",
    }
    request = urllib.request.Request(
        "https://runless-proof-plane.onrender.com/prove",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            body = response.read().decode("utf-8", "replace")
            status = int(response.status)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        status = int(exc.code)
    print(f"RUNLESS_CFB_STEP4_RELAY_HTTP={status}")
    print("RUNLESS_CFB_STEP4_RELAY_BODY=" + body)
    assert status == 200, body
