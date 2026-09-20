from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_step2_universal_shell_contract():
    shell = (ROOT / "sports_universal_shell_v1.py").read_text(encoding="utf-8")
    page = (ROOT / "nfl_passing_yards_hub_v16.py").read_text(encoding="utf-8")

    assert 'data-universal-shell="v1"' in shell
    assert 'class="ks-sidebar"' in shell
    assert 'class="ks-topbar"' in shell
    assert 'Passing Yards' in shell
    assert 'position:fixed' in shell
    assert '@media(max-width:1000px)' in shell
    assert '@media(max-width:720px)' in shell
    assert 'padding-left:calc(var(--ks-nav-w) + 30px)' in shell
    assert 'from sports_universal_shell_v1 import render_universal_shell' in page
    assert 'render_universal_shell(sport="NFL", market="Passing Yards")' in page

def test_step2_preserves_frozen_passing_yards_logic_hooks():
    page = (ROOT / "nfl_passing_yards_hub_v16.py").read_text(encoding="utf-8")
    for marker in (
        "original_identity = step7_ui.identity.resolve_matchup_identity",
        "original_baseline = step7_ui.projection.build_baseline_projection",
        "original_context = step8_ui.context.build_context_projection",
        "original_distribution = step9_ui.distribution.build_distribution",
        "original_market_card = step10_ui._market_card",
        "step7_ui.identity.resolve_matchup_identity = original_identity",
        "step10_ui._market_card = original_market_card",
    ):
        assert marker in page
