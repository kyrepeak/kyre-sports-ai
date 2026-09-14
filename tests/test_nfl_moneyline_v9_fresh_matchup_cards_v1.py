from __future__ import annotations

import inspect

import nfl_hub_v18 as router
import nfl_moneyline_hub_v9 as page


def test_v9_is_presentation_only_over_frozen_v8():
    assert page.PRESENTATION_ONLY is True
    assert page.MATCHUP_CARD_FIRST is True
    assert page.FROZEN_ENGINE == "nfl_moneyline_hub_v8"
    assert page.SPORTSBOOK_MODEL_INFLUENCE == 0.0
    assert page.STAKE_SIZING_ENABLED is False


def test_v9_runs_then_clears_frozen_legacy_surface():
    source = inspect.getsource(page._run_frozen_engine)
    assert "frozen.render_nfl_moneyline_hub()" in source
    assert "legacy.empty()" in source


def test_v9_render_owns_no_analytical_formulas():
    source = inspect.getsource(page)
    forbidden = (
        "np.random",
        "random.normal",
        "default_rng",
        "_expected_return(",
        "_fair_american(",
        "QUALIFIED_EDGE =",
        "QUALIFIED_EV =",
        "LEAN_EDGE =",
        "MAX_COMFORTABLE_INTERVAL =",
        "monte_carlo_simulate",
        "simulate_moneyline",
    )
    for token in forbidden:
        assert token not in source, token


def test_matchup_card_contains_new_visual_contract():
    game = {
        "game_id": "401000001",
        "away_team": "Away Team",
        "home_team": "Home Team",
        "away_abbr": "AWY",
        "home_abbr": "HME",
        "away_record": "1-0",
        "home_record": "1-0",
        "season_type": "Regular Season",
        "tip_et": "8:15 PM ET",
        "venue": "Example Stadium",
        "broadcast": "ABC",
    }
    edge = {
        "away": {"ready": True, "model_p": .54, "market_p": .50, "edge": .04, "fair_ml": -117, "best_price": -110, "best_book": "FanDuel", "ev": .03, "conservative_edge": .01, "conservative_ev": .01},
        "home": {"ready": True, "model_p": .46, "market_p": .50, "edge": -.04, "fair_ml": 117, "best_price": 105, "best_book": "DraftKings", "ev": -.05, "conservative_edge": -.07, "conservative_ev": -.08},
    }
    final = {
        "state": "LEAN / WATCH",
        "leader_side": "away",
        "away_grade": {"grade": "LEAN / WATCH"},
        "home_grade": {"grade": "NO PLAY"},
        "prerequisites": {"calibration_quality": "HIGH", "market_quality": "HIGH", "reasons": []},
    }
    mc = {"converged": True, "simulations": 5_000_000, "p05_probability": .49, "p95_probability": .59}
    snap = {"quality": "HIGH"}
    contexts = {
        "AWY": {"depth_state": "VERIFIED", "injury_state": "VERIFIED", "qbs": [{"name": "Away QB", "injury_status": "No listed injury"}]},
        "HME": {"depth_state": "VERIFIED", "injury_state": "VERIFIED", "qbs": [{"name": "Home QB", "injury_status": "No listed injury"}]},
    }
    html = page._matchup_html(game, final, edge, mc, snap, contexts, {})
    assert 'class="kml9-matchup-card"' in html
    assert html.count('class="kml9-team-panel') == 2
    assert "MODEL P(WIN)" in html
    assert "MARKET NO-VIG" in html
    assert "EDGE" in html
    assert "EV / 1U" in html
    assert "FINAL MONEYLINE STATE" in html
    assert "Moneyline Command Center" not in html
    assert "STEP 1A PASSED" not in html


def test_nfl_router_advances_only_moneyline_to_v9():
    source = inspect.getsource(router.render_nfl_hub)
    assert 'if market == "Moneyline"' in source
    assert "from nfl_moneyline_hub_v9 import render_nfl_moneyline_hub" in source
    assert "return base.render_nfl_hub(market)" in source


def test_nfl_router_preserves_v8_descendant_cert_anchor():
    source = inspect.getsource(router)
    runtime = inspect.getsource(router.render_nfl_hub)
    assert "from nfl_moneyline_hub_v8 import render_nfl_moneyline_hub" in source
    assert "from nfl_moneyline_hub_v9 import render_nfl_moneyline_hub" in runtime
