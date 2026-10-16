from runless_v2.models import FailureClass
from runless_v2.sandbox_executor import (
    _MIN_BOOTSTRAP_PACKAGES,
    _classify_proof_command_failure,
)
from runless_v2.state_store import DurableStateStore


def test_runless_v2_bootstrap_includes_runtime_dependencies_needed_by_proof_plans():
    required = {"pandas", "numpy", "streamlit"}
    assert required.issubset(set(_MIN_BOOTSTRAP_PACKAGES))


def test_missing_module_is_proof_environment_infra_not_static_proof():
    failure_class, detail = _classify_proof_command_failure(
        "", "ModuleNotFoundError: No module named 'streamlit'\n"
    )
    assert failure_class is FailureClass.INFRA
    assert detail == "RUNLESS_V2_PROOF_ENVIRONMENT_DEPENDENCY_MISSING"


def test_missing_dependency_infra_release_does_not_record_failed_fingerprint():
    failure_class, detail = _classify_proof_command_failure(
        "", "ModuleNotFoundError: No module named 'streamlit'\n"
    )
    assert failure_class is FailureClass.INFRA

    class RecordingStore:
        def __init__(self):
            self.calls = []

        def record_failure_and_release(
            self, claim, *, failure_class, detail, record_fingerprint=True
        ):
            self.calls.append((claim, failure_class, detail, record_fingerprint))
            return "released"

    store = RecordingStore()
    claim = object()
    result = DurableStateStore.release_infra(store, claim, detail=detail)

    assert result == "released"
    assert store.calls == [
        (claim, FailureClass.INFRA, "RUNLESS_V2_PROOF_ENVIRONMENT_DEPENDENCY_MISSING", False)
    ]


def test_real_pytest_assertion_remains_static_proof():
    failure_class, detail = _classify_proof_command_failure(
        "FAILED tests/test_example.py::test_value - AssertionError: expected 2", ""
    )
    assert failure_class is FailureClass.STATIC_PROOF
    assert detail == "RUNLESS_V2_STATIC_PROOF_FAILED"
