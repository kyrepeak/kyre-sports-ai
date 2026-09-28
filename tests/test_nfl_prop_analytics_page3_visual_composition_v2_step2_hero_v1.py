from pathlib import Path
import nfl_prop_analytics_page3_visual_composition_v2_step2_hero_v1 as v2

SRC=Path("nfl_prop_analytics_page3_visual_composition_v2_step2_hero_v1.py").read_text()
PAGE=Path("nfl_prop_analytics_prop_page_v1.py").read_text()
CONTRACT=Path("devsystem/contracts/nfl-prop-page3-visual-composition-v2-contract-v1.json").read_text()

def test_step2_contract_and_real_composition():
    assert v2.VISUAL_COMPOSITION_V2_STEP==2
    assert v2.PRESENTATION_ONLY is True
    assert v2.DATA_OWNERSHIP_CHANGED is False
    assert v2.INTERACTION_BEHAVIOR_CHANGED is False
    for token in ("ks-v2-hero-team-left","ks-v2-hero-player","ks-v2-hero-team-right","ks-v2-game-meta","ks-v2-portrait-ring"):
        assert token in SRC
    assert "render_visual_composition_v2_hero(" in PAGE
    assert 'class="ks-pa3-hero"' not in PAGE
    assert '"scope": "Hero composition rebuild"' in CONTRACT

def test_step2_does_not_own_frozen_behavior():
    for token in ("st.button(","st.segmented_control(","st.slider(","query_params","load_player_history","load_verified_market","requests.get("):
        assert token not in SRC, token
