"""MLB Pitcher Strikeouts O/U V1.0.6 — NaN-safe market grading.

Only hardens the isolated Pitcher K line-grading layer. Projection math,
workload modeling, simulations, and nested sportsbook parsing remain unchanged.
"""
from __future__ import annotations

import math
import numpy as np

import mlb_pitcher_k_hub_v105 as v105

engine = v105.engine
MODEL_VERSION = "Pitcher K V1.0.6"


def _safe_grade_line(sim, line):
    try:
        line = float(line)
    except Exception:
        return None
    if not math.isfinite(line):
        return None

    try:
        pmf = np.asarray((sim or {}).get("pmf") or [], dtype=float)
    except Exception:
        return None
    if pmf.size == 0:
        return None

    # Never allow a malformed/non-finite simulation bucket to crash grading.
    pmf = np.where(np.isfinite(pmf) & (pmf >= 0), pmf, 0.0)
    total = float(pmf.sum())
    if not math.isfinite(total) or total <= 0:
        return None
    pmf = pmf / total

    values = np.arange(pmf.size, dtype=float)
    p_over = float(pmf[values > line].sum())
    p_under = float(pmf[values < line].sum())
    p_push = float(pmf[values == line].sum()) if abs(line - round(line)) < 1e-9 else 0.0

    nums = (p_over, p_under, p_push)
    if not all(math.isfinite(x) for x in nums):
        return None

    denom = p_over + p_under
    if not math.isfinite(denom) or denom <= 0:
        return None

    fair_over = p_over / denom
    fair_under = p_under / denom
    if not (math.isfinite(fair_over) and math.isfinite(fair_under)):
        return None

    side = "OVER" if fair_over >= fair_under else "UNDER"
    win = fair_over if side == "OVER" else fair_under
    if not math.isfinite(win) or win <= 0 or win >= 1:
        # 0/100% can occur with finite Monte Carlo samples; cap only for fair-odds
        # display so the market can still be graded without integer conversion errors.
        safe_win = min(max(win if math.isfinite(win) else 0.5, 1e-6), 1 - 1e-6)
    else:
        safe_win = win

    try:
        fair_odds = engine.odds(safe_win)
    except Exception:
        fair_odds = None

    return {
        "line": line,
        "p_over": p_over,
        "p_under": p_under,
        "p_push": p_push,
        "fair_over": fair_over,
        "fair_under": fair_under,
        "side": side,
        "win_prob": win,
        "fair_odds": fair_odds,
    }


# Patch the exact global used by the V1.0 renderer.
engine._grade_line = _safe_grade_line


def render_pitcher_k_hub(games_df, section_header, status_info, team_logo, h):
    return v105.render_pitcher_k_hub(games_df, section_header, status_info, team_logo, h)
