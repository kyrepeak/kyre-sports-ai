from devsystem.api2_registry_step4_controlplane_repair_r1 import (
    BRIDGE_HASH,
    REGISTRY_BRANCH,
    REGISTRY_PATH,
    STEP4_CANDIDATE_SHA,
    STEP4_THAW_ID,
    TARGET_HASH,
    TARGET_REVISION,
    validate_target_payload,
)


def _payload():
    return {
        "revision": TARGET_REVISION,
        "state_hash": TARGET_HASH,
        "source_main_sha": "6b3a37891fc2938736e8f371d29c3337682a4a22",
        "entries": {
            "NBA_SPREAD_STEP3_SCHEDULE_PHOENIX_FROZEN": {
                "status": "FROZEN",
                "checkpoint_id": "NBA_SPREAD_STEP3_SCHEDULE_PHOENIX_FROZEN",
                "source_main_sha": "6b3a37891fc2938736e8f371d29c3337682a4a22",
                "artifacts": {},
            }
        },
        "active_thaws": [
            {
                "thaw_id": STEP4_THAW_ID,
                "status": "ACTIVE",
                "target_head_sha": STEP4_CANDIDATE_SHA,
                "files": {
                    "nba_spread_page_v1.py": {
                        "from_blob": "b55cfb431dcbb867b5bfd5807efeca1dc66ebcb0",
                        "to_blob": "0ad62af70010051c3ac8f4477d63263a228eb76b",
                    }
                },
            }
        ],
    }


def test_repair_identity_is_pinned():
    assert REGISTRY_BRANCH == "monster-frozen-artifact-registry"
    assert REGISTRY_PATH == "devsystem/frozen_artifact_registry_state_v1.json"
    assert BRIDGE_HASH == "e48fabb3601919a07b8b15eb93f832867a593ccadddefa056d3c4fb61a5553ff"
    assert TARGET_REVISION == 297
    assert TARGET_HASH == "cd805a3acb3d6c1ab083a753bf943ac7f596950f8995675bc969597af3a09905"


def test_target_requires_exact_step4_thaw():
    validate_target_payload(_payload(), require_full_registry=False)
    bad = _payload()
    bad["active_thaws"][0]["target_head_sha"] = "0" * 40
    try:
        validate_target_payload(bad, require_full_registry=False)
    except RuntimeError as exc:
        assert "STEP4_THAW_IDENTITY" in str(exc)
    else:
        raise AssertionError("wrong candidate must fail closed")


def test_full_target_requires_146_entries_and_5_thaws():
    try:
        validate_target_payload(_payload(), require_full_registry=True)
    except RuntimeError as exc:
        assert "TARGET_ENTRY_COUNT" in str(exc)
    else:
        raise AssertionError("partial registry must fail full-target validation")
