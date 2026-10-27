"""KYRE GUARDIAN exact-head Runless proof for infrastructure + automation cleanup V1."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_BASE_PATH = Path(__file__).with_name("guardian_pytest_entrypoint_contract_proof_v1_base.py")
_spec = importlib.util.spec_from_file_location(
    "guardian_infrastructure_automation_cleanup_proof_v1_base_adapter",
    _BASE_PATH,
)
if not _spec or not _spec.loader:
    raise RuntimeError("GUARDIAN_INFRASTRUCTURE_AUTOMATION_CLEANUP_BASE_LOAD_FAILED")
_base = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _base
_spec.loader.exec_module(_base)

_base.TASK_ID = "guardian-infrastructure-automation-cleanup-v1"
_base.WORKSTREAM = _base.TASK_ID
_base.PR_NUMBER = 1902
_base.BRANCH = "guardian-infrastructure-automation-cleanup-v1"
_base.EXPECTED_MAIN_SHA = "c9efdc4179235e11e06162a0d7b684134d1c03ee"
_base.PLAN_PATH = "devsystem/runless_proof_plans/guardian-infrastructure-automation-cleanup-v1.json"
_base.ALLOWED_CHANGED_PATHS = frozenset(
    {
        ".github/workflows/mlb-step18b-production-observability-cert.yml",
        ".github/workflows/mlb-step6b-production-canary-monitor.yml",
        ".github/workflows/mlb-step6d-controlled-25-production-cert.yml",
        ".github/workflows/mlb-step6e-25pct-stability-window.yml",
        "docs/superpowers/plans/2026-10-27-guardian-infrastructure-automation-cleanup-v1.md",
        "docs/superpowers/specs/2026-10-27-guardian-infrastructure-automation-cleanup-v1.md",
        "tests/test_guardian_infrastructure_automation_cleanup_v1.py",
        "vercel_finalizer/app.py",
        "vercel_finalizer/test_health_truthfulness.py",
        "devsystem/runless_proof_plans/guardian-infrastructure-automation-cleanup-v1.json",
        "runless_v2/guardian_freeze_closeout_bootstrap_v1.py",
        "runless_v2/guardian_infrastructure_automation_cleanup_proof_v1.py",
    }
)

prove_guardian_infrastructure_automation_cleanup = _base.prove_guardian_pytest_entrypoint_contract
ALLOWED_CHANGED_PATHS = _base.ALLOWED_CHANGED_PATHS
TASK_ID = _base.TASK_ID
WORKSTREAM = _base.WORKSTREAM
PR_NUMBER = _base.PR_NUMBER
BRANCH = _base.BRANCH
EXPECTED_MAIN_SHA = _base.EXPECTED_MAIN_SHA
