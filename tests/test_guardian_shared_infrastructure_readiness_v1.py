from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from devsystem.guardian_shared_infrastructure_readiness_v1 import (
    AUTO_MUTATE,
    NETWORK_CALLS,
    ReadinessContractError,
    load_readiness,
    validate_baseline,
)

ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = ROOT / "devsystem" / "guardian_shared_infrastructure_readiness_v1.json"
PARITY_PATH = ROOT / "devsystem" / "guardian_source_of_truth_configuration_parity_v1.json"
AGENTS_PATH = ROOT / "AGENTS.md"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_api2_and_monster_receive_same_shared_facts_without_borrowed_authority() -> None:
    api2 = load_readiness("API2", repo_root=ROOT)
    monster = load_readiness("MONSTER", repo_root=ROOT)

    assert api2["status"] == "GREEN"
    assert monster["status"] == "GREEN"
    assert api2["consumer_system"] == "API2"
    assert monster["consumer_system"] == "MONSTER"
    assert api2["shared_infrastructure"] == monster["shared_infrastructure"]
    assert api2["baseline_digest"] == monster["baseline_digest"]
    assert api2["authority_policy"] == "CONTEXT_ONLY_NOT_EXECUTION_EVIDENCE"
    assert monster["authority_policy"] == "CONTEXT_ONLY_NOT_EXECUTION_EVIDENCE"
    assert api2["may_authorize_consumer_execution"] is False
    assert monster["may_authorize_consumer_execution"] is False


def test_unknown_consumer_fails_closed() -> None:
    with pytest.raises(ReadinessContractError, match="consumer"):
        load_readiness("GUARDIAN", repo_root=ROOT)


def test_forbidden_execution_authority_fields_fail_validation() -> None:
    payload = _load(BASELINE_PATH)
    for forbidden in (
        "branch",
        "pr",
        "lease",
        "lock",
        "checkpoint",
        "receipt",
        "proof_artifact",
        "execution_state",
        "failure_state",
        "recovery_state",
        "green_frozen",
        "percentage",
        "frozen_registry",
    ):
        candidate = copy.deepcopy(payload)
        candidate[forbidden] = "foreign-system-state"
        with pytest.raises(ReadinessContractError, match="forbidden"):
            validate_baseline(candidate)


def test_baseline_matches_guardian_source_parity_manifest() -> None:
    baseline = _load(BASELINE_PATH)
    parity = _load(PARITY_PATH)
    shared = baseline["shared_infrastructure"]

    assert shared["github"]["repository"] == parity["authority"]["github_repo"]
    assert shared["supabase"]["migration_count"] == parity["supabase"]["migration_count"]
    assert shared["vercel"]["production_projects"] == parity["vercel"]["production_projects"]
    assert shared["vercel"]["stale_preview_env_count"] == parity["vercel"]["stale_preview_env_count"]
    assert shared["supabase"]["actionable_security_findings"] == parity["supabase"]["security_actionable_findings"]


def test_reader_is_dependency_light_and_read_only() -> None:
    assert NETWORK_CALLS is False
    assert AUTO_MUTATE is False


def test_baseline_declares_independence_and_refresh_semantics() -> None:
    baseline = validate_baseline(_load(BASELINE_PATH))
    policy = baseline["consumer_policy"]
    freshness = baseline["freshness"]

    assert baseline["contract"] == "GUARDIAN_SHARED_INFRASTRUCTURE_READINESS_CONTRACT_V1"
    assert baseline["status"] == "GREEN"
    assert baseline["consumer_systems"] == ["API2", "MONSTER"]
    assert policy["authority_policy"] == "CONTEXT_ONLY_NOT_EXECUTION_EVIDENCE"
    assert "execution_authorization" in policy["forbidden_uses"]
    assert "green_frozen_authority" in policy["forbidden_uses"]
    assert freshness["scope"] == "SHARED_INFRASTRUCTURE_REVISION"
    assert freshness["page_only_merge_invalidates_baseline"] is False


def test_repository_entry_requires_readiness_preflight_without_borrowed_authority() -> None:
    text = AGENTS_PATH.read_text(encoding="utf-8")
    assert "GUARDIAN_SHARED_INFRASTRUCTURE_READINESS_CONTRACT_V1" in text
    assert "load_readiness(\"API2\")" in text
    assert "load_readiness(\"MONSTER\")" in text
    assert "CONTEXT_ONLY_NOT_EXECUTION_EVIDENCE" in text
    assert "must not" in text.lower()
    assert "GREEN/FROZEN" in text
