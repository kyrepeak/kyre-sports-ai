from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _offer(book="FanDuel", *, player="Rhyne Howard", side="over", line=23.5, odds=-120):
    return {
        "sportsbook": book,
        "provider_id": book.casefold().replace(" ", ""),
        "player_name": player,
        "stat": "pra",
        "side": side,
        "line": line,
        "american_odds": odds,
        "market_captured_at_utc": "2026-10-21T16:50:00+00:00",
        "source_event_id": "evt-gsv-atl",
        "away_team": "Golden State Valkyries",
        "home_team": "Atlanta Dream",
    }


def test_pra_lane_uses_vercel_gateway_without_moving_unrelated_wnba_pages():
    import wnba_api_client_v1 as client
    import wnba_pra_api_market_bridge_v2 as bridge
    import wnba_pra_playoff_context_v1 as playoff

    # The shared legacy client default is intentionally not migrated by this
    # page-scoped repair. PRA explicitly selects the Vercel Kyre gateway.
    assert bridge.PRA_API_BASE_URL == "https://kyre-runless-proof.vercel.app"
    assert playoff.PRA_API_BASE_URL == "https://kyre-runless-proof.vercel.app"
    assert client.KyreWNBAAPIClient(base_url=bridge.PRA_API_BASE_URL).base_url == bridge.PRA_API_BASE_URL

    for rel in ["wnba_pra_api_market_bridge_v2.py", "wnba_pra_playoff_context_v1.py"]:
        source = (ROOT / rel).read_text(encoding="utf-8").casefold()
        assert "onrender.com" not in source
        assert "sportsgameodds" not in source
        assert "espn" not in source
        assert "espn bet" not in source


def test_vercel_wnba_market_router_falls_back_without_averaging():
    from runless_v2 import wnba_pra_market_v1 as market

    calls: list[str] = []

    def fd(*, date: str, season: int):
        calls.append("fanduel")
        return []

    def dk(*, date: str, season: int):
        calls.append("draftkings")
        return [
            _offer("DraftKings", side="over", line=23.5, odds=-120),
            _offer("DraftKings", side="under", line=23.5, odds=-110),
        ]

    result = market.build_pra_market_board(
        date="2026-10-21",
        season=2026,
        fanduel_collector=fd,
        draftkings_collector=dk,
    )

    assert calls == ["fanduel", "draftkings"]
    assert result["state"] == "READY"
    assert result["selected_provider"] == "draftkings"
    assert result["pra_offer_count"] == 2
    assert result["player_count"] == 1
    assert [(r["line"], r["american_odds"], r["side"]) for r in result["offers"]] == [
        (23.5, -120, "over"),
        (23.5, -110, "under"),
    ]


def test_vercel_wnba_market_router_skips_secondary_when_primary_ready():
    from runless_v2 import wnba_pra_market_v1 as market

    calls: list[str] = []

    def fd(*, date: str, season: int):
        calls.append("fanduel")
        return [_offer(side="over"), _offer(side="under", odds=-112)]

    def dk(*, date: str, season: int):
        calls.append("draftkings")
        raise AssertionError("secondary must stay lazy")

    result = market.build_pra_market_board(
        date="2026-10-21",
        season=2026,
        fanduel_collector=fd,
        draftkings_collector=dk,
    )

    assert calls == ["fanduel"]
    assert result["selected_provider"] == "fanduel"
    assert result["sportsbooks"] == ["FanDuel"]


def test_vercel_wnba_schedule_router_is_official_only():
    from runless_v2 import wnba_schedule_v1 as schedule

    payload = {
        "leagueSchedule": {
            "leagueId": "10",
            "gameDates": [
                {
                    "gameDate": "10/21/2026 12:00:00 AM",
                    "games": [
                        {
                            "gameId": "1042600303",
                            "gameCode": "20261021/GSVATL",
                            "gameDateTimeUTC": "2026-10-22T00:00:00Z",
                            "gameDateTimeEst": "2026-10-21T20:00:00Z",
                            "gameStatus": 1,
                            "gameStatusText": "8:00 pm ET",
                            "gameLabel": "WNBA Finals",
                            "gameSubLabel": "Game 3",
                            "seriesText": "Series tied 1-1",
                            "awayTeam": {"teamId": 1611661331, "teamCity": "Golden State", "teamName": "Valkyries", "teamTricode": "GSV"},
                            "homeTeam": {"teamId": 1611661329, "teamCity": "Atlanta", "teamName": "Dream", "teamTricode": "ATL"},
                        }
                    ],
                }
            ],
        }
    }

    result = schedule.build_daily_schedule(
        date="2026-10-21",
        season=2026,
        payload_fetcher=lambda *, season: payload,
    )
    assert result["source"] == "WNBA Official Schedule"
    assert result["game_count"] == 1
    assert result["games"][0]["away"]["team_tricode"] == "GSV"
    assert result["games"][0]["home"]["team_tricode"] == "ATL"
    assert result["games"][0]["competition"]["game_sub_label"] == "Game 3"


def test_runless_app_mounts_wnba_kyre_api_routes_and_prohibited_sources_absent():
    app_source = (ROOT / "runless_v2/app.py").read_text(encoding="utf-8")
    assert "wnba_pra_market_router" in app_source
    assert "wnba_schedule_router" in app_source

    for rel in [
        "runless_v2/wnba_pra_market_v1.py",
        "runless_v2/wnba_schedule_v1.py",
        "wnba_api_client_v1.py",
    ]:
        text = (ROOT / rel).read_text(encoding="utf-8").casefold()
        assert "sportsgameodds" not in text
        assert "espn" not in text
        assert "espn bet" not in text
