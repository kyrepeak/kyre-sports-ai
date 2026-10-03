import json

import pytest

from devsystem.descendant_thaw_awareness_v1 import (
    _sample_registry,
    evaluate_descendant_authority,
)
from devsystem.frozen_artifact_registry_v1 import _hash, _payload_without_hash
from devsystem.registry_wait_resume_v1 import (
    RegistryWaitResumeFailure,
    classify_from_descendant_result,
    resume_once_from_descendant_result,
    self_test,
)


def _wait_case():
    registry = _sample_registry()
    actual = {"shared.py": "b" * 40, "keep.py": "c" * 40}
    result = evaluate_descendant_authority(
        registry,
        actual,
        candidate_head_sha="4" * 40,
        current_main_sha="3" * 40,
        main_descends_from_targets={"2" * 40: True},
        candidate_descends_from_main=True,
    )
    return registry, actual, classify_from_descendant_result(registry, result)


def _aligned_after_forward_port(registry, actual):
    advanced = json.loads(json.dumps(registry))
    advanced["revision"] += 1
    advanced["source_main_sha"] = "3" * 40
    advanced["entries"]["STEP_A"]["artifacts"]["shared.py"] = "b" * 40
    advanced["active_thaws"] = []
    advanced["state_hash"] = _hash(_payload_without_hash(advanced))
    result = evaluate_descendant_authority(
        advanced,
        actual,
        candidate_head_sha="4" * 40,
        current_main_sha="3" * 40,
        main_descends_from_targets={},
        candidate_descends_from_main=True,
    )
    return advanced, result


def test_self_test_green():
    result = self_test()
    assert result["status"] == "GREEN"
    assert result["legitimate_inherited_thaw_waits"] is True
    assert result["wait_is_not_hard_failure"] is True
    assert result["unchanged_registry_does_not_rerun_proof"] is True
    assert result["registry_hash_change_allows_one_resume"] is True
    assert result["one_resume_allows_frozen_verification"] is True
    assert result["second_resume_blocked"] is True
    assert result["blind_retry_allowed"] is False
    assert result["network_calls"] is False
    assert result["auto_mutate"] is False
    assert result["product_runtime_mutation"] is False
    assert result["mutation_authority_granted"] is False


def test_inherited_thaw_is_wait_not_failure():
    registry, _, wait = _wait_case()
    assert wait["status"] == "WAIT"
    assert wait["decision"] == "WAIT_REGISTRY_RECONCILIATION"
    assert wait["hard_failure"] is False
    assert wait["allow_frozen_verification"] is False
    assert wait["registry_state_hash"] == registry["state_hash"]
    assert wait["resume_count"] == 0
    assert wait["max_resumes"] == 1


def test_unchanged_registry_does_not_consume_resume():
    registry, actual, wait = _wait_case()
    advanced, result = _aligned_after_forward_port(registry, actual)
    same_hash_registry = json.loads(json.dumps(advanced))
    same_hash_registry["state_hash"] = wait["registry_state_hash"]
    pending = resume_once_from_descendant_result(wait, same_hash_registry, result)
    assert pending["status"] == "WAIT"
    assert pending["decision"] == "REGISTRY_STATE_UNCHANGED"
    assert pending["resume_count"] == 0
    assert pending["retry_allowed_now"] is False


def test_state_hash_change_consumes_exactly_one_resume():
    registry, actual, wait = _wait_case()
    advanced, result = _aligned_after_forward_port(registry, actual)
    resumed = resume_once_from_descendant_result(wait, advanced, result)
    assert resumed["status"] == "GREEN"
    assert resumed["decision"] == "RESUMED_ONCE_REGISTRY_READY"
    assert resumed["resume_count"] == 1
    assert resumed["resume_allowed"] is False
    assert resumed["retry_allowed_now"] is True
    assert resumed["allow_frozen_verification"] is True


def test_second_resume_is_rejected():
    registry, actual, wait = _wait_case()
    advanced, result = _aligned_after_forward_port(registry, actual)
    used = dict(wait)
    used["resume_count"] = 1
    with pytest.raises(RegistryWaitResumeFailure, match="already consumed"):
        resume_once_from_descendant_result(used, advanced, result)


def test_unauthorized_drift_is_hard_failure():
    registry = _sample_registry()
    result = evaluate_descendant_authority(
        registry,
        {"shared.py": "d" * 40, "keep.py": "c" * 40},
        candidate_head_sha="4" * 40,
        current_main_sha="3" * 40,
        main_descends_from_targets={"2" * 40: True},
        candidate_descends_from_main=True,
    )
    gate = classify_from_descendant_result(registry, result)
    assert gate["status"] == "BLOCKED"
    assert gate["hard_failure"] is True
    assert gate["resume_allowed"] is False
