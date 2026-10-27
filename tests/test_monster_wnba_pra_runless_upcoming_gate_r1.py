from __future__ import annotations

from datetime import datetime, timezone

from runless_v2 import wnba_pra_runless_upcoming_gate_r1 as gate

NOW = datetime(2026, 10, 27, 2, 30, tzinfo=timezone.utc)
DATE = "2026-10-27"


def _game(game_id: str, away: str, home: str, *, status: str, start: str) -> dict:
    return {
        "game_id": game_id,
        "game_datetime_utc": start,
        "status": {"category": status},
        "away": {"full_name": away},
        "home": {"full_name": home},
    }


def _offer(player: str, away: str, home: str, side: str) -> dict:
    return {
        "sportsbook": "DraftKings",
        "provider_id": "draftkings",
        "player_name": player,
        "stat": "pra",
        "side": side,
        "line": 20.5,
        "american_odds": -110,
        "market_captured_at_utc": NOW.isoformat(),
        "source_event_id": player.lower().replace(" ", "-") + "-event",
        "away_team": away,
        "home_team": home,
    }


def test_active_runless_gate_rejects_live_final_and_past_tip_offers() -> None:
    schedule = {
        "games": [
            _game("future", "New York Liberty", "Las Vegas Aces", status="scheduled", start="2026-10-27T05:00:00Z"),
            _game("live", "Golden State Valkyries", "Atlanta Dream", status="live", start="2026-10-27T00:00:00Z"),
            _game("final", "Chicago Sky", "Seattle Storm", status="final", start="2026-10-26T22:00:00Z"),
            _game("past", "Dallas Wings", "Phoenix Mercury", status="scheduled", start="2026-10-27T01:00:00Z"),
        ]
    }
    rows = []
    for player, away, home in (
        ("Future Player", "NY Liberty", "Las Vegas Aces"),
        ("Live Player", "GS Valkyries", "ATL Dream"),
        ("Final Player", "Chicago Sky", "Seattle Storm"),
        ("Past Player", "Dallas Wings", "Phoenix Mercury"),
    ):
        rows.extend([_offer(player, away, home, "over"), _offer(player, away, home, "under")])

    calls: list[str] = []
    def fd(*, date: str, season: int):
        calls.append("fanduel")
        return []
    def dk(*, date: str, season: int):
        calls.append("draftkings")
        return rows
    def schedule_builder(*, date: str, season: int):
        return schedule

    result = gate.build_pra_market_board(
        date=DATE,
        season=2026,
        fanduel_collector=fd,
        draftkings_collector=dk,
        schedule_builder=schedule_builder,
        now_utc=NOW,
    )

    assert calls == ["fanduel", "draftkings"]
    assert result["state"] == "READY"
    assert {row["player_name"] for row in result["offers"]} == {"Future Player"}
    assert result["pra_offer_count"] == 2
    assert result["pregame_gate"]["eligible_games"] == 1
    assert result["pregame_gate"]["offers_removed"] == 6


def test_no_upcoming_game_fails_closed_before_any_sportsbook_call() -> None:
    schedule = {
        "games": [
            _game("live", "Golden State Valkyries", "Atlanta Dream", status="live", start="2026-10-27T00:00:00Z"),
            _game("past", "Dallas Wings", "Phoenix Mercury", status="scheduled", start="2026-10-27T01:00:00Z"),
        ]
    }
    calls: list[str] = []
    def collector(*, date: str, season: int):
        calls.append("sportsbook")
        return [_offer("Stale Player", "GS Valkyries", "ATL Dream", "over")]

    result = gate.build_pra_market_board(
        date=DATE,
        season=2026,
        fanduel_collector=collector,
        draftkings_collector=collector,
        schedule_builder=lambda *, date, season: schedule,
        now_utc=NOW,
    )

    assert calls == []
    assert result["state"] == "NO_UPCOMING_WNBA_GAMES"
    assert result["offers"] == []
    assert result["selected_provider"] is None
    assert result["pregame_gate"]["eligible_games"] == 0


def test_schedule_failure_fails_closed_without_sportsbook_calls() -> None:
    calls: list[str] = []
    def collector(*, date: str, season: int):
        calls.append("sportsbook")
        return []
    def bad_schedule(*, date: str, season: int):
        raise RuntimeError("schedule unavailable")

    result = gate.build_pra_market_board(
        date=DATE,
        season=2026,
        fanduel_collector=collector,
        draftkings_collector=collector,
        schedule_builder=bad_schedule,
        now_utc=NOW,
    )

    assert calls == []
    assert result["state"] == "SCHEDULE_UNAVAILABLE"
    assert result["offers"] == []
    assert result["pregame_gate"]["error"] == "RuntimeError"


def test_dependency_injected_provider_routing_tests_remain_backward_compatible() -> None:
    calls: list[str] = []
    def fd(*, date: str, season: int):
        calls.append("fanduel")
        return []
    def dk(*, date: str, season: int):
        calls.append("draftkings")
        return [_offer("Test Player", "GS Valkyries", "ATL Dream", "over"), _offer("Test Player", "GS Valkyries", "ATL Dream", "under")]

    result = gate.build_pra_market_board(
        date=DATE,
        season=2026,
        fanduel_collector=fd,
        draftkings_collector=dk,
    )
    assert calls == ["fanduel", "draftkings"]
    assert result["pra_offer_count"] == 2
