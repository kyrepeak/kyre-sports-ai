from __future__ import annotations

from devsystem.preflight_gate_compiler_v1 import compile_preflight, contract_self_test

HEAD = "a" * 40
LEDGER_PATH = "devsystem/task_ledgers/unit-preflight.json"
PY_PATH = "devsystem/unit_feature.py"
TEST_PATH = "tests/test_unit_feature.py"

LEDGER = {
    "version": 2,
    "task_id": "unit-preflight",
    "status": "DONE",
    "action_log": {
        "head_chain_hash": "0" * 64,
        "events": [],
        "consumed_receipts": [],
    },
}


def _run(**overrides):
    args = {
        "changed_paths": [PY_PATH, TEST_PATH, LEDGER_PATH],
        "task_ledgers": {LEDGER_PATH: LEDGER},
        "python_sources": {
            PY_PATH: "VALUE = 1\n",
            TEST_PATH: "def test_ok():\n    assert True\n",
        },
        "available_paths": [PY_PATH, TEST_PATH, LEDGER_PATH],
        "required_test_paths": [TEST_PATH],
        "expected_head_sha": HEAD,
        "observed_head_sha": HEAD,
        "scope_authorized": True,
    }
    args.update(overrides)
    return compile_preflight(**args)


def test_contract_self_test_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["clean_bundle_goes_to_ci"] is True
    assert result["terminal_proof_still_required"] is True


def test_clean_bundle_goes_to_ci():
    result = _run()
    assert result["status"] == "GREEN"
    assert result["decision"] == "GO_TO_CI"
    assert result["next_legal_action"] == "START_AUTHORITATIVE_CI"


def test_stale_head_fails_closed():
    result = _run(observed_head_sha="b" * 40)
    assert result["decision"] == "BLOCK_BEFORE_CI"
    assert any(item["code"] == "STALE_OR_INVALID_HEAD" for item in result["blockers"])


def test_bad_action_ledger_fails_before_ci():
    bad = {**LEDGER, "status": "OPEN"}
    result = _run(task_ledgers={LEDGER_PATH: bad})
    assert any(item["code"] == "ACTION_LEDGER_V2_INVALID" for item in result["blockers"])


def test_python_syntax_error_fails_before_ci():
    result = _run(python_sources={PY_PATH: "def bad(:\n pass\n", TEST_PATH: "def test_ok():\n assert True\n"})
    assert any(item["code"] == "PYTHON_SYNTAX_INVALID" for item in result["blockers"])


def test_required_test_must_exist():
    result = _run(available_paths=[PY_PATH, LEDGER_PATH])
    assert any(item["code"] == "REQUIRED_TEST_MISSING" for item in result["blockers"])


def test_required_permanent_marker_must_exist():
    result = _run(
        permanent_contract_text="only-other-marker",
        required_permanent_markers=["preflight_gate_compiler_v1.py"],
    )
    assert any(item["code"] == "PERMANENT_CONTRACT_MARKER_MISSING" for item in result["blockers"])


def test_malformed_workflow_fails_before_ci():
    workflow = ".github/workflows/bad.yml"
    result = _run(
        changed_paths=[PY_PATH, TEST_PATH, LEDGER_PATH, workflow],
        available_paths=[PY_PATH, TEST_PATH, LEDGER_PATH, workflow],
        workflow_texts={workflow: "name: Bad\njobs:\n  test: {}\n"},
    )
    assert any(item["code"] == "WORKFLOW_CONTRACT_INVALID" for item in result["blockers"])


def test_frozen_artifact_requires_thaw():
    result = _run(frozen_paths=[PY_PATH])
    assert any(item["code"] == "FROZEN_ARTIFACT_TOUCH_WITHOUT_THAW" for item in result["blockers"])

    thawed = _run(frozen_paths=[PY_PATH], thawed_paths=[PY_PATH])
    assert thawed["decision"] == "GO_TO_CI"


def test_scope_authorization_is_mandatory():
    result = _run(scope_authorized=False)
    assert any(item["code"] == "SCOPE_LEASE_NOT_AUTHORIZED" for item in result["blockers"])


def test_compiler_never_grants_mutation_authority():
    result = _run()
    assert result["protections"]["step_2a_still_required"] is True
    assert result["protections"]["scope_lease_still_required_for_mutation"] is True
    assert result["protections"]["mutation_authority_granted"] is False


def test_required_permanent_contract_path_must_exist():
    result = _run(required_permanent_paths=["devsystem/permanent_contract.py"])
    assert any(item["code"] == "PERMANENT_CONTRACT_PATH_MISSING" for item in result["blockers"])
