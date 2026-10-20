from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import importlib
from pathlib import Path

from nfl_daily_picks_core_v1 import DailyPickCandidate


NOW = datetime(2026, 10, 20, 2, 30, tzinfo=timezone.utc)
DAY = date(2026, 10, 20)
ROOT = Path(__file__).resolve().parents[1]


def _candidate(*, market_id="spread", side="HOME", line=-3.0, probability=0.64) -> DailyPickCandidate:
    return DailyPickCandidate(
        market_id=market_id,
        market_label={"moneyline": "Moneyline", "spread": "Spread", "game-total": "Game Total"}[market_id],
        game_id="g1",
        game_date=DAY,
        kickoff_at=NOW + timedelta(hours=3),
        team_id="SF",
        opponent_team_id="WAS",
        athlete_id=None,
        subject_label="SF",
        matchup_label="WAS at SF",
        side=side,
        market_line=line,
        model_projection=-5.1 if market_id == "spread" else None,
        model_probability=probability,
        edge_value=0.06,
        source_ready=True,
        source_fresh_at=NOW - timedelta(seconds=15),
        source_age_seconds=15.0,
        data_quality=0.94,
        uncertainty=0.04,
        source_version="certified-v4-fixture",
        reason_components=("Certified source-owned probability",),
        source_grade="CERTIFIED",
        source_state="READY",
        freshness_limit_seconds=300.0,
        metadata=(),
    )


def _obs(line: float, seconds: int) -> dict:
    return {
        "game_id": "g1", "market_id": "spread", "side": "HOME", "book": "FanDuel",
        "price": -110, "line": line, "updated_at": NOW - timedelta(seconds=seconds),
        "verified": True, "provider": "Kyre Sports API",
    }


def test_v4_board_adds_verified_team_identity_and_live_market_tape() -> None:
    page = importlib.import_module("nfl_daily_picks_command_center_v4")
    states = {
        "g1": {
            "state": "scheduled",
            "kickoff_at": NOW + timedelta(hours=3),
            "matchup": "WAS at SF",
            "away_abbr": "WAS",
            "away_team": "Washington Commanders",
            "away_logo": "https://a.espncdn.com/i/teamlogos/nfl/500/wsh.png",
            "home_abbr": "SF",
            "home_team": "San Francisco 49ers",
            "home_logo": "https://a.espncdn.com/i/teamlogos/nfl/500/sf.png",
        }
    }
    board = page.build_premium_board(
        (_candidate(),),
        now_utc=NOW,
        game_states=states,
        observations=(_obs(-3.5, 10),),
        observation_history=(_obs(-3.0, 50),),
    )
    row = board["buckets"]["NEXT GAMES"][0]

    assert row["teams"]["away"]["abbr"] == "WAS"
    assert row["teams"]["away"]["logo"].startswith("https://")
    assert row["teams"]["home"]["abbr"] == "SF"
    move = row["markets"]["spread"]["movement_v4"]
    assert move["ready"] is True
    assert move["previous_value"] == -3.0
    assert move["current_value"] == -3.5
    assert board["sportsbook_projection_influence"] == 0.0


def test_v4_logo_fallback_never_guesses_a_different_team() -> None:
    page = importlib.import_module("nfl_daily_picks_command_center_v4")
    teams = page.team_identity_from_state({"matchup": "WAS at SF", "away_abbr": "WAS", "home_abbr": "SF"})
    assert teams["away"]["abbr"] == "WAS"
    assert teams["away"]["logo"] is None
    assert teams["home"]["abbr"] == "SF"
    assert teams["home"]["logo"] is None


def test_v4_preserves_total_probability_fail_closed_contract() -> None:
    page = importlib.import_module("nfl_daily_picks_command_center_v4")
    total = _candidate(market_id="game-total", side="OVER", line=47.5, probability=0.55)
    board = page.build_premium_board(
        (total,), now_utc=NOW,
        game_states={"g1": {"state": "scheduled", "kickoff_at": NOW + timedelta(hours=3), "away_abbr": "WAS", "home_abbr": "SF"}},
    )
    payload = board["buckets"]["NEXT GAMES"][0]["markets"]["game-total"]
    assert payload["visible"] is True
    assert payload["probability_state"] == "SOURCE_PROBABILITY_UNAVAILABLE"
    assert payload["probability"] is None
    assert payload["parlay_eligible"] is False


def test_v4_runtime_overlay_owns_only_nfl_daily_picks() -> None:
    overlay = importlib.import_module("universal_runtime_v5_loader_nfl_daily_picks_command_v4")
    upstream = importlib.import_module("universal_runtime_v5_loader_nfl_daily_picks_command_v3")
    state = importlib.import_module("universal_runtime_v5_state")
    daily = state.RuntimeRoute("nfl", "daily-picks", {})
    nfl_spread = state.RuntimeRoute("nfl", "spread", {})
    nba_spread = state.RuntimeRoute("nba", "spread", {})

    assert "V4" in overlay.resolve_destination(daily).source_version
    assert overlay.resolve_destination(nfl_spread).source_version == upstream.resolve_destination(nfl_spread).source_version
    assert overlay.resolve_destination(nba_spread).source_version == upstream.resolve_destination(nba_spread).source_version
    assert overlay.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert overlay.MAY_MODIFY_PROJECTION is False


def test_v4_terminal_is_live_refresh_capable_and_app_advances_once() -> None:
    page = importlib.import_module("nfl_daily_picks_command_center_v4")
    terminal = importlib.import_module("streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v4")
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    page_source = (ROOT / "nfl_daily_picks_command_center_v4.py").read_text(encoding="utf-8")

    assert page.LIVE_REFRESH_SECONDS == 15
    assert "fragment" in page_source and "run_every" in page_source
    assert "LIVE MARKET TAPE" in page_source
    assert "TEAM LOGOS" in page.MODEL_VERSION
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v4" in app_source
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v3" in terminal.FROZEN_RUNTIME
