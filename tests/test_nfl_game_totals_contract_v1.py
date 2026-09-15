from sports_api.api import nfl_game_totals_market_v1 as totals


def test_game_totals_contract_is_market_context_only():
    contract = totals.CONTRACT
    assert contract["schema_version"] == "nfl_game_totals_market_v1"
    assert contract["service"] == "Kyre Sports API"
    assert contract["sport"] == "nfl"
    assert contract["market"] == "game_total"
    assert contract["official_authority"] == "ESPN"
    assert contract["official_event_id_required"] is True
    assert contract["fuzzy_matching"] is False
    assert contract["synthetic_event_ids"] is False
    assert contract["projection_weight"] == 0.0
    assert contract["market_context_only"] is True
    assert contract["may_modify_projection"] is False
    assert contract["model_probability_input"] is False
    assert contract["multi_book_capable"] is True
    assert contract["stake_sizing_enabled"] is False
    assert contract["wager_actions"] is False


def test_game_totals_response_shape_is_frozen():
    assert totals.RESPONSE_REQUIRED_FIELDS == (
        "schema_version",
        "service",
        "sport",
        "market",
        "official_event_id",
        "captured_at_utc",
        "ready",
        "market_available",
        "identity",
        "books",
        "market_semantics",
    )
    assert totals.IDENTITY_REQUIRED_FIELDS == (
        "official_authority",
        "official_event_id",
        "provider_event_id",
        "away_team_id",
        "home_team_id",
        "away_abbr",
        "home_abbr",
        "kickoff_delta_seconds",
        "team_name_matching",
        "fuzzy_matching",
        "synthetic_event_ids",
    )
    assert totals.BOOK_REQUIRED_FIELDS == (
        "official_event_id",
        "sportsbook",
        "provider",
        "provider_event_id",
        "market_id",
        "total",
        "over_price",
        "under_price",
        "updated_at_utc",
        "line_status",
    )


def test_status_reports_route_ready_and_shared_host_attached():
    payload = totals.game_totals_market_status()
    assert payload["status"] == "collector_ready"
    assert payload["endpoint"] == "/api/v1/nfl/game-totals/market"
    assert payload["live_market_route_ready"] is True
    assert payload["shared_host_attached"] is True
    assert payload["projection_weight"] == 0.0
    assert payload["wager_actions"] is False


def test_isolated_router_has_status_and_exact_id_market_routes():
    paths = {route.path for route in totals.router.routes}
    assert paths == {
        "/api/v1/nfl/game-totals/market/status",
        "/api/v1/nfl/game-totals/market",
    }
