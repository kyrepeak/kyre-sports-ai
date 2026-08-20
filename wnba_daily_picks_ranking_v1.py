"""WNBA Daily Picks Step 8 — cross-market ranking engine.

Consumes only Step-7 protected rows. It never imports or runs PRA, Points or
Rebounds production models, never refreshes injuries/markets, never launches
Monte Carlo, and never writes production/session state.

Step 8 does four things only:
1) keeps Step-6 SAFE rows,
2) collapses exact same-wager multi-book quotes to one best available quote,
3) scores comparable PRA / Points / Rebounds candidates from existing outputs,
4) applies a small exposure penalty from Step-7 correlation tags.

The result is a ranking preview for audit. Step 9 owns visual Top-5 cards.
"""
from __future__ import annotations

from typing import Any
import re

import numpy as np
import pandas as pd

MODEL_VERSION = "WNBA DAILY PICKS RANKING V1 • STEP 8 READ ONLY"

RANK_COLUMNS = [
    "Rank state", "Rank", "Ranking score", "Raw score", "Exposure penalty",
    "Probability score", "Edge score", "EV score", "Projection score",
    "Freshness score", "Quality score", "Quote selection", "EV source",
]


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    s = str(value).strip()
    return "" if s.upper() in {"", "—", "NONE", "NAN", "NULL", "N/A", "NA"} else s


def _num(value: Any) -> float:
    try:
        x = float(value)
        return float(x) if np.isfinite(x) else np.nan
    except Exception:
        return np.nan


def _prob(value: Any) -> float:
    x = _num(value)
    if not np.isfinite(x):
        return np.nan
    if 1.0 < abs(x) <= 100.0:
        x /= 100.0
    return float(x) if 0.0 <= x <= 1.0 else np.nan


def _edge(value: Any) -> float:
    x = _num(value)
    if not np.isfinite(x):
        return np.nan
    if abs(x) > 1.0 and abs(x) <= 100.0:
        x /= 100.0
    return float(x)


def _american_ev100(probability: float, odds: Any) -> float:
    o = _num(odds)
    if not np.isfinite(probability) or not np.isfinite(o) or o == 0:
        return np.nan
    win_profit = o / 100.0 if o > 0 else 100.0 / abs(o)
    return float((probability * win_profit - (1.0 - probability)) * 100.0)


def _fresh_minutes(value: Any) -> float | None:
    s = _text(value).upper()
    if not s:
        return None
    if "STALE" in s or "EXPIRED" in s:
        return float("inf")
    m = re.search(r"(\d+(?:\.\d+)?)\s*(M|MIN|MINS|MINUTE|MINUTES)\b", s)
    if m:
        return float(m.group(1))
    sec = re.search(r"(\d+(?:\.\d+)?)\s*(S|SEC|SECS|SECOND|SECONDS)\b", s)
    if sec:
        return float(sec.group(1)) / 60.0
    if "FRESH" in s:
        return 0.0
    return None


def _quality_points(confidence: Any, qualification: Any) -> float:
    c = _text(confidence).upper().replace(" ", "")
    q = _text(qualification).upper()
    grade_map = {
        "A+": 5.0, "A": 4.7, "A-": 4.4,
        "B+": 4.0, "B": 3.7, "B-": 3.4,
        "C+": 3.0, "C": 2.7, "C-": 2.4,
    }
    for grade, pts in grade_map.items():
        if c == grade or c.startswith(grade + "/"):
            return pts
    numeric = _num(confidence)
    if np.isfinite(numeric):
        if numeric > 1:
            return float(np.clip(numeric / 100.0, 0.0, 1.0) * 5.0)
        return float(np.clip(numeric, 0.0, 1.0) * 5.0)
    if "FINAL READY" in q or "READY" in q:
        return 5.0
    if "QUALIFIED" in q:
        return 4.5
    return 3.0


