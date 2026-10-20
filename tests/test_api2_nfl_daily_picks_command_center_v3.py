from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import importlib
import importlib.util
from pathlib import Path

from nfl_daily_picks_core_v1 import DailyPickCandidate


NOW = datetime(2026, 10, 19, 18, 0, tzinfo=timezone.utc)
DAY = date(2026, 10, 19)
ROOT = Path(__file__).resolve().parents[1]


def _module(name: str):
    spec = importlib.util.find_spec(name)
    assert spec is not None, f"{name} must exist"
    return importlib.import_module(name)


def _candidate(
    *,
    game_id: str = "g1",
    market_id: str = "moneyline",
    side: str = "HOME",
    team: str = "SF",
    opponent: str = "WAS",
    probability: float = 0.64,
    edge: float = 0.06,
    line: float | None = None,
    kickoff_delta_hours: float = 3.0,
    metadata: tuple[tuple[str, object], ...] = (),
) -> DailyPickCandidate:
    market_label = {
        "moneyline": "Moneyline",
        "spread": "Spread",
        "game-total": "Game Total",
    }[market_id]
    if line is None and market_id == "spread":
        line = -3.0
    if line is None and market_id == "game-total":
        line = 47.5
    projection = None
    if market_id == "spread":
        projection = -5.2
    elif market_id == "game-total":
        projection = 50.1
    return DailyPickCandidate(
        market_id=market_id,
        market_label=market_label,
        game_id=game_id,
        game_date=DAY,
        kickoff_at=NOW + timedelta(hours=kickoff_delta_hours),
        team_id=team,
        opponent_team_id=opponent,
        athlete_id=None,
        subject_label=team,
        matchup_label=f"{opponent} at {team}",
        side=side,
        market_line=line,
        model_projection=projection,
        model_probability=probability,
        edge_value=edge,
        source_ready=True,
        source_fresh_at=NOW - timedelta(seconds=30),
        source_age_seconds=30.0,
        data_quality=0.92,
        uncertainty=0.04,
        source_version=f"certified-{market_id}",
        reason_components=("Certified source-owned probability",),
        source_grade="CERTIFIED",
        source_state="READY",
        freshness_limit_seconds=300.0,
        metadata=metadata,
    )


def test_v3_modules_exist_and_scope_is_three_markets_only() -> None:
    page = _module("nfl_daily_picks_command_center_v3")
    parlay = _module("nfl_daily_picks_parlay_v3")
    market = _module("nfl_daily_picks_market_v3")

    assert page.MARKET_IDS == ("moneyline", "spread", "game-total")
    assert page.DEFAULT_RISK_MODE == "Balanced"
    assert page.RISK_MODES == ("Safe", "Balanced", "Aggressive", "Max Edge")
    assert parlay.DEFAULT_RISK_MODE == "Balanced"
    assert market.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert "passing-yards" not in page.MARKET_IDS
    assert "rushing-yards" not in page.MARKET_IDS
    assert "receiving-yards" not in page.MARKET_IDS


def test_parlay_blocks_direct_contradictions_and_duplicates() -> None:
    parlay = _module("nfl_daily_picks_parlay_v3")
    home_ml = _candidate(side="HOME", team="SF", opponent="WAS")
    away_ml = _candidate(side="AWAY", team="WAS", opponent="SF")
    over = _candidate(
        market_id="game-total",
        side="OVER",
        team="SF",
        opponent="WAS",
        metadata=(("source_probability_certified", True),),
    )
    under = _candidate(
        market_id="game-total",
        side="UNDER",
        team="SF",
        opponent="WAS",
        metadata=(("source_probability_certified", True),),
    )

    assert parlay.validate_parlay_legs((home_ml, home_ml))["allowed"] is False
    assert parlay.validate_parlay_legs((home_ml, away_ml))["allowed"] is False
    assert parlay.validate_parlay_legs((over, under))["allowed"] is False


