from __future__ import annotations

from pathlib import Path


def test_app_bootstraps_router_v148() -> None:
    source = Path("app.py").read_text(encoding="utf-8")
    assert "STREAMLIT_MAIN_V148_CFB_MONEYLINE_MONSTER_DASHBOARD_2026-09-16" in source
    assert "from streamlit_memory_lazy_router_v148 import record_bootstrap_import_ms, render_app" in source


def test_receiving_yards_v147_history_remains_present() -> None:
    source = Path("app.py").read_text(encoding="utf-8")
    assert (
        'FROZEN_V147_DEPLOYMENT_HEARTBEAT = '
        '"STREAMLIT_MAIN_V147_NFL_RECEIVING_YARDS_FUTURE_CARD_RENDER_FIX_2026-09-16"'
    ) in source
