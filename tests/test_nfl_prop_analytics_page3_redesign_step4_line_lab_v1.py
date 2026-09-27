from pathlib import Path
import nfl_prop_analytics_page3_redesign_step4_line_lab_v1 as r4
SRC=Path("nfl_prop_analytics_page3_redesign_step4_line_lab_v1.py").read_text()
FINAL=Path("nfl_prop_analytics_page3_final_polish_v1.py").read_text()
def test_contract():
    assert r4.PAGE3_REDESIGN_STEP==4 and r4.PRESENTATION_ONLY is True
    assert r4.FROZEN_PAGE3_STEPS_1_TO_8_PROTECTED is True and r4.FROZEN_FUN_POLISH_STEPS_1_TO_5_PROTECTED is True
    assert r4.FROZEN_REDESIGN_STEPS_1_TO_3_PROTECTED is True and r4.INTERACTION_BEHAVIOR_CHANGED is False
    assert r4.DATA_OWNERSHIP_CHANGED is False and r4.MIN_TOUCH_TARGET_PX==44 and r4.CERTIFIED_VIEWPORTS==(390,768,1440)
def test_visual():
    for t in ('data-prop-page3-redesign-step4="','.ks-pa4-line-intro','[data-testid="stSlider"]','.ks-pa4-line-grid','.ks-pa4-line-value','@media(max-width:560px)'): assert t in SRC
def test_no_behavior():
    for t in ("query_params","session_state","st.slider(","st.segmented_control(","st.button(","load_player_history","load_verified_market"): assert t not in SRC
def test_wired():
    assert "render_redesign_step4_line_lab" in FINAL and '"redesign_step4_line_lab": redesign_step4_line_lab' in FINAL
    assert FINAL.index("redesign_step3_analysis_settings = render_redesign_step3_analysis_settings()") < FINAL.index("redesign_step4_line_lab = render_redesign_step4_line_lab()")
