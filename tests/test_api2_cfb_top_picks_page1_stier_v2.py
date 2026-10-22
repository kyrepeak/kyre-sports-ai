from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "sports_api/api/cfb_top_picks_page1_v2.py"
PAGE = ROOT / "cfb_top_picks_page_v13.py"
TERMINAL = ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1.py"
VERCEL = ROOT / "kyre_sports_api_vercel_v1.py"


def _load_api():
    assert API.exists(), "CFB Top Picks Page 1 V2 API successor must exist"
    spec = importlib.util.spec_from_file_location("cfb_top_picks_page1_v2_test_target", API)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _game() -> dict:
    return {
        "game_id": "ncaa-memphis",
        "identity_key": "ncaa-memphis",
        "away_team": "East Carolina",
        "home_team": "Memphis",
        "away_logo": "https://example.invalid/ecu.png",
        "home_logo": "https://example.invalid/memphis.png",
        "kickoff_iso": "2026-10-22T19:30:00+00:00",
        "market_quotes": [
            {
                "sportsbook": "FanDuel",
                "away_price": 330,
                "home_price": -420,
                "observed_at_utc": "2026-10-22T14:05:00+00:00",
                "provider_event_id": "fd-1",
                "provider_market_id": "fdm-1",
                "opening_away_price": 300,
                "opening_home_price": -380,
            },
            {
                "sportsbook": "DraftKings",
                "away_price": 320,
                "home_price": -410,
                "observed_at_utc": "2026-10-22T14:06:00+00:00",
                "provider_event_id": "dk-1",
                "provider_market_id": "dkm-1",
            },
        ],
    }


def _analysis() -> dict:
    return {
        "away": {
            "record_text": "3-4",
            "record": {"wins": 3, "losses": 4, "games": 7},
            "away_record": {"wins": 1, "losses": 3, "games": 4},
            "recent_form": "2-3",
            "recent_record": {"wins": 2, "losses": 3, "games": 5},
            "ppg": 24.0,
            "points_allowed_pg": 29.0,
            "point_diff_pg": -5.0,
            "sos_opponent_win_pct": 0.48,
            "official_stats": {
                "turnover_margin": {"value_numeric": -0.5},
            },
        },
        "home": {
            "record_text": "6-1",
            "record": {"wins": 6, "losses": 1, "games": 7},
            "home_record": {"wins": 4, "losses": 0, "games": 4},
            "recent_form": "4-1",
            "recent_record": {"wins": 4, "losses": 1, "games": 5},
            "ppg": 35.0,
            "points_allowed_pg": 20.0,
            "point_diff_pg": 15.0,
            "sos_opponent_win_pct": 0.55,
            "official_stats": {
                "turnover_margin": {"value_numeric": 1.0},
            },
        },
        "final": {
            "ready": True,
            "final_pick_ready": True,
            "winner_side": "home",
            "winner_team": "Memphis",
            "winner_probability_final": 0.777,
            "home_fair_moneyline": -348,
            "away_fair_moneyline": 348,
            "reliability": 0.938,
        },
    }


def test_v2_keeps_frozen_v1_ranking_but_adds_verified_decision_intelligence():
    api = _load_api()
    rows = api.rank_moneyline_games_v2([_game()], {"ncaa-memphis": _analysis()}, limit=10)
    assert len(rows) == 1
    pick = rows[0]
    assert pick["pick"] == "Memphis"
    assert pick["model_probability"] == 0.777
    assert pick["confidence_score"] >= 80
    assert pick["value_status"] == "PRICE TOO EXPENSIVE"
    assert pick["matchup_snapshot"]["pick_record"] == "6-1"
    assert pick["matchup_snapshot"]["opponent_record"] == "3-4"
    assert pick["reason_factors"]
    why = pick["why"].lower()
    assert "recent" in why
    assert "home" in why
    assert "scoring" in why or "point" in why
    assert "kyre model makes" not in why


def test_v2_preserves_every_book_quote_and_only_reports_real_line_movement():
    api = _load_api()
    pick = api.rank_moneyline_games_v2([_game()], {"ncaa-memphis": _analysis()}, limit=10)[0]
    assert [row["sportsbook"] for row in pick["book_prices"]] == ["FanDuel", "DraftKings"]
    assert pick["book_prices"][0]["price"] == -420
    assert pick["book_prices"][1]["price"] == -410
    assert pick["line_movement"]["sportsbook"] == "FanDuel"
    assert pick["line_movement"]["open_price"] == -380
    assert pick["line_movement"]["current_price"] == -420
    assert pick["line_movement"]["direction"] == "TOWARD PICK"
    assert pick["availability"] is None
    assert "average" not in str(pick).lower()


def test_v2_page_has_s_tier_identity_value_health_filters_and_dynamic_whys():
    assert PAGE.exists(), "CFB Top Picks V13 page must exist"
    text = PAGE.read_text(encoding="utf-8")
    low = text.lower()
    for token in (
        'PAGE1_ENDPOINT = "/api/v2/cfb/top-picks/page1"',
        "CONFIDENCE SCORE",
        "PRICE TOO EXPENSIVE",
        "MODEL VALUE",
        "BOOK COMPARISON",
        "LINE MOVEMENT",
        "AVAILABILITY",
        "SOURCE HEALTH",
        "MATCHUP SNAPSHOT",
        "WHY THIS PICK",
        "High Confidence",
        "Market Movers",
        "team-logo",
    ):
        assert token in text
    for forbidden in ("sportsgameodds", "sgo", "espn bet", "espn"):
        assert forbidden not in low


def test_v2_terminal_and_gateway_switch_only_the_top_picks_successor():
    terminal = TERMINAL.read_text(encoding="utf-8")
    gateway = VERCEL.read_text(encoding="utf-8")
    assert 'route.sport_id == "cfb" and route.market_id == "top-picks"' in terminal
    assert 'importlib.import_module("cfb_top_picks_page_v13")' in terminal
    assert "cfb_top_picks_page1_v2" in gateway
    assert "cfb_top_picks_page1_v1" in gateway
    assert '"cfb_top_picks_page1_v2": True' in gateway
