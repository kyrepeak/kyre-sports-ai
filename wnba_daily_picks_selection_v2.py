"""WNBA Daily Picks selection adapter V2 — Assists Connector Step 6.

Builds the existing four-market read-only ranking (PRA, Points, Rebounds,
Assists), then applies the frozen Daily Picks Step-9 selection contract.

No ranking formula is changed here. Selection preserves ranking order, publishes
at most five rows, allows at most one card per player, caps same-game and
same-team concentration at three, and never forces five. The final production
recheck/guard remains separate and is owned by Connector Step 7.

This module does not import or run source production models, launch/restore Monte
Carlo, refresh markets/injuries, request network data, or write source/Daily Picks
production state.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

import wnba_daily_picks_ranking_v2 as ranking_v2
import wnba_daily_picks_selection_v1 as selection

MODEL_VERSION = "WNBA DAILY PICKS SELECTION V2 • ASSISTS CONNECTOR STEP 6"


def build_four_market_selection(day: Any) -> dict[str, Any]:
    """Return the read-only ranking bundle plus selected Top-5 and skip audit."""
    bundle = ranking_v2.build_four_market_ranking(day)
    ranked = bundle.get("ranked") if isinstance(bundle, dict) else pd.DataFrame()
    if not isinstance(ranked, pd.DataFrame):
        ranked = pd.DataFrame()

    selected, skipped = selection.select_top5(ranked)
    out = dict(bundle or {})
    out.update({
        "selected": selected,
        "skipped": skipped,
    })
    return out


def diagnostics(bundle: dict[str, Any]) -> dict[str, Any]:
    rank_diag = ranking_v2.diagnostics(bundle)
    ranked = bundle.get("ranked") if isinstance(bundle, dict) else pd.DataFrame()
    selected = bundle.get("selected") if isinstance(bundle, dict) else pd.DataFrame()
    skipped = bundle.get("skipped") if isinstance(bundle, dict) else pd.DataFrame()

    if not isinstance(ranked, pd.DataFrame):
        ranked = pd.DataFrame()
    if not isinstance(selected, pd.DataFrame):
        selected = pd.DataFrame()
    if not isinstance(skipped, pd.DataFrame):
        skipped = pd.DataFrame()

    sdiag = selection.diagnostics(ranked, selected, skipped)

    def count_market(frame: pd.DataFrame, market: str) -> int:
        if frame.empty or "Market" not in frame.columns:
            return 0
        return int(frame["Market"].astype(str).str.strip().str.upper().eq(market).sum())

    selected_counts = {
        m: count_market(selected, m)
        for m in ("PRA", "POINTS", "REBOUNDS", "ASSISTS")
    }
    assists_ranked = int(rank_diag.get("assists_ranked", 0))
    assists_selected = selected_counts["ASSISTS"]

    # Selection integration is considered covered when the four-market ranking
    # is valid and every output selection came from RANKED rows. It is normal for
    # a ranked Assists row not to be selected because Top-5/diversity rules can
    # hold lower-ranked candidates.
    selected_from_ranked = True
    if not selected.empty:
        selected_from_ranked = bool(
            "Rank state" in selected.columns
            and selected["Rank state"].astype(str).str.upper().eq("RANKED").all()
            and "Selection state" in selected.columns
            and selected["Selection state"].astype(str).str.upper().eq("SELECTED").all()
        )

    coverage = bool(rank_diag.get("assists_coverage") and selected_from_ranked)

    return {
        **rank_diag,
        "eligible": int(sdiag.get("eligible", 0)),
        "published": int(sdiag.get("published", 0)),
        "selected_markets": int(sdiag.get("markets", 0)),
        "skipped": int(sdiag.get("skipped", 0)),
        "same_player_skips": int(sdiag.get("same_player_skips", 0)),
        "game_cap_skips": int(sdiag.get("game_cap_skips", 0)),
        "team_cap_skips": int(sdiag.get("team_cap_skips", 0)),
        "selected_counts": selected_counts,
        "assists_ranked": assists_ranked,
        "assists_selected": assists_selected,
        "selection_coverage": coverage,
        "max_cards": selection.MAX_CARDS,
        "max_per_game": selection.MAX_PER_GAME,
        "max_per_team": selection.MAX_PER_TEAM,
        "selection_enabled": True,
        "guard_enabled": False,
        "simulations": 0,
        "network_requests": 0,
        "writes": 0,
    }


__all__ = ["MODEL_VERSION", "build_four_market_selection", "diagnostics"]
