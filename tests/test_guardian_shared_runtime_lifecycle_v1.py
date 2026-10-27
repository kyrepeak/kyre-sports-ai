from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
LIFECYCLE = ROOT / "devsystem" / "shared_runtime_lifecycle_v1.py"


def _load_lifecycle():
    assert LIFECYCLE.is_file(), "Guardian shared lifecycle implementation is missing"
    spec = importlib.util.spec_from_file_location("guardian_shared_runtime_lifecycle_v1", LIFECYCLE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_shared_lifecycle_module_exists():
    assert LIFECYCLE.is_file(), "Guardian shared lifecycle implementation is missing"


def test_neutral_runner_orders_pre_render_and_post_render_hooks():
    lifecycle = _load_lifecycle()
    events: list[str] = []

    def pre_one():
        events.append("pre-one")

    def pre_two():
        events.append("pre-two")

    def render():
        events.append("render")
        return "render-result"

    def post_one():
        events.append("post-one")

    result = lifecycle.run_shared_runtime_lifecycle(
        render=render,
        pre_render_hooks=(pre_one, pre_two),
        post_render_hooks=(post_one,),
    )

    assert result == "render-result"
    assert events == ["pre-one", "pre-two", "render", "post-one"]


def test_pre_render_hook_runs_before_renderer_interruption_and_post_hook_does_not():
    lifecycle = _load_lifecycle()
    events: list[str] = []

    class RenderInterrupted(RuntimeError):
        pass

    def pre_hook():
        events.append("pre")

    def render():
        events.append("render")
        raise RenderInterrupted("simulated Streamlit interruption")

    def post_hook():
        events.append("post")

    with pytest.raises(RenderInterrupted, match="simulated Streamlit interruption"):
        lifecycle.run_shared_runtime_lifecycle(
            render=render,
            pre_render_hooks=(pre_hook,),
            post_render_hooks=(post_hook,),
        )

    assert events == ["pre", "render"]


def test_shared_lifecycle_module_is_system_neutral():
    source = LIFECYCLE.read_text(encoding="utf-8") if LIFECYCLE.exists() else ""
    lowered = source.lower()
    assert "api2" not in lowered
    assert "monster" not in lowered
    assert "streamlit" not in lowered


def test_app_delegates_shared_lifecycle_without_direct_sidecar_ordering():
    source = APP.read_text(encoding="utf-8")
    assert "from devsystem.shared_runtime_lifecycle_v1 import run_shared_runtime_lifecycle" in source
    assert "run_shared_runtime_lifecycle(" in source
    assert "render=render_app" in source
    assert "pre_render_hooks=(emit_runtime_identity_marker,)" in source
    assert "\nrender_app()\n" not in source
    assert "\nemit_runtime_identity_marker()\n" not in source
