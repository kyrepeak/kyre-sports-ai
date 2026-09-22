"""WNBA Daily Picks selection V3 — five-market Top-5.

Uses the frozen Step-9 diversity selector on the combined PRA/Points/Rebounds/
Assists/Spread ranking. Spread uses its team name in the common Player identity
slot so the existing one-identity rule remains deterministic without colliding
with actual player names.
"""
from __future__ import annotations

from typing import Any
import pandas as pd

import wnba_daily_picks_ranking_v3 as ranking_v3
import wnba_daily_picks_selection_v1 as selection

MODEL_VERSION = "WNBA DAILY PICKS SELECTION V3 • FIVE MARKET TOP 5"


def build_five_market_selection(day: Any) -> dict:
    bundle=ranking_v3.build_five_market_ranking(day)
    ranked=bundle.get("ranked") if isinstance(bundle,dict) else pd.DataFrame()
    if not isinstance(ranked,pd.DataFrame): ranked=pd.DataFrame()
    selected, skipped=selection.select_top5(ranked)
    out=dict(bundle or {}); out.update({"selected":selected,"skipped":skipped}); return out


def diagnostics(bundle: dict) -> dict:
    rdiag=ranking_v3.diagnostics(bundle)
    ranked=bundle.get("ranked") if isinstance(bundle,dict) else pd.DataFrame()
    selected=bundle.get("selected") if isinstance(bundle,dict) else pd.DataFrame()
    skipped=bundle.get("skipped") if isinstance(bundle,dict) else pd.DataFrame()
    if not isinstance(ranked,pd.DataFrame): ranked=pd.DataFrame()
    if not isinstance(selected,pd.DataFrame): selected=pd.DataFrame()
    if not isinstance(skipped,pd.DataFrame): skipped=pd.DataFrame()
    sdiag=selection.diagnostics(ranked,selected,skipped)
    spread_selected=int(selected.get("Market",pd.Series(dtype=str)).astype(str).str.upper().eq("SPREAD").sum()) if not selected.empty else 0
    return {**rdiag,"eligible":int(sdiag.get("eligible",0)),"published":int(sdiag.get("published",0)),
            "spread_selected":spread_selected,"max_cards":selection.MAX_CARDS,"selection_enabled":True,
            "simulations":0,"network_requests":0,"writes":0}


__all__=["MODEL_VERSION","build_five_market_selection","diagnostics"]
