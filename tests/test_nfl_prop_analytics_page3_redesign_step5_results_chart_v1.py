from pathlib import Path
import nfl_prop_analytics_page3_redesign_step5_results_chart_v1 as r5
SRC=Path("nfl_prop_analytics_page3_redesign_step5_results_chart_v1.py").read_text(); FINAL=Path("nfl_prop_analytics_page3_final_polish_v1.py").read_text()
def test_contract():
    assert r5.PAGE3_REDESIGN_STEP==5 and r5.PRESENTATION_ONLY and r5.CERTIFIED_VIEWPORTS==(390,768,1440)
    assert r5.FROZEN_PAGE3_STEPS_1_TO_8_PROTECTED and r5.FROZEN_FUN_POLISH_STEPS_1_TO_5_PROTECTED and r5.FROZEN_REDESIGN_STEPS_1_TO_4_PROTECTED
    assert r5.INTERACTION_BEHAVIOR_CHANGED is False and r5.DATA_OWNERSHIP_CHANGED is False and r5.SPORTSBOOK_PROJECTION_INFLUENCE==0.0
def test_visual_tokens():
    for t in ('data-prop-page3-redesign-step5="','.ks-pa5-chart','.ks-pa5-scroll','.ks-pa6-grid','.ks-pa7mi-insights','@media(max-width:560px)'): assert t in SRC
def test_no_behavior_ownership():
    for t in ("query_params","session_state","st.slider(","st.segmented_control(","st.button(","load_player_history","load_verified_market","fetch_event_market","build_game_chart_spec("): assert t not in SRC
def test_order():
    assert "render_redesign_step5_results_chart" in FINAL and '"redesign_step5_results_chart": redesign_step5_results_chart' in FINAL
    assert FINAL.index("redesign_step4_line_lab = render_redesign_step4_line_lab()") < FINAL.index("redesign_step5_results_chart = render_redesign_step5_results_chart()")
