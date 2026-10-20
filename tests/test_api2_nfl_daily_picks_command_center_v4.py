from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


def _live_module():
    try:
        import nfl_daily_picks_live_v4 as live
    except ModuleNotFoundError:
        pytest.fail("V4 Smart Live module is not implemented yet")
    return live


def test_v4_smart_live_contract_constants_and_refresh_cadence():
    live = _live_module()
    assert live.PREGAME_REFRESH_SECONDS == 45
    assert live.LIVE_REFRESH_SECONDS == 20
    assert live.IDLE_REFRESH_SECONDS == 120
    assert live.LIVE_QUOTE_FRESH_SECONDS == 75
    assert live.LIVE_QUOTE_STALE_SECONDS == 120
    assert live.smart_refresh_seconds(["scheduled"]) == 45
    assert live.smart_refresh_seconds(["live", "scheduled"]) == 20
    assert live.smart_refresh_seconds(["final"]) == 120


def test_team_logos_use_existing_canonical_nfl_identity():
    live = _live_module()
    assert live.nfl_team_logo_url("PHI").endswith("/phi.png")
    assert live.nfl_team_logo_url("WAS").endswith("/wsh.png")
    assert "espncdn.com" in live.nfl_team_logo_url("DAL")


def test_live_quote_firewall_requires_explicit_live_verification_and_freshness():
    live = _live_module()
    now = datetime(2026, 10, 20, 3, 0, tzinfo=timezone.utc)
    rows = [
        {"game_id": "g1", "market_id": "spread", "book": "FanDuel", "line": -3.5, "age_seconds": 20, "verified": True, "live_verified": True},
        {"game_id": "g1", "market_id": "moneyline", "book": "DraftKings", "price": -155, "age_seconds": 15, "verified": True, "live_verified": False},
        {"game_id": "g1", "market_id": "game-total", "book": "BetMGM", "line": 47.5, "age_seconds": 90, "verified": True, "live_verified": True},
    ]
    status = live.live_market_firewall("live", rows, game_id="g1", now_utc=now)
    assert status["label"] == "LIVE MARKET VERIFIED"
    assert status["model_label"] == "PREGAME MODEL"
    assert len(status["observations"]) == 1
    assert status["observations"][0]["market_id"] == "spread"

    unavailable = live.live_market_firewall(
        "live",
        [{"game_id": "g1", "age_seconds": 5, "verified": True, "live_verified": False}],
        game_id="g1",
        now_utc=now,
    )
    assert unavailable["label"] == "LIVE ODDS UNAVAILABLE"
    assert unavailable["observations"] == ()


def test_session_line_history_tracks_only_real_changes_and_never_calls_it_opening_line():
    live = _live_module()
    state: dict = {}
    t0 = datetime(2026, 10, 20, 3, 0, tzinfo=timezone.utc)
    quote = {"game_id": "g1", "market_id": "spread", "side": "HOME", "book": "FanDuel", "line": -2.5, "price": -110, "verified": True}
    live.update_session_line_history(state, [quote], now_utc=t0)
    live.update_session_line_history(state, [quote], now_utc=t0 + timedelta(seconds=20))
    moved = dict(quote, line=-3.5)
    live.update_session_line_history(state, [moved], now_utc=t0 + timedelta(seconds=40))
    history = live.session_line_history(state, moved)
    assert len(history) == 2
    movement = live.session_line_movement(history)
    assert movement["ready"] is True
    assert movement["scope"] == "SESSION"
    assert movement["previous_line"] == -2.5
    assert movement["current_line"] == -3.5
    assert movement["delta"] == -1.0
    assert "opening" not in str(movement).lower()


def test_v4_renderer_and_overlay_contract_is_additive_and_fail_closed():
    renderer = Path("nfl_daily_picks_command_center_v4.py")
    loader = Path("universal_runtime_v5_loader_nfl_daily_picks_command_v4.py")
    terminal = Path("streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v4.py")
    app = Path("app.py")
    for path in (renderer, loader, terminal):
        assert path.exists(), f"missing {path}"
    text = renderer.read_text()
    assert "NFL INTELLIGENCE TERMINAL" in text
    assert "LIVE MARKET FEED" in text
    assert "LIVE ODDS UNAVAILABLE" in text
    assert "PREGAME MODEL" in text
    assert "team-logo" in text
    assert "st_autorefresh" in text
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in text
    loader_text = loader.read_text()
    assert "universal_runtime_v5_loader_nfl_daily_picks_command_v3" in loader_text
    assert 'route.sport_id == "nfl" and route.market_id == "daily-picks"' in loader_text
    terminal_text = terminal.read_text()
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v3" in terminal_text
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in terminal_text
    app_text = app.read_text()
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v4" in app_text


