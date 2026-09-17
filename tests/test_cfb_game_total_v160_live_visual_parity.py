from pathlib import Path


PAGE = Path("cfb_game_total_clean_page_v10.py")


def _source() -> str:
    return PAGE.read_text(encoding="utf-8")


def test_v160_live_visual_parity_keeps_frozen_model_boundaries() -> None:
    source = _source()
    assert 'FROZEN_PRESENTATION = "cfb_game_total_clean_page_v9"' in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source


def test_v160_live_visual_parity_matches_compact_monster_dashboard_contract() -> None:
    source = _source()

    assert "MONSTER SPORTS INTELLIGENCE" in source
    assert ".gt159-gamefacts{grid-template-columns:repeat(4,minmax(0,1fr))" in source
    assert ".gt159-totalgrid{grid-template-columns:repeat(4,minmax(0,1fr))" in source
    assert ".gt159-badges{grid-template-columns:repeat(3,minmax(0,1fr))" in source
    assert ".gt159-teamgrid{grid-template-columns:repeat(2,minmax(0,1fr))" in source
    assert ".gt159-stepgrid{grid-template-columns:repeat(2,minmax(0,1fr))" in source
    assert ".gt159-finalgrid{grid-template-columns:repeat(5,minmax(0,1fr))" in source
    assert ".gt159-notes{grid-template-columns:repeat(2,minmax(0,1fr))" in source

    assert ".gt159-teamgrid{grid-template-columns:1fr}" not in source
    assert ".gt159-badges{grid-template-columns:1fr}" not in source
    assert ".gt159-notes{grid-template-columns:1fr}" not in source
    assert ".gt159-stepgrid{grid-template-columns:1fr}" not in source
    assert ".gt159-finalgrid{grid-template-columns:repeat(2,minmax(0,1fr))}" not in source
