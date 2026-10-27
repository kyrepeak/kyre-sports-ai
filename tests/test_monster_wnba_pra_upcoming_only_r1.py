from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import wnba_pra_api_market_bridge_upcoming_only_r1 as gate

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 27, 23, 0, tzinfo=timezone.utc)
DAY = "2026-10-27"


def _game(game_id: str, away: str, home: str, *, category: str, tip: str) -> dict:
    return {
        "game_id": game_id,
        "game_datetime_eastern": tip,
        "status": {"category": category, "text": category},
        "away": {"full_name": away},
        "home": {"full_name": home},
    }


def _offer(player: str, away: str, home: str, event: str) -> dict:
    return {
        "sportsbook": "FanDuel",
        "player_name": player,
        "stat": "pra",
        "side": "over",
        "line": 20.5,
        "american_odds": -110,
        "market_captured_at_utc": NOW.isoformat(),
        "source_event_id": event,
        "source_market_id": event + "-market",
        "source_offer_id": event + "-offer",
        "away_team": away,
        "home_team": home,
    }


def test_status_and_tip_time_gate_rejects_live_final_and_past_scheduled_games() -> None:
    future = _game("future", "Atlanta Dream", "Golden State Valkyries", category="scheduled", tip="2026-10-27T22:00:00-04:00")
    live = _game("live", "Chicago Sky", "New York Liberty", category="in_progress", tip="2026-10-27T19:00:00-04:00")
    final = _game("final", "Phoenix Mercury", "Seattle Storm", category="final", tip="2026-10-27T16:00:00-04:00")
    stale_scheduled = _game("past", "Dallas Wings", "Las Vegas Aces", category="scheduled", tip="2026-10-27T18:00:00-04:00")

    assert gate._is_upcoming_game(future, now=NOW) is True
    assert gate._is_upcoming_game(live, now=NOW) is False
    assert gate._is_upcoming_game(final, now=NOW) is False
    assert gate._is_upcoming_game(stale_scheduled, now=NOW) is False


def test_started_game_offers_never_enter_the_pra_snapshot() -> None:
    schedule = {
        "season": 2026,
        "games": [
            _game("future", "Atlanta Dream", "Golden State Valkyries", category="scheduled", tip="2026-10-27T22:00:00-04:00"),
            _game("live", "Chicago Sky", "New York Liberty", category="in_progress", tip="2026-10-27T19:00:00-04:00"),
            _game("past", "Dallas Wings", "Las Vegas Aces", category="scheduled", tip="2026-10-27T18:00:00-04:00"),
        ],
    }
    snapshot = {
        "snapshots": [{
            "snapshot_id": "current",
            "provider_id": "fanduel",
            "feed_source": "FanDuel anonymous public WNBA sportsbook JSON",
            "date": DAY,
            "collected_at_utc": NOW.isoformat(),
            "normalized_input_feed": {
                "offers": [
                    _offer("Allisha Gray", "Atlanta Dream", "Golden State Valkyries", "future-event"),
                    _offer("Angel Reese", "Chicago Sky", "New York Liberty", "live-event"),
                    _offer("Paige Bueckers", "Dallas Wings", "Las Vegas Aces", "past-event"),
                ]
            },
        }]
    }

    result = gate._build_snapshot(DAY, schedule, snapshot, now=NOW)
    props = result["player_props"]

    assert set(props["game_id"].tolist()) == {"future"}
    assert set(props["player_name"].tolist()) == {"Allisha Gray"}
    assert result["schedule_games"] == 1
    assert result["matched_games"] == 1
    assert result["live_games_removed"] == 2
    assert result["pregame_gate"]["rule"] == "UPCOMING_GAMES_ONLY"


def test_compatibility_hub_installs_the_upcoming_only_gate() -> None:
    source = (ROOT / "wnba_pra_hub_v3612.py").read_text(encoding="utf-8")
    assert "import wnba_pra_api_market_bridge_upcoming_only_r1 as _upcoming_only" in source
    assert "_upcoming_only.install()" in source
    assert source.index("_upcoming_only.install()") < source.index("active.render_page_snapshot")
