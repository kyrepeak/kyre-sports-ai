from pathlib import Path

RESPONSIVE = Path("nfl_prop_analytics_page2_responsive_polish_v1.py").read_text()
HUB = Path("nfl_prop_analytics_hub_v1.py").read_text()


def test_step5_responsive_contract():
    assert 'RESPONSIVE_TARGETS = (390, 768, 1440)' in RESPONSIVE
    assert 'data-prop-page2-responsive-polish="v1"' in RESPONSIVE
    assert 'data-prop-page2-responsive-targets="390,768,1440"' in RESPONSIVE
    assert '@media (max-width:900px)' in RESPONSIVE
    assert '@media (max-width:640px)' in RESPONSIVE
    assert '@media (max-width:420px)' in RESPONSIVE
    assert 'div[data-testid="stHorizontalBlock"]' in RESPONSIVE
    assert 'min-height:48px' in RESPONSIVE
    assert '.ks-pa-u-grid{grid-template-columns:1fr !important}' in RESPONSIVE


def test_step5_is_presentation_only():
    assert 'PRESENTATION_ONLY = True' in RESPONSIVE
    assert 'MAY_MODIFY_PASSING_YARDS = False' in RESPONSIVE
    assert 'load_verified_roster_truth' not in RESPONSIVE
    assert 'load_availability_depth_truth' not in RESPONSIVE
    assert 'eligible_players' not in RESPONSIVE
    assert 'build_player_handoff' not in RESPONSIVE


def test_step5_hub_composition_only():
    assert 'from nfl_prop_analytics_page2_responsive_polish_v1 import render_page2_responsive_polish' in HUB
    assert HUB.count('render_page2_responsive_polish()') == 1
    assert 'render_unified_roster_availability(handoff, roster_truth, availability_truth)' in HUB
    assert 'render_tap_player_handoff(handoff, availability_truth)' in HUB
    assert 'render_prop_page_open_control(player_handoff)' in HUB
