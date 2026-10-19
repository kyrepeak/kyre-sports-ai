from pathlib import Path
import importlib


def test_v4_module_exists_and_preserves_frozen_model_contract():
    m = importlib.import_module('cfb_moneyline_clean_page_v4')
    assert m.FROZEN_MONEYLINE_OWNER == 'cfb_moneyline_hub_v5'
    assert m.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert m.MAY_MODIFY_PROJECTION is False


def test_v4_is_presentation_only_successor_over_v3():
    src = Path('cfb_moneyline_clean_page_v4.py').read_text()
    assert 'import cfb_moneyline_clean_page_v3 as prior' in src
    assert 'market_value_verdict = prior.market_value_verdict' in src
    assert 'human_reason_summary = prior.human_reason_summary' in src


def test_v4_contains_lean_customer_facing_sections_and_prominent_logos():
    src = Path('cfb_moneyline_clean_page_v4.py').read_text()
    for token in ('MONEYLINE DECISION','BET VERDICT','WHY THIS SIDE','DATA FRESHNESS','cfbm4-logo','cfbm4-matchup-hero','cfbm4-decision-grid','cfbm4-reasons','@media(max-width:800px)'):
        assert token in src
    assert 'SELECTED MONEYLINE MATCHUPIDENTITY VERIFIED' not in src
    assert 'STEP 5' not in src
    assert 'STEP 6' not in src


def test_v4_matchup_header_renders_both_team_logos_and_context():
    m = importlib.import_module('cfb_moneyline_clean_page_v4')
    game = {'away_team':'Middle Tenn.','home_team':'FIU','venue':'Pitbull Stadium','broadcast':'ESPN+'}
    away = {'team':'Middle Tenn.'}
    home = {'team':'FIU'}
    html = m._matchup_header(game, away, home, visuals={'away':{'logo':'https://example.com/mt.png'},'home':{'logo':'https://example.com/fiu.png'}}, kickoff='4:00 PM Phoenix')
    for token in ('Middle Tenn.','FIU','https://example.com/mt.png','https://example.com/fiu.png','Pitbull Stadium','4:00 PM Phoenix'):
        assert token in html


def test_v4_reason_cards_are_capped_to_three_for_lean_layout():
    m = importlib.import_module('cfb_moneyline_clean_page_v4')
    raw = {'ready':True,'components':{'home_base_points':4.4,'away_base_points':0.0,'home_recent_adjustment':1.0,'away_recent_adjustment':0.0,'home_efficiency_adjustment':-1.3,'away_efficiency_adjustment':0.0,'home_turnover_adjustment':-3.0,'away_turnover_adjustment':0.0,'home_schedule_adjustment':0.5,'away_schedule_adjustment':0.0,'home_field_adjustment':2.5,'away_field_adjustment':0.0}}
    final = {'ready':True,'winner_team':'FIU'}
    html = m._why_html(raw, final)
    assert html.count('cfbm4-reason ') == 3


def test_v15_routes_cfb_moneyline_to_v4_and_preserves_wrappers():
    src = Path('universal_runtime_v5_loader_v15.py').read_text()
    assert 'cfb_moneyline_clean_page_v4' in src
    assert 'install_cfb_next_slate_date_bridge' in src
    assert 'install_universal_tap_only_selectboxes' in src
    assert 'market_id == "moneyline"' in src


def test_runtime_handoff_stays_on_v15():
    src = Path('streamlit_memory_lazy_router_universal_runtime_v5.py').read_text()
    assert 'from universal_runtime_v5_loader_v15 import choose_prefetch, load_destination, resolve_destination' in src
