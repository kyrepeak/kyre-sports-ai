from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
MONEYLINE = ROOT / "nfl_moneyline_hub_v20.py"

HEARTBEAT = "API2_SITEWIDE_RENDER_REPAIR_R1_20261026"


def test_api2_app_renders_before_monster_identity_sidecar():
    text = APP.read_text(encoding="utf-8")
    assert HEARTBEAT in text
    assert text.count("emit_runtime_identity_marker()") == 1
    assert text.count("render_app()") == 1
    assert text.index("render_app()") < text.index("emit_runtime_identity_marker()")


def test_moneyline_page1_uses_direct_compact_renderer_not_runtime_monkey_patch():
    text = MONEYLINE.read_text(encoding="utf-8")
    assert "prior.market_visual._market_matchup_html = _simple_matchup_html" not in text
    assert "prior.render_nfl_moneyline_hub()" not in text
    assert "prior._silent_frozen_engine()" in text
    assert "_simple_matchup_html(game, final, edge_out, mc_out, snap, contexts, gameplans)" in text
    for marker in (
        "GAME TIME / VENUE",
        "MODEL PICK / PROBABILITY",
        "BEST ML",
        "EDGE / CONFIDENCE",
        "VIEW FULL ANALYSIS",
    ):
        assert marker in text


def test_moneyline_page2_remains_on_existing_war_room_path():
    text = MONEYLINE.read_text(encoding="utf-8")
    assert "page2_api.build_page2_context" in text
    assert "war_room.render_context(context)" in text
    assert 'if view == "analysis"' in text
