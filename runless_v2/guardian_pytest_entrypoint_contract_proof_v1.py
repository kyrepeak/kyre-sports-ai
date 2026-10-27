"""KYRE GUARDIAN exact-head proof wrapper for lifecycle-neutral certification closeout."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_BASE_PATH = Path(__file__).with_name("guardian_pytest_entrypoint_contract_proof_v1_base.py")
_spec = importlib.util.spec_from_file_location("guardian_pytest_entrypoint_contract_proof_v1_base", _BASE_PATH)
if not _spec or not _spec.loader:
    raise RuntimeError("GUARDIAN_PYTEST_ENTRYPOINT_BASE_LOAD_FAILED")
_base = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _base
_spec.loader.exec_module(_base)

_EXTRA_ALLOWED = frozenset(
    {
        "runless_v2/guardian_pytest_entrypoint_contract_proof_v1_base.py",
        "tests/guardian_v168_step5_pace_legacy_contract.py",
        "tests/test_cfb_game_total_v162_cache_boundary.py",
        "tests/test_cfb_game_total_v163_game_selector.py",
        "tests/test_cfb_game_total_v168_step5_pace.py",
        "tests/test_cfb_game_total_v184_step6_scoring.py",
    }
)
_base.ALLOWED_CHANGED_PATHS = frozenset(_base.ALLOWED_CHANGED_PATHS | _EXTRA_ALLOWED)

for _name in dir(_base):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_base, _name)
ALLOWED_CHANGED_PATHS = _base.ALLOWED_CHANGED_PATHS
