from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MARKET_PATH = ROOT / "cfb_game_total_page1_daily_slate_market_v1.py"
PAGE_PATH = ROOT / "cfb_game_total_page1_daily_slate_v1.py"
ROUTER_PATH = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page1_daily_slate_v1.py"
OUTER_PATH = ROOT / "streamlit_memory_lazy_router_nfl_spread_mobile_repair_v1.py"


def _market():
    assert MARKET_PATH.exists(), "Page 1 market-consensus owner is not implemented yet"
    import cfb_game_total_page1_daily_slate_market_v1 as mod

    return mod


def _obs(
    *,
    game_id: str = "g1",
    book: str = "Book A",
    provider: str | None = None,
    market: str = "game_total",
    phase: str = "pregame",
    value: float = 55.5,
    timestamp: str = "2026-10-17T16:00:00+00:00",
    transport: str = "source_a",
    identity_verified: bool = True,
    side: str | None = None,
) -> dict:
    row = {
        "game_id": game_id,
        "sportsbook": book,
        "provider_id": provider or book.casefold().replace(" ", "_"),
        "market_type": market,
        "phase": phase,
        "value": value,
        "observed_at_utc": timestamp,
        "transport": transport,
        "identity_verified": identity_verified,
        "fabrication": False,
    }
    if side is not None:
        row["side"] = side
    return row


def test_market_owner_does_not_exist_before_implementation() -> None:
    assert MARKET_PATH.exists(), "market owner intentionally missing at RED"


def test_normalization_rejects_unverified_or_wrong_identity() -> None:
    mod = _market()
    assert mod.normalize_market_observation(_obs(identity_verified=False)) is None
    assert mod.normalize_market_observation({**_obs(), "game_id": ""}) is None


def test_duplicate_same_book_across_transports_counts_once() -> None:
    mod = _market()
    rows = [
        _obs(book="FanDuel", transport="espn", timestamp="2026-10-17T15:59:00+00:00", value=56.0),
        _obs(book="FanDuel", transport="kyre", timestamp="2026-10-17T16:00:00+00:00", value=56.0),
    ]
    result = mod.select_observed_consensus(rows, tolerance=0.5)
    assert result["status"] == "VERIFIED"
    assert result["confidence"] == "Limited coverage"
    assert result["independent_source_count"] == 1
    assert result["selected_quote"]["transport"] == "kyre"


def test_consensus_selects_actual_observed_quote_nearest_median() -> None:
    mod = _market()
    rows = [
        _obs(book="A", value=54.5),
        _obs(book="B", value=55.5),
        _obs(book="C", value=57.0),
    ]
    result = mod.select_observed_consensus(rows, tolerance=0.5)
    assert result["selected_quote"]["value"] == 55.5
    assert result["selected_quote"] in [mod.normalize_market_observation(row) for row in rows]
    assert result["synthetic_value"] is False


def test_consensus_tie_prefers_freshest_then_stable_provider_id() -> None:
    mod = _market()
    rows = [
        _obs(book="A", provider="provider_a", value=55.0, timestamp="2026-10-17T15:00:00+00:00"),
        _obs(book="B", provider="provider_b", value=56.0, timestamp="2026-10-17T16:00:00+00:00"),
    ]
    result = mod.select_observed_consensus(rows, tolerance=1.0)
    assert result["selected_quote"]["provider_id"] == "provider_b"

    same_time = [
        _obs(book="A", provider="provider_a", value=55.0),
        _obs(book="B", provider="provider_b", value=56.0),
    ]
    result = mod.select_observed_consensus(same_time, tolerance=1.0)
    assert result["selected_quote"]["provider_id"] == "provider_a"


def test_confidence_strong_mixed_limited_and_unavailable() -> None:
    mod = _market()
    strong = mod.select_observed_consensus(
        [_obs(book="A", value=55.0), _obs(book="B", value=55.5)], tolerance=0.5
    )
    assert strong["confidence"] == "Strong consensus"

    mixed = mod.select_observed_consensus(
        [_obs(book="A", value=54.0), _obs(book="B", value=56.0)], tolerance=0.5
    )
    assert mixed["confidence"] == "Mixed market"

    limited = mod.select_observed_consensus([_obs(book="A", value=55.0)], tolerance=0.5)
    assert limited["confidence"] == "Limited coverage"

    unavailable = mod.select_observed_consensus([], tolerance=0.5)
    assert unavailable["status"] == "UNAVAILABLE"
    assert unavailable["confidence"] == "Unavailable"


def test_opening_pregame_and_live_market_states_remain_separate() -> None:
    mod = _market()
    rows = [
        _obs(book="A", phase="opening", value=52.5, timestamp="2026-10-15T12:00:00+00:00"),
        _obs(book="A", phase="pregame", value=54.5, timestamp="2026-10-17T15:00:00+00:00"),
        _obs(book="A", phase="live", value=61.5, timestamp="2026-10-17T20:00:00+00:00"),
    ]
    context = mod.build_game_market_context("g1", rows)
    assert context["opening"]["game_total"]["selected_quote"]["value"] == 52.5
    assert context["pregame"]["game_total"]["selected_quote"]["value"] == 54.5
    assert context["live"]["game_total"]["selected_quote"]["value"] == 61.5
    assert context["current"]["game_total"]["selected_quote"]["value"] == 54.5


def test_market_specific_tolerances_are_pinned() -> None:
    mod = _market()
    assert mod.SPREAD_TOLERANCE == 0.5
    assert mod.GAME_TOTAL_TOLERANCE == 0.5
    assert mod.MONEYLINE_TOLERANCE == 15.0
    assert mod.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0


def test_moneyline_same_side_is_required_for_consensus() -> None:
    mod = _market()
    rows = [
        _obs(book="A", market="moneyline", side="home", value=-130),
        _obs(book="B", market="moneyline", side="away", value=120),
    ]
    context = mod.build_game_market_context("g1", rows)
    home = context["pregame"]["moneyline_home"]
    away = context["pregame"]["moneyline_away"]
    assert home["independent_source_count"] == 1
    assert away["independent_source_count"] == 1
    assert home["confidence"] == "Limited coverage"
    assert away["confidence"] == "Limited coverage"
