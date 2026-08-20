"""WNBA Daily Picks ranking adapter V2 — Assists Connector Step 5.

Builds one read-only four-market ranking preview from already-completed same-day
PRA, Points, Rebounds and Assists outputs. The existing Daily Picks safety,
protection and ranking engines are reused; this adapter only supplies Assists to
the same pipeline.

No production model is imported or run. No Monte Carlo is launched/restored, no
sportsbook/injury/roster/network request is made, and no source-model or Daily
Picks production state is written. Step 6 still owns final Top-5 selection.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

import wnba_daily_picks_pra_connector_v1 as pra_feed
import wnba_daily_picks_points_connector_v1 as points_feed
import wnba_daily_picks_rebounds_connector_v1 as rebounds_feed
import wnba_daily_picks_assists_connector_v1 as assists_feed
import wnba_daily_picks_standardizer_v2 as standardizer
import wnba_daily_picks_safety_v1 as base_safety
import wnba_daily_picks_safety_v2 as assists_safety
import wnba_daily_picks_protection_v1 as protection
import wnba_daily_picks_ranking_v1 as ranking

MODEL_VERSION = "WNBA DAILY PICKS RANKING V2 • ASSISTS CONNECTOR STEP 5"


def _day(value: Any) -> str:
    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except Exception:
        return ""


def build_four_market_ranking(day: Any) -> dict[str, Any]:
    """Return read-only common/audit/protection/ranking frames for four markets."""
    day_str = _day(day)
    common = standardizer.normalize_all(day_str)

    if common.empty:
        base_rows = common.copy()
        assists_rows = common.copy()
    else:
        market = common["Market"].astype(str).str.strip().str.upper()
        base_rows = common.loc[market.isin({"PRA", "POINTS", "REBOUNDS"})].copy()
        assists_rows = common.loc[market.eq("ASSISTS")].copy()

    feeds = {
        "PRA": pra_feed.status(day_str),
        "POINTS": points_feed.status(day_str),
        "REBOUNDS": rebounds_feed.status(day_str),
        "ASSISTS": assists_feed.status(day_str),
    }

    base_audit = base_safety.evaluate(
        base_rows,
        day_str,
        feeds={k: feeds[k] for k in ("PRA", "POINTS", "REBOUNDS")},
    )
    assists_audit = assists_safety.evaluate_assists(assists_rows, day_str)

    audit_frames = [f for f in (base_audit, assists_audit) if isinstance(f, pd.DataFrame) and not f.empty]
    audit = pd.concat(audit_frames, ignore_index=True, sort=False) if audit_frames else pd.DataFrame()

    # Re-run only the read-only exposure annotation across the combined SAFE set.
    # This is necessary so same-player/game/team correlation can be seen across
    # different markets rather than inside Assists alone.
    protected = protection.annotate(audit)
    ranked = ranking.rank_candidates(protected)

    return {
        "day": day_str,
        "feeds": feeds,
        "common": common,
        "audit": audit,
        "protected": protected,
        "ranked": ranked,
    }


def diagnostics(bundle: dict[str, Any]) -> dict[str, Any]:
    common = bundle.get("common") if isinstance(bundle, dict) else pd.DataFrame()
    audit = bundle.get("audit") if isinstance(bundle, dict) else pd.DataFrame()
    protected = bundle.get("protected") if isinstance(bundle, dict) else pd.DataFrame()
    ranked = bundle.get("ranked") if isinstance(bundle, dict) else pd.DataFrame()

    rdiag = ranking.diagnostics(ranked)
    pdiag = protection.diagnostics(protected)
    states = ranked.get("Rank state", pd.Series(dtype=str)).astype(str).str.upper() if isinstance(ranked, pd.DataFrame) else pd.Series(dtype=str)
    ranked_rows = ranked.loc[states.eq("RANKED")].copy() if isinstance(ranked, pd.DataFrame) and not ranked.empty else pd.DataFrame()

    def count_market(frame: pd.DataFrame, market: str) -> int:
        if frame is None or frame.empty or "Market" not in frame.columns:
            return 0
        return int(frame["Market"].astype(str).str.strip().str.upper().eq(market).sum())

    market_counts = {m: count_market(common, m) for m in ("PRA", "POINTS", "REBOUNDS", "ASSISTS")}
    ranked_counts = {m: count_market(ranked_rows, m) for m in ("PRA", "POINTS", "REBOUNDS", "ASSISTS")}
    safe_rows = 0
    if isinstance(audit, pd.DataFrame) and not audit.empty and "Safety state" in audit.columns:
        safe_rows = int(audit["Safety state"].astype(str).str.upper().eq("SAFE").sum())

    assists_source = bundle.get("feeds", {}).get("ASSISTS", {}) if isinstance(bundle, dict) else {}
    assists_input = market_counts["ASSISTS"]
    assists_ranked = ranked_counts["ASSISTS"]
    assists_connected = bool(assists_source.get("connected"))
    # A connected source with 0/5 is a valid ranking integration pass with zero
    # Assists rows. Otherwise every standardized Assists row must make it through
    # the ranking engine as either RANKED or SCORE HOLD (never silently vanish).
    assists_rank_rows = 0
    if isinstance(ranked, pd.DataFrame) and not ranked.empty and "Market" in ranked.columns:
        assists_rank_rows = int(ranked["Market"].astype(str).str.upper().eq("ASSISTS").sum())
    assists_coverage = bool(assists_connected and assists_rank_rows == assists_input)

    return {
        "common_rows": 0 if common is None else int(len(common)),
        "safe_rows": safe_rows,
        "candidate_groups": int(pdiag.get("candidate_groups", 0)),
        "ranked": int(rdiag.get("ranked", 0)),
        "score_holds": int(rdiag.get("score_holds", 0)),
        "markets_represented": int(rdiag.get("markets", 0)),
        "market_counts": market_counts,
        "ranked_counts": ranked_counts,
        "assists_input": assists_input,
        "assists_rank_rows": assists_rank_rows,
        "assists_ranked": assists_ranked,
        "assists_connected": assists_connected,
        "assists_coverage": assists_coverage,
        "duplicate_quote_groups": int(pdiag.get("duplicate_quote_groups", 0)),
        "player_correlation_groups": int(pdiag.get("player_correlation_groups", 0)),
        "game_exposure_groups": int(pdiag.get("game_exposure_groups", 0)),
        "team_exposure_groups": int(pdiag.get("team_exposure_groups", 0)),
        "ranking_active": True,
        "selection_enabled": False,
        "guard_enabled": False,
        "simulations": 0,
        "network_requests": 0,
        "writes": 0,
    }


__all__ = ["MODEL_VERSION", "build_four_market_ranking", "diagnostics"]
