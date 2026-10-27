from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
HUB = ROOT / "nfl_moneyline_hub_v20.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_nfl_moneyline_page1_live_route_restore_r1.py"

HEARTBEAT = "API2_NFL_MONEYLINE_PAGE1_CURRENT_CONVERGENCE_R1_20261026"


def test_current_convergence_heartbeat_uses_shared_runtime_lifecycle_contract():
    text = APP.read_text(encoding="utf-8")
    assert HEARTBEAT in text
    assert "API2_STEP2G_DUAL_MAIN_STREAMLIT_CONVERGENCE_V1" in text
    assert "API2_NFL_MONEYLINE_PAGE1_SIMPLE_LIVE_ROUTE_RESTORE_R1_20261026" in text
    assert 'sys.modules.pop("nfl_moneyline_hub_v20", None)' in text
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_moneyline_page1_live_route_restore_r1" in text
    assert "API2_SITEWIDE_RENDER_REPAIR_R1_20261026" in text
    assert "from devsystem.shared_runtime_lifecycle_v1 import run_shared_runtime_lifecycle" in text
    assert "render=render_app" in text
    assert "pre_render_hooks=(emit_runtime_identity_marker,)" in text


def test_page1_compact_decision_contract_remains_active():
    text = HUB.read_text(encoding="utf-8")
    for marker in (
        "SIMPLE PAGE1",
        "GAME TIME / VENUE",
        "MODEL PICK / PROBABILITY",
        "BEST ML",
        "EDGE / CONFIDENCE",
        "VIEW FULL ANALYSIS",
        "_simple_matchup_html",
    ):
        assert marker in text
    assert "prior._silent_frozen_engine()" in text
    assert "prior.market_visual._market_matchup_html = _simple_matchup_html" not in text
    assert "war_room.render_context(context)" in text
    assert "page2_api.build_page2_context" in text


def test_terminal_route_shadows_only_nfl_moneyline_to_v20():
    text = ROUTER.read_text(encoding="utf-8")
    assert 'route.sport_id == "nfl" and route.market_id == "moneyline"' in text
    assert 'canonical_loader._nfl_adapter(route, "nfl_moneyline_hub_v20", ttl_ms=20_000)' in text
    assert "return prior.resolve_destination(route)" in text
    assert "MAY_MODIFY_PROJECTION = False" in text
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in text
    assert "STAKE_SIZING_ENABLED = False" in text
