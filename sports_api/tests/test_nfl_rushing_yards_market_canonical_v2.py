from pathlib import Path

from sports_api.collectors import nfl_fanduel_rushing_yards_v1 as frozen
from sports_api.collectors import nfl_fanduel_rushing_yards_v2 as market


def _market(market_type: str, name: str, market_id: str = "m1") -> dict:
    return {
        "marketId": market_id,
        "marketType": market_type,
        "marketName": name,
        "marketStatus": "OPEN",
        "inPlay": False,
        "runners": [],
    }


def test_v2_is_additive_over_frozen_v1_and_keeps_schema():
    assert market.FROZEN_COLLECTOR == "sports_api.collectors.nfl_fanduel_rushing_yards_v1"
    assert market.SCHEMA_VERSION == frozen.SCHEMA_VERSION == "nfl_rushing_yards_market_v1"
    assert frozen.MODEL_VERSION == "NFL RUSHING YARDS MARKET COLLECTOR V1"


def test_standard_fanduel_rushing_yards_families_are_canonical():
    assert market.is_canonical_rushing_yards_market(
        _market("PLAYER_X_RUSHING_YARDS_LOW", "Samaje Perine - Rushing Yds")
    )
    assert market.is_canonical_rushing_yards_market(
        _market("PLAYER_X_RUSHING_YARDS_MEDIUM", "Bucky Irving - Rushing Yds")
    )
    assert market.is_canonical_rushing_yards_market(
        _market("PLAYER_X_RUSHING_YARDS_HIGH", "Chase Brown - Rushing Yds")
    )
    assert market.is_canonical_rushing_yards_market(
        _market("PLAYER_X_RUSHING_YARDS", "Player Rushing Yards")
    )


def test_nonstandard_fanduel_market_families_fail_closed():
    assert not market.is_canonical_rushing_yards_market(
        _market("PLAYER_X_ALT_RUSHING_YARDS_LOW", "Chase Brown - Alt Rushing Yds")
    )
    assert not market.is_canonical_rushing_yards_market(
        _market("PLAYER_X_RUSHING_+_RECEIVING_YARDS", "Chase Brown - Rushing + Receiving Yds")
    )
    assert not market.is_canonical_rushing_yards_market(
        _market("MOST_RUSHING_YARDS", "Most Rushing Yards")
    )
    assert not market.is_canonical_rushing_yards_market(
        _market("TEAM_RUSHING_YARDS", "Cincinnati Bengals - Team Rushing Yards")
    )


def test_market_name_guard_rejects_noncanonical_label_even_if_type_looks_standard():
    assert not market.is_canonical_rushing_yards_market(
        _market("PLAYER_X_RUSHING_YARDS_HIGH", "Chase Brown - Alt Rushing Yds")
    )
    assert not market.is_canonical_rushing_yards_market(
        _market("PLAYER_X_RUSHING_YARDS_MEDIUM", "Bucky Irving - Rushing + Receiving Yds")
    )
    assert not market.is_canonical_rushing_yards_market(
        _market("PLAYER_X_RUSHING_YARDS_LOW", "Most Rushing Yards")
    )


def test_standard_and_rushing_receiving_for_same_player_do_not_enter_same_canonical_set():
    standard = _market(
        "PLAYER_X_RUSHING_YARDS_HIGH",
        "Chase Brown - Rushing Yds",
        "734.185578911",
    )
    rushing_receiving = _market(
        "PLAYER_X_RUSHING_+_RECEIVING_YARDS",
        "Chase Brown - Rushing + Receiving Yds",
        "734.185578845",
    )
    payload = {"attachments": {"markets": [standard, rushing_receiving]}}
    rows = market._canonical_markets(payload)
    assert [row["marketId"] for row in rows] == ["734.185578911"]


def test_live_observed_standard_market_shapes_survive_and_contaminants_do_not():
    observed = [
        _market("PLAYER_X_RUSHING_YARDS_MEDIUM", "Bucky Irving - Rushing Yds", "bucky-standard"),
        _market("PLAYER_X_RUSHING_YARDS_HIGH", "Chase Brown - Rushing Yds", "chase-standard"),
        _market("PLAYER_X_RUSHING_YARDS_LOW", "Kenneth Gainwell - Rushing Yds", "gainwell-standard"),
        _market("PLAYER_X_RUSHING_+_RECEIVING_YARDS", "Bucky Irving - Rushing + Receiving Yds", "bucky-combo"),
        _market("PLAYER_X_RUSHING_+_RECEIVING_YARDS", "Chase Brown - Rushing + Receiving Yds", "chase-combo"),
        _market("PLAYER_X_ALT_RUSHING_YARDS_LOW", "Chase Brown - Alt Rushing Yds", "chase-alt"),
        _market("MOST_RUSHING_YARDS", "Most Rushing Yards", "most-rushing"),
    ]
    rows = market._canonical_markets({"attachments": {"markets": observed}})
    assert {row["marketId"] for row in rows} == {
        "bucky-standard",
        "chase-standard",
        "gainwell-standard",
    }


def test_v2_preserves_frozen_identity_and_market_safety_semantics():
    identity = frozen._identity_contract()
    semantics = frozen._market_semantics()
    assert identity["player_name_matching"] is False
    assert identity["fuzzy_matching"] is False
    assert identity["synthetic_event_ids"] is False
    assert identity["synthetic_player_ids"] is False
    assert semantics["projection_weight"] == 0.0
    assert semantics["market_context_only"] is True
    assert semantics["may_modify_projection"] is False
    assert semantics["probability_enabled"] is False
    assert semantics["fair_odds_enabled"] is False
    assert semantics["ev_enabled"] is False
    assert semantics["grading_enabled"] is False
    assert semantics["stake_sizing_enabled"] is False
    assert semantics["wager_actions"] is False


def test_market_route_owns_v2_without_changing_public_schema_or_path():
    source = Path("sports_api/api/nfl_rushing_yards_market_v1.py").read_text()
    assert "nfl_fanduel_rushing_yards_v2" in source
    assert "nfl_fanduel_rushing_yards_v1 import" not in source
    assert 'prefix="/api/v1/nfl/rushing-yards/market"' in source
    assert '"projection_weight": 0.0' in source
