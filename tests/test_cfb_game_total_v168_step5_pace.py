from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "tests" / "guardian_v168_step5_pace_legacy_contract.py"
APP = ROOT / "app.py"
ROUTER_V163 = ROOT / "streamlit_memory_lazy_router_v163.py"

_spec = importlib.util.spec_from_file_location("guardian_v168_step5_pace_legacy_contract", LEGACY)
assert _spec and _spec.loader
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)

# Re-export every frozen V168/V175/V176/V178/V182/V183/V185 test unchanged,
# except the one stale app-entrypoint assertion repaired below.
_STALE = "test_app_activates_v163_router_while_preserving_v162_delegate"
for _name in dir(_legacy):
    if _name.startswith("test_") and _name != _STALE:
        globals()[_name] = getattr(_legacy, _name)


def test_app_activates_v163_router_while_preserving_v162_delegate():
    source = APP.read_text(encoding="utf-8")
    router_v163 = ROUTER_V163.read_text(encoding="utf-8")
    assert "from devsystem.shared_runtime_lifecycle_v1 import run_shared_runtime_lifecycle" in source
    assert "run_shared_runtime_lifecycle(" in source
    assert "import streamlit_memory_lazy_router_v162 as prior" in router_v163
    assert "return prior.render_app()" in router_v163
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v162"' in router_v163
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in router_v163
    assert "MAY_MODIFY_PROJECTION = False" in router_v163
    assert "from streamlit_memory_lazy_router_v161 import record_bootstrap_import_ms, render_app" not in source
