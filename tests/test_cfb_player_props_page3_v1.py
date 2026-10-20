from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_page3_source_has_required_navigation_and_no_keyboard_inputs():
    source=(ROOT/'cfb_player_props_page3_v1.py').read_text()
    assert '← Back to Game Props' in source
    assert 'clear_page3_selection' in source
    assert '↑ TOP' in source
    assert 'href="#cfbpp3-top"' in source
    assert 'position:fixed' in source
    assert 'st.slider(' in source
    assert 'st.text_input(' not in source
    assert 'st.number_input(' not in source


def test_page3_source_renders_intelligence_sections_and_live_refresh():
    source=(ROOT/'cfb_player_props_page3_v1.py').read_text()
    for text in (
        'PLAYER PROP INTELLIGENCE LAB','Kyre Projection','LINE LAB','SPORTSBOOK BOARD',
        'RECENT PRODUCTION','OPPORTUNITY','OPPONENT DEFENSE','WHY THE MODEL SEES IT THIS WAY',
        'EVIDENCE QUALITY','No verified prior matchup sample.'
    ):
        assert text in source
    assert 'st_autorefresh' in source
    assert 'reline_page3_analysis' in source
    assert 'switch_page3_market' in source
    assert 'st.line_chart' in source


def test_page3_projection_contract_stays_zero_influence():
    import cfb_player_props_page3_v1 as page3
    assert page3.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
