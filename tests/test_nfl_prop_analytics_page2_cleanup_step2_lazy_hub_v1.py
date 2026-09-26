import ast
from pathlib import Path

HUB_PATH = Path("nfl_prop_analytics_hub_v1.py")
HUB = HUB_PATH.read_text()
APP = Path("app.py").read_text()


def _top_level_import_modules():
    tree = ast.parse(HUB)
    modules = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            modules.add(node.module or "")
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    return modules


def test_fresh_route_import_graph_is_lightweight():
    top = _top_level_import_modules()
    forbidden = {
        "nfl_prop_analytics_roster_truth_v1",
        "nfl_prop_analytics_availability_depth_v1",
        "nfl_prop_analytics_page2_unified_roster_v1",
        "nfl_prop_analytics_player_select_v1",
        "nfl_prop_analytics_page2_tap_player_v1",
        "nfl_prop_analytics_page2_responsive_polish_v1",
        "nfl_prop_analytics_prop_page_v1",
        "nfl_moneyline_hub_v2",
        "nfl_moneyline_hub_v21",
    }
    assert not (top & forbidden), sorted(top & forbidden)
    assert "nfl_prop_analytics_schedule_v1" in top
    assert "nfl_prop_analytics_game_select_v1" in top
    assert "nfl_prop_analytics_matchup_shell_v1" in top


def test_heavy_modules_are_lazy_wrappers_not_removed():
    for token in (
        "from nfl_prop_analytics_roster_truth_v1 import load_verified_roster_truth as impl",
        "from nfl_prop_analytics_availability_depth_v1 import load_availability_depth_truth as impl",
        "from nfl_prop_analytics_page2_unified_roster_v1 import render_unified_roster_availability as impl",
        "from nfl_prop_analytics_page2_tap_player_v1 import render_tap_player_handoff as impl",
        "from nfl_prop_analytics_page2_responsive_polish_v1 import render_page2_responsive_polish as impl",
        "from nfl_prop_analytics_prop_page_v1 import render_prop_page_shell as impl",
        "from nfl_prop_analytics_prop_page_v1 import render_prop_page_open_control as impl",
    ):
        assert token in HUB, token


def test_page2_shell_renders_before_heavy_truth_graph():
    assert "if is_matchup_page():" in HUB
    assert "handoff = render_matchup_shell()" in HUB
    assert "render_page2_responsive_polish()" in HUB
    assert "roster_truth = load_verified_roster_truth(handoff)" in HUB
    assert HUB.index("handoff = render_matchup_shell()") < HUB.index(
        "roster_truth = load_verified_roster_truth(handoff)"
    )


def test_existing_page2_and_step7_composition_is_preserved():
    assert "availability_truth = load_availability_depth_truth(handoff, roster_truth)" in HUB
    assert 'roster_truth.get("state") == "live"' in HUB
    assert 'availability_truth.get("state") == "live"' in HUB
    assert "render_unified_roster_availability(" in HUB
    assert "render_tap_player_handoff(" in HUB
    assert "render_prop_page_open_control(player_handoff)" in HUB


def test_route_and_safety_flags_remain_frozen():
    for token in (
        'MARKET = "Prop Analytics"',
        'data-nfl-prop-analytics-route="v1"',
        'data-prop-analytics-owner="nfl_prop_analytics_hub_v1"',
        "MAY_MODIFY_PASSING_YARDS = False",
        "MAY_MODIFY_EXISTING_NFL_MARKETS = False",
        "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0",
    ):
        assert token in HUB, token


def test_production_refresh_marker_is_present():
    assert (
        'PROP_ANALYTICS_PAGE2_CLEANUP_STEP2_LAZY_HUB_REFRESH = '
        '"NFL_PROP_ANALYTICS_PAGE2_CLEANUP_STEP2_LAZY_HUB_REFRESH_2026_09_26_R1"'
    ) in APP
