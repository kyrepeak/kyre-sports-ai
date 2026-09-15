from pathlib import Path

import pytest

from sports_api.api import nfl_game_totals_market_v1 as market
from sports_api.collectors import nfl_game_totals_features_v1 as features
from sports_api.nfl_game_totals_projection_v1 import project_game_total
from sports_api.nfl_game_totals_probability_v1 import (
    CERTIFIED_BATCHES,
    CERTIFIED_SIMULATIONS,
    SPORTSBOOK_DISTRIBUTION_INFLUENCE,
    simulate_over_under,
)


GAME = {
    "official_event_id": "401772714",
    "away": {"team_id": "8", "abbr": "DET", "name": "Detroit Lions"},
    "home": {"team_id": "2", "abbr": "BUF", "name": "Buffalo Bills"},
    "neutral_site": False,
    "venue": {"available": True, "name": "Fixture Stadium", "indoor": False},
}

AWAY = {
    "ready": True,
    "official_team_id": "8",
    "abbr": "DET",
    "prior_games": 17,
    "current_games": 2,
    "current_weight": 0.25,
    "ppg": 27.5,
    "papg": 22.0,
    "recent6_pf_pg": 29.0,
    "recent6_pa_pg": 21.5,
}

HOME = {
    "ready": True,
    "official_team_id": "2",
    "abbr": "BUF",
    "prior_games": 17,
    "current_games": 2,
    "current_weight": 0.25,
    "ppg": 28.0,
    "papg": 20.5,
    "recent6_pf_pg": 30.0,
    "recent6_pa_pg": 19.0,
}


def test_market_transport_safety_invariants_are_frozen():
    contract = market.CONTRACT
    assert contract["official_event_id_required"] is True
    assert contract["fuzzy_matching"] is False
    assert contract["synthetic_event_ids"] is False
    assert contract["projection_weight"] == 0.0
    assert contract["market_context_only"] is True
    assert contract["may_modify_projection"] is False
    assert contract["model_probability_input"] is False
    assert contract["stake_sizing_enabled"] is False
    assert contract["wager_actions"] is False


def test_end_to_end_football_pipeline_preserves_identity_and_zero_market_influence():
    vector = features.build_game_totals_feature_vector(GAME, AWAY, HOME)
    projection = project_game_total(vector)
    probability = simulate_over_under(
        projection,
        49.5,
        simulations=50_000,
        batches=5,
        seed=101,
    )

    assert vector["official_event_id"] == projection["official_event_id"] == probability["official_event_id"] == "401772714"
    assert vector["away_team_id"] == projection["away_team_id"] == probability["away_team_id"] == "8"
    assert vector["home_team_id"] == projection["home_team_id"] == probability["home_team_id"] == "2"
    assert vector["sportsbook_projection_influence"] == 0.0
    assert projection["sportsbook_projection_influence"] == 0.0
    assert projection["market_total_used"] is False
    assert probability["sportsbook_projection_influence"] == 0.0
    assert probability["sportsbook_distribution_influence"] == 0.0
    assert probability["market_line_influence_on_distribution"] == 0.0
    assert probability["over_probability"] + probability["under_probability"] == pytest.approx(1.0)


def test_certified_monte_carlo_settings_remain_five_million_twenty_batches():
    assert CERTIFIED_SIMULATIONS == 5_000_000
    assert CERTIFIED_BATCHES == 20
    assert SPORTSBOOK_DISTRIBUTION_INFLUENCE == 0.0


def test_football_modules_do_not_import_market_or_frozen_spread_logic():
    protected = (
        Path("sports_api/collectors/nfl_game_totals_team_profiles_v1.py"),
        Path("sports_api/collectors/nfl_game_totals_features_v1.py"),
        Path("sports_api/nfl_game_totals_projection_v1.py"),
        Path("sports_api/nfl_game_totals_probability_v1.py"),
    )
    forbidden_tokens = (
        "nfl_fanduel_totals_v1",
        "nfl_game_totals_market_v1",
        "nfl_spread",
        "nfl_moneyline",
    )
    for path in protected:
        text = path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            assert token not in text, f"{path} illegally references {token}"


def test_game_totals_is_still_not_attached_to_shared_host_before_step_12():
    health_source = Path("sports_api/api/health.py").read_text(encoding="utf-8")
    assert "nfl_game_totals" not in health_source
    status = market.game_totals_market_status()
    assert status["shared_host_attached"] is False


def test_isolated_router_has_only_game_totals_market_paths():
    paths = [route.path for route in market.router.routes]
    assert paths == [
        "/api/v1/nfl/game-totals/market/status",
        "/api/v1/nfl/game-totals/market",
    ]
