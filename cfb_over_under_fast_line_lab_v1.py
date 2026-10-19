"""CFB Over/Under Fast Line Lab V1 — pure in-memory threshold replay.

This module makes an already-certified selected-game result cheap to re-evaluate
at a different analysis total. It deliberately does *not* fetch or rebuild team
data, schedules, markets, NCAA tables, ESPN context, weather, history, rosters,
or any other provider evidence.

The frozen model contract already defines the analysis line as a 0.0%-weight
comparison threshold. Therefore a slider move can safely reuse the exact
selected-game evidence/engine objects and replay only the deterministic raw
probability + downstream apply functions that depend on the threshold.
"""
from __future__ import annotations

from math import isfinite
from time import perf_counter
from typing import Any, Mapping

import cfb_over_under_environment_engine_v1 as environment_engine
import cfb_over_under_explosive_engine_v1 as explosive_engine
import cfb_over_under_final_v1 as final_model
import cfb_over_under_form_strength_engine_v1 as form_engine
import cfb_over_under_history_engine_v1 as history_engine
import cfb_over_under_matchup_engine_v1 as matchup_engine
import cfb_over_under_model_v1 as raw_model
import cfb_over_under_pace_engine_v1 as pace_engine
import cfb_over_under_red_zone_engine_v1 as red_zone_engine
import cfb_over_under_slate_v11 as step12
import cfb_over_under_third_down_engine_v1 as third_down_engine
import cfb_over_under_turnover_engine_v1 as turnover_engine

MODEL_VERSION = "CFB O/U FAST LINE LAB V1 • PURE THRESHOLD REPLAY"
FROZEN_RUNTIME = "cfb_over_under_slate_v14_runtime"
MAY_FETCH_EXTERNAL_DATA = False
PROJECTION_MATH_CHANGED = False
SELECTION_MATH_CHANGED = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def _line(value: Any) -> float:
    try:
        line = float(value)
    except Exception as exc:
        raise ValueError("FAST_LINE_LAB_INVALID_LINE") from exc
    if not isfinite(line) or not (raw_model.MIN_ANALYSIS_LINE <= line <= raw_model.MAX_ANALYSIS_LINE):
        raise ValueError("FAST_LINE_LAB_INVALID_LINE")
    return line


def _lean(p_over: float, p_under: float, p_push: float) -> str:
    if p_push >= max(p_over, p_under):
        return "PASS"
    if p_over > p_under:
        return "OVER"
    if p_under > p_over:
        return "UNDER"
    return "PASS"


def _reline_base_raw(base_result: Mapping[str, Any], analysis_line: float) -> dict[str, Any]:
    """Rebuild only line-dependent Step-8 fields from frozen selected-game state."""
    line = _line(analysis_line)
    game = dict(base_result.get("game") or {})
    away = dict(base_result.get("away") or {})
    home = dict(base_result.get("home") or {})
    template = dict(base_result.get("base_raw") or {})

    # A complete V14 selected-game result always carries base_raw. This fallback
    # remains provider-free and preserves frozen Step-8 behavior for defensive
    # compatibility with older stored results.
    if not template or not template.get("ready"):
        return raw_model.project_matchup(game, away, home, line)

    projected_total = float(template.get("projected_total") or 0.0)
    sigma = float(template.get("structural_total_sigma") or raw_model.BASE_TOTAL_SIGMA)
    p_over, p_under, p_push = raw_model._line_probabilities(
        projected_total,
        sigma,
        line,
    )

    out = dict(template)
    out.update({
        "analysis_line": line,
        "analysis_line_used": True,
        "analysis_line_projection_weight": raw_model.ANALYSIS_LINE_PROJECTION_WEIGHT,
        "over_probability": float(p_over),
        "under_probability": float(p_under),
        "push_probability": float(p_push),
        "model_lean": _lean(p_over, p_under, p_push),
        "sportsbook_input_used": False,
        "market_price_used": False,
        "empirical_calibration_claimed": False,
        "monte_carlo_used": False,
    })
    return out


