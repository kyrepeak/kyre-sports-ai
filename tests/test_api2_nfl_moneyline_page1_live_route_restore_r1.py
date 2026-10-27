from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
TERMINAL = ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_nfl_moneyline_page1_live_route_restore_r1.py"
PAGE1 = ROOT / "nfl_moneyline_hub_v20.py"


def test_app_activates_fresh_moneyline_page1_terminal_identity():
    source = APP.read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_moneyline_page1_live_route_restore_r1" in source
    assert "API2_NFL_MONEYLINE_PAGE1_SIMPLE_LIVE_ROUTE_RESTORE_R1_20261026" in source
    assert 'sys.modules.pop("nfl_moneyline_hub_v20", None)' in source


def test_terminal_shadows_only_nfl_moneyline_to_existing_v20():
    assert TERMINAL.exists(), "Moneyline Page1 live-route restore terminal is missing"
    source = TERMINAL.read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_moneyline_page2_route_restore_v1 as prior" in source
    assert 'route.sport_id == "nfl" and route.market_id == "moneyline"' in source
    assert '"nfl_moneyline_hub_v20"' in source
    assert "return prior.resolve_destination(route)" in source
    assert "frozen_runtime.resolve_destination = resolve_destination" in source


def test_live_route_restore_preserves_moneyline_safety_contract():
    source = TERMINAL.read_text(encoding="utf-8") if TERMINAL.exists() else ""
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "STAKE_SIZING_ENABLED = False" in source


def test_v20_still_owns_the_simple_page1_and_separate_page2():
    source = PAGE1.read_text(encoding="utf-8")
    assert "_simple_matchup_html" in source
    assert "GAME TIME / VENUE" in source
    assert "MODEL PICK / PROBABILITY" in source
    assert "EDGE / CONFIDENCE" in source
    assert "VIEW FULL ANALYSIS" in source
    assert "war_room.render_context(context)" in source


def test_main_runtime_identity_marker_is_preserved_as_shared_prerender_hook():
    source = APP.read_text(encoding="utf-8")
    assert "from devsystem.monster_runtime_identity_v1 import emit_runtime_identity_marker" in source
    assert "from devsystem.shared_runtime_lifecycle_v1 import run_shared_runtime_lifecycle" in source
    assert "pre_render_hooks=(emit_runtime_identity_marker,)" in source
