"""KYRE GUARDIAN exact-head Runless proof for shared infrastructure readiness contract V1."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_BASE_PATH = Path(__file__).with_name("guardian_pytest_entrypoint_contract_proof_v1_base.py")
_spec = importlib.util.spec_from_file_location(
    "guardian_shared_infrastructure_readiness_contract_proof_v1_base_adapter",
    _BASE_PATH,
)
if not _spec or not _spec.loader:
    raise RuntimeError("GUARDIAN_SHARED_READINESS_BASE_LOAD_FAILED")
_base = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _base
_spec.loader.exec_module(_base)

_base.TASK_ID = "guardian-shared-infrastructure-readiness-contract-v1"
_base.WORKSTREAM = _base.TASK_ID
_base.PR_NUMBER = 1907
_base.BRANCH = "guardian-shared-infrastructure-readiness-contract-v1"
_base.EXPECTED_MAIN_SHA = "b4b953ca413eca787489a8fb577182a60e4622ec"
_base.PLAN_PATH = "devsystem/runless_proof_plans/guardian-shared-infrastructure-readiness-contract-v1.json"
_base.ALLOWED_CHANGED_PATHS = frozenset(
    {
        "AGENTS.md",
        "docs/superpowers/specs/2026-10-27-guardian-shared-infrastructure-readiness-contract-v1-design.md",
        "docs/superpowers/plans/2026-10-27-guardian-shared-infrastructure-readiness-contract-v1.md",
        "devsystem/guardian_shared_infrastructure_readiness_v1.json",
        "devsystem/guardian_shared_infrastructure_readiness_v1.py",
        "devsystem/guardian_shared_infrastructure_readiness_contract_v1.json",
        "devsystem/runless_proof_plans/guardian-shared-infrastructure-readiness-contract-v1.json",
        "runless_v2/guardian_shared_infrastructure_readiness_contract_proof_v1.py",
        "runless_v2/guardian_freeze_closeout_bootstrap_v1.py",
        "tests/test_guardian_shared_infrastructure_readiness_v1.py",
    }
)

prove_guardian_shared_infrastructure_readiness_contract = _base.prove_guardian_pytest_entrypoint_contract
ALLOWED_CHANGED_PATHS = _base.ALLOWED_CHANGED_PATHS
TASK_ID = _base.TASK_ID
WORKSTREAM = _base.WORKSTREAM
PR_NUMBER = _base.PR_NUMBER
BRANCH = _base.BRANCH
EXPECTED_MAIN_SHA = _base.EXPECTED_MAIN_SHA
PLAN_PATH = _base.PLAN_PATH