def reline_result(base_result: Mapping[str, Any], analysis_line: float) -> dict[str, Any]:
    """Replay frozen line-dependent math using already-built evidence only.

    No build_* function and no provider function is called here. The stored
    selected-game engines are reused byte-for-byte, then each frozen pure
    apply_to_raw stage recomputes its probabilities against the new line.
    """
    started = perf_counter()
    if not isinstance(base_result, Mapping) or not base_result:
        raise ValueError("FAST_LINE_LAB_BASE_RESULT_REQUIRED")

    line = _line(analysis_line)
    game = dict(base_result.get("game") or {})
    away = dict(base_result.get("away") or {})
    home = dict(base_result.get("home") or {})

    raw0 = _reline_base_raw(base_result, line)
    raw3 = matchup_engine.apply_to_raw(raw0, dict(base_result.get("matchup_engine") or {}))
    raw4 = pace_engine.apply_to_raw(raw3, dict(base_result.get("pace_engine") or {}))
    raw5 = explosive_engine.apply_to_raw(raw4, dict(base_result.get("explosive_engine") or {}))
    raw6 = red_zone_engine.apply_to_raw(raw5, dict(base_result.get("red_zone_engine") or {}))
    raw7 = third_down_engine.apply_to_raw(raw6, dict(base_result.get("third_down_engine") or {}))
    raw8 = turnover_engine.apply_to_raw(raw7, dict(base_result.get("turnover_engine") or {}))
    raw9 = environment_engine.apply_to_raw(raw8, dict(base_result.get("environment_engine") or {}))
    raw10 = history_engine.apply_to_raw(raw9, dict(base_result.get("history_engine") or {}))
    raw11 = form_engine.apply_to_raw(raw10, dict(base_result.get("form_strength_engine") or {}))
    final = final_model.synthesize(game, raw11)

    out = dict(base_result)
    out.update({
        "game": game,
        "away": away,
        "home": home,
        "raw": dict(raw11),
        "final": dict(final),
        "analysis_line": line,
        "base_raw": dict(raw0),
        "step3_raw": dict(raw3),
        "step4_raw": dict(raw4),
        "step5_raw": dict(raw5),
        "step6_raw": dict(raw6),
        "step7_raw": dict(raw7),
        "step8_raw": dict(raw8),
        "step9_raw": dict(raw9),
        "step10_raw": dict(raw10),
        "analysis_line_matchup_weight": 0.0,
        "analysis_line_pace_weight": 0.0,
        "analysis_line_explosive_weight": 0.0,
        "analysis_line_red_zone_weight": 0.0,
        "analysis_line_third_down_weight": 0.0,
        "analysis_line_turnover_weight": 0.0,
        "analysis_line_environment_weight": 0.0,
        "analysis_line_history_weight": 0.0,
        "analysis_line_form_weight": 0.0,
        "sportsbook_input_used": False,
        "market_price_used": False,
        "market_probability_used": False,
        "edge_or_ev_used": False,
        "monte_carlo_used": False,
        "new_model_formula_added": False,
    })

    # Re-run the existing read-only Step-12 integrity certificate against the
    # new threshold result. This is local CPU work and performs zero I/O.
    out = step12._attach_certificate(out)
    out.update({
        "version": str(base_result.get("version") or FROZEN_RUNTIME),
        "game": game,
        "away": away,
        "home": home,
        "analysis_line": line,
        "fast_line_lab": True,
        "fast_line_lab_version": MODEL_VERSION,
        "external_fetches": 0,
        "may_fetch_external_data": MAY_FETCH_EXTERNAL_DATA,
        "projection_math_changed": PROJECTION_MATH_CHANGED,
        "selection_math_changed": SELECTION_MATH_CHANGED,
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        "fast_line_compute_ms": round((perf_counter() - started) * 1000.0, 3),
    })
    return out


__all__ = [
    "FROZEN_RUNTIME",
    "MAY_FETCH_EXTERNAL_DATA",
    "MODEL_VERSION",
    "PROJECTION_MATH_CHANGED",
    "SELECTION_MATH_CHANGED",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_reline_base_raw",
    "reline_result",
]
