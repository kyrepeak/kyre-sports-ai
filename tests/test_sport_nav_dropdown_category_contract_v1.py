from __future__ import annotations

import cfb_hub_v1 as cfb
import streamlit_memory_lazy_router_v1 as base


EXPECTED = {
    "NFL": ["Slate","Moneyline","Spread","Game Total","Passing Yards","Rushing Yards","Receiving Yards","Receptions","Passing TDs","Anytime TD","Daily Picks"],
    "CFB": ["Moneyline","Over/Under","Game Total"],
    "MLB": ["Slate","1+ Hit","2+ Hits","Home Run","Hits + Runs + RBIs","Pitcher Strikeouts","Matchup Explorer","Daily Game Picks","Moneyline","Run Line","Game Total","Live Game"],
    "WNBA": ["Points","Rebounds","Assists","Rebounds + Assists","PRA","Spread","Moneyline","Game Total","Daily Picks"],
}


def test_dropdown_category_contract_matches_existing_streamlit_routes() -> None:
    assert list(base.NFL_MARKETS) == EXPECTED["NFL"]
    assert list(cfb.CFB_MARKETS) == EXPECTED["CFB"]
    assert list(base.MLB_MARKETS) == EXPECTED["MLB"]
    assert list(base.WNBA_MARKETS) == EXPECTED["WNBA"]


def test_dropdown_category_contract_contains_no_duplicates() -> None:
    for values in EXPECTED.values():
        assert len(values) == len(set(values))
        assert all(str(value).strip() for value in values)
