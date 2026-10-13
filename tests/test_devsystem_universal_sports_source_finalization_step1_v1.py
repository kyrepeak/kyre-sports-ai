import copy
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
