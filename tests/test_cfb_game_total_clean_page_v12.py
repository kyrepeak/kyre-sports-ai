from pathlib import Path


PAGE = Path(__file__).resolve().parents[1] / "cfb_game_total_clean_page_v12.py"


def _source() -> str:
    assert PAGE.exists(), "V161 identity successor must exist"
    return PAGE.read_text(encoding="utf-8")


def test_v12_inherits_v11_verified_market_surface():
    source = _source()
    assert "cfb_game_total_clean_page_v11" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source


def test_v12_reads_official_espn_event_and_team_ids():
    source = _source()
    assert '"espn_event_id"' in source
    assert 'f"{side}_espn_team_id"' in source


def test_v12_patches_only_identity_helpers_during_render():
    source = _source()
    assert "prior._game_id = _game_id" in source
    assert "prior._team_id = _team_id" in source
    assert "prior._game_id = original_game_id" in source
    assert "prior._team_id = original_team_id" in source
