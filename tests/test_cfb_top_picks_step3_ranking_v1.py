from __future__ import annotations

from pathlib import Path

import cfb_top_picks_engine_v1 as engine
import cfb_top_picks_market_context_v1 as markets


PAGE = Path("cfb_top_picks_page_v3.py").read_text(encoding="utf-8")
ROUTER = Path("streamlit_memory_lazy_router_v243.py").read_text(encoding="utf-8")
APP = Path("app.py").read_text(encoding="utf-8")


def test_market_context_extracts_official_spread_total_and_moneyline():
    payload = {
        "events": [{
            "id": "401234567",
            "competitions": [{
                "competitors": [
                    {"homeAway": "away", "team": {"abbreviation": "AWY"}},
                    {"homeAway": "home", "team": {"abbreviation": "HME"}},
                ],
                "odds": [{
                    "provider": {"name": "ESPN BET"},
                    "details": "HME -7.5",
                    "spread": 7.5,
                    "overUnder": 54.5,
                    "awayTeamOdds": {
                        "favorite": False,
                        "moneyLine": 240,
                        "spreadOdds": -105,
                    },
                    "homeTeamOdds": {
                        "favorite": True,
                        "moneyLine": -300,
                        "spreadOdds": -115,
                    },
                }],
            }],
        }],
    }
    board = markets.extract_market_context(payload)
    row = board["401234567"]
    assert row["home_spread"] == -7.5
    assert row["away_spread"] == 7.5
    assert row["total"] == 54.5
    assert row["home_moneyline"] == -300
    assert row["away_moneyline"] == 240
    assert row["projection_weight"] == 0.0
    assert row["may_modify_projection"] is False


def test_spread_candidate_uses_model_margin_distribution_and_market_only_as_threshold():
    analyzed = {
        "game": {
            "espn_event_id": "401",
            "identity_verified": True,
            "date_matches_query": True,
            "away_team": "Away",
            "home_team": "Home",
        },
        "final": {
            "ready": True,
            "projected_margin_home": 10.0,
            "margin_uncertainty": {"sigma": 14.0},
            "reliability": 0.82,
        },
    }
    market = {
        "provider": "ESPN BET",
        "home_spread": -3.5,
        "away_spread": 3.5,
        "home_spread_price": -110,
        "away_spread_price": -110,
    }
    pick = engine._spread_candidate(analyzed, market)
    assert pick is not None
    assert pick["market"] == "SPREAD"
    assert pick["pick"] == "Home -3.5"
    assert 0.50 < pick["probability_value"] < 1.0
    assert pick["sportsbook_projection_weight"] == 0.0


def test_over_under_candidate_uses_existing_ou_model_and_final(monkeypatch):
    game = {
        "espn_event_id": "402",
        "identity_verified": True,
        "date_matches_query": True,
        "away_team": "Away",
        "home_team": "Home",
        "market_line_available": True,
        "market_total": 51.5,
        "market_sportsbook": "FanDuel",
    }
    row = {"game": game, "away": {"team": "Away"}, "home": {"team": "Home"}}

    monkeypatch.setattr(
        engine.ou_model,
        "project_matchup",
        lambda game, away, home, line: {"ready": True, "analysis_line": line},
    )
    monkeypatch.setattr(
        engine.ou_final,
        "synthesize",
        lambda game, raw: {
            "ready": True,
            "rank_eligible": True,
            "selection": "OVER",
            "selection_probability": 0.64,
            "reliability": 0.80,
        },
    )
    pick = engine._ou_candidate(row, {})
    assert pick is not None
    assert pick["market"] == "OVER/UNDER"
    assert pick["pick"] == "Over 51.5"
    assert pick["probability"] == 64


def test_balanced_top_ten_is_unique_by_game_and_spans_all_three_markets():
    candidates = []
    seq = 0
    for market, count in (("MONEYLINE", 6), ("SPREAD", 5), ("OVER/UNDER", 5)):
        for i in range(count):
            seq += 1
            candidates.append({
                "event_id": f"{market}-{i}",
                "market": market,
                "probability_value": 0.90 - (seq * 0.01),
                "reliability": 0.80,
            })
    picks = engine._rank_balanced(candidates, limit=10)
    assert len(picks) == 10
    assert len({row["event_id"] for row in picks}) == 10
    counts = {market: sum(row["market"] == market for row in picks) for market in engine.MARKET_QUOTAS}
    assert counts == {"MONEYLINE": 4, "SPREAD": 3, "OVER/UNDER": 3}
    assert [row["rank"] for row in picks] == list(range(1, 11))
    assert [row["probability_value"] for row in picks] == sorted(
        [row["probability_value"] for row in picks], reverse=True
    )


def test_toughness_is_probability_driven():
    assert engine._toughness(0.72) == (2, "Easy")
    assert engine._toughness(0.65) == (3, "Medium")
    assert engine._toughness(0.56) == (4, "Tough")


def test_step3_page_uses_live_engine_not_step2_sample_rows():
    assert "engine.build_top_picks(limit=10)" in PAGE
    assert "LAYOUT_PREVIEW = False" in PAGE
    assert "LIVE MODEL BOARD" in PAGE
    assert "SAMPLE_LAYOUT_ROWS" not in PAGE


def test_v243_is_additive_over_frozen_v242():
    assert "import streamlit_memory_lazy_router_v242 as prior" in ROUTER
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v242"' in ROUTER
    assert 'TOP_PICKS_PAGE = "cfb_top_picks_page_v3"' in ROUTER
    assert "return prior.render_app()" in ROUTER
    assert "MAY_MODIFY_EXISTING_CFB_PRODUCTS = False" in ROUTER
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in ROUTER


def test_app_activates_v243_and_keeps_v242_frozen_parent():
    assert "from streamlit_memory_lazy_router_v243 import record_bootstrap_import_ms, render_app" in APP
    assert "Frozen V242 compatibility" in APP


def test_step3_engine_preserves_zero_market_projection_weight():
    assert engine.MARKET_PROJECTION_WEIGHT == 0.0
    assert markets.PROJECTION_WEIGHT == 0.0
    assert markets.MAY_MODIFY_PROJECTION is False
