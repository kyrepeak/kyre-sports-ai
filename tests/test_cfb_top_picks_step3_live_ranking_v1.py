from __future__ import annotations

import math
from pathlib import Path

import cfb_top_picks_engine_v1 as engine


def _espn_fixture():
    return {
        "events":[{
            "id":"401",
            "competitions":[{
                "id":"401",
                "competitors":[
                    {"homeAway":"away","team":{"abbreviation":"ALA","displayName":"Alabama"}},
                    {"homeAway":"home","team":{"abbreviation":"TENN","displayName":"Tennessee"}},
                ],
                "odds":[{
                    "provider":{"name":"ESPN BET"},
                    "details":"ALA -3.5",
                    "spread":3.5,
                    "overUnder":52.5,
                    "awayTeamOdds":{"favorite":True,"moneyLine":-165,"spreadOdds":-110},
                    "homeTeamOdds":{"favorite":False,"moneyLine":140,"spreadOdds":-110},
                }],
            }],
        }]
    }


def _game(identity="g1", event_id="401"):
    return {
        "identity_key":identity,
        "espn_event_id":event_id,
        "identity_verified":True,
        "date_matches_query":True,
        "away_team":"Alabama",
        "home_team":"Tennessee",
        "kickoff_iso":"2026-10-03T19:30:00Z",
        "broadcast":"ESPN",
    }


def _ml_row(identity="g1", event_id="401", winner="away", probability=.69, margin=-5.0):
    game=_game(identity,event_id)
    return {
        "game":game,
        "final":{
            "ready":True,
            "final_pick_ready":True,
            "winner_side":winner,
            "winner_team":"Alabama" if winner=="away" else "Tennessee",
            "winner_probability_final":probability,
            "away_fair_moneyline":-223,
            "home_fair_moneyline":223,
            "projected_margin_home":margin,
            "margin_uncertainty":{"sigma":12.0},
            "reliability":.84,
            "feature_coverage":.86,
        },
    }


def _ou_row(identity="g1", event_id="401", probability=.64):
    return {
        "game":_game(identity,event_id),
        "final":{
            "ready":True,
            "rank_eligible":True,
            "selection":"OVER",
            "selection_probability":probability,
            "analysis_line":52.5,
            "reliability":.81,
            "feature_coverage":.83,
        },
    }


def test_espn_parser_extracts_total_moneyline_and_resolved_spread():
    board=engine.extract_espn_market_board(_espn_fixture())
    row=board["401"]
    assert row["total"]==52.5
    assert row["away_moneyline"]==-165
    assert row["home_moneyline"]==140
    assert row["home_spread"]==3.5
    assert row["away_spread"]==-3.5
    assert row["projection_weight"]==0.0


def test_spread_probability_uses_model_margin_and_market_only_as_threshold():
    probability=engine._home_cover_probability(projected_margin_home=7.0,sigma=10.0,home_spread=-3.5)
    assert 0.50 < probability < 1.0
    reverse=engine._home_cover_probability(projected_margin_home=-7.0,sigma=10.0,home_spread=3.5)
    assert reverse < 0.50


def test_moneyline_spread_and_total_candidates_are_real_model_outputs():
    market=engine.extract_espn_market_board(_espn_fixture())
    ml=engine.moneyline_candidates([_ml_row()],market)
    spread=engine.spread_candidates([_ml_row()],market)
    ou=engine.over_under_candidates([_ou_row()])
    assert len(ml)==1
    assert len(spread)==1
    assert len(ou)==1
    assert ml[0]["market"]=="MONEYLINE"
    assert spread[0]["market"]=="SPREAD"
    assert ou[0]["market"]=="OVER/UNDER"
    assert all(row["market_projection_weight"]==0.0 for row in ml+spread+ou)


def test_toughness_gets_harder_as_model_strength_falls():
    easy=engine._toughness(.78,.88,.90)
    medium=engine._toughness(.66,.78,.80)
    tough=engine._toughness(.56,.65,.65)
    assert easy==(2,"Easy")
    assert medium==(3,"Medium")
    assert tough==(4,"Tough")


def test_rank_candidates_returns_exact_top10_by_model_strength():
    candidates=[]
    for i in range(14):
        p=.80-i*.015
        candidates.append({
            "identity":f"g{i}",
            "market":("MONEYLINE","SPREAD","OVER/UNDER")[i%3],
            "probability":p,
            "reliability":.82,
            "coverage":.84,
            "rank_score":engine._rank_score(p,.82,.84),
            "kickoff_iso":f"2026-10-03T{12+i%10:02d}:00:00Z",
        })
    ranked=engine.rank_candidates(candidates,10)
    assert len(ranked)==10
    assert [row["rank"] for row in ranked]==list(range(1,11))
    assert all(ranked[i]["rank_score"]>=ranked[i+1]["rank_score"] for i in range(9))


def test_rank_contract_never_uses_sportsbook_price_or_implied_probability():
    assert engine.MARKET_PROJECTION_WEIGHT==0.0
    assert engine.RANK_WEIGHTS=={"probability":0.75,"reliability":0.15,"coverage":0.10}
    source=Path("cfb_top_picks_engine_v1.py").read_text(encoding="utf-8")
    assert '"sportsbook_probability_used": False' in source
    assert '"sportsbook_price_ranking_weight": 0.0' in source


def test_page_v3_removes_step2_sample_board_from_production_path():
    source=Path("cfb_top_picks_page_v3.py").read_text(encoding="utf-8")
    assert "engine.cached_daily_board(today)" in source
    assert "CFB_TOP_PICKS_BROWSER_FIXTURE" in source
    assert "No qualified model picks are available" in source
    assert "Why This Pick" not in source
    assert "Actual Matchup History" not in source


def test_router_v243_is_additive_and_scoped_only_to_top_picks():
    source=Path("streamlit_memory_lazy_router_v243.py").read_text(encoding="utf-8")
    assert "import streamlit_memory_lazy_router_v242 as prior" in source
    assert 'FROZEN_ROUTER="streamlit_memory_lazy_router_v242"' in source
    assert 'TOP_PICKS_PAGE="cfb_top_picks_page_v3"' in source
    assert "return prior.render_app()" in source
    assert "MAY_MODIFY_EXISTING_CFB_PRODUCTS=False" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE=0.0" in source


def test_app_activates_v243_and_preserves_v242_compatibility():
    source=Path("app.py").read_text(encoding="utf-8")
    assert "from streamlit_memory_lazy_router_v243 import record_bootstrap_import_ms, render_app" in source
    assert "Frozen V242 compatibility" in source
