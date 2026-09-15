import pytest
from fastapi import HTTPException

from sports_api.api import nfl_game_totals_analysis_v1 as analysis_api


DATE = "2026-09-20"
EVENT_ID = "401772714"


def _game():
    return {
        "official_event_id": EVENT_ID,
        "kickoff_utc": "2026-09-20T17:00:00+00:00",
        "status": {"state": "pre", "completed": False, "detail": "Scheduled", "pregame": True},
        "away": {"team_id": "8", "abbr": "DET", "name": "Detroit Lions"},
        "home": {"team_id": "2", "abbr": "BUF", "name": "Buffalo Bills"},
        "venue": {
            "available": True,
            "name": "Highmark Stadium",
            "city": "Orchard Park",
            "state": "NY",
            "indoor": False,
        },
        "neutral_site": False,
        "identity_policy": {
            "official_authority": "ESPN",
            "fuzzy_matching": False,
            "synthetic_event_ids": False,
            "synthetic_team_ids": False,
        },
    }


def _slate():
    return {
        "schema_version": "nfl_game_totals_schedule_v1",
        "official_authority": "ESPN",
        "requested_date": DATE,
        "game_count": 1,
        "games": [_game()],
    }


def _profile(team):
    is_away = str(team["team_id"]) == "8"
    return {
        "schema_version": "nfl_game_totals_team_profile_v1",
        "ready": True,
        "official_authority": "ESPN",
        "official_team_id": str(team["team_id"]),
        "abbr": team["abbr"],
        "name": team["name"],
        "season": 2026,
        "prior_season": 2025,
        "prior_games": 17,
        "current_games": 1,
        "current_weight": 1 / 7,
        "ppg": 27.0 if is_away else 30.0,
        "papg": 22.0 if is_away else 20.0,
        "recent6_pf_pg": 28.0 if is_away else 31.0,
        "recent6_pa_pg": 21.0 if is_away else 19.0,
        "sportsbook_projection_influence": 0.0,
        "sportsbook_inputs": [],
    }


def _market(total=47.5):
    return {
        "schema_version": "nfl_game_totals_v1",
        "service": "Kyre Sports API",
        "sport": "nfl",
        "market": "game_total",
        "official_event_id": EVENT_ID,
        "ready": True,
        "market_available": True,
        "books": [
            {
                "official_event_id": EVENT_ID,
                "sportsbook": "FanDuel",
                "provider": "fanduel",
                "provider_event_id": "fd-123",
                "market_id": "total-points",
                "total": total,
                "over_price": -110,
                "under_price": -110,
                "updated_at_utc": "2026-09-20T16:59:00+00:00",
                "line_status": "active",
            }
        ],
        "market_semantics": {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
            "model_probability_input": False,
            "stake_sizing_enabled": False,
            "wager_actions": False,
        },
    }


def _install_dependencies(monkeypatch, market_total=47.5):
    monkeypatch.setattr(analysis_api, "collect_official_nfl_slate", lambda requested: _slate())
    monkeypatch.setattr(
        analysis_api,
        "collect_team_scoring_profile",
        lambda team, requested: _profile(team),
    )
    monkeypatch.setattr(
        analysis_api,
        "_collect_or_reuse_market",
        lambda event_id: _market(market_total),
    )

    captured = {}

    def fake_simulation(projection, total_line, *, simulations, batches, seed):
        captured.update(
            {
                "projection": dict(projection),
                "total_line": total_line,
                "simulations": simulations,
                "batches": batches,
                "seed": seed,
            }
        )
        return {
            "ready": True,
            "official_event_id": projection["official_event_id"],
            "away_team_id": projection["away_team_id"],
            "home_team_id": projection["home_team_id"],
            "projected_total": projection["projected_total"],
            "market_total_line": float(total_line),
            "market_line_role": "evaluation_threshold_only",
            "market_line_influence_on_distribution": 0.0,
            "over_probability": 0.57,
            "under_probability": 0.43,
            "push_probability": 0.0,
            "simulation": {
                "simulations": simulations,
                "batches": batches,
                "seed": seed,
                "monte_carlo_se": 0.0002,
                "max_batch_over_probability_difference": 0.001,
                "converged": True,
            },
            "football_only_distribution": True,
            "sportsbook_projection_influence": 0.0,
            "sportsbook_distribution_influence": 0.0,
            "probability_generated": True,
            "monte_carlo_generated": True,
        }

    monkeypatch.setattr(analysis_api, "simulate_over_under", fake_simulation)
    return captured


