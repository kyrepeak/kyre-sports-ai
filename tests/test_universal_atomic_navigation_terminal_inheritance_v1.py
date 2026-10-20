from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
V3 = ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v3.py"
ATOMIC = ROOT / "universal_atomic_navigation_runtime_v1.py"


def _source(path: Path) -> str:
    assert path.exists(), f"missing required file: {path.name}"
    return path.read_text(encoding="utf-8")


def test_app_stays_on_existing_v3_terminal_so_v4_lane_keeps_entrypoint_ownership():
    app = _source(APP)
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v3" in app
    assert "streamlit_memory_lazy_router_universal_runtime_v5_atomic_navigation_v1" not in app


def test_v3_terminal_delegates_rendering_to_atomic_runtime_without_changing_loader_ownership():
    source = _source(V3)
    assert "from universal_atomic_navigation_runtime_v1 import render_atomic_app" in source
    assert "frozen_runtime.choose_prefetch = choose_prefetch" in source
    assert "frozen_runtime.load_destination = load_destination" in source
    assert "frozen_runtime.resolve_destination = resolve_destination" in source
    assert "return render_atomic_app(frozen_runtime)" in source
    assert 'FROZEN_RUNTIME = "streamlit_memory_lazy_router_universal_runtime_v5_nba_spread_v8"' in source


def test_atomic_runtime_is_terminal_agnostic_and_has_zero_background_destination_prefetch():
    source = _source(ATOMIC)
    assert "nfl_daily_picks_v3" not in source
    assert "nfl_daily_picks_v4" not in source
    assert "route_identity(runtime.active)" in source
    assert "transition_markup(runtime.active)" in source
    assert "transition_slot = st.empty()" in source
    assert "destination_slot = st.empty()" in source
    assert "transition_slot.markdown" in source
    assert "destination_slot.empty()" in source
    assert "with destination_slot.container()" in source
    assert "_run_bounded_prefetch(" not in source
    assert "choose_prefetch(" not in source
    assert "run_prefetch(" not in source


def test_atomic_runtime_preserves_generation_guards_and_only_unmasks_after_current_commit():
    source = _source(ATOMIC)
    load_at = source.index("core.load_destination")
    shield_at = source.index("transition_slot.markdown")
    clear_at = source.index("destination_slot.empty()")
    render_at = source.index("adapter.renderer")
    unmask_at = source.index("transition_slot.empty()", render_at)

    assert shield_at < load_at
    assert clear_at < load_at
    assert render_at < unmask_at
    assert "core.can_commit(scope, runtime)" in source
    assert "core.can_commit(scope, current)" in source
    assert "core.commit_if_current" in source
    assert "stale_commit_attempt" in source
