from __future__ import annotations

import inspect
from pathlib import Path

import nfl_spread_hub_v4 as page


def _game() -> dict:
    return {
        "game_id": "401000001",
        "state": "pre",
        "season_type": "Regular Season",
        "away_team": "Arizona Cardinals",
        "away_abbr": "ARI",
        "away_record": "1-0",
        "away_logo": "https://example.com/ari.png",
        "home_team": "New Orleans Saints",
        "home_abbr": "NO",
        "home_record": "1-0",
        "home_logo": "https://example.com/no.png",
        "tip_et": "1:00 PM ET",
        "venue": "Caesars Superdome",
        "broadcast": "FOX",
    }


def _market() -> dict:
    return {
        "ready": True,
        "reason": "",
        "projection_weight": 0.0,
        "books": [
            {
                "sportsbook": "FanDuel",
                "away_spread": -2.5,
                "away_price": -110,
                "home_spread": 2.5,
                "home_price": -110,
                "age_seconds": 18,
            }
        ],
    }


def _analytics() -> dict:
    return {
        "ready": True,
        "projected_away_margin": 3.2,
        "parameter_se": 1.15,
        "residual_sd": 12.4,
        "model_quality": "HIGH",
        "certified_run": True,
        "converged": True,
        "simulations": 5_000_000,
        "seed": 20260914,
        "simulated_away_margin_mean": 3.1,
        "simulated_away_margin_median": 3.0,
        "away_cover_probability": 0.548,
        "home_cover_probability": 0.442,
        "push_probability": 0.010,
        "away_win_probability": 0.603,
        "margin_quantiles": {"p25": -4.0, "p75": 10.0},
        "sportsbook_projection_influence": 0.0,
    }


def test_v4_is_additive_presentation_over_frozen_v3() -> None:
    assert page.PRESENTATION_ONLY is True
    assert page.MATCHUP_CARD_FIRST is True
    assert page.FROZEN_ANALYTICS == "nfl_spread_hub_v3"
    assert page.FROZEN_MODEL == "nfl_spread_model_v1"
    assert page.FROZEN_MONTE_CARLO == "nfl_spread_mc_v1"
    assert page.FROZEN_TRANSPORT == "nfl_spread_hub_v1"
    assert page.CERTIFIED_SIMULATIONS == 5_000_000
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.MARKET_LINE_ROLE == "settlement_only"
    assert page.RANKINGS_ENABLED is False
    assert page.STAKE_SIZING_ENABLED is False
    assert page.WAGER_ACTIONS_ENABLED is False


def test_team_panels_match_family_structure_and_keep_fair_line_independent() -> None:
    away = page._team_panel(_game(), "away", _market(), _analytics())
    home = page._team_panel(_game(), "home", _market(), _analytics())

    assert "Arizona Cardinals" in away
    assert "New Orleans Saints" in home
    assert "ksp4-team-id" in away
    assert "ksp4-team-id" in home
    assert "FANDUEL SPREAD" in away
    assert "MODEL FAIR SPREAD" in away
    assert "5M COVER" in away
    assert "WIN PROB." in away
    assert "SIM MEDIAN MARGIN" in away
    assert "MARKET FAVORITE" not in away  # compact badge removes redundant prefix
    assert "FAVORITE" in away
    assert "UNDERDOG" in home

    fair_away, fair_home = page._fair_spreads(_analytics())
    assert fair_away == -3.2
    assert fair_home == 3.2


def test_matchup_card_contains_visual_parity_sections_and_safety_copy() -> None:
    html = page._matchup_card(_game(), _market(), _analytics())

    assert 'data-spread-v4="true"' in html
    assert "Arizona Cardinals" in html
    assert "New Orleans Saints" in html
    assert "Caesars Superdome" in html
    assert "MARKET READY" in html
    assert "MODEL HIGH" in html
    assert "MC 5M CERTIFIED" in html
    assert "Support vs Concern" in html
    assert "Supports" in html
    assert "Concerns / Counterweights" in html
    assert "FINAL SPREAD READOUT" in html
    assert "5,000,000 simulations" in html
    assert "market is settlement/comparison only" in html
    assert "sportsbook influence on projection math 0.0%" in html


def test_market_unavailable_keeps_cover_probability_gated() -> None:
    market = {"ready": False, "reason": "No certified line", "books": []}
    html = page._matchup_card(_game(), market, _analytics())
    assert "MARKET UNAVAILABLE" in html
    assert "FANDUEL SPREAD" in html
    assert "—" in html
    assert "Certified pregame FanDuel spread is unavailable; cover probability remains gated." in html


def test_unready_model_fails_closed_without_synthetic_projection() -> None:
    analytics = {
        "ready": False,
        "error": "Independent model not ready.",
        "sportsbook_projection_influence": 0.0,
    }
    html = page._matchup_card(_game(), _market(), analytics)
    assert "MODEL GATED" in html
    assert "FINAL SPREAD READOUT" in html
    assert "GATED" in html
    assert "Independent model not ready." in html
    assert "No synthetic line, projection, or recommendation is created." in html


def test_v4_has_mobile_breakpoints_and_does_not_reimplement_simulator() -> None:
    source = Path("nfl_spread_hub_v4.py").read_text(encoding="utf-8")
    assert "@media(max-width:820px)" in source
    assert "@media(max-width:520px)" in source
    assert "grid-template-columns:1fr" in source
    assert "prior._analytics_for_game" in source
    assert "simulate_game_spread" not in source
    assert "spread_mc.simulate" not in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source


def test_render_owner_is_spread_only() -> None:
    params = inspect.signature(page.render_nfl_hub).parameters
    assert "market" in params
    try:
        page.render_nfl_hub("Moneyline")
    except RuntimeError as exc:
        assert "Spread route" in str(exc)
    else:
        raise AssertionError("V4 must reject non-Spread routes")
