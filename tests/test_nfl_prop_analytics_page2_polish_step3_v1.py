from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "nfl_prop_analytics_page2_unified_roster_v1.py").read_text()

def test_step3_position_filter_contract():
    assert 'FILTERS = ("ALL", "QB", "RB", "WR", "TE")' in SRC
    assert 'st.segmented_control(' in SRC
    assert 'data-prop-page2-position-filter="v1"' in SRC
    assert 'data-prop-page2-position-filter-active=' in SRC
    assert 'data-prop-page2-position-filter-options="ALL,QB,RB,WR,TE"' in SRC
    assert '_team_column(filtered_truth["teams"][away]' in SRC
    assert '_team_column(filtered_truth["teams"][home]' in SRC

def test_step3_preserves_truth_contract():
    assert "load_verified_roster_truth(handoff)" in SRC
    assert "load_availability_depth_truth(handoff, roster_truth)" in SRC
    assert "return truth" in SRC