def _projection_edge(side: Any, projection: Any, line: Any) -> float:
    p, l = _num(projection), _num(line)
    if not np.isfinite(p) or not np.isfinite(l):
        return np.nan
    s = _text(side).upper()
    if s == "OVER":
        return float(p - l)
    if s == "UNDER":
        return float(l - p)
    return np.nan


def _score_quote(row: pd.Series) -> dict[str, Any]:
    p = _prob(row.get("Model probability"))
    nv = _prob(row.get("No-vig probability"))
    edge = _edge(row.get("Edge"))

    # Edge and no-vig are algebraically linked. Derive only when one is present;
    # never invent both from nothing.
    if not np.isfinite(edge) and np.isfinite(p) and np.isfinite(nv):
        edge = p - nv
    if not np.isfinite(nv) and np.isfinite(p) and np.isfinite(edge):
        nv = p - edge

    source_ev = _num(row.get("EV / $100"))
    ev_source = "SOURCE"
    ev100 = source_ev
    if not np.isfinite(ev100) and np.isfinite(p):
        ev100 = _american_ev100(p, row.get("Posted odds"))
        if np.isfinite(ev100):
            ev_source = "DERIVED: model p + posted odds"

    proj_edge = _projection_edge(row.get("Side"), row.get("Projection"), row.get("Line"))
    line = abs(_num(row.get("Line")))

    rankable = bool(
        _text(row.get("Safety state")).upper() == "SAFE"
        and np.isfinite(p)
        and np.isfinite(nv)
        and np.isfinite(edge)
        and np.isfinite(ev100)
        and np.isfinite(proj_edge)
        and np.isfinite(line)
    )
    if not rankable:
        return {
            "Rank state": "SCORE HOLD", "Ranking score": np.nan, "Raw score": np.nan,
            "Exposure penalty": np.nan, "Probability score": np.nan, "Edge score": np.nan,
            "EV score": np.nan, "Projection score": np.nan, "Freshness score": np.nan,
            "Quality score": np.nan, "EV / $100 ranked": ev100, "No-vig ranked": nv,
            "Edge ranked": edge, "Projection edge": proj_edge, "EV source": ev_source,
        }

    probability_score = float(np.clip((p - 0.50) / 0.25, 0.0, 1.0) * 40.0)
    edge_score = float(np.clip(edge / 0.15, 0.0, 1.0) * 25.0)
    ev_score = float(np.clip(ev100 / 25.0, 0.0, 1.0) * 15.0)
    proj_ratio = proj_edge / max(line, 1.0)
    projection_score = float(np.clip(proj_ratio / 0.15, 0.0, 1.0) * 10.0)

    fresh = _fresh_minutes(row.get("Freshness"))
    if fresh is None:
        freshness_score = 2.0
    elif fresh <= 5:
        freshness_score = 5.0
    elif fresh <= 10:
        freshness_score = 3.5
    elif fresh <= 15:
        freshness_score = 1.5
    else:
        freshness_score = 0.0

    quality_score = _quality_points(row.get("Confidence"), row.get("Qualification state"))
    raw = probability_score + edge_score + ev_score + projection_score + freshness_score + quality_score

    alt = max(int(_num(row.get("Alternate lines")) if np.isfinite(_num(row.get("Alternate lines"))) else 0) - 1, 0)
    player_markets = max(int(_num(row.get("Player markets")) if np.isfinite(_num(row.get("Player markets"))) else 0) - 1, 0)
    game_groups = max(int(_num(row.get("Game candidate groups")) if np.isfinite(_num(row.get("Game candidate groups"))) else 0) - 1, 0)
    team_groups = max(int(_num(row.get("Team candidate groups")) if np.isfinite(_num(row.get("Team candidate groups"))) else 0) - 1, 0)
    exposure_penalty = float(min(8.0, 1.5 * alt + 3.0 * player_markets + 0.75 * game_groups + 0.35 * team_groups))
    final = float(max(raw - exposure_penalty, 0.0))

    return {
        "Rank state": "RANKED", "Ranking score": final, "Raw score": raw,
        "Exposure penalty": exposure_penalty, "Probability score": probability_score,
        "Edge score": edge_score, "EV score": ev_score, "Projection score": projection_score,
        "Freshness score": freshness_score, "Quality score": quality_score,
        "EV / $100 ranked": ev100, "No-vig ranked": nv, "Edge ranked": edge,
        "Projection edge": proj_edge, "EV source": ev_source,
    }


