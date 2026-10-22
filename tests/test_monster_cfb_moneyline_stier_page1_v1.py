from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'cfb_moneyline_clean_page_v7.py'
LOADER = ROOT / 'universal_runtime_v5_loader_v17.py'


def _source() -> str:
    assert PAGE.exists(), 'V7 S-tier CFB moneyline page does not exist yet'
    return PAGE.read_text(encoding='utf-8')


def test_v7_is_presentation_only_successor_over_v6():
    src = _source()
    assert 'import cfb_moneyline_clean_page_v6 as prior' in src
    for token in (
        'FROZEN_MONEYLINE_OWNER = prior.FROZEN_MONEYLINE_OWNER',
        'FROZEN_RAW_MODEL = prior.FROZEN_RAW_MODEL',
        'FROZEN_FINAL_MODEL = prior.FROZEN_FINAL_MODEL',
        'SPORTSBOOK_PROJECTION_INFLUENCE = prior.SPORTSBOOK_PROJECTION_INFLUENCE',
        'MAY_MODIFY_PROJECTION = prior.MAY_MODIFY_PROJECTION',
    ):
        assert token in src


def test_v7_replaces_primary_form_controls_and_dropdown_stack():
    src = _source()
    assert 'st.date_input(' not in src
    assert 'st.selectbox(' not in src
    assert 'st.segmented_control(' in src
    assert 'st.tabs(' in src
    assert src.count('st.expander(') <= 1
    for token in ('MATCHUP RAIL', 'ANALYTICS LAB', 'Team Data', 'Model Audit', 'Sources', 'Full Slate'):
        assert token in src


def test_v7_has_s_tier_decision_first_analytics_sections():
    src = _source()
    for token in (
        'DECISION COMMAND CENTER',
        'MODEL DRIVERS',
        'MATCHUP EDGE',
        'WIN PROBABILITY',
        'LIVE MONEYLINE MARKET',
        'BET AT',
        'PRICE WATCH',
        'cfbm7-command',
        'cfbm7-driver',
        'cfbm7-compare',
        'cfbm7-prob',
        'cfbm7-market',
    ):
        assert token in src


def test_v7_uses_verified_existing_data_only_and_no_new_network_provider():
    src = _source().casefold()
    assert 'import requests' not in src
    assert 'import httpx' not in src
    assert 'espn.com' not in src
    assert 'sportsgameodds' not in src
    assert 'sgo' not in src
    assert 'render.com' not in src
    assert 'prior.market_value_verdict' in src
    assert 'prior.human_reason_summary' in src


def test_runtime_loader_routes_moneyline_to_v7_only():
    src = LOADER.read_text(encoding='utf-8')
    assert 'page = importlib.import_module("cfb_moneyline_clean_page_v7")' in src
    assert 'route.sport_id == "cfb" and route.market_id == "moneyline"' in src


def _ready_final():
    return {
        'ready': True,
        'winner_side': 'away',
        'winner_team': 'James Madison',
        'winner_probability_final': 0.60,
        'away_fair_moneyline': -150,
        'home_fair_moneyline': 130,
        'model_tier': 'LEAN',
        'model_grade': 'C',
        'reliability': 0.94,
        'feature_coverage': 0.75,
    }


def test_decision_command_fails_closed_to_price_watch_without_verified_market():
    import cfb_moneyline_clean_page_v7 as page
    html = page._decision_command_html(
        {'away_team': 'James Madison', 'home_team': 'App State'},
        {'confidence': 'MEDIUM'},
        _ready_final(),
    )
    assert 'PRICE WATCH' in html
    assert 'VERIFIED PRICE NEEDED' in html
    assert 'BET AT -' not in html


def test_decision_command_only_uses_existing_certified_value_verdict_for_bet_at():
    import cfb_moneyline_clean_page_v7 as page
    game = {
        'away_team': 'James Madison',
        'home_team': 'App State',
        'sportsbook_moneylines': {
            'DraftKings': {'away': 110, 'home': -130, 'updated_at': '2026-10-21T18:20:00-07:00'}
        },
    }
    html = page._decision_command_html(game, {'confidence': 'MEDIUM'}, _ready_final())
    assert 'BET AT +110 OR BETTER' in html
    assert 'VALUE' in html
    assert 'DraftKings' in html


def test_v7_is_kyre_api_only_and_removes_direct_schedule_model_calls():
    src = _source()
    assert 'KYRE_SPORTS_API_BASE_URL' in src
    assert '/api/v1/cfb/moneyline/page1' in src
    assert 'base.schedule_v3.load_with_diagnostics' not in src
    assert 'base.slate.analyze_game' not in src
    assert 'cfb_universal_next_slate_navigation_v1' not in src
    loader = LOADER.read_text()
    assert 'page = importlib.import_module("cfb_moneyline_clean_page_v7")' in loader
    block = loader.split('if route.sport_id == "cfb" and route.market_id == "moneyline":',1)[1].split('return prior.resolve_destination(route)',1)[0]
    assert 'cfb_universal_next_slate_navigation_v1' not in block
    assert 'cfb_schedule_v1' not in block
