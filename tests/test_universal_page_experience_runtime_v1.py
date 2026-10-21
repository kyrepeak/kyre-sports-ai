from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_runtime_mounts_page_experience_before_destination_load() -> None:
    source = _source("universal_page_experience_runtime_v1.py")
    assert "page_experience_controller_markup" in source
    assert "_mount_page_experience_controller(runtime.active)" in source
    assert source.index("_mount_page_experience_controller(runtime.active)") < source.index("core.load_destination(adapter)")
    assert "destination_slot = st.empty()" in source
    assert "core.can_commit" in source
    assert "core.commit_if_current" in source
    assert "choose_prefetch" not in source
    assert "_run_bounded_prefetch" not in source


def test_runtime_uses_opaque_fail_closed_fallback() -> None:
    source = _source("universal_page_experience_runtime_v1.py")
    assert "page_experience_fallback_markup(runtime.active)" in source
    assert "if is_transition and not client_controller" in source
    except_block = source.rsplit("except Exception:", 1)[1].split("raise", 1)[0]
    assert "transition_slot.empty()" not in except_block


def test_single_ancestor_terminal_seam_inherits_page_experience() -> None:
    v3 = _source("streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v3.py")
    v4 = _source("streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v4.py")
    nba = _source("streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1.py")
    app = _source("app.py")

    assert "from universal_page_experience_runtime_v1 import render_page_experience_app" in v3
    assert "return render_page_experience_app(frozen_runtime)" in v3
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v3 as prior" in v4
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v4 as prior" in nba
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1" in app
