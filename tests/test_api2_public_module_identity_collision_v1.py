from __future__ import annotations

import importlib
from pathlib import Path
import runpy
import sys
import types

import pytest


ROOT = Path(__file__).resolve().parents[1]
V2_NAME = "streamlit_memory_lazy_router_universal_nav_v2"
V4_NAME = "streamlit_memory_lazy_router_universal_nav_v4"
ACTIVE_LEGACY_ROUTER_IMPORT = (
    "from streamlit_memory_lazy_router_universal_nav_v2 import "
    "record_bootstrap_import_ms, render_app"
)


def _real_router_modules():
    real_v2 = importlib.import_module(V2_NAME)
    v4 = importlib.import_module(V4_NAME)
    assert v4.v2 is real_v2
    return real_v2, v4


def _execute_production_app_activation(monkeypatch) -> None:
    importlib.import_module("kyre_universal_shell_runtime_v2")
    cold_start = importlib.import_module("kyre_universal_entrypoint_cold_start_v1")
    monkeypatch.setattr(cold_start, "seed_canonical_route_if_missing", lambda *_args, **_kwargs: None)

    fake_streamlit = types.ModuleType("streamlit")
    fake_streamlit.session_state = {}
    fake_streamlit.query_params = {}
    monkeypatch.setitem(sys.modules, "streamlit", fake_streamlit)

    original_read_text = Path.read_text

    def activation_only_source(path: Path, *args, **kwargs):
        if path.name == "app_legacy_entrypoint_v1.py":
            return "try:\n    " + ACTIVE_LEGACY_ROUTER_IMPORT + "\nexcept Exception:\n    raise\n"
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", activation_only_source)
    runpy.run_path(str(ROOT / "app.py"), run_name="__main__")


def test_real_app_boot_preserves_v2_identity_across_v4_reload(monkeypatch):
    real_v2, v4 = _real_router_modules()
    try:
        _execute_production_app_activation(monkeypatch)
        first_boot_v2_identity = sys.modules[V2_NAME]
        _execute_production_app_activation(monkeypatch)
        rerun_v2_identity = sys.modules[V2_NAME]
        reloaded_v4 = importlib.reload(v4)
        assert first_boot_v2_identity is real_v2
        assert rerun_v2_identity is real_v2
        assert reloaded_v4.v2 is real_v2
        assert reloaded_v4.v2 is not reloaded_v4
    finally:
        sys.modules[V2_NAME] = real_v2
        importlib.reload(v4)


def test_prepoisoned_process_self_heals_without_v2_alias_activation(monkeypatch):
    real_v2, v4 = _real_router_modules()
    try:
        sys.modules[V2_NAME] = v4
        poisoned_v4 = importlib.reload(v4)
        assert poisoned_v4.v2 is poisoned_v4

        _execute_production_app_activation(monkeypatch)

        healed_v2 = sys.modules[V2_NAME]
        assert healed_v2 is not poisoned_v4
        assert getattr(healed_v2, "__name__", "") == V2_NAME
        assert hasattr(healed_v2, "nav_ui")
        assert poisoned_v4.v2 is healed_v2
        assert poisoned_v4.v2 is not poisoned_v4
    finally:
        sys.modules.pop(V2_NAME, None)
        real_v2 = importlib.import_module(V2_NAME)
        v4.v2 = real_v2
        importlib.reload(v4)


def test_forbidden_v2_to_v4_alias_reproduces_public_nav_ui_attributeerror(monkeypatch):
    real_v2, v4 = _real_router_modules()
    try:
        sys.modules[V2_NAME] = v4
        reloaded_v4 = importlib.reload(v4)
        assert reloaded_v4.v2 is reloaded_v4
        with pytest.raises(AttributeError, match="nav_ui"):
            reloaded_v4.render_app()
    finally:
        sys.modules[V2_NAME] = real_v2
        importlib.reload(v4)
