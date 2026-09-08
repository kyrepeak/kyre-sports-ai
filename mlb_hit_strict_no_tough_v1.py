"""MLB Hits strict no-TOUGH visible gate.

Additive correctness hotfix over permanently frozen Hits Step 5.

Why this exists:
- Frozen Step 4/5 used broader composite matchup/starter scores.
- The visible Step-2 "Opposing Probable Starter" badge has its own certified
  TOUGH rule: ERA <= 3.35 OR WHIP <= 1.12 OR K% >= 27.
- Therefore a hitter could pass Step 4/5 yet still visibly carry a red TOUGH
  starter badge. That is inconsistent with the user's "no tough picks" intent.

This helper reuses the frozen Step-5 qualified ordering, evaluates the exact
certified Step-2 starter-grade thresholds from the Step-5 starter profile, and
removes those rows from the visible board. It never changes probabilities,
Monte Carlo, candidate generation, deep finalist modeling, or calibration.
"""
from __future__ import annotations

import math
from typing import Any, Iterable

import mlb_hit_starter_vulnerability_v1 as frozen_step5

VERSION = "HIT-STRICT-NO-TOUGH-V1"
_FROZEN_STEP5_RANKER = frozen_step5.rank_results

STEP2_TOUGH_ERA_MAX = 3.35
STEP2_TOUGH_WHIP_MAX = 1.12
STEP2_TOUGH_K_PCT_MIN = 0.27


def _f(value: Any) -> float | None:
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError, OverflowError):
        return None


def certified_step2_starter_grade(profile: dict[str, Any] | None) -> str:
    """Mirror frozen V13.16 Step-2 starter grade thresholds exactly."""
    p = dict(profile or {})
    era = _f(p.get("era"))
    whip = _f(p.get("whip"))
    k_pct = _f(p.get("k_pct"))
    if k_pct is not None and k_pct > 1:
        k_pct /= 100.0

    if era is None and whip is None and k_pct is None:
        return "DATA LIMITED"
    if (
        (era is not None and era <= STEP2_TOUGH_ERA_MAX)
        or (whip is not None and whip <= STEP2_TOUGH_WHIP_MAX)
        or (k_pct is not None and k_pct >= STEP2_TOUGH_K_PCT_MIN)
    ):
        return "TOUGH"
    if era is not None and era >= 4.75 and (whip is None or whip >= 1.30):
        return "FAVORABLE"
    return "NEUTRAL"


def strict_rank_results(
    results: Iterable[dict[str, Any]],
    profile_lookup,
    limit: int = 5,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Post-filter the full frozen Step-5 qualified list; never backfill TOUGH."""
    frozen_rows, frozen_meta = _FROZEN_STEP5_RANKER(
        results,
        profile_lookup,
        limit=999,
    )

    kept: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    for row in frozen_rows:
        item = dict(row or {})
        step5_ctx = dict(item.get("_step5") or {})
        prof = dict(step5_ctx.get("starter_profile") or {})
        grade = certified_step2_starter_grade(prof)

        strict_ctx = {
            "certified_step2_starter_grade": grade,
            "strict_no_tough_qualified": grade != "TOUGH",
        }

        item["_strict_no_tough"] = strict_ctx
        if grade == "TOUGH":
            excluded.append(item)
        else:
            kept.append(item)

    selected = kept[: max(0, int(limit))]
    out = []
    for rank, row in enumerate(selected, 1):
        item = dict(row)
        strict_ctx = dict(item.get("_strict_no_tough") or {})
        strict_ctx["strict_rank"] = rank
        item["_strict_no_tough"] = strict_ctx
        out.append(item)

    meta = {
        "version": VERSION,
        "frozen_step5_meta": dict(frozen_meta or {}),
        "frozen_step5_qualified_count": len(frozen_rows),
        "strict_tough_excluded": len(excluded),
        "strict_visible_count": len(out),
        "backfilled_tough": 0,
        "probability_impact": False,
        "simulation_impact": False,
        "candidate_pool_impact": False,
        "calibration_history_impact": False,
        "visible_selection_impact": True,
        "visible_ranking_impact": False,
    }
    return out, meta


__all__ = [
    "VERSION",
    "_FROZEN_STEP5_RANKER",
    "STEP2_TOUGH_ERA_MAX",
    "STEP2_TOUGH_WHIP_MAX",
    "STEP2_TOUGH_K_PCT_MIN",
    "certified_step2_starter_grade",
    "strict_rank_results",
]