def test_same_game_correlation_is_conservative_and_cross_game_is_low() -> None:
    parlay = _module("nfl_daily_picks_parlay_v3")
    ml = _candidate(game_id="g1", market_id="moneyline", side="HOME", probability=0.70)
    spread = _candidate(game_id="g1", market_id="spread", side="HOME", probability=0.66)
    other = _candidate(game_id="g2", market_id="spread", side="AWAY", team="CHI", opponent="NE", probability=0.62)

    same = parlay.estimate_parlay_probability((ml, spread))
    cross = parlay.estimate_parlay_probability((ml, other))

    assert same["correlation_grade"] == "HIGH"
    assert same["penalty_points"] == 0.07
    assert same["estimated_probability"] == round((0.70 * 0.66) - 0.07, 6)
    assert cross["correlation_grade"] == "LOW"
    assert cross["penalty_points"] == 0.0
    assert cross["estimated_probability"] == round(0.70 * 0.62, 6)
    assert same["probability_label"] == "estimated parlay probability"


def test_game_total_without_source_owned_probability_is_visible_but_not_parlay_eligible() -> None:
    parlay = _module("nfl_daily_picks_parlay_v3")
    total = _candidate(market_id="game-total", side="OVER", probability=0.61)
    ml = _candidate(game_id="g2", market_id="moneyline", side="HOME")

    result = parlay.validate_parlay_legs((total, ml))
    assert result["allowed"] is False
    assert result["reason"] == "GAME_TOTAL_PROBABILITY_NOT_SOURCE_CERTIFIED"


def test_build_me_a_parlay_respects_risk_mode_leg_bounds() -> None:
    parlay = _module("nfl_daily_picks_parlay_v3")
    candidates = tuple(
        _candidate(
            game_id=f"g{i}",
            market_id="moneyline" if i % 2 else "spread",
            side="HOME",
            team=f"T{i}",
            opponent=f"O{i}",
            probability=0.70 - i * 0.01,
            edge=0.08 - i * 0.004,
        )
        for i in range(1, 8)
    )

    safe = parlay.build_parlay(candidates, "Safe")
    balanced = parlay.build_parlay(candidates, "Balanced")
    aggressive = parlay.build_parlay(candidates, "Aggressive")
    max_edge = parlay.build_parlay(candidates, "Max Edge")

    assert 2 <= len(safe["legs"]) <= 3
    assert 3 <= len(balanced["legs"]) <= 4
    assert 4 <= len(aggressive["legs"]) <= 5
    assert 2 <= len(max_edge["legs"]) <= 6
    assert balanced["risk_mode"] == "Balanced"
    assert balanced["probability_label"] == "estimated parlay probability"


def test_market_board_ignores_unverified_and_stale_books_and_selects_best_price() -> None:
    market = _module("nfl_daily_picks_market_v3")
    observations = [
        {"game_id": "g1", "market_id": "moneyline", "side": "HOME", "book": "FanDuel", "price": -120, "line": None, "updated_at": NOW - timedelta(seconds=60), "verified": True, "opening_line": None},
        {"game_id": "g1", "market_id": "moneyline", "side": "HOME", "book": "DraftKings", "price": -110, "line": None, "updated_at": NOW - timedelta(seconds=45), "verified": True, "opening_line": None},
        {"game_id": "g1", "market_id": "moneyline", "side": "HOME", "book": "BetMGM", "price": 105, "line": None, "updated_at": NOW - timedelta(seconds=30), "verified": False, "opening_line": None},
        {"game_id": "g1", "market_id": "moneyline", "side": "HOME", "book": "Caesars", "price": 100, "line": None, "updated_at": NOW - timedelta(seconds=2000), "verified": True, "opening_line": None},
    ]

    normalized = market.normalize_market_observations(observations, now_utc=NOW, max_age_seconds=900)
    best = market.best_verified_book(normalized, game_id="g1", market_id="moneyline", side="HOME")

    assert [row["book"] for row in normalized] == ["FanDuel", "DraftKings"]
    assert best["ready"] is True
    assert best["book"] == "DraftKings"
    assert best["price"] == -110
    assert best["sportsbook_projection_influence"] == 0.0


