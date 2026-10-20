from __future__ import annotations

import subprocess
import sys


def test_production_pra_wrapper_populates_cached_nba_market_pills() -> None:
    code = r'''
import streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1  # noqa: F401
import universal_sports_nav_ui_v1 as ui
assert ui._MARKET_IDS_BY_SPORT["nba"] == ("spread", "pra"), ui._MARKET_IDS_BY_SPORT["nba"]
assert ui._MARKET_LABELS_BY_SPORT["nba"]["pra"] == "PRA"
'''
    result = subprocess.run([sys.executable, "-c", code], text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
