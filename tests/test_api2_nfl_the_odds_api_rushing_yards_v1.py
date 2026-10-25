from __future__ import annotations

from datetime import datetime, timezone

from sports_api.collectors import nfl_the_odds_api_rushing_yards_v1 as collector


def _game():
    return {
        "source_game_id": "2026_08_PIT_NO",
        "away": "PIT",
        "home": "NO",
        "away_name": "Pittsburgh Steelers",
        "home_name": "New Orleans Saints",
    }


def test_missing_credential_is_technical_unavailable_not_verified_absence(monkeypatch):
    for name in ("THE_ODDS_API_KEY", "KYRE_THE_ODDS_API_KEY", "ODDS_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    result = collector.collect_the_odds_api_game_markets(_game(), timeout=1)
    assert result["state"] == "ALL_SOURCES_UNAVAILABLE"
    assert result["observations"] == []
    assert result["evidence"]["configured"] is False
    assert result["fabricated"] is False


def test_exact_event_player_rush_market_uses_one_priority_book_without_fabricated_identity(monkeypatch):
    monkeypatch.setenv("THE_ODDS_API_KEY", "test-key")
    stamp = datetime.now(timezone.utc).isoformat()
    calls = []

    def fake_get_json(url, *, params, timeout):
        calls.append((url, dict(params), timeout))
        if url.endswith("/events"):
            return ([{
                "id": "event-1",
                "away_team": "Pittsburgh Steelers",
                "home_team": "New Orleans Saints",
            }], None)
        return ({
            "id": "event-1",
            "bookmakers": [
                {
                    "key": "draftkings",
                    "title": "DraftKings",
                    "last_update": stamp,
                    "markets": [{
                        "key": "player_rush_yds",
                        "last_update": stamp,
                        "outcomes": [
                            {"name": "Over", "description": "Kendre Miller", "point": 37.5, "price": -113},
                            {"name": "Under", "description": "Kendre Miller", "point": 37.5, "price": -113},
                        ],
                    }],
                },
                {
                    "key": "fanduel",
                    "title": "FanDuel",
                    "last_update": stamp,
                    "markets": [{
                        "key": "player_rush_yds",
                        "last_update": stamp,
                        "outcomes": [
                            {"name": "Over", "description": "Kendre Miller", "point": 38.5, "price": -110},
                            {"name": "Under", "description": "Kendre Miller", "point": 38.5, "price": -120},
                        ],
                    }],
                },
            ],
        }, None)

    monkeypatch.setattr(collector, "_get_json", fake_get_json)
    result = collector.collect_the_odds_api_game_markets(_game(), timeout=2)

    assert result["state"] == "AVAILABLE"
    assert result["evidence"]["event_match"] == "exact_home_away"
    assert result["evidence"]["market_key"] == "player_rush_yds"
    assert result["evidence"]["sportsbook_line_averaging"] is False
    assert len(result["observations"]) == 1
    row = result["observations"][0]
    assert row["player_name"] == "Kendre Miller"
    assert row["sportsbook"] == "FanDuel"
    assert row["line"] == 38.5
    assert row["over_odds"] == -110
    assert row["under_odds"] == -120
    assert row["provider_event_id"] == "event-1"
    assert "team_abbr" not in row
    assert "position" not in row
    assert calls[1][1]["markets"] == "player_rush_yds"


def test_exact_parsed_event_with_no_requested_market_is_verified_absence_for_that_provider(monkeypatch):
    monkeypatch.setenv("THE_ODDS_API_KEY", "test-key")

    def fake_get_json(url, *, params, timeout):
        if url.endswith("/events"):
            return ([{
                "id": "event-2",
                "away_team": "Pittsburgh Steelers",
                "home_team": "New Orleans Saints",
            }], None)
        return ({"id": "event-2", "bookmakers": []}, None)

    monkeypatch.setattr(collector, "_get_json", fake_get_json)
    result = collector.collect_the_odds_api_game_markets(_game(), timeout=1)
    assert result["state"] == "VERIFIED_NOT_POSTED"
    assert result["evidence"]["provider_event_id"] == "event-2"
    assert result["observations"] == []
