from __future__ import annotations

from pathlib import Path


def test_app_bootstraps_router_v149() -> None:
    source = Path("app.py").read_text(encoding="utf-8")
    assert "STREAMLIT_MAIN_V149_CFB_OVER_UNDER_MONSTER_COMPACT_DASHBOARD_2026-09-16" in source
    assert "from streamlit_memory_lazy_router_v149 import record_bootstrap_import_ms, render_app" in source


def test_cfb_moneyline_v148_history_remains_present() -> None:
    source = Path("app.py").read_text(encoding="utf-8")
    assert "STREAMLIT_MAIN_V148_CFB_MONEYLINE_MONSTER_DASHBOARD_2026-09-16" in source
    assert "FROZEN_V148_DEPLOYMENT_HEARTBEAT" in source