def rank_candidates(protected: pd.DataFrame) -> pd.DataFrame:
    """Collapse exact candidate families to best quote, then return ranked preview."""
    if protected is None or protected.empty:
        cols = list(protected.columns) if isinstance(protected, pd.DataFrame) else []
        extras = RANK_COLUMNS + ["EV / $100 ranked", "No-vig ranked", "Edge ranked", "Projection edge"]
        return pd.DataFrame(columns=cols + [c for c in extras if c not in cols])

    d = protected.copy().reset_index(drop=True)
    if "Safety state" not in d.columns or "Candidate key" not in d.columns:
        return pd.DataFrame()
    safe = d[d["Safety state"].astype(str).str.upper().eq("SAFE")].copy()
    if safe.empty:
        return pd.DataFrame(columns=list(d.columns) + [c for c in RANK_COLUMNS if c not in d.columns])

    picked: list[pd.Series] = []
    for _, group in safe.groupby("Candidate key", dropna=False, sort=False):
        scored_rows: list[tuple[pd.Series, dict[str, Any]]] = []
        for _, row in group.iterrows():
            scored_rows.append((row.copy(), _score_quote(row)))

        # Best exact quote: highest expected value, then best American price.
        def quote_key(item: tuple[pd.Series, dict[str, Any]]):
            row, score = item
            ev = _num(score.get("EV / $100 ranked"))
            odds = _num(row.get("Posted odds"))
            return (
                ev if np.isfinite(ev) else -1e9,
                odds if np.isfinite(odds) else -1e9,
            )

        row, score = max(scored_rows, key=quote_key)
        for k, v in score.items():
            row[k] = v
        row["Quote selection"] = f"BEST OF {len(group)}" if len(group) > 1 else "ONLY QUOTE"
        picked.append(row)

    out = pd.DataFrame(picked)
    if out.empty:
        return out

    ranked_mask = out["Rank state"].astype(str).str.upper().eq("RANKED")
    rankable = out[ranked_mask].copy().sort_values(
        ["Ranking score", "Model probability", "Edge ranked", "EV / $100 ranked"],
        ascending=[False, False, False, False], na_position="last",
    )
    rankable["Rank"] = np.arange(1, len(rankable) + 1)
    holds = out[~ranked_mask].copy()
    holds["Rank"] = np.nan
    result = pd.concat([rankable, holds], ignore_index=True, sort=False)
    return result


def diagnostics(ranked: pd.DataFrame) -> dict[str, Any]:
    if ranked is None or ranked.empty:
        return {
            "candidate_groups": 0, "ranked": 0, "score_holds": 0,
            "markets": 0, "quotes_selected": 0, "ranking_active": True,
            "simulations": 0, "writes": 0,
        }
    states = ranked.get("Rank state", pd.Series(dtype=str)).astype(str).str.upper()
    ranked_rows = ranked[states.eq("RANKED")]
    markets = ranked_rows.get("Market", pd.Series(dtype=str)).astype(str).str.upper()
    return {
        "candidate_groups": int(len(ranked)),
        "ranked": int(states.eq("RANKED").sum()),
        "score_holds": int(states.eq("SCORE HOLD").sum()),
        "markets": int(markets[markets.str.len().gt(0)].nunique()),
        "quotes_selected": int(len(ranked)),
        "ranking_active": True,
        "simulations": 0,
        "writes": 0,
    }


__all__ = ["MODEL_VERSION", "RANK_COLUMNS", "rank_candidates", "diagnostics"]
