from sports_api.api import health
from sports_api.api import nfl_game_totals_analysis_v1 as analysis
from sports_api.api import nfl_game_totals_games_v1 as games
from sports_api.api import nfl_game_totals_market_v1 as market


EXPECTED_GAME_TOTALS_ROUTES = (
    "/api/v1/nfl/game-totals/games/status",
    "/api/v1/nfl/game-totals/games",
    "/api/v1/nfl/game-totals/market/status",
    "/api/v1/nfl/game-totals/market",
    "/api/v1/nfl/game-totals/analysis/status",
    "/api/v1/nfl/game-totals/analysis",
)


def _paths():
    return [str(getattr(route, "path", "")) for route in health.router.routes]


def test_complete_game_totals_api_family_is_attached_exactly_once():
    paths = _paths()
    for path in EXPECTED_GAME_TOTALS_ROUTES:
        assert paths.count(path) == 1, f"shared host expected exactly one {path}; got {paths.count(path)}"


def test_game_totals_status_contracts_report_shared_host_attached():
    assert games.game_totals_games_status()["shared_host_attached"] is True
    assert market.game_totals_market_status()["shared_host_attached"] is True
    assert analysis.game_totals_analysis_status()["shared_host_attached"] is True


def test_existing_health_and_frozen_spread_routes_remain_singletons():
    paths = _paths()
    assert paths.count("/health") == 1
    assert paths.count("/api/v1/nfl/spread/market/status") == 1
    assert paths.count("/api/v1/nfl/spread/market") == 1


def test_game_totals_attachment_does_not_duplicate_any_new_path():
    paths = _paths()
    attached = [path for path in paths if path.startswith("/api/v1/nfl/game-totals/")]
    assert len(attached) == len(set(attached)) == len(EXPECTED_GAME_TOTALS_ROUTES)
