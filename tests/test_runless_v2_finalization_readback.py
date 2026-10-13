import hashlib
import json

import pytest

from runless_v2.finalization_readback import validate_finalization_closeout

SHA = "a" * 40
MERGED = "b" * 40
BLOB = "c" * 40
PROOF = "sha256:" + "d" * 64
TOKEN = "STEP6-FROZEN"
WORKSTREAM = "universal-sports-source-finalization-v1"


def canonical_hash(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def record():
    value = {
        "version": "UNIVERSAL_SPORTS_FINALIZATION_BOOTSTRAP_V1",
        "workstream": WORKSTREAM,
        "freeze_token": TOKEN,
        "merged_main_sha": MERGED,
        "candidate_sha": SHA,
        "proof_digest": PROOF,
        "artifacts": {"artifact.py": BLOB},
        "render_dependency": False,
        "github_actions_fallback": 0,
        "legacy_registry_mutation": False,
    }
    value["record_hash"] = canonical_hash(value)
    return value


def previous_manifest():
    value = {
        "version": "UNIVERSAL_SPORTS_FINALIZATION_LEDGER_V2_MANIFEST",
        "revision": 5,
        "previous_state_hash": "0" * 64,
        "latest_freeze_token": "STEP5",
        "latest_record_path": "records/step5.json",
        "latest_record_blob_sha": "e" * 40,
        "latest_merged_main_sha": "f" * 40,
        "render_dependency": False,
        "github_actions_fallback": 0,
        "legacy_registry_mutation": False,
    }
    value["state_hash"] = canonical_hash(value)
    return value


def manifest(prior):
    value = {
        "version": "UNIVERSAL_SPORTS_FINALIZATION_LEDGER_V2_MANIFEST",
        "revision": 6,
        "previous_state_hash": prior["state_hash"],
        "latest_freeze_token": TOKEN,
        "latest_record_path": f"devsystem/finalization_ledger_v2/records/{TOKEN}.json",
        "latest_record_blob_sha": "1" * 40,
        "latest_merged_main_sha": MERGED,
        "render_dependency": False,
        "github_actions_fallback": 0,
        "legacy_registry_mutation": False,
    }
    value["state_hash"] = canonical_hash(value)
    return value


def validate(rec=None, man=None, prior=None, **overrides):
    rec = rec or record()
    prior = prior or previous_manifest()
    man = man or manifest(prior)
    expected = dict(
        expected_workstream=WORKSTREAM,
        expected_freeze_token=TOKEN,
        expected_candidate_sha=SHA,
        expected_proof_digest=PROOF,
        expected_merged_main_sha=MERGED,
        previous_manifest=prior,
    )
    expected.update(overrides)
    return validate_finalization_closeout(rec, man, **expected)


def test_wrong_freeze_token_fails_closed():
    with pytest.raises(ValueError, match="RUNLESS_V2_FINALIZATION_FREEZE_TOKEN_MISMATCH"):
        validate(expected_freeze_token="WRONG")


def test_record_hash_tampering_fails_closed():
    rec = record()
    rec["candidate_sha"] = "9" * 40
    with pytest.raises(ValueError, match="RUNLESS_V2_FINALIZATION_RECORD_HASH_MISMATCH"):
        validate(rec=rec)


def test_stale_manifest_chain_fails_closed():
    prior = previous_manifest()
    man = manifest(prior)
    man["previous_state_hash"] = "9" * 64
    raw = dict(man)
    raw.pop("state_hash")
    man["state_hash"] = canonical_hash(raw)
    with pytest.raises(ValueError, match="RUNLESS_V2_FINALIZATION_MANIFEST_STALE_PRECONDITION"):
        validate(man=man, prior=prior)


def test_manifest_self_hash_tampering_fails_closed():
    prior = previous_manifest()
    man = manifest(prior)
    man["latest_merged_main_sha"] = "9" * 40
    with pytest.raises(ValueError, match="RUNLESS_V2_FINALIZATION_MANIFEST_HASH_MISMATCH"):
        validate(man=man, prior=prior)


def test_successful_closeout_binds_all_exact_evidence():
    result = validate()
    assert result["status"] == "GREEN"
    assert result["candidate_sha"] == SHA
    assert result["merged_main_sha"] == MERGED
    assert result["proof_digest"] == PROOF
    assert result["freeze_token"] == TOKEN
    assert result["manifest_revision"] == 6
