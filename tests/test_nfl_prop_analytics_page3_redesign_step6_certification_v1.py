from pathlib import Path
import nfl_prop_analytics_page3_redesign_step6_certification_v1 as r6
SRC=Path("nfl_prop_analytics_page3_redesign_step6_certification_v1.py").read_text()
FINAL=Path("nfl_prop_analytics_page3_final_polish_v1.py").read_text()

def test_contract():
    assert r6.PAGE3_REDESIGN_STEP==6 and r6.PAGE3_REDESIGN_STEP6_VERSION=="v1"
    assert r6.PRESENTATION_ONLY is True and r6.VISIBLE_UI_CHANGED is False
    assert r6.FROZEN_PAGE3_STEPS_1_TO_8_PROTECTED is True
    assert r6.FROZEN_FUN_POLISH_STEPS_1_TO_5_PROTECTED is True
    assert r6.FROZEN_REDESIGN_STEPS_1_TO_5_PROTECTED is True
    assert r6.INTERACTION_BEHAVIOR_CHANGED is False and r6.DATA_OWNERSHIP_CHANGED is False
    assert r6.MIN_TOUCH_TARGET_PX==44 and r6.CERTIFIED_VIEWPORTS==(390,768,1440)

def test_marker_only():
    assert 'data-prop-page3-redesign-step6="' in SRC
    assert '.ks-pa3-redesign-step6-marker{{display:none!important}}' in SRC
    for t in (".ks-pa3-hero{",".ks-pa4-line{",".ks-pa5-chart{",".ks-pa6-support{",".ks-pa7mi{","st.slider(","st.segmented_control(","st.button(","query_params","session_state"):
        assert t not in SRC,t

def test_wired_after_step5():
    assert "render_redesign_step6_certification" in FINAL
    assert '"redesign_step6_certification": redesign_step6_certification' in FINAL
    assert FINAL.index("redesign_step5_results_chart = render_redesign_step5_results_chart()") < FINAL.index("redesign_step6_certification = render_redesign_step6_certification()")
