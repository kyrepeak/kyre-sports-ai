from __future__ import annotations

from pathlib import Path

import nba_data_foundation_v1 as nba


def test_kyre_sports_api_is_primary_page_transport():
    contract = nba.source_contract()
    assert contract["page_transport_primary"] == "KYRE_SPORTS_API"
    assert contract["kyre_api_base_url"] == "https://kyre-sports-api.onrender.com"
    assert contract["kyre_nba_slate_path"] == "/api/v1/nba/over-under/slate"
    assert contract["schedule_primary"] == "NBA_OFFICIAL_CDN"
    assert contract["schedule_fallback"] == "ESPN_NBA_SCOREBOARD"


def test_page_client_calls_kyre_sports_api_before_direct_sources():
    class FakeHTTP:
        def __init__(self): self.calls = []
        def get_json(self, url, *, params=None, headers=None, timeout=8):
            self.calls.append((url, params))
            if url == nba.KYRE_NBA_SLATE_URL:
                return {
                    "data_type": "nba_over_under_step2_slate_v1",
                    "source": "Kyre Sports API",
                    "date": "2026-10-23",
                    "timezone": "America/Phoenix",
                    "games": [{"game_id": "0022600001", "home_abbr": "PHX", "away_abbr": "LAL"}],
                    "totals": [],
                    "market_state": "NOT_CONFIGURED",
                }
            raise AssertionError(f"direct provider should not be called when Kyre API is healthy: {url}")
    http = FakeHTTP()
    slate = nba.NBADataClient(http).slate_for_date("2026-10-23")
    assert slate["source"] == "Kyre Sports API"
    assert slate["games"][0]["game_id"] == "0022600001"
    assert http.calls == [(nba.KYRE_NBA_SLATE_URL, {"date": "2026-10-23"})]


def test_page_client_falls_back_only_after_kyre_api_failure():
    class FakeHTTP:
        def __init__(self): self.calls = []
        def get_json(self, url, *, params=None, headers=None, timeout=8):
            self.calls.append((url, params))
            if url == nba.KYRE_NBA_SLATE_URL:
                raise RuntimeError("hosted API unavailable")
            if url == nba.NBA_OFFICIAL_SCHEDULE_URL:
                return {"leagueSchedule": {"gameDates": [{"games": [{
                    "gameId": "0022600001", "gameStatus": 1, "gameStatusText": "7:00 pm ET",
                    "gameDateTimeUTC": "2026-10-24T02:00:00Z", "arenaName": "Footprint Center", "arenaCity": "Phoenix",
                    "homeTeam": {"teamId": 1610612756, "teamTricode": "PHX", "teamName": "Suns", "wins": 2, "losses": 0},
                    "awayTeam": {"teamId": 1610612747, "teamTricode": "LAL", "teamName": "Lakers", "wins": 1, "losses": 1},
                }]}]}}
            raise AssertionError(url)
    http = FakeHTTP()
    slate = nba.NBADataClient(http).slate_for_date("2026-10-23")
    assert slate["source"] == "DIRECT_FALLBACK"
    assert slate["games"][0]["game_id"] == "0022600001"
    assert [url for url, _ in http.calls] == [nba.KYRE_NBA_SLATE_URL, nba.NBA_OFFICIAL_SCHEDULE_URL]


def test_nba_fastapi_route_is_mounted_through_certified_shared_route_table():
    root = Path(__file__).resolve().parents[1]
    route_path = root / "sports_api" / "api" / "nba_over_under_v1.py"
    provider_path = root / "sports_api" / "nba_over_under_data_v1.py"
    health_path = root / "sports_api" / "api" / "health.py"
    main_path = root / "sports_api" / "main.py"
    assert route_path.exists() and provider_path.exists()
    route = route_path.read_text(encoding="utf-8")
    provider = provider_path.read_text(encoding="utf-8")
    health = health_path.read_text(encoding="utf-8")
    main = main_path.read_text(encoding="utf-8")
    assert 'APIRouter(prefix="/api/v1/nba/over-under"' in route
    assert '@router.get("/slate")' in route
    assert "build_nba_over_under_slate" in route
    assert "NBA_OFFICIAL_SCHEDULE_URL" in provider
    assert "ESPN_SCOREBOARD_URL" in provider
    assert "America/Phoenix" in provider
    assert "sports_api.api.nba_over_under_v1" in health
    assert "router.routes.extend(nba_over_under_router.routes)" in health
    assert "app.include_router(health_router)" in main
    lowered = route.lower() + provider.lower()
    assert "/wnba/" not in lowered
    assert "/nfl/" not in lowered
    assert "/cfb/" not in lowered
    assert "/mlb/" not in lowered
