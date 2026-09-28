from pathlib import Path

import nfl_prop_analytics_page3_visual_v2_step3_stat_ribbon_v1 as v2

SRC = Path("nfl_prop_analytics_page3_visual_v2_step3_stat_ribbon_v1.py").read_text()
PAGE = Path("nfl_prop_analytics_prop_page_v1.py").read_text()
CONTRACT = Path(
    "devsystem/contracts/nfl-prop-page3-visual-composition-v2-contract-v1.json"
).read_text()


def test_step3_contract_identity():
    assert v2.VISUAL_SERIES == "v2"
    assert v2.VISUAL_STEP == 3
    assert v2.VISUAL_VERSION == "v1"
    assert v2.REAL_COMPOSITION_REBUILD is True
    assert v2.PRESENTATION_ONLY is True
    assert v2.FROZEN_STEP2_HERO_PROTECTED is True
    assert v2.DATA_OWNERSHIP_CHANGED is False
    assert v2.INTERACTION_BEHAVIOR_CHANGED is False
    assert v2.CERTIFIED_VIEWPORTS == (390, 768, 1440)


def test_step3_matches_locked_five_card_quick_stat_contract():
    for token in (
        '"id": "quick_stat_ribbon"',
        '"required_cards": ["average", "median", "season_high", "season_low", "hit_rate"]',
        '"Five equal-width stat cards in one row at reference width."',
        '{"step": 3, "scope": "Quick-stat ribbon rebuild"}',
    ):
        assert token in CONTRACT, token

    for token in (
        'class="ks-v2-stat-ribbon"',
        'data-page3-visual-v2-step3="',
        'data-page3-visual-v2-step3-real-composition="true"',
        'data-v2-stat-card="average"',
        'data-v2-stat-card="median"',
        'data-v2-stat-card="season-high"',
        'data-v2-stat-card="season-low"',
        'data-v2-stat-card="hit-rate"',
        "grid-template-columns:repeat(5,minmax(0,1fr))",
        ".ks-pa3-stats{{display:none!important}}",
    ):
        assert token in SRC, token

    assert SRC.count('data-v2-stat-card="') == 5


def test_step3_is_presentation_only_and_reuses_frozen_summary():
    forbidden = (
        "requests.get(",
        "load_player_history(",
        "summarize_history(",
        "st.segmented_control(",
        "st.slider(",
        "st.button(",
        "st.query_params",
        "render_analysis_line_control(",
    )
    for token in forbidden:
        assert token not in SRC, token

    for token in (
        'summary.get("average")',
        'summary.get("median")',
        'summary.get("high")',
        'summary.get("low")',
        'summary.get("hit_rate_pct")',
    ):
        assert token in SRC or token.replace("summary", "payload") in SRC, token


def test_step3_wiring_preserves_visual_order_and_frozen_logic():
    assert (
        "from nfl_prop_analytics_page3_visual_v2_step3_stat_ribbon_v1 import ("
        in PAGE
    )
    hero_call = PAGE.index("visual_v2_step2_hero = render_visual_v2_hero(")
    slot = PAGE.index("visual_v2_step3_ribbon_slot = st.empty()")
    old_hero = PAGE.index('<section class="ks-pa3-hero"')
    controls = PAGE.index('st.segmented_control(\n        "History window"')
    render = PAGE.index("visual_v2_step3_stat_ribbon = render_visual_v2_stat_ribbon(")

    assert hero_call < slot < old_hero < controls < render
    assert "target=visual_v2_step3_ribbon_slot" in PAGE
    assert '"visual_v2_step3_stat_ribbon": visual_v2_step3_stat_ribbon' in PAGE


def test_step3_keeps_frozen_step2_hero_import_and_owner():
    assert "render_visual_v2_hero" in PAGE
    assert '"visual_v2_step2_hero": visual_v2_step2_hero' in PAGE
