from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_game_total_page2_successor_exists_and_routes_selected_game():
    source = _read("nfl_game_totals_hub_v11.py")
    assert 'market=game-total&view=analysis&game=' in source
    assert 'view == "analysis"' in source
    assert "def _page2(" in source
    assert "def _page1(" in source


def test_page1_handoff_is_real_same_tab_navigation_not_details_disclosure():
    source = _read("nfl_game_totals_hub_v11.py")
    assert 'target="_self"' in source
    assert "VIEW FULL ANALYSIS →" in source
    assert "<details" not in source


def test_successor_reuses_frozen_page1_and_existing_v10_v9_analysis_owners():
    source = _read("nfl_game_totals_hub_v11.py")
    assert "import nfl_game_totals_page1_s_tier_v1 as page1" in source
    assert "import nfl_game_totals_hub_v10 as v10" in source
    assert "v9 = v10.v9" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "STAKE_SIZING_ENABLED = False" in source
    assert "WAGER_ACTIONS_ENABLED = False" in source


def test_canonical_loader_activates_page2_successor_only_for_game_total():
    source = _read("universal_runtime_v5_loader.py")
    block = source.split("def _nfl_game_total_adapter", 1)[1].split("def _nfl_passing_yards_adapter", 1)[0]
    assert '_import("nfl_game_totals_hub_v11")' in block
    assert '"nfl_game_totals_hub_v11"' in block


def test_original_page1_file_remains_the_frozen_presentation_owner():
    source = _read("nfl_game_totals_page1_s_tier_v1.py")
    assert 'MODEL_VERSION = "NFL GAME TOTALS PAGE1 S-TIER V1"' in source
    assert '<summary>VIEW FULL ANALYSIS →</summary>' in source