def test_market_movement_requires_verified_opening_evidence() -> None:
    market = _module("nfl_daily_picks_market_v3")
    verified = {
        "game_id": "g1", "market_id": "spread", "side": "HOME", "book": "FanDuel",
        "price": -110, "line": -3.0, "updated_at": NOW - timedelta(seconds=20), "verified": True,
        "opening_line": -2.5, "opening_updated_at": NOW - timedelta(hours=8),
    }
    missing_open = dict(verified, opening_line=None, opening_updated_at=None)

    move = market.line_movement(verified)
    unavailable = market.line_movement(missing_open)

    assert move == {"ready": True, "opening_line": -2.5, "current_line": -3.0, "delta": -0.5}
    assert unavailable["ready"] is False


def test_command_center_buckets_live_next_and_all_without_reusing_pregame_as_live() -> None:
    page = _module("nfl_daily_picks_command_center_v3")
    live_candidate = _candidate(game_id="live1", kickoff_delta_hours=-1.0)
    next_candidate = _candidate(game_id="next1", kickoff_delta_hours=3.0, team="CHI", opponent="NE")
    states = {
        "live1": {"state": "live", "kickoff_at": NOW - timedelta(hours=1)},
        "next1": {"state": "scheduled", "kickoff_at": NOW + timedelta(hours=3)},
    }

    board = page.build_command_center_board(
        (live_candidate, next_candidate),
        now_utc=NOW,
        game_states=states,
        observations=(),
    )

    assert board["risk_mode"] == "Balanced"
    assert board["market_ids"] == ("moneyline", "spread", "game-total")
    assert [row["game_id"] for row in board["buckets"]["LIVE NOW"]] == ["live1"]
    assert board["buckets"]["LIVE NOW"][0]["live_recommendation_enabled"] is False
    assert [row["game_id"] for row in board["buckets"]["NEXT GAMES"]] == ["next1"]
    assert {row["game_id"] for row in board["buckets"]["ALL NFL"]} == {"live1", "next1"}


def test_total_stays_visible_as_analytics_when_probability_contract_is_absent() -> None:
    page = _module("nfl_daily_picks_command_center_v3")
    total = _candidate(market_id="game-total", side="OVER", probability=0.50)
    board = page.build_command_center_board((total,), now_utc=NOW, game_states={"g1": {"state": "scheduled", "kickoff_at": NOW + timedelta(hours=3)}}, observations=())

    row = board["buckets"]["NEXT GAMES"][0]["markets"]["game-total"]
    assert row["visible"] is True
    assert row["parlay_eligible"] is False
    assert row["probability_state"] == "SOURCE_PROBABILITY_UNAVAILABLE"


def test_isolated_runtime_overlay_changes_only_nfl_daily_picks() -> None:
    overlay = _module("universal_runtime_v5_loader_nfl_daily_picks_command_v3")
    upstream = _module("universal_runtime_v5_loader_nba_spread_stier_v2")
    state = _module("universal_runtime_v5_state")

    daily = state.RuntimeRoute("nfl", "daily-picks", {})
    nba_spread = state.RuntimeRoute("nba", "spread", {})
    nfl_spread = state.RuntimeRoute("nfl", "spread", {})

    assert "NFL DAILY PICKS COMMAND CENTER V3" in overlay.resolve_destination(daily).source_version
    assert overlay.resolve_destination(nba_spread).source_version == upstream.resolve_destination(nba_spread).source_version
    assert overlay.resolve_destination(nfl_spread).source_version == upstream.resolve_destination(nfl_spread).source_version
    assert overlay.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert overlay.MAY_MODIFY_PROJECTION is False


def test_terminal_router_and_app_advance_only_to_v3_overlay() -> None:
    terminal = _module("streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v3")
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    terminal_source = (ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v3.py").read_text(encoding="utf-8")

    assert "NFL DAILY PICKS COMMAND CENTER V3" in terminal.MODEL_VERSION
    assert terminal.FROZEN_RUNTIME == "streamlit_memory_lazy_router_universal_runtime_v5_nba_spread_v8"
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v3" in app_source
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nba_spread_v8" in terminal_source
    assert "universal_runtime_v5_loader_nfl_daily_picks_command_v3" in terminal_source
