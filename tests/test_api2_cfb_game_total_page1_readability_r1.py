from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _compact(text: str) -> str:
    return "".join(text.split()).casefold()


def test_v7_readability_successor_exists_and_is_presentation_only():
    page = ROOT / "cfb_game_total_page1_atier_v7.py"
    assert page.exists(), "V7 readability successor is missing"
    source = page.read_text(encoding="utf-8")
    folded = _compact(source)
    assert "importcfb_game_total_page1_atier_v6asprior" in folded
    assert "sportsbook_projection_influence=0.0" in folded
    for flag in (
        "may_modify_model=false",
        "may_modify_projection=false",
        "may_modify_probability=false",
        "may_modify_ranking=false",
        "may_modify_selection=false",
        "may_modify_selected_game_runtime=false",
    ):
        assert flag in folded
    assert "prior.render_game_total_page1()" in source
    assert "sports_api" not in source
    assert "decision_endpoint" not in source.casefold()


def test_v7_matchup_rail_has_tablet_readability_scale():
    source = (ROOT / "cfb_game_total_page1_atier_v7.py").read_text(encoding="utf-8")
    folded = _compact(source)
    assert ".cfbgt5-chip{flex-basis:228px!important;width:228px!important;height:104px!important" in folded
    assert ".cfbgt5-team-logo{width:46px!important;height:46px!important;flex-basis:46px!important" in folded
    assert ".cfbgt5-team-logoimg{inset:2px!important;width:42px!important;height:42px!important" in folded
    assert ".cfbgt5-abbr{font-size:17px!important" in folded
    assert ".cfbgt5-time{font-size:13px!important" in folded
    assert ".cfbgt5-at{font-size:14px!important" in folded


def test_v7_selected_card_has_s_tier_primary_hierarchy():
    source = (ROOT / "cfb_game_total_page1_atier_v7.py").read_text(encoding="utf-8")
    folded = _compact(source)
    assert ".cfbgt6-team-logo{width:52px!important;height:52px!important;flex-basis:52px!important" in folded
    assert ".cfbgt6-team-logoimg{inset:3px!important;width:46px!important;height:46px!important" in folded
    assert ".cfbgt6-team{font-size:20px!important" in folded
    assert ".cfbgt6-kick{font-size:13px!important" in folded
    assert ".cfbgt6-metricsmall{font-size:12px!important" in folded
    assert ".cfbgt6-metricstrong{font-size:28px!important" in folded
    assert ".cfbgt6-probstrong{font-size:22px!important" in folded
    assert ".cfbgt6-secondarysmall{font-size:11px!important" in folded
    assert ".cfbgt6-secondarystrong{font-size:14px!important" in folded
    assert ".cfbgt6-opendisplay:inline-flex" in folded
    assert "min-width:150px!important" in folded
    assert "min-height:42px!important" in folded
    assert "font-size:12px!important" in folded


def test_v7_mobile_overrides_preserve_readability_floor():
    source = (ROOT / "cfb_game_total_page1_atier_v7.py").read_text(encoding="utf-8")
    folded = _compact(source)
    assert "@media(max-width:620px)" in folded
    assert ".cfbgt5-team-logo{width:42px!important;height:42px!important;flex-basis:42px!important" in folded
    assert ".cfbgt5-abbr{font-size:16px!important" in folded
    assert ".cfbgt5-time{font-size:13px!important" in folded
    assert ".cfbgt6-team-logo{width:48px!important;height:48px!important;flex-basis:48px!important" in folded
    assert ".cfbgt6-team{font-size:18px!important" in folded
    assert ".cfbgt6-metricsmall{font-size:11px!important" in folded
    assert ".cfbgt6-metricstrong{font-size:24px!important" in folded
    assert ".cfbgt6-probstrong{font-size:18px!important" in folded


def test_bootstrap_activates_v7_without_expanding_ownership():
    source = (ROOT / "cfb_game_total_page1_api_bootstrap_repair_r1.py").read_text(encoding="utf-8")
    folded = _compact(source)
    assert "cfb_game_total_page1_atier_v7" in source
    assert "a-tierv7readability" in folded
    assert "sportsbook_projection_influence=0.0" in folded
    for flag in (
        "may_modify_model=false",
        "may_modify_projection=false",
        "may_modify_probability=false",
        "may_modify_ranking=false",
        "may_modify_selection=false",
        "may_modify_selected_game_runtime=false",
    ):
        assert flag in folded
