from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "streamlit_memory_lazy_router_universal_runtime_v5.py"
APP = ROOT / "app.py"


def _source(path: Path) -> str:
    assert path.exists(), path
    return path.read_text(encoding="utf-8")


def _function_source(source: str, name: str) -> str:
    start = source.index(f"def {name}")
    end = source.find("\ndef ", start + 5)
    return source[start:] if end < 0 else source[start:end]


def test_runtime_v5_owns_atomic_destination_handoff():
    source = _source(CORE)
    active = _function_source(source, "_render_v5_active")

    assert "route_identity(runtime.active)" in active
    assert "transition_markup(runtime.active)" in active
    assert "transition_slot = st.empty()" in active
    assert "destination_slot = st.empty()" in active
    assert "transition_slot.markdown" in active
    assert "destination_slot.empty()" in active
    assert "with destination_slot.container()" in active
    assert active.index("transition_slot.markdown") < active.index("load_destination")
    assert active.index("destination_slot.empty()") < active.index("load_destination")
    assert active.index("adapter.renderer") < active.index("transition_slot.empty()", active.index("adapter.renderer"))


def test_runtime_v5_atomic_handoff_keeps_stale_commit_guards():
    source = _source(CORE)
    active = _function_source(source, "_render_v5_active")

    assert "can_commit(scope, runtime)" in active
    assert "can_commit(scope, current)" in active
    assert "commit_if_current" in active
    assert "stale_commit_attempt" in active


def test_runtime_v5_does_not_render_old_cached_destination_or_background_prefetch():
    source = _source(CORE)
    active = _function_source(source, "_render_v5_active")

    assert "_render_cached_snapshot" not in active
    assert "_run_bounded_prefetch(runtime)" not in active
    assert "choose_prefetch(" not in active
    assert "run_prefetch(" not in active


def test_atomic_navigation_does_not_own_terminal_entrypoint():
    app = _source(APP)
    assert "streamlit_memory_lazy_router_universal_runtime_v5_atomic_navigation_v1" not in app
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v3" in app
