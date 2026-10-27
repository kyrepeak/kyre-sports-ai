"""KYRE GUARDIAN exact-head Runless proof for Finalizer authority capability V1."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_BASE_PATH = Path(__file__).with_name("guardian_pytest_entrypoint_contract_proof_v1_base.py")
_spec = importlib.util.spec_from_file_location(
    "guardian_finalizer_authority_bridge_proof_v1_base_adapter",
    _BASE_PATH,
)
if not _spec or not _spec.loader:
    raise RuntimeError("GUARDIAN_FINALIZER_AUTHORITY_BRIDGE_BASE_LOAD_FAILED")
_base = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _base
_spec.loader.exec_module(_base)

_base.TASK_ID = "guardian-finalizer-authority-bridge-v1"
_base.WORKSTREAM = _base.TASK_ID
_base.PR_NUMBER = 1904
_base.BRANCH = "guardian-finalizer-authority-bridge-v1"
_base.EXPECTED_MAIN_SHA = "e4e42fb0338c55c16fc4aa5fd08aeb181e142e03"
_base.PLAN_PATH = "devsystem/runless_proof_plans/guardian-finalizer-authority-bridge-v1.json"
_base.ALLOWED_CHANGED_PATHS = frozenset(
    {
        "devsystem/runless_proof_plans/guardian-finalizer-authority-bridge-v1.json",
        "runless_v2/guardian_finalizer_authority_bridge_proof_v1.py",
        "runless_v2/guardian_freeze_closeout_bootstrap_v1.py",
        "supabase/functions/guardian-finalizer-authority-bridge-v1/index.ts",
        "tests/test_guardian_finalizer_authority_bridge_v1.py",
        "vercel_finalizer/authority_bridge.py",
        "vercel_finalizer/bridge_entrypoint.py",
        "vercel_finalizer/bridge_runtime.py",
        "vercel_finalizer/pyproject.toml",
        "vercel_finalizer/test_guardian_authority_bridge_v1.py",
    }
)

prove_guardian_finalizer_authority_bridge = _base.prove_guardian_pytest_entrypoint_contract
ALLOWED_CHANGED_PATHS = _base.ALLOWED_CHANGED_PATHS
TASK_ID = _base.TASK_ID
WORKSTREAM = _base.WORKSTREAM
PR_NUMBER = _base.PR_NUMBER
BRANCH = _base.BRANCH
EXPECTED_MAIN_SHA = _base.EXPECTED_MAIN_SHA
