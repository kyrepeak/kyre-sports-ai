from devsystem.nba_spread_step4_thaw_rebind_r1 import (
    OLD_CANDIDATE_SHA,
    NEW_CANDIDATE_SHA,
    PRESTATE_HASH,
    TARGET_HASH,
    TARGET_REVISION,
    THAW_ID,
    validate_target,
)


def _payload():
    return {
        "revision": TARGET_REVISION,
        "state_hash": TARGET_HASH,
        "source_main_sha": "6b3a37891fc2938736e8f371d29c3337682a4a22",
        "entries": {f"E{i}": {} for i in range(146)},
        "active_thaws": [
            {"thaw_id": f"OTHER-{i}", "status": "ACTIVE", "target_head_sha": "0" * 40, "files": {}}
            for i in range(4)
        ] + [
            {
                "thaw_id": THAW_ID,
                "status": "ACTIVE",
                "target_head_sha": NEW_CANDIDATE_SHA,
                "files": {
                    "nba_spread_page_v1.py": {
                        "from_blob": "b55cfb431dcbb867b5bfd5807efeca1dc66ebcb0",
                        "to_blob": "0ad62af70010051c3ac8f4477d63263a228eb76b",
                    }
                },
            }
        ],
    }


def test_rebind_identity_is_pinned():
    assert OLD_CANDIDATE_SHA == "dd1ecbbe24299b453aab8dea290061b8613d5e8b"
    assert NEW_CANDIDATE_SHA == "1a1445d3cfaa7e3074c73b91bc3d94ab814daac5"
    assert PRESTATE_HASH == "cd805a3acb3d6c1ab083a753bf943ac7f596950f8995675bc969597af3a09905"
    assert TARGET_HASH == "8fe7ae89228fcfc04e816212cffa3dfce8a4ca6a25357c8be17a0d04eda19a62"


def test_target_accepts_exact_new_candidate():
    validate_target(_payload(), require_full=True)


def test_target_rejects_old_candidate():
    bad = _payload()
    bad["active_thaws"][-1]["target_head_sha"] = OLD_CANDIDATE_SHA
    try:
        validate_target(bad, require_full=True)
    except RuntimeError as exc:
        assert "TARGET_THAW_IDENTITY" in str(exc)
    else:
        raise AssertionError("old candidate must fail closed")
