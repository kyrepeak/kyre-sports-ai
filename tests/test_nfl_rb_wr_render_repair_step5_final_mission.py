from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path("devsystem/nfl_rb_wr_render_repair_step5_final_mission_v1.py")


def _load_module():
    assert MODULE_PATH.exists(), "Step 5 final-mission cert module is missing"
    spec = importlib.util.spec_from_file_location("step5_final_mission", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_step5_contract_is_final_verification_only():
    mod = _load_module()
    assert mod.MISSION_STEP == "5/5"
    assert mod.WORKSTREAM == "nfl-rb-wr-render-repair-v1"
    assert mod.EXPECTED_MAIN_SHA == "76dde02ccd468447422710051ce2cb145aff2ebe"
    assert mod.EXPECTED_REGISTRY_REVISION == 210
    assert mod.EXPECTED_REGISTRY_HASH == "9d11310bc96136b1d5e70e7b85c42ba3b62f4c0226075d9c711bbbcb001a1b3b"
    assert mod.AUTO_MUTATE is False
    assert mod.MAY_MODIFY_PRODUCT_RUNTIME is False
    assert mod.GITHUB_ACTIONS_FALLBACK is False


def test_step5_requires_all_four_prior_freezes():
    mod = _load_module()
    assert mod.REQUIRED_FREEZE_TOKENS == (
        "NFL_RB_WR_RENDER_REPAIR_V1_STEP1_ROOT_CAUSE_FROZEN",
        "NFL_RB_WR_RENDER_REPAIR_V1_STEP2_PRESENTATION_TRANSPORT_FROZEN",
        "NFL_RB_WR_RENDER_REPAIR_V1_STEP3_DATA_BINDING_FROZEN",
        "NFL_RB_WR_RENDER_REPAIR_V1_STEP4_MOBILE_ROUTE_FROZEN",
    )


def test_registry_contract_rejects_missing_prior_freeze():
    mod = _load_module()
    payload = {
        "revision": mod.EXPECTED_REGISTRY_REVISION,
        "state_hash": mod.EXPECTED_REGISTRY_HASH,
        "entries": {
            token: {"status": "FROZEN"}
            for token in mod.REQUIRED_FREEZE_TOKENS[:-1]
        },
    }
    try:
        mod.verify_registry_contract(payload)
    except mod.FinalMissionFailure as exc:
        assert "MISSING_FREEZE" in str(exc)
    else:
        raise AssertionError("missing freeze token must fail closed")


def test_registry_contract_accepts_exact_prior_freezes():
    mod = _load_module()
    payload = {
        "revision": mod.EXPECTED_REGISTRY_REVISION,
        "state_hash": mod.EXPECTED_REGISTRY_HASH,
        "entries": {
            token: {"status": "FROZEN"}
            for token in mod.REQUIRED_FREEZE_TOKENS
        },
    }
    result = mod.verify_registry_contract(payload)
    assert result["status"] == "GREEN"
    assert result["freeze_count"] == 4


def test_blob_contract_detects_tamper_and_accepts_exact_bytes(tmp_path):
    mod = _load_module()
    payload = b"final mission witness\n"
    path = tmp_path / "witness.txt"
    path.write_bytes(payload)
    expected = mod.git_blob_sha(payload)
    assert mod.verify_blob(path, expected) == expected

    path.write_bytes(b"tampered\n")
    try:
        mod.verify_blob(path, expected)
    except mod.FinalMissionFailure as exc:
        assert "BLOB_DRIFT" in str(exc)
    else:
        raise AssertionError("tampered artifact must fail closed")


def test_final_artifact_contract_pins_key_step2_step3_step4_blobs():
    mod = _load_module()
    assert mod.REQUIRED_ARTIFACTS["nfl_rushing_yards_hub_v4.py"] == "5a6e10f5efe5ac27df7c9691d289ae5698e8e3cf"
    assert mod.REQUIRED_ARTIFACTS["nfl_receiving_yards_hub_v13.py"] == "202d5852414197170c910c96bae2fefa41fcb398"
    assert mod.REQUIRED_ARTIFACTS["devsystem/nfl_rb_wr_render_repair_step3_data_binding_v1.py"] == "916df46771ff75fba4a0edc6f90468a45e5cea49"
    assert mod.REQUIRED_ARTIFACTS["devsystem/nfl_rb_wr_render_repair_step4_mobile_route_v1.py"] == "ba25ac2bd8725677f6646e32b8ddfaa5c59d20c7"
    assert mod.REQUIRED_ARTIFACTS["tests/test_nfl_rb_wr_render_repair_step4_mobile_route.py"] == "9fc021b1e55d5cc456b15ad7eb2dac4c9104a4ef"


def test_step5_reuses_frozen_step4_public_proof_instead_of_live_market_replay():
    mod = _load_module()
    assert mod.STEP4_PUBLIC_PROOF_REUSED is True
    assert mod.STEP4_PUBLIC_PROOF_ID == "nfl-rb-wr-render-repair-step4-mobile-route-f503fcc4f1ead82e-5025754ac04ac692"
    assert mod.STEP4_PUBLIC_RECEIPT_DIGEST == "01aa378412eeecece65d5e9f44fd9f914e96ecc9869e42d6d8e3db4ed19da2a5"
