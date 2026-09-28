from pathlib import Path
import nfl_prop_analytics_page3_visual_v2_step2_hero_v1 as v2

SRC=Path("nfl_prop_analytics_page3_visual_v2_step2_hero_v1.py").read_text()
PAGE=Path("nfl_prop_analytics_prop_page_v1.py").read_text()
CONTRACT=Path("devsystem/contracts/nfl-prop-page3-visual-composition-v2-contract-v1.json").read_text()

def test_step2_contract_identity():
    assert v2.VISUAL_SERIES=="v2"
    assert v2.VISUAL_STEP==2
    assert v2.VISUAL_VERSION=="v1"
    assert v2.REAL_COMPOSITION_REBUILD is True
    assert v2.PRESENTATION_ONLY is True
    assert v2.DATA_OWNERSHIP_CHANGED is False
    assert v2.INTERACTION_BEHAVIOR_CHANGED is False
    assert v2.CERTIFIED_VIEWPORTS==(390,768,1440)

def test_step2_is_real_replacement_composition():
    for token in (
        'class="ks-v2-hero"',
        'ks-v2-hero-team-home',
        'ks-v2-hero-player',
        'ks-v2-hero-team-away',
        'ks-v2-game-meta',
        '.ks-pa3-hero{display:none!important}',
        'grid-template-areas:"home player away" "meta meta meta"',
    ):
        assert token in SRC, token
    assert "Match the approved mockup composition" in CONTRACT

def test_dynamic_truth_nodes_are_rendered():
    for token in ("player_logo","opponent_logo","headshot","player_name","market_label","depth_role","player_id","gate_state","display_date","kickoff","network","venue"):
        assert token in SRC, token

def test_step2_does_not_own_interactions_or_data():
    for token in ("st.segmented_control(","st.slider(","st.button(","st.query_params","load_player_history(","summarize_history(","requests.get("):
        assert token not in SRC, token

def test_step2_is_wired_additively_before_frozen_hero():
    assert "from nfl_prop_analytics_page3_visual_v2_step2_hero_v1 import render_visual_v2_hero" in PAGE
    assert "visual_v2_step2_hero = render_visual_v2_hero(" in PAGE
    assert PAGE.index("visual_v2_step2_hero = render_visual_v2_hero(") < PAGE.index('<section class="ks-pa3-hero"')
    assert '"visual_v2_step2_hero": visual_v2_step2_hero' in PAGE
