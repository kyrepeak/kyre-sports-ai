from __future__ import annotations

from sports_api.api import cfb_odds_v1
from sports_api.api import health
from sports_api.api import nfl_moneyline_market_v1
from sports_api.api import nfl_passing_yards_market_v1
from sports_api.api import nfl_receiving_yards_context_v1
from sports_api.api import nfl_receiving_yards_market_v1
from sports_api.api import nfl_rushing_yards_context_v1
from sports_api.api import nfl_rushing_yards_context_v2
from sports_api.api import nfl_rushing_yards_market_v1
from sports_api.api import nfl_spread_market_v1


EXPECTED_SHARED_HOST_ROUTES = {
    "/health",
    "/health/ready",
    "/health/details",
    "/api/v1/cfb/markets/status",
    "/api/v1/cfb/markets/current",
    "/api/v1/cfb/markets/feed",
    "/api/v1/cfb/markets/identity-status",
    "/api/v1/cfb/markets/reconciled",
    "/api/v1/cfb/odds/status",
    "/api/v1/cfb/odds",
    "/api/v1/nfl/moneyline/market/status",
    "/api/v1/nfl/moneyline/market",
    "/api/v1/nfl/passing-yards/status",
    "/api/v1/nfl/passing-yards",
    "/api/v1/nfl/receiving-yards/status",
    "/api/v1/nfl/receiving-yards",
    "/api/v1/nfl/receiving-yards/market/status",
    "/api/v1/nfl/receiving-yards/market",
    "/api/v1/nfl/rushing-yards/status",
    "/api/v1/nfl/rushing-yards",
    "/api/v1/nfl/rushing-yards/fast/status",
    "/api/v1/nfl/rushing-yards/fast",
    "/api/v1/nfl/rushing-yards/market/status",
    "/api/v1/nfl/rushing-yards/market",
    "/api/v1/nfl/spread/market/status",
    "/api/v1/nfl/spread/market",
}


def _route_paths() -> set[str]:
    return {str(getattr(route, "path", "")) for route in health.router.routes}


def _assert_market_guardrails(contract: dict) -> None:
    assert contract["projection_weight"] == 0.0
    assert contract["market_context_only"] is True
    assert contract["may_modify_projection"] is False
    assert contract["fuzzy_matching"] is False
    assert contract["synthetic_event_ids"] is False
    assert contract["stake_sizing_enabled"] is False
    assert contract["wager_actions"] is False


def _assert_context_guardrails(contract: dict) -> None:
    assert contract["sportsbook_influence"] == 0.0
    assert contract["model_enabled"] is False
    assert contract["projection_enabled"] is False
    assert contract["market_enabled"] is False
    assert contract["fuzzy_matching"] is False
    assert contract["synthetic_event_ids"] is False
    assert contract["synthetic_player_ids"] is False
    assert contract["stake_sizing_enabled"] is False
    assert contract["wager_actions"] is False


def test_shared_host_route_surface_is_preserved() -> None:
    missing = EXPECTED_SHARED_HOST_ROUTES - _route_paths()
    assert not missing, f"missing restored shared-host routes: {sorted(missing)}"


def test_cfb_public_odds_status_keeps_frozen_market_semantics() -> None:
    payload = cfb_odds_v1.odds_status()
    assert payload["endpoint_ready"] is True
    assert payload["identity_policy"]["synthetic_ids"] is False
    assert payload["identity_policy"]["fuzzy_matching"] is False
    assert payload["identity_policy"]["fail_closed"] is True
    semantics = payload["market_semantics"]
    assert semantics["projection_weight"] == 0.0
    assert semantics["market_context_only"] is True
    assert semantics["may_modify_projection"] is False


def test_nfl_market_status_contracts_are_network_free_and_safe() -> None:
    statuses = [
        nfl_moneyline_market_v1.moneyline_market_status(),
        nfl_passing_yards_market_v1.passing_yards_market_status(),
        nfl_receiving_yards_market_v1.receiving_yards_market_status(),
        nfl_rushing_yards_market_v1.rushing_yards_market_status(),
        nfl_spread_market_v1.spread_market_status(),
    ]
    for payload in statuses:
        assert payload["status"] == "ready"
        _assert_market_guardrails(payload)


def test_nfl_context_status_contracts_are_network_free_and_safe() -> None:
    statuses = [
        nfl_receiving_yards_context_v1.receiving_yards_context_status(),
        nfl_rushing_yards_context_v1.rushing_yards_context_status(),
        nfl_rushing_yards_context_v2.rushing_yards_fast_context_status(),
    ]
    for payload in statuses:
        assert payload["status"] == "ready"
        _assert_context_guardrails(payload)


def test_exact_identity_flags_remain_strict() -> None:
    passing = nfl_passing_yards_market_v1.CONTRACT
    receiving_market = nfl_receiving_yards_market_v1.CONTRACT
    receiving_context = nfl_receiving_yards_context_v1.CONTRACT
    rushing_context = nfl_rushing_yards_context_v1.CONTRACT

    assert passing["official_event_id_required"] is True
    assert passing["official_athlete_id_required"] is True
    assert passing["player_name_matching"] is False
    assert passing["synthetic_player_ids"] is False

    for contract in (receiving_market, receiving_context, rushing_context):
        assert contract["official_event_id_required"] is True
        assert contract["official_athlete_id_required"] is True
        assert contract["official_team_id_required"] is True
        assert contract["player_name_matching"] is False
        assert contract["synthetic_player_ids"] is False


def test_health_probe_remains_provider_free(monkeypatch) -> None:
    # Health must stay lightweight even though it owns the shared-host route table.
    def _provider_call_forbidden(*_args, **_kwargs):
        raise AssertionError("health probe attempted a provider/network collector")

    monkeypatch.setattr(
        nfl_moneyline_market_v1,
        "collect_fanduel_nfl_moneyline",
        _provider_call_forbidden,
    )
    monkeypatch.setattr(
        nfl_passing_yards_market_v1,
        "collect_fanduel_nfl_passing_yards",
        _provider_call_forbidden,
    )
    monkeypatch.setattr(
        nfl_receiving_yards_market_v1,
        "collect_fanduel_nfl_receiving_yards_hosted",
        _provider_call_forbidden,
    )
    monkeypatch.setattr(
        nfl_rushing_yards_market_v1,
        "collect_fanduel_nfl_rushing_yards_hosted",
        _provider_call_forbidden,
    )
    monkeypatch.setattr(
        nfl_spread_market_v1,
        "collect_fanduel_nfl_spread",
        _provider_call_forbidden,
    )

    payload = health.health_check()
    assert payload["status"] == "ok"
    assert payload["service"] == "kyre-sports-api"
    assert "deployment" in payload