def test_v3_source_contract_remains_read_only_zero_sportsbook_influence():
    import nfl_daily_picks_market_v3 as market
    assert market.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0


def test_live_sgo_parser_requires_exact_fresh_pairs_for_each_market():
    live = _live_module()
    now = datetime(2026, 10, 20, 3, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(seconds=20)).isoformat()
    event = {
        "odds": {
            "ml-a": {"periodID": "game", "betTypeID": "ml", "statEntityID": "away", "sideID": "away", "byBookmaker": {"fanduel": {"available": True, "odds": -120, "lastUpdatedAt": fresh}}},
            "ml-h": {"periodID": "game", "betTypeID": "ml", "statEntityID": "home", "sideID": "home", "byBookmaker": {"fanduel": {"available": True, "odds": 105, "lastUpdatedAt": fresh}}},
            "sp-a": {"periodID": "game", "betTypeID": "sp", "statEntityID": "away", "sideID": "away", "byBookmaker": {"fanduel": {"available": True, "odds": -110, "spread": 2.5, "lastUpdatedAt": fresh}}},
            "sp-h": {"periodID": "game", "betTypeID": "sp", "statEntityID": "home", "sideID": "home", "byBookmaker": {"fanduel": {"available": True, "odds": -110, "spread": -2.5, "lastUpdatedAt": fresh}}},
            "ou-o": {"periodID": "game", "betTypeID": "ou", "statEntityID": "all", "sideID": "over", "byBookmaker": {"fanduel": {"available": True, "odds": -105, "overUnder": 47.5, "lastUpdatedAt": fresh}}},
            "ou-u": {"periodID": "game", "betTypeID": "ou", "statEntityID": "all", "sideID": "under", "byBookmaker": {"fanduel": {"available": True, "odds": -115, "overUnder": 47.5, "lastUpdatedAt": fresh}}},
        }
    }
    rows = live._parse_exact_live_pairs(event, "g1", now)
    assert len(rows) == 6
    assert {row["market_id"] for row in rows} == {"moneyline", "spread", "game-total"}
    assert all(row["verified"] is True and row["live_verified"] is True for row in rows)
    home_spread = next(row for row in rows if row["market_id"] == "spread" and row["side"] == "HOME")
    assert home_spread["line"] == -2.5
    total_over = next(row for row in rows if row["market_id"] == "game-total" and row["side"] == "OVER")
    assert total_over["line"] == 47.5


def test_live_sgo_parser_fails_closed_on_missing_pair_or_stale_quote():
    live = _live_module()
    now = datetime(2026, 10, 20, 3, 0, tzinfo=timezone.utc)
    stale = (now - timedelta(seconds=130)).isoformat()
    event = {
        "odds": {
            "sp-a": {"periodID": "game", "betTypeID": "sp", "statEntityID": "away", "sideID": "away", "byBookmaker": {"fanduel": {"available": True, "odds": -110, "spread": 3.5, "lastUpdatedAt": stale}}},
            "sp-h": {"periodID": "game", "betTypeID": "sp", "statEntityID": "home", "sideID": "home", "byBookmaker": {"fanduel": {"available": True, "odds": -110, "spread": -3.5, "lastUpdatedAt": stale}}},
            "ml-a-only": {"periodID": "game", "betTypeID": "ml", "statEntityID": "away", "sideID": "away", "byBookmaker": {"fanduel": {"available": True, "odds": -120, "lastUpdatedAt": stale}}},
        }
    }
    rows = live._parse_exact_live_pairs(event, "g1", now)
    assert {row["market_id"] for row in rows} == {"spread"}
    assert all(row["verified"] is False and row["live_verified"] is False for row in rows)
