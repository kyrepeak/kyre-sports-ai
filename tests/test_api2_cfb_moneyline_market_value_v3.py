from pathlib import Path
import importlib
import math


def test_v3_module_exists_and_preserves_frozen_model_contract():
    m = importlib.import_module('cfb_moneyline_clean_page_v3')
    assert m.FROZEN_MONEYLINE_OWNER == 'cfb_moneyline_hub_v5'
    assert m.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert m.MAY_MODIFY_PROJECTION is False


def test_american_implied_probability_is_correct():
    m = importlib.import_module('cfb_moneyline_clean_page_v3')
    assert math.isclose(m.american_implied_probability(-123), 123 / 223, rel_tol=1e-9)
    assert math.isclose(m.american_implied_probability(120), 100 / 220, rel_tol=1e-9)


def test_market_verdict_waits_when_no_verified_price():
    m = importlib.import_module('cfb_moneyline_clean_page_v3')
    final = {'ready': True, 'winner_probability_final': 0.551, 'winner_team': 'FIU', 'home_fair_moneyline': -123, 'away_fair_moneyline': 123}
    out = m.market_value_verdict({}, final)
    assert out['verdict'] == 'WAIT FOR PRICE'
    assert out['best_price'] is None
    assert out['edge_pp'] is None


def test_market_verdict_uses_best_verified_price_for_selected_side():
    m = importlib.import_module('cfb_moneyline_clean_page_v3')
    game = {'sportsbook_moneylines': {'FanDuel': {'home': -105, 'away': -115, 'updated_at': '2026-10-19T00:00:00Z'}, 'Book B': {'home': 100, 'away': -120, 'updated_at': '2026-10-19T00:00:00Z'}}}
    final = {'ready': True, 'winner_probability_final': 0.551, 'winner_team': 'FIU', 'home_fair_moneyline': -123, 'away_fair_moneyline': 123}
    out = m.market_value_verdict(game, final, winner_side='home')
    assert out['best_book'] == 'Book B'
    assert out['best_price'] == 100
    assert out['edge_pp'] > 5.0
    assert out['verdict'] == 'VALUE'


def test_market_verdict_passes_when_price_is_worse_than_model():
    m = importlib.import_module('cfb_moneyline_clean_page_v3')
    game = {'sportsbook_moneylines': {'FanDuel': {'home': -145, 'away': 125}}}
    final = {'ready': True, 'winner_probability_final': 0.551, 'winner_team': 'FIU', 'home_fair_moneyline': -123, 'away_fair_moneyline': 123}
    out = m.market_value_verdict(game, final, winner_side='home')
    assert out['verdict'] == 'PASS — PRICE TOO EXPENSIVE'
    assert out['edge_pp'] < 0


def test_human_reason_summary_names_team_and_direction():
    m = importlib.import_module('cfb_moneyline_clean_page_v3')
    raw = {'ready': True, 'components': {'home_base_points': 4.4, 'away_base_points': 0.0, 'home_recent_adjustment': 0.0, 'away_recent_adjustment': 0.0, 'home_efficiency_adjustment': -1.3, 'away_efficiency_adjustment': 0.0, 'home_turnover_adjustment': -3.0, 'away_turnover_adjustment': 0.0, 'home_schedule_adjustment': 0.0, 'away_schedule_adjustment': 0.0, 'home_field_adjustment': 2.5, 'away_field_adjustment': 0.0}}
    final = {'ready': True, 'winner_team': 'FIU'}
    summary = m.human_reason_summary(raw, final, winner_side='home')
    assert 'FIU' in summary
    assert 'scoring' in summary.lower()
    assert 'home' in summary.lower()
    assert 'turnover' in summary.lower()


def test_premium_v3_contains_customer_facing_sections_and_no_raw_audit_heading():
    src = Path('cfb_moneyline_clean_page_v3.py').read_text()
    for token in ('BET VERDICT', 'BEST VERIFIED PRICE', 'WHY THIS SIDE', 'MATCHUP SNAPSHOT', 'DATA FRESHNESS'):
        assert token in src
    assert 'SELECTED MONEYLINE MATCHUPIDENTITY VERIFIED' not in src
    assert 'STEP 5' not in src
    assert 'STEP 6' not in src


def test_v15_routes_only_cfb_moneyline_to_v3_and_preserves_cfb_wrapper():
    src = Path('universal_runtime_v5_loader_v15.py').read_text()
    assert 'cfb_moneyline_clean_page_v3' in src
    assert 'install_cfb_next_slate_date_bridge' in src
    assert 'install_universal_tap_only_selectboxes' in src
    assert 'market_id == "moneyline"' in src


def test_runtime_handoff_points_to_v15():
    src = Path('streamlit_memory_lazy_router_universal_runtime_v5.py').read_text()
    assert 'from universal_runtime_v5_loader_v15 import choose_prefetch, load_destination, resolve_destination' in src


def test_v3_prefers_exact_fanduel_provider_event_enricher():
    src = Path('cfb_moneyline_clean_page_v3.py').read_text()
    assert 'cfb_game_total_page1_v2_step4_side_market_completeness_v1' in src
    assert 'enrich_verified_side_market' in src
