from universal_runtime_v5_loader_v11 import resolve_destination
from universal_runtime_v5_state import RuntimeRoute


def _source(market: str) -> str:
    return resolve_destination(RuntimeRoute("nfl", market, {})).source_version


def test_daily_picks_has_explicit_owner_and_never_falls_back() -> None:
    assert _source("daily-picks") == "nfl_daily_picks_hub_v1"
    assert _source("daily-picks") != "nfl_hub_v18"


def test_existing_nfl_destinations_remain_unchanged() -> None:
    assert _source("spread") == "nfl_spread_hub_v8"
    assert _source("passing-yards") == "nfl_passing_yards_hub_v42"
    assert _source("rushing-yards") == "nfl_rushing_yards_hub_v18"
    assert _source("receiving-yards") == "nfl_receiving_yards_hub_v21"
    assert _source("moneyline") == "nfl_hub_v18"
    assert _source("game-total") == "nfl_hub_v18"
