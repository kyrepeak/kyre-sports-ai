from __future__ import annotations

from sports_api import nfl_rushing_yards_data_truth_v1 as truth


def test_default_rushing_fallback_chain_registers_the_odds_api_only_after_primary():
    names = [name for name, _collector in truth.APPROVED_FALLBACK_COLLECTORS]
    assert names == ["The Odds API"]


def test_identity_incomplete_fallback_quote_cannot_be_promoted_to_player_market():
    def fallback(_game, timeout=8):
        assert timeout == 8
        return {
            "state": "AVAILABLE",
            "observations": [
                {
                    "player_name": "Kendre Miller",
                    "sportsbook": "DraftKings",
                    "market": "Rushing Yards",
                    "line": 37.5,
                    "over_odds": -113,
                    "under_odds": -113,
                    "source_timestamp": "2026-10-25T03:00:00+00:00",
                    "source_provider": "The Odds API",
                    "provider_event_id": "event-1",
                }
            ],
            "evidence": {"event_match": "exact_home_away"},
        }

    primary = truth._bundle(
        "FanDuel",
        "MARKET_MAPPING_FAILURE",
        [],
        reason="legacy collector returned empty without absence proof",
    )
    resolved = truth._apply_fallbacks(
        {"source_game_id": "g1", "away": "PIT", "home": "NO"},
        primary,
        timeout=1,
        fallback_collectors=(("The Odds API", fallback),),
    )

    assert resolved["state"] == "AVAILABLE"
    assert resolved["fallback_used"] is True
    assert [attempt["provider"] for attempt in resolved["provider_attempts"]] == ["FanDuel", "The Odds API"]

    market = truth.market_state_from_bundle(
        resolved,
        player={"player_name": "Kendre Miller", "team_abbr": "NO", "jersey_number": "25", "position": "RB", "active": True},
    )
    assert market["status"] == "DATA_UNAVAILABLE"
    assert market["state"] == "PLAYER_MAPPING_UNAVAILABLE"
    assert market["verified_absence"] is False
    assert market["line"] is None


def test_unverified_primary_empty_invokes_one_field_specific_fallback_and_stops():
    calls: list[str] = []

    def primary(_game, timeout=8):
        calls.append("FanDuel")
        return []

    def fallback(_game, timeout=8):
        assert timeout == 8
        calls.append("The Odds API")
        return {
            "state": "AVAILABLE",
            "observations": [
                {
                    "player_name": "Alvin Kamara",
                    "sportsbook": "FanDuel",
                    "market": "Rushing Yards",
                    "line": 16.5,
                    "over_odds": -113,
                    "under_odds": -113,
                    "source_timestamp": "2026-10-25T03:00:00+00:00",
                    "source_provider": "The Odds API",
                    "provider_event_id": "event-2",
                }
            ],
        }

    original = truth.direct_book.collect_fanduel_game_markets
    try:
        truth.direct_book.collect_fanduel_game_markets = primary
        bundles = truth.collect_markets(
            [{"source_game_id": "g2", "away": "PIT", "home": "NO"}],
            budget_seconds=1.0,
            call_timeout_seconds=1,
            fallback_collectors=(("The Odds API", fallback),),
        )
    finally:
        truth.direct_book.collect_fanduel_game_markets = original

    assert calls == ["FanDuel", "The Odds API"]
    assert bundles["g2"]["state"] == "AVAILABLE"
    assert bundles["g2"]["fallback_used"] is True
