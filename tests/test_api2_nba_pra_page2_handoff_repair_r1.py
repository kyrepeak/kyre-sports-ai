from __future__ import annotations

from datetime import datetime, timezone

from nba_pra_page2_api_only_v1 import load_page2_snapshot_v1
from nba_pra_page2_context_v1 import build_page2_context


def _game():
    return {
        "gameStatus": 1,
        "status": "UPCOMING",
        "game_date_phoenix": "2026-10-24",
        "tip_utc": "2026-10-25T02:00:00Z",
        "away_tricode": "GSW",
        "away_name": "Golden State Warriors",
        "home_tricode": "PHX",
        "home_name": "Phoenix Suns",
    }


def _quote():
    return {
        "sportsbook": "FanDuel",
        "line": 42.5,
        "over_price": -110,
        "under_price": -120,
        "provider": "FanDuel",
        "observed_at_utc": "2026-10-24T23:19:30Z",
    }


def test_verified_page1_handoff_keeps_page2_open_when_live_market_refresh_temporarily_misses_player():
    now = datetime(2026, 10, 24, 23, 20, tzinfo=timezone.utc)
    quote = _quote()
    snapshot = load_page2_snapshot_v1(
        "stephencurry",
        now=now,
        selected_player_name="Stephen Curry",
        selected_team="GSW",
        selected_quote=quote,
        schedule_loader=lambda **_: {"verification": "VERIFIED", "games": [_game()], "fabrication": False},
        api_loader=lambda _day: {
            "verification": "VERIFIED",
            "diagnostic_state": "MARKET_REFRESH_TRANSIENT_MISS",
            "observations": [],
            "fabrication": False,
            "sportsbook_projection_influence": 0.0,
        },
        player_context_loader=lambda _day, names, **_: {
            "verification": "VERIFIED",
            "profiles": {
                "stephencurry": {
                    "player_name": "Stephen Curry",
                    "team": "GSW",
                    "position": "G",
                    "current_games": [{"pra": 44.0}],
                    "prior_games": [],
                    "season_baseline": {"pra": 41.0},
                }
            },
            "fabrication": False,
        },
        injury_loader=lambda *_args, **_kwargs: {"verification": "VERIFIED", "players": {}, "fabrication": False},
    )
    assert snapshot["market"]["stephencurry"]["featured_quote"] == quote
    assert snapshot["profiles"]["stephencurry"]["player_name"] == "Stephen Curry"
    assert len(snapshot["games"]) == 1
    context = build_page2_context(snapshot, "stephencurry", selected_quote=quote)
    assert context["state"] == "ready"
    assert context["current_quote"]["sportsbook"] == "FanDuel"
    assert context["current_quote"]["line"] == 42.5


def test_sync_loader_kwargs_forward_only_matching_verified_page1_handoff():
    from nba_pra_page2_sync_v1 import build_handoff_loader_kwargs
    now = datetime(2026, 10, 24, 23, 20, tzinfo=timezone.utc)
    quote = _quote()
    handoff = {"player_key": "stephencurry", "player_name": "Stephen Curry", "team": "GSW", "quote": quote}
    assert build_handoff_loader_kwargs("stephencurry", handoff, quote, now=now) == {
        "now": now,
        "selected_player_name": "Stephen Curry",
        "selected_team": "GSW",
        "selected_quote": quote,
    }


def test_sync_loader_kwargs_ignore_mismatched_player_handoff():
    from nba_pra_page2_sync_v1 import build_handoff_loader_kwargs
    now = datetime(2026, 10, 24, 23, 20, tzinfo=timezone.utc)
    handoff = {"player_key": "kevindurant", "player_name": "Kevin Durant", "team": "PHX", "quote": {"sportsbook": "FanDuel", "line": 30.5}}
    assert build_handoff_loader_kwargs("stephencurry", handoff, None, now=now) == {"now": now}


def test_transient_market_miss_still_fails_closed_without_verified_book_and_numeric_line():
    calls = []
    now = datetime(2026, 10, 24, 23, 20, tzinfo=timezone.utc)
    snapshot = load_page2_snapshot_v1(
        "stephencurry",
        now=now,
        selected_player_name="Stephen Curry",
        selected_team="GSW",
        selected_quote={"sportsbook": "", "line": "not-a-line"},
        schedule_loader=lambda **_: {"verification": "VERIFIED", "games": [_game()]},
        api_loader=lambda _day: {"verification": "VERIFIED", "observations": []},
        player_context_loader=lambda *_args, **_kwargs: calls.append("context") or {"profiles": {}},
    )
    assert snapshot["market"] == {}
    assert snapshot["profiles"] == {}
    assert calls == []
