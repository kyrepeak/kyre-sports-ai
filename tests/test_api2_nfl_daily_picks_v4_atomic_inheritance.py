from pathlib import Path


def test_v4_inherits_current_universal_atomic_navigation_without_reimplementing_it():
    v4 = Path("streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v4.py").read_text()
    v3 = Path("streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v3.py").read_text()
    app = Path("app.py").read_text()
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v4" in app
    assert "import streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v3 as prior" in v4
    assert "return prior.render_app()" in v4
    assert "from universal_atomic_navigation_runtime_v1 import render_atomic_app" in v3
    assert "return render_atomic_app(frozen_runtime)" in v3
