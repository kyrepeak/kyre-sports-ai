"""KYRE GUARDIAN exact-head proof wrapper for the pytest entrypoint closeout."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_BASE_PATH = Path(__file__).with_name("guardian_pytest_entrypoint_contract_proof_v1_base.py")
_spec = importlib.util.spec_from_file_location(
    "guardian_pytest_entrypoint_contract_proof_v1_base",
    _BASE_PATH,
)
if not _spec or not _spec.loader:
    raise RuntimeError("GUARDIAN_PYTEST_ENTRYPOINT_BASE_LOAD_FAILED")
_base = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _base
_spec.loader.exec_module(_base)

_base.ALLOWED_CHANGED_PATHS = frozenset(
    {
        ".github/workflows/cfb-game-total-v150-browser.yml",
        ".github/workflows/cfb-game-total-v152-activation.yml",
        "devsystem/guardian_cfb_game_total_terminal_browser_qa_v1.py",
        "devsystem/runless_proof_plans/guardian-pytest-entrypoint-contract-v1.json",
        "runless_v2/guardian_freeze_closeout_bootstrap_v1.py",
        "runless_v2/guardian_pytest_entrypoint_contract_proof_v1.py",
        "runless_v2/guardian_pytest_entrypoint_contract_proof_v1_base.py",
        "tests/conftest.py",
        "tests/test_guardian_cfb_game_total_terminal_browser_qa_v1.py",
        "tests/test_guardian_pytest_entrypoint_contract_proof_v1.py",
    }
)

for _name in dir(_base):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_base, _name)
ALLOWED_CHANGED_PATHS = _base.ALLOWED_CHANGED_PATHS
