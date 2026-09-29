from __future__ import annotations

from pathlib import Path

import streamlit_memory_lazy_router_v244 as top_picks
import streamlit_memory_lazy_router_v245 as nav


APP = Path("app.py").read_text(encoding="utf-8")
V244 = Path("streamlit_memory_lazy_router_v244.py").read_text(encoding="utf-8")
V245 = Path("streamlit_memory_lazy_router_v245.py").read_text(encoding="utf-8")


def test_step2_uses_frozen_step1_dropdown_owner():
    assert nav.FROZEN_ROUTER == "streamlit_memory_lazy_router_v244"
    assert nav.TOP_PICKS_MARKET == "Top Picks"
    assert "from streamlit_memory_lazy_router_v245 import record_bootstrap_import_ms, render_app" in APP


def test_step2_top_picks_selection_targets_existing_frozen_v5():
    assert top_picks.TOP_PICKS_PAGE == "cfb_top_picks_page_v5"
    assert "top_picks_base._active_top_picks_route()" in V244
    assert "top_picks_base._persist_top_picks_query()" in V244
    assert "return _render_direct_top_picks_v244()" in V244


def test_step2_preserves_existing_products_and_math():
    assert nav.MAY_MODIFY_TOP_PICKS_PRODUCT is False
    assert nav.MAY_MODIFY_EXISTING_CFB_PRODUCTS is False
    assert nav.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert nav.HISTORY_PROJECTION_INFLUENCE == 0.0
    assert top_picks.MAY_MODIFY_EXISTING_CFB_PRODUCTS is False
    assert top_picks.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert top_picks.HISTORY_PROJECTION_INFLUENCE == 0.0
