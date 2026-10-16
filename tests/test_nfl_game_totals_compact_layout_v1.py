from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPACT = ROOT / "nfl_game_totals_compact_layout_v1.py"
HUB = ROOT / "nfl_hub_v36.py"
V10 = ROOT / "nfl_game_totals_hub_v10.py"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_compact_layout_wraps_frozen_v10_without_replacing_model_contract():
    compact = _text(COMPACT)
    assert "import nfl_game_totals_hub_v10 as v10" in compact
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = v10.SPORTSBOOK_PROJECTION_INFLUENCE" in compact
    assert "STAKE_SIZING_ENABLED = v10.STAKE_SIZING_ENABLED" in compact
    assert "WAGER_ACTIONS_ENABLED = v10.WAGER_ACTIONS_ENABLED" in compact
    assert "v10.v9._market_read_contexts" in compact
    assert "v10.v9.v8._projection_contexts" in compact


def test_compact_layout_is_dense_full_width_and_responsive():
    compact = _text(COMPACT)
    required = (
        ".kgt-grid{grid-template-columns:1fr",
        ".kgt-compact-game",
        ".kgt-compact-summary",
        ".kgt-compact-analysis-grid",
        "grid-template-columns:repeat(2,minmax(0,1fr))",
        ".kgt-compact-controls",
        "@media(max-width:760px)",
    )
    for token in required:
        assert token in compact


def test_compact_card_keeps_all_certified_sections_inside_one_matchup_article():
    compact = _text(COMPACT)
    for helper in (
        "_market_html",
        "_offense_defense_html",
        "_pace_html",
        "_explosive_html",
        "_red_zone_drive_html",
        "_environment_html",
        "_projection_html",
        "_market_read_html",
    ):
        assert helper in compact
    assert '<article class="kgt-game kgt-compact-game"' in compact
    assert '<div class="kgt-compact-analysis-grid">' in compact


def test_game_total_router_activates_compact_wrapper_only_for_game_total():
    hub = _text(HUB)
    assert 'if market == "Game Total":' in hub
    assert "from nfl_game_totals_compact_layout_v1 import render_nfl_game_totals_hub" in hub
    assert "return base.render_nfl_hub(market)" in hub


def test_frozen_v10_file_is_still_step10_final_certification():
    v10 = _text(V10)
    assert 'PAGE_BUILD_STEP = 10' in v10
    assert 'FINAL_CERTIFICATION_ENABLED = True' in v10
    assert 'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0' in v10
    assert 'STAKE_SIZING_ENABLED = False' in v10
    assert 'WAGER_ACTIONS_ENABLED = False' in v10
