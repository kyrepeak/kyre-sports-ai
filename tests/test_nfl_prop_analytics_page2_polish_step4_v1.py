from pathlib import Path

TAP = Path("nfl_prop_analytics_page2_tap_player_v1.py").read_text()
HUB = Path("nfl_prop_analytics_hub_v1.py").read_text()
STEP7 = Path("nfl_prop_analytics_player_select_v1.py").read_text()

def test_step4_tap_player_contract():
    assert "eligible_players(step6_truth)" in TAP
    assert "build_player_handoff(matchup_handoff, step6_truth, selected)" in TAP
    assert 'data-prop-page2-tap-player="v1"' in TAP
    assert 'data-prop-page2-tap-handoff="v1"' in TAP
    assert "st.button(" in TAP
    assert "render_tap_player_handoff(handoff, availability_truth)" in HUB
    assert "render_player_selection_handoff(handoff, availability_truth)" not in HUB

def test_step7_safety_contract_still_present():
    assert 'SELECTABLE_AVAILABILITY = frozenset({"PENDING", "AVAILABLE"})' in STEP7
    assert 'BLOCKED_AVAILABILITY = frozenset({"UNAVAILABLE", "CLOSED", "UNVERIFIED"})' in STEP7
    assert 'availability in SELECTABLE_AVAILABILITY' in STEP7
    assert '"prop_analysis_gate_open": prop_gate_open' in STEP7
