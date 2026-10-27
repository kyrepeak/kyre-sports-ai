"""KYRE GUARDIAN exact-head Runless proof for security + configuration hardening V1."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_BASE_PATH = Path(__file__).with_name("guardian_pytest_entrypoint_contract_proof_v1_base.py")
_spec = importlib.util.spec_from_file_location(
    "guardian_security_configuration_hardening_proof_v1_base_adapter",
    _BASE_PATH,
)
if not _spec or not _spec.loader:
    raise RuntimeError("GUARDIAN_SECURITY_CONFIGURATION_HARDENING_BASE_LOAD_FAILED")
_base = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _base
_spec.loader.exec_module(_base)

_base.TASK_ID = "guardian-security-configuration-hardening-v1"
_base.WORKSTREAM = _base.TASK_ID
_base.PR_NUMBER = 1903
_base.BRANCH = "guardian-security-configuration-hardening-v1"
_base.EXPECTED_MAIN_SHA = "31f94eae6e007a61d01397e6d868df3a6a3bd1e2"
_base.PLAN_PATH = "devsystem/runless_proof_plans/guardian-security-configuration-hardening-v1.json"
_base.ALLOWED_CHANGED_PATHS = frozenset(
    {
        "devsystem/runless_proof_plans/guardian-finalizer-baseline-v1.json",
        "devsystem/runless_proof_plans/guardian-security-configuration-hardening-v1.json",
        "docs/superpowers/plans/2026-10-27-guardian-security-configuration-hardening-v1.md",
        "docs/superpowers/specs/2026-10-27-guardian-security-configuration-hardening-v1.md",
        "runless_v2/guardian_freeze_closeout_bootstrap_v1.py",
        "runless_v2/guardian_security_configuration_hardening_proof_v1.py",
        "supabase/migrations/20261027_guardian_security_configuration_hardening_v1.sql",
        "tests/test_guardian_security_configuration_hardening_v1.py",
    }
)

prove_guardian_security_configuration_hardening = _base.prove_guardian_pytest_entrypoint_contract
ALLOWED_CHANGED_PATHS = _base.ALLOWED_CHANGED_PATHS
TASK_ID = _base.TASK_ID
WORKSTREAM = _base.WORKSTREAM
PR_NUMBER = _base.PR_NUMBER
BRANCH = _base.BRANCH
EXPECTED_MAIN_SHA = _base.EXPECTED_MAIN_SHA
