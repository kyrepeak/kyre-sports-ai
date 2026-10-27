"""KYRE GUARDIAN exact-head Runless proof for source-of-truth + configuration parity V1."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_BASE_PATH = Path(__file__).with_name("guardian_pytest_entrypoint_contract_proof_v1_base.py")
_spec = importlib.util.spec_from_file_location(
    "guardian_source_of_truth_configuration_parity_proof_v1_base_adapter",
    _BASE_PATH,
)
if not _spec or not _spec.loader:
    raise RuntimeError("GUARDIAN_SOURCE_PARITY_BASE_LOAD_FAILED")
_base = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _base
_spec.loader.exec_module(_base)

_base.TASK_ID = "guardian-source-of-truth-configuration-parity-v1"
_base.WORKSTREAM = _base.TASK_ID
_base.PR_NUMBER = 1906
_base.BRANCH = "guardian-source-parity-archive-v1"
_base.EXPECTED_MAIN_SHA = "2b6c6464d539515c73838929cbe265a3b9be9b11"
_base.PLAN_PATH = "devsystem/runless_proof_plans/guardian-source-of-truth-configuration-parity-v1.json"
_base.ALLOWED_CHANGED_PATHS = frozenset(
    {
        "devsystem/guardian_source_of_truth_configuration_parity_v1.json",
        "devsystem/runless_proof_plans/guardian-source-of-truth-configuration-parity-v1.json",
        "runless_v2/guardian_freeze_closeout_bootstrap_v1.py",
        "runless_v2/guardian_source_of_truth_configuration_parity_proof_v1.py",
        "supabase/source_parity_ledger/archive-v1/chunk-01.b64",
        "supabase/source_parity_ledger/archive-v1/chunk-02.b64",
        "supabase/source_parity_ledger/archive-v1/chunk-03.b64",
        "supabase/source_parity_ledger/archive-v1/chunk-04.b64",
        "supabase/source_parity_ledger/archive-v1/chunk-05.b64",
        "supabase/source_parity_ledger/archive-v1/chunk-06.b64",
        "supabase/source_parity_ledger/archive-v1/chunk-07.b64",
        "supabase/source_parity_ledger/archive-v1/chunk-08.b64",
        "supabase/source_parity_ledger/archive-v1/index.json",
        "supabase/source_parity_ledger/archive-v1/supplemental-39.json",
        "tests/test_guardian_source_of_truth_configuration_parity_v1.py",
        "tests/test_guardian_source_parity_archive_v1.py",
    }
)

prove_guardian_source_of_truth_configuration_parity = _base.prove_guardian_pytest_entrypoint_contract
ALLOWED_CHANGED_PATHS = _base.ALLOWED_CHANGED_PATHS
TASK_ID = _base.TASK_ID
WORKSTREAM = _base.WORKSTREAM
PR_NUMBER = _base.PR_NUMBER
BRANCH = _base.BRANCH
EXPECTED_MAIN_SHA = _base.EXPECTED_MAIN_SHA
PLAN_PATH = _base.PLAN_PATH
