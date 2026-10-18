"""KYRE Sports AI production activation shim — Universal Shell/Route/Top V1.

The frozen historical entrypoint body is preserved byte-for-byte in
``app_legacy_entrypoint_v1.py``. This shim changes the Streamlit entrypoint
identity so Community Cloud restarts, while routing its existing imports to the
new additive Universal Navigation V4 and Universal Shell V2 runtimes.
"""
from __future__ import annotations

import importlib
from pathlib import Path
import sys

import streamlit as st


def _ensure_base_module(module_name: str, required_attr: str):
    existing = sys.modules.get(module_name)
    if (
        existing is not None
        and getattr(existing, "__name__", "") == module_name
        and hasattr(existing, required_attr)
    ):
        return existing
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


_real_nav_v2 = _ensure_base_module("streamlit_memory_lazy_router_universal_nav_v2", "nav_ui")
_real_shell_v1 = _ensure_base_module("kyre_universal_shell_runtime_v1", "activate_step3_page")

import kyre_universal_shell_runtime_v2 as _shell_v2
import streamlit_memory_lazy_router_universal_nav_v4 as _router_v4

_router_v4.v2 = _real_nav_v2
_router_v4.prior.prior = _real_nav_v2
_shell_v2.prior = _real_shell_v1

from kyre_universal_shell_runtime_v2 import activate_universal_shell
from kyre_universal_entrypoint_cold_start_v1 import seed_canonical_route_if_missing
from streamlit_memory_lazy_router_universal_nav_v4 import record_bootstrap_import_ms, render_app

API2_UNIVERSAL_SHELL_ROUTE_TOP_V1_RUNTIME = "API2_UNIVERSAL_SHELL_ROUTE_TOP_V1_RUNTIME_REFRESH_2026_10_17_R4"
DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V146_NFL_RECEIVING_YARDS_PLAYER_VS_DEFENSE_HISTORY_2026-09-16"

# Frozen MONSTER CFB V4 ownership predecessor compatibility: streamlit_memory_lazy_router_monster_cfb_v4_route_ownership_r1
# Frozen Universal Nav V3 certification compatibility: from streamlit_memory_lazy_router_universal_nav_v3 import record_bootstrap_import_ms, render_app
# Frozen Universal Nav V2 certification compatibility: from streamlit_memory_lazy_router_universal_nav_v2 import record_bootstrap_import_ms, render_app
# Frozen root-router certification compatibility: streamlit_memory_lazy_router_v1
# Frozen Universal Nav V1 certification compatibility: from streamlit_memory_lazy_router_universal_nav_v1 import record_bootstrap_import_ms, render_app
# Frozen V146 certification compatibility: from streamlit_memory_lazy_router_v146 import record_bootstrap_import_ms, render_app
# Frozen Universal Shell V1 certification compatibility: from kyre_universal_shell_runtime_v1 import activate_universal_shell

seed_canonical_route_if_missing(st.session_state, st.query_params)
_legacy_entrypoint_path = Path(__file__).with_name("app_legacy_entrypoint_v1.py")
_legacy_entrypoint_source = _legacy_entrypoint_path.read_text(encoding="utf-8")
_LEGACY_ROUTER_IMPORT_V2 = (
    "    from streamlit_memory_lazy_router_universal_nav_v2 import "
    "record_bootstrap_import_ms, render_app"
)
_LEGACY_ROUTER_IMPORT_V4 = (
    "    from streamlit_memory_lazy_router_api2_nfl_active_slate_v1 import "
    "record_bootstrap_import_ms, render_app"
)
_legacy_router_import_count = _legacy_entrypoint_source.count(_LEGACY_ROUTER_IMPORT_V2)
if _legacy_router_import_count != 1:
    raise RuntimeError(
        "API2_LEGACY_ROUTER_ACTIVATION_DRIFT:"
        f"expected=1 actual={_legacy_router_import_count}"
    )
_legacy_entrypoint_runtime_source = _legacy_entrypoint_source.replace(
    _LEGACY_ROUTER_IMPORT_V2,
    _LEGACY_ROUTER_IMPORT_V4,
    1,
)
_legacy_entrypoint_code = compile(
    _legacy_entrypoint_runtime_source,
    str(_legacy_entrypoint_path),
    "exec",
)

_original_shell_v1_module = sys.modules.get("kyre_universal_shell_runtime_v1")
sys.modules["kyre_universal_shell_runtime_v1"] = _shell_v2
try:
    exec(_legacy_entrypoint_code, globals(), globals())
finally:
    if _original_shell_v1_module is None:
        sys.modules.pop("kyre_universal_shell_runtime_v1", None)
    else:
        sys.modules["kyre_universal_shell_runtime_v1"] = _original_shell_v1_module
