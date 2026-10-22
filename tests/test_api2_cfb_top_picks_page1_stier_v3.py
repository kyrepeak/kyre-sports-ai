from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "sports_api/api/cfb_top_picks_page1_v3.py"
PAGE = ROOT / "cfb_top_picks_page_v14.py"
OVERLAY = ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_v3.py"
APP = ROOT / "app.py"
GATEWAY = ROOT / "kyre_sports_api_vercel_v1.py"


def _load_api():
    assert API.exists(), "CFB Top Picks Page 1 V3 API successor must exist"
    spec = importlib.util.spec_from_file_location("cfb_top_picks_page1_v3_test_target", API)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _game_candidate(rank: int, market: str, probability: float) -> dict:
    selection = {
        "MONEYLINE": "Memphis ML",
        "SPREAD": "Memphis -6.5",
        "TOTAL": "Over 52.5",
    }[market]
    return {
        "candidate_id": f"game-{rank}-{market.lower()}",
        "event_id": f"event-{rank}",
        "market_type": market,
        "selection": selection,
        "line": None if market == "MONEYLINE" else (6.5 if market == "SPREAD" else 52.5),
        "side": "HOME" if market != "TOTAL" else "OVER",
        "american_odds": -110 - rank,
        "sportsbook": "FanDuel",
        "probability": probability,
        "away_team": "East Carolina",
        "home_team": "Memphis",
        "away_record": "4-3",
        "home_record": "6-1",
        "away_logo": "https://example.invalid/ecu.png",
        "home_logo": "https://example.invalid/memphis.png",
        "kickoff_iso": "2026-10-22T23:30:00+00:00",
        "market_timestamp": "2026-10-22T16:20:00+00:00",
    }


def _prop_candidate(rank: int, probability: float, *, source: str = "FanDuel") -> dict:
    return {
        "candidate_id": f"prop-{rank}",
        "event_id": f"prop-event-{rank}",
        "player_id": f"player-{rank}",
        "player_name": f"Player {rank}",
        "team": "Memphis",
        "opponent": "East Carolina",
        "team_logo": "https://example.invalid/memphis.png",
        "opponent_logo": "https://example.invalid/ecu.png",
        "team_record": "6-1",
        "opponent_record": "4-3",
        "away_team": "East Carolina",
        "home_team": "Memphis",
        "away_record": "4-3",
        "home_record": "6-1",
        "market_key": "player_passing_yards",
        "market_label": "Passing Yards",
        "side": "OVER",
        "line": 249.5,
        "american_odds": -115,
        "sportsbook": source,
        "probability": probability,
        "probability_basis": "same_book_devig",
        "kickoff_iso": "2026-10-22T23:30:00+00:00",
        "market_timestamp": "2026-10-22T16:20:00+00:00",
    }


def test_game_top10_is_one_combined_pool_without_market_quotas():
    api = _load_api()
    candidates = []
    markets = ["SPREAD", "TOTAL", "MONEYLINE", "SPREAD", "TOTAL", "SPREAD", "MONEYLINE", "SPREAD", "TOTAL", "SPREAD", "MONEYLINE", "TOTAL"]
    for idx, market in enumerate(markets, start=1):
        candidates.append(_game_candidate(idx, market, 0.80 - idx * 0.01))
    ranked = api.rank_game_candidates(candidates, limit=10)
    assert len(ranked) == 10
    assert [row["market_type"] for row in ranked[:3]] == ["SPREAD", "TOTAL", "MONEYLINE"]
    assert sum(row["market_type"] == "SPREAD" for row in ranked) == 5
    assert all(row["rank"] == i for i, row in enumerate(ranked, start=1))


def test_game_ranking_rejects_blank_cards_and_never_null_to_zero():
    api = _load_api()
    valid = [_game_candidate(i, "MONEYLINE", 0.75 - i * 0.01) for i in range(1, 12)]
    broken = _game_candidate(99, "SPREAD", 0.99)
    broken["sportsbook"] = None
    broken["american_odds"] = None
    broken["home_record"] = None
    ranked = api.rank_game_candidates([broken, *valid], limit=10)
    assert len(ranked) == 10
    assert all(row["candidate_id"] != broken["candidate_id"] for row in ranked)
    assert all(row["american_odds"] not in (None, 0) for row in ranked)
    assert all(row["away_record"] and row["home_record"] for row in ranked)