def test_analysis_contract_is_public_read_only_and_market_is_threshold_only():
    contract = analysis_api.CONTRACT
    assert contract["exact_event_identity"] is True
    assert contract["sportsbook_projection_influence"] == 0.0
    assert contract["sportsbook_distribution_influence"] == 0.0
    assert contract["market_line_role"] == "evaluation_threshold_only"
    assert contract["stake_sizing_enabled"] is False
    assert contract["wager_actions"] is False
    assert analysis_api.game_totals_analysis_status()["shared_host_attached"] is False


def test_analysis_endpoint_orchestrates_certified_pipeline(monkeypatch):
    captured = _install_dependencies(monkeypatch)
    payload = analysis_api.game_totals_analysis(DATE, EVENT_ID)

    assert payload["ready"] is True
    assert payload["official_event_id"] == EVENT_ID
    assert payload["game"]["away"]["team_id"] == "8"
    assert payload["game"]["home"]["team_id"] == "2"
    assert payload["projection"]["football_only"] is True
    assert payload["projection"]["sportsbook_projection_influence"] == 0.0
    assert payload["market"]["sportsbook"] == "FanDuel"
    assert payload["market"]["total"] == 47.5
    assert payload["probability"]["market_line_role"] == "evaluation_threshold_only"
    assert payload["probability"]["sportsbook_distribution_influence"] == 0.0
    assert payload["safety"]["sportsbook_projection_influence"] == 0.0
    assert payload["safety"]["sportsbook_distribution_influence"] == 0.0
    assert payload["safety"]["stake_sizing_enabled"] is False
    assert payload["safety"]["wager_actions"] is False

    assert captured["total_line"] == 47.5
    assert captured["simulations"] == analysis_api.CERTIFIED_SIMULATIONS == 5_000_000
    assert captured["batches"] == analysis_api.CERTIFIED_BATCHES == 20
    assert captured["seed"] == analysis_api.CERTIFIED_SEED


def test_market_total_cannot_change_fair_projection(monkeypatch):
    _install_dependencies(monkeypatch, 45.5)
    lower = analysis_api.game_totals_analysis(DATE, EVENT_ID)

    _install_dependencies(monkeypatch, 53.5)
    upper = analysis_api.game_totals_analysis(DATE, EVENT_ID)

    assert lower["projection"]["projected_away_points"] == upper["projection"]["projected_away_points"]
    assert lower["projection"]["projected_home_points"] == upper["projection"]["projected_home_points"]
    assert lower["projection"]["projected_total"] == upper["projection"]["projected_total"]
    assert lower["market"]["total"] == 45.5
    assert upper["market"]["total"] == 53.5


def test_analysis_rejects_non_numeric_event_id_before_network(monkeypatch):
    called = {"network": False}

    def network(_):
        called["network"] = True
        return _slate()

    monkeypatch.setattr(analysis_api, "collect_official_nfl_slate", network)
    with pytest.raises(HTTPException) as exc:
        analysis_api.game_totals_analysis(DATE, "DET-BUF")
    assert exc.value.status_code == 422
    assert called["network"] is False


def test_analysis_fails_closed_when_exact_event_is_not_on_official_slate(monkeypatch):
    monkeypatch.setattr(analysis_api, "collect_official_nfl_slate", lambda requested: _slate())
    with pytest.raises(HTTPException) as exc:
        analysis_api.game_totals_analysis(DATE, "401772999")
    assert exc.value.status_code == 404
