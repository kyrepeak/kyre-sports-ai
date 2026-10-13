import copy
import json
from pathlib import Path

import pytest

from devsystem.universal_sports_source_finalization_step1_contract_v1 import (
    certify_contract,
    load_contract,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "devsystem" / "contracts" / "universal-sports-source-finalization-v1-step1.json"
SPEC_PATH = ROOT / "docs" / "superpowers" / "specs" / "2026-10-12-universal-sports-source-finalization-v1-design.md"


def _load():
    return load_contract(CONTRACT_PATH)


def test_valid_contract_certifies_step1_architecture():
    result = certify_contract(_load(), SPEC_PATH.read_text())
    assert result["status"] == "GREEN"
    assert result["workstream"] == "universal-sports-source-finalization-v1"
    assert result["step"] == "1/8"
    assert result["routing_unit"] == "DATA_FIELD"
    assert result["page_wide_source_authority"] is False
    assert result["active_provider_semantics"] == "ACTUALLY_CONSULTED_ONLY"
    assert result["incompatible_metric_substitution"] is False
    assert result["minimum_quorum_early_stop"] is True
    assert result["render_dependency"] is False
    assert result["github_actions_fallback"] == 0
    assert result["legacy_registry_mutation"] is False
    assert result["freeze_token"] == "UNIVERSAL_SPORTS_SOURCE_FINALIZATION_V1_STEP1_ARCHITECTURE_CONTRACT_FROZEN"


@pytest.mark.parametrize(
    "field,value",
    [
        ("page_wide_source_authority", True),
        ("incompatible_metric_substitution", True),
        ("render_dependency", True),
        ("github_actions_fallback", 1),
        ("legacy_registry_mutation", True),
    ],
)
def test_contract_drift_fails_closed(field, value):
    contract = _load()
    contract[field] = value
    with pytest.raises(ValueError):
        certify_contract(contract, SPEC_PATH.read_text())


def test_approved_pool_and_active_providers_are_distinct():
    contract = _load()
    assert contract["provider_semantics"]["approved_pool_is_active_pool"] is False
    assert contract["provider_semantics"]["active_means_consulted"] is True


def test_raw_bet_count_cannot_fallback_to_percentage_metrics():
    contract = _load()
    forbidden = contract["semantic_compatibility"]["forbidden_substitutions"]["public_bet_count"]
    assert "public_bet_percentage" in forbidden
    assert "money_percentage" in forbidden


from devsystem.universal_sports_finalization_bootstrap_v1 import (
    build_freeze_record,
    build_manifest,
    canonical_hash,
    validate_freeze_record,
    validate_manifest_transition,
)

SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40
PROOF = "sha256:" + ("1" * 64)
TOKEN = "UNIVERSAL_SPORTS_SOURCE_FINALIZATION_V1_STEP1_ARCHITECTURE_CONTRACT_FROZEN"


def _record():
    return build_freeze_record(
        workstream="universal-sports-source-finalization-v1",
        freeze_token=TOKEN,
        merged_main_sha=SHA_A,
        candidate_sha=SHA_B,
        proof_digest=PROOF,
        artifacts={
            "devsystem/contracts/universal-sports-source-finalization-v1-step1.json": SHA_C,
            "devsystem/universal_sports_source_finalization_step1_contract_v1.py": SHA_A,
        },
    )


def test_freeze_record_is_deterministic_and_portable():
    first = _record()
    second = _record()
    assert first == second
    assert first["record_hash"] == second["record_hash"]
    assert first["render_dependency"] is False
    assert first["github_actions_fallback"] == 0
    assert first["legacy_registry_mutation"] is False
    assert validate_freeze_record(first) == first


def test_freeze_record_tamper_fails_closed():
    record = _record()
    record["artifacts"]["devsystem/universal_sports_source_finalization_step1_contract_v1.py"] = SHA_B
    with pytest.raises(ValueError):
        validate_freeze_record(record)


@pytest.mark.parametrize("field,value", [
    ("merged_main_sha", "bad"),
    ("candidate_sha", "bad"),
    ("proof_digest", "bad"),
])
def test_freeze_record_rejects_invalid_identity(field, value):
    kwargs = dict(
        workstream="universal-sports-source-finalization-v1",
        freeze_token=TOKEN,
        merged_main_sha=SHA_A,
        candidate_sha=SHA_B,
        proof_digest=PROOF,
        artifacts={"a.py": SHA_C},
    )
    kwargs[field] = value
    with pytest.raises(ValueError):
        build_freeze_record(**kwargs)


def test_genesis_manifest_is_revision_one():
    manifest = build_manifest(
        previous=None,
        freeze_token=TOKEN,
        record_path=f"devsystem/finalization_ledger_v2/records/{TOKEN}.json",
        record_blob_sha=SHA_C,
        merged_main_sha=SHA_A,
    )
    assert manifest["revision"] == 1
    assert manifest["previous_state_hash"] is None
    assert manifest["latest_freeze_token"] == TOKEN
    assert manifest["latest_record_blob_sha"] == SHA_C
    assert manifest["latest_merged_main_sha"] == SHA_A
    assert manifest["render_dependency"] is False
    assert manifest["legacy_registry_mutation"] is False
    assert validate_manifest_transition(None, manifest) == manifest


def test_manifest_transition_is_monotonic_and_chained():
    first = build_manifest(
        previous=None,
        freeze_token=TOKEN,
        record_path=f"devsystem/finalization_ledger_v2/records/{TOKEN}.json",
        record_blob_sha=SHA_C,
        merged_main_sha=SHA_A,
    )
    second = build_manifest(
        previous=first,
        freeze_token="NEXT_FREEZE",
        record_path="devsystem/finalization_ledger_v2/records/NEXT_FREEZE.json",
        record_blob_sha=SHA_B,
        merged_main_sha=SHA_C,
    )
    assert second["revision"] == 2
    assert second["previous_state_hash"] == first["state_hash"]
    assert validate_manifest_transition(first, second) == second


def test_manifest_stale_precondition_fails_closed():
    first = build_manifest(
        previous=None,
        freeze_token=TOKEN,
        record_path=f"devsystem/finalization_ledger_v2/records/{TOKEN}.json",
        record_blob_sha=SHA_C,
        merged_main_sha=SHA_A,
    )
    second = build_manifest(
        previous=first,
        freeze_token="NEXT_FREEZE",
        record_path="devsystem/finalization_ledger_v2/records/NEXT_FREEZE.json",
        record_blob_sha=SHA_B,
        merged_main_sha=SHA_C,
    )
    stale = copy.deepcopy(first)
    stale["state_hash"] = "0" * 64
    with pytest.raises(ValueError):
        validate_manifest_transition(stale, second)


def test_canonical_hash_is_stable_across_key_order():
    assert canonical_hash({"b": 2, "a": 1}) == canonical_hash({"a": 1, "b": 2})


def test_runless_metadata_contract_is_static_and_isolated():
    execution = json.loads((ROOT / "devsystem" / "execution_plans" / "universal-sports-source-finalization-v1-step1.json").read_text())
    proof = json.loads((ROOT / "devsystem" / "runless_proof_plans" / "universal-sports-source-finalization-v1-step1.json").read_text())
    ledger = json.loads((ROOT / "devsystem" / "task_ledgers" / "universal-sports-source-finalization-v1-step1.json").read_text())
    assert execution["workstream"] == "universal-sports-source-finalization-v1"
    assert execution["step"] == "1/8"
    assert execution["scope"]["product_runtime"] is False
    assert execution["scope"]["sports_model"] is False
    assert execution["scope"]["legacy_registry_mutation"] is False
    assert execution["github_actions_fallback"] == 0
    assert proof["task_id"] == "universal-sports-source-finalization-v1-step1"
    assert proof["workstream"] == "universal-sports-source-finalization-v1"
    assert proof["freeze_token"] == TOKEN
    assert proof["probes"] == []
    assert ["python", "-m", "pytest", "-q", "tests/test_devsystem_universal_sports_source_finalization_step1_v1.py"] in proof["commands"]
    assert proof["github_actions_fallback"] == 0
    assert ledger["status"] == "IMPLEMENTED_AWAITING_EXACT_HEAD_PROOF"
    assert ledger["render_dependency"] is False
    assert ledger["legacy_registry_mutation"] is False


def test_runless_metadata_artifacts_cover_step1_contract():
    proof = json.loads((ROOT / "devsystem" / "runless_proof_plans" / "universal-sports-source-finalization-v1-step1.json").read_text())
    required = {
        "devsystem/contracts/universal-sports-source-finalization-v1-step1.json",
        "devsystem/universal_sports_source_finalization_step1_contract_v1.py",
        "devsystem/universal_sports_finalization_bootstrap_v1.py",
        "tests/test_devsystem_universal_sports_source_finalization_step1_v1.py",
        "docs/superpowers/specs/2026-10-12-universal-sports-source-finalization-v1-design.md",
        "docs/superpowers/plans/2026-10-12-universal-sports-source-finalization-v1-step1.md",
        "devsystem/execution_plans/universal-sports-source-finalization-v1-step1.json",
        "devsystem/runless_proof_plans/universal-sports-source-finalization-v1-step1.json",
        "devsystem/task_ledgers/universal-sports-source-finalization-v1-step1.json",
    }
    assert required <= set(proof["artifacts"])