def test_player_prop_top10_is_complete_and_preserves_exact_book_identity():
    api = _load_api()
    rows = [_prop_candidate(i, 0.78 - i * 0.01) for i in range(1, 13)]
    ranked = api.rank_player_props(rows, limit=10)
    assert len(ranked) == 10
    assert ranked[0]["sportsbook"] == "FanDuel"
    assert ranked[0]["player_id"] == "player-1"
    assert ranked[0]["probability_basis"] == "same_book_devig"
    assert all(row["rank"] == i for i, row in enumerate(ranked, start=1))


def test_same_book_devig_uses_only_the_two_exact_sides_not_cross_book_average():
    api = _load_api()
    over = {"american_odds": -120, "sportsbook": "FanDuel", "line": 249.5, "side": "OVER"}
    under = {"american_odds": 100, "sportsbook": "FanDuel", "line": 249.5, "side": "UNDER"}
    p = api.same_book_devig_probability(over, under)
    assert 0.52 < p < 0.53
    assert api.same_book_devig_probability(over, {**under, "sportsbook": "DraftKings"}) is None
    assert api.same_book_devig_probability(over, {**under, "line": 250.5}) is None


def test_player_id_can_be_explicitly_unreported_but_never_fabricated():
    api = _load_api()
    prop = _prop_candidate(1, 0.70)
    prop["player_id"] = None
    ranked = api.rank_player_props([prop], limit=10)
    assert ranked[0]["player_id"] is None
    assert ranked[0]["player_id_display"] == "ID not reported"


def test_v3_page_is_deliberately_simple():
    assert PAGE.exists(), "CFB Top Picks V14 page must exist"
    text = PAGE.read_text(encoding="utf-8")
    low = text.casefold()
    for token in (
        'PAGE1_ENDPOINT = "/api/v3/cfb/top-picks/page1"',
        "TOP 10 GAME PICKS",
        "TOP 10 PLAYER PROPS",
        "HIT PROBABILITY",
        "ODDS",
        "RECORD",
        "GAME TIME",
        "PLAYER ID",
        "ML",
        "SPREAD",
        "TOTAL",
        "team-logo",
        "player-id",
        "Tap for full analysis",
    ):
        assert token in text
    for deep_module in (
        "WHY THIS PICK",
        "BOOK COMPARISON",
        "LINE MOVEMENT",
        "SOURCE HEALTH",
        "MATCHUP SNAPSHOT",
        "AVAILABILITY",
    ):
        assert deep_module not in text
    for forbidden in ("sportsgameodds", "sgo", "espn bet", "espn"):
        assert forbidden not in low


def test_v3_owns_kyre_gateway_only_and_preserves_v2():
    overlay = OVERLAY.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    gateway = GATEWAY.read_text(encoding="utf-8")
    assert 'importlib.import_module("cfb_top_picks_page_v14")' in overlay
    assert "streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_v3" in app
    assert "cfb_top_picks_page1_v3" in gateway
    assert "cfb_top_picks_page1_v2" in gateway
    assert '"cfb_top_picks_page1_v3": True' in gateway


def test_v3_api_contract_declares_completeness_and_safe_fallbacks():
    text = API.read_text(encoding="utf-8")
    low = text.casefold()
    for token in (
        'APIRouter(prefix="/api/v3/cfb/top-picks"',
        '"application_gateway": "Kyre Sports API"',
        '"game_picks_10_of_10"',
        '"player_props_10_of_10"',
        '"slate_backfill_used"',
        '"slate_dates"',
        '"FanDuel"',
        '"The Odds API"',
        '"consensus_averaging": False',
        '"null_to_zero": False',
        '"fabrication": False',
        "rank_game_candidates",
        "rank_player_props",
        "same_book_devig_probability",
    ):
        assert token in text
    for forbidden in ("sportsgameodds", "sgo", "espn bet", "espn"):
        assert forbidden not in low
