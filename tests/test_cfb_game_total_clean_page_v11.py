from pathlib import Path


PAGE = Path(__file__).resolve().parents[1] / "cfb_game_total_clean_page_v11.py"


def _source() -> str:
    assert PAGE.exists(), "V161 successor page must exist"
    return PAGE.read_text(encoding="utf-8")


def test_v161_is_additive_successor_of_v160():
    source = _source()
    assert "cfb_game_total_clean_page_v10" in source
    assert "V161" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source


def test_v161_exposes_visible_seven_day_game_strip():
    source = _source()
    assert "range(7)" in source
    assert "V161_GAME_DAY" in source
    assert "st.columns(7" in source or "st.columns([1] * 7" in source


def test_v161_keeps_frozen_date_engine_and_hides_sidebar_date_picker():
    source = _source()
    assert "date_input" in source
    assert "selected_date" in source
    assert "render_game_total_hub" in source


def test_v161_does_not_render_monster_masthead():
    source = _source()
    assert "_render_v160_masthead()" not in source
