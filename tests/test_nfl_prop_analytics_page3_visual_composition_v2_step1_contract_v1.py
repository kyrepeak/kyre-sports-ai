import json
from pathlib import Path

CONTRACT_PATH=Path("devsystem/contracts/nfl-prop-page3-visual-composition-v2-contract-v1.json")
CONTRACT=json.loads(CONTRACT_PATH.read_text())

def test_reference_contract_identity():
    assert CONTRACT["contract_version"]=="v1"
    assert CONTRACT["series"]=="NFL_PROP_ANALYTICS_PAGE3_VISUAL_COMPOSITION_V2"
    assert CONTRACT["step"]==1
    assert CONTRACT["source_of_truth"]["reference_canvas_px"]=={"width":1080,"height":1440}
    assert "Do not satisfy this contract with a CSS skin" in CONTRACT["source_of_truth"]["instruction"]

def test_exact_section_order_and_composition():
    regions=CONTRACT["reference_regions"]
    assert [r["id"] for r in regions]==[
        "app_header","hero","quick_stat_ribbon","analysis_settings",
        "line_lab","live_recalculation","game_chart"
    ]
    assert [r["order"] for r in regions]==list(range(1,8))
    ribbon=next(r for r in regions if r["id"]=="quick_stat_ribbon")
    assert ribbon["required_cards"]==["average","median","season_high","season_low","hit_rate"]
    settings=next(r for r in regions if r["id"]=="analysis_settings")
    assert settings["left_control_card"]=="History Window"
    assert settings["right_control_card"]=="Prop Category"
    assert settings["interaction_rule"].startswith("Existing Streamlit controls remain real")
    line=next(r for r in regions if r["id"]=="line_lab")
    assert "large centered current line value" in line["required_composition"]

def test_accessibility_and_responsive_contract():
    g=CONTRACT["global"]
    assert g["minimum_touch_target_px"]==44
    assert g["focus_visible_required"] is True
    assert g["reduced_motion_required"] is True
    assert g["horizontal_document_overflow_forbidden"] is True
    assert g["certified_viewports"]==[390,768,1440]

def test_frozen_behavior_contract():
    f=CONTRACT["functional_freeze"]
    assert f["protect_page3_steps_1_to_8"] is True
    assert f["protect_fun_polish_steps_1_to_5"] is True
    assert f["protect_redesign_steps_1_to_6"] is True
    assert f["protect_passing_yards_frozen_work"] is True
    assert f["query_navigation_semantics_changed"] is False
    assert f["widget_keys_changed"] is False
    assert f["data_ownership_changed"] is False
    assert f["projection_weight"]==0.0

def test_future_step_map_is_locked():
    assert CONTRACT["future_step_map"]==[
        {"step":2,"scope":"Hero composition rebuild"},
        {"step":3,"scope":"Quick-stat ribbon rebuild"},
        {"step":4,"scope":"Analysis Settings composition rebuild"},
        {"step":5,"scope":"Line Lab + lower analytics/chart composition rebuild"},
        {"step":6,"scope":"Full integration, accessibility, responsive and public certification"}
    ]
