"""WNBA Live Games Step-6 replay validation harness.

Purpose
-------
When no Step-1 verified game is live, this isolated harness can replay a recent
completed WNBA game from an exact quarter-boundary state and run the existing
Step-6 5M simulation engine against held-out final truth.

Anti-leakage contract
---------------------
- Replay states are built only from completed quarter lines THROUGH the selected
  checkpoint. Future quarter scoring is removed from the model state.
- ESPN's completed full-game box score is NOT passed into the replay projection.
  Replay flow is intentionally SCORE/CLOCK ONLY.
- Current injury feeds are NOT used as historical injury truth.
- Step-4 history is cut off before the replay event and excludes that event id.
- No historical sportsbook market is requested or attached.
- The actual final score is held separately and is used only after projection
  for validation/error reporting.

This module does not modify the production Step-6 model.
"""
from __future__ import annotations

from datetime import datetime
import math
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_live_flow_v1 as flow
import wnba_live_projection_v1 as model
import wnba_live_second_half_v14 as history
import wnba_live_step5_preview_v1 as preview

ET = ZoneInfo("America/New_York")
MODEL_VERSION = "WNBA LIVE STEP-6 REPLAY V1 • QUARTER-BOUNDARY HOLDOUT VALIDATION"


def _num(value: Any, default=None):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _int(value: Any, default=0):
    try:
        if isinstance(value, dict):
            value = value.get("value", value.get("displayValue"))
        return int(round(float(value)))
    except Exception:
        return int(default)


def _line_scores(competitor: dict) -> dict[int, int]:
    out: dict[int, int] = {}
    for idx, item in enumerate((competitor or {}).get("linescores") or [], 1):
        if not isinstance(item, dict):
            continue
        period = _int(item.get("period"), idx)
        raw = item.get("displayValue", item.get("value"))
        try:
            score = int(round(float(raw)))
        except Exception:
            continue
        if period > 0:
            out[period] = score
    return out


def _competition(payload: dict) -> dict:
    comps = ((payload or {}).get("header") or {}).get("competitions") or []
    return comps[0] if comps and isinstance(comps[0], dict) else {}


def _summary_truth(base_game: dict, payload: dict) -> dict:
    comp = _competition(payload)
    sides = {
        str(c.get("homeAway") or "").lower(): c
        for c in comp.get("competitors") or []
        if isinstance(c, dict)
    }
    away = sides.get("away") or {}
    home = sides.get("home") or {}
    away_lines = _line_scores(away)
    home_lines = _line_scores(home)
    away_final = _int(away.get("score"), base_game.get("away_score") or 0)
    home_final = _int(home.get("score"), base_game.get("home_score") or 0)
    return {
        "event_id": str(base_game.get("espn_event_id") or ""),
        "away_team": str(base_game.get("away_team") or "Away"),
        "home_team": str(base_game.get("home_team") or "Home"),
        "away_final": away_final,
        "home_final": home_final,
        "final_total": away_final + home_final,
        "home_margin": home_final - away_final,
        "away_lines": away_lines,
        "home_lines": home_lines,
        "game_start": str(base_game.get("captured_at") or ""),
    }


def _state_from_completed_periods(
    base_game: dict,
    truth: dict,
    *,
    checkpoint_id: str,
    label: str,
    period: int,
    clock: str,
    phase: str,
    completed_periods: int,
) -> dict | None:
    away_full = truth.get("away_lines") or {}
    home_full = truth.get("home_lines") or {}
    if any(p not in away_full or p not in home_full for p in range(1, completed_periods + 1)):
        return None

    away_lines = {p: int(away_full[p]) for p in range(1, completed_periods + 1)}
    home_lines = {p: int(home_full[p]) for p in range(1, completed_periods + 1)}
    away_score = sum(away_lines.values())
    home_score = sum(home_lines.values())

    if phase.startswith("Q") and period > completed_periods:
        away_lines[period] = 0
        home_lines[period] = 0

    return {
        "espn_event_id": str(base_game.get("espn_event_id") or ""),
        "event_id": str(base_game.get("espn_event_id") or ""),
        "away_team_id": _int(base_game.get("away_team_id")),
        "home_team_id": _int(base_game.get("home_team_id")),
        "away_team": str(base_game.get("away_team") or "Away"),
        "home_team": str(base_game.get("home_team") or "Home"),
        "away_abbr": str(base_game.get("away_abbr") or ""),
        "home_abbr": str(base_game.get("home_abbr") or ""),
        "away_logo": str(base_game.get("away_logo") or ""),
        "home_logo": str(base_game.get("home_logo") or ""),
        "away_score": away_score,
        "home_score": home_score,
        "away_lines": away_lines,
        "home_lines": home_lines,
        "period": int(period),
        "clock": str(clock),
        "phase": str(phase),
        "captured_at": str(base_game.get("captured_at") or datetime.now(ET).isoformat()),
        "game_date_et": str(base_game.get("game_date_et") or ""),
        "preview_only": True,
        "replay_only": True,
        "replay_checkpoint_id": checkpoint_id,
        "replay_checkpoint_label": label,
        "replay_completed_periods": int(completed_periods),
        "future_truth_attached_to_state": False,
    }


@st.cache_data(ttl=600, show_spinner=False, max_entries=24)
def replay_bundle(base_game: dict) -> dict:
    event_id = str(base_game.get("espn_event_id") or "")
    payload, meta = flow.espn_summary(event_id) if event_id else ({}, {"error": "missing event id"})
    if not payload:
        return {
            "game": base_game,
            "truth": {},
            "checkpoints": [],
            "summary_meta": meta,
            "error": str((meta or {}).get("error") or "completed-game summary unavailable"),
        }

    truth = _summary_truth(base_game, payload)
    checkpoints = []
    candidates = [
        dict(
            checkpoint_id="HALFTIME",
            label="Halftime • start of second-half forecast",
            period=2,
            clock="0:00",
            phase="HALFTIME",
            completed_periods=2,
        ),
        dict(
            checkpoint_id="Q3_START",
            label="Start Q3 • 10:00",
            period=3,
            clock="10:00",
            phase="Q3",
            completed_periods=2,
        ),
        dict(
            checkpoint_id="Q4_START",
            label="Start Q4 • 10:00",
            period=4,
            clock="10:00",
            phase="Q4",
            completed_periods=3,
        ),
    ]
    for spec in candidates:
        state = _state_from_completed_periods(base_game, truth, **spec)
        if state is not None:
            checkpoints.append(state)

    return {
        "game": base_game,
        "truth": truth,
        "checkpoints": checkpoints,
        "summary_meta": meta,
        "error": "" if checkpoints else "no exact quarter-boundary replay state could be constructed",
    }


def _score_clock_flow(state: dict) -> dict:
    elapsed = flow.elapsed_seconds(state)
    remaining = flow.regulation_seconds_remaining(state)
    away = _int(state.get("away_score"))
    home = _int(state.get("home_score"))
    total = away + home
    elapsed_min = elapsed / 60.0 if elapsed > 0 else 0.0
    score_pace_total = (total / elapsed_min * 40.0) if elapsed_min > 0 else None

    first_half_away = sum(_int((state.get("away_lines") or {}).get(p)) for p in (1, 2))
    first_half_home = sum(_int((state.get("home_lines") or {}).get(p)) for p in (1, 2))
    current_period = _int(state.get("period"), 1)
    second_half_away = sum(
        _int((state.get("away_lines") or {}).get(p))
        for p in range(3, min(current_period, 4) + 1)
    )
    second_half_home = sum(
        _int((state.get("home_lines") or {}).get(p))
        for p in range(3, min(current_period, 4) + 1)
    )
    return {
        "event_id": str(state.get("espn_event_id") or ""),
        "summary_meta": {
            "available": False,
            "replay_future_boxscore_blocked": True,
            "source": "quarter-boundary score/clock only",
        },
        "data_quality": "SCORE/CLOCK ONLY",
        "elapsed_seconds": elapsed,
        "regulation_remaining_seconds": remaining,
        "total_points": total,
        "score_pace_total": score_pace_total,
        "current_period": current_period,
        "current_quarter_total": 0,
        "current_quarter_scoring_pace": None,
        "first_half_away": first_half_away,
        "first_half_home": first_half_home,
        "second_half_away": second_half_away,
        "second_half_home": second_half_home,
        "away": {},
        "home": {},
        "blended_possessions": None,
        "pace40": None,
        "remaining_possessions": None,
        "replay_safe": True,
    }


@st.cache_data(ttl=600, show_spinner=False, max_entries=24)
def projection_for_replay(state: dict) -> dict:
    """Build a Step-6-compatible projection without full-game future leakage."""
    flow_data = _score_clock_flow(state)
    hist = history.profiles_for_game(state)
    away_profile = hist.get("away") or {}
    home_profile = hist.get("home") or {}

    segments, mu_a, mu_h, live_rate_a, live_rate_h = model._segment_projection(
        state, flow_data, away_profile, home_profile
    )
    current_a = _int(state.get("away_score"))
    current_h = _int(state.get("home_score"))

    history_mult = model._history_uncertainty(away_profile, home_profile)
    availability_mult = 1.06
    availability_meta = {
        "both_teams_covered": False,
        "active_designations": 0,
        "team_feeds_connected": 0,
        "historical_availability_used": False,
        "source_limitation": "historical injury state intentionally not reconstructed",
    }

    flow_mult = 1.08
    uncertainty_mult = model._clip(history_mult * availability_mult * flow_mult, 1.0, 1.35)
    sd_a = max(0.85, math.sqrt(max(0.25, mu_a) * 1.35) * uncertainty_mult)
    sd_h = max(0.85, math.sqrt(max(0.25, mu_h) * 1.35) * uncertainty_mult)

    pace40 = model.LEAGUE_PACE_PRIOR
    rho = model._clip(0.10 + (pace40 - model.LEAGUE_PACE_PRIOR) / 120.0, 0.04, 0.18)

    away_games = _int(away_profile.get("games"))
    home_games = _int(home_profile.get("games"))
    enough_history = away_games >= model.MIN_HISTORY_GAMES and home_games >= model.MIN_HISTORY_GAMES
    has_state = (
        state.get("away_score") is not None
        and state.get("home_score") is not None
        and _int(state.get("period")) > 0
        and bool(segments)
    )
    ready = bool(has_state and enough_history)
    quality = "MEDIUM" if enough_history else "LOW"

    live_w = model._live_weight(_int(flow_data.get("elapsed_seconds")), flow_data.get("data_quality") or "")
    ot_hist_a = model._historical_rate(away_profile, home_profile, 4)
    ot_hist_h = model._historical_rate(home_profile, away_profile, 4)
    ot_rate_a = model._clip((1.0 - live_w) * ot_hist_a + live_w * live_rate_a, 1.0, 3.2)
    ot_rate_h = model._clip((1.0 - live_w) * ot_hist_h + live_w * live_rate_h, 1.0, 3.2)

    return {
        "model_version": model.MODEL_VERSION,
        "replay_harness_version": MODEL_VERSION,
        "state_key": model.state_key(state),
        "ready": ready,
        "data_quality": quality,
        "flow": flow_data,
        "history": hist,
        "context": {"availability": availability_meta, "replay_only": True},
        "segments": segments,
        "away_history_games": away_games,
        "home_history_games": home_games,
        "away_history_reliability": away_profile.get("reliability") or "THIN",
        "home_history_reliability": home_profile.get("reliability") or "THIN",
        "projected_remaining_away": mu_a,
        "projected_remaining_home": mu_h,
        "projected_base_final_away": current_a + mu_a,
        "projected_base_final_home": current_h + mu_h,
        "projected_base_total": current_a + current_h + mu_a + mu_h,
        "projected_base_home_margin": (current_h + mu_h) - (current_a + mu_a),
        "remaining_sd_away": sd_a,
        "remaining_sd_home": sd_h,
        "residual_correlation": rho,
        "uncertainty_multiplier": uncertainty_mult,
        "history_uncertainty_multiplier": history_mult,
        "availability_uncertainty_multiplier": availability_mult,
        "availability_meta": availability_meta,
        "ot_rate_away": ot_rate_a,
        "ot_rate_home": ot_rate_h,
        "sportsbook_used_in_projection": False,
        "h2h_used_in_mean": False,
        "player_value_adjustment_used": False,
        "future_boxscore_used": False,
        "historical_availability_used": False,
        "actual_final_used_in_projection": False,
        "replay_only": True,
    }


def run_replay_5m(state: dict, projection: dict) -> dict:
    """Run the unchanged production Step-6 simulator with no sportsbook specs."""
    result = model.simulate_5m(state, projection, [])
    result = dict(result or {})
    result.update({
        "replay_validation": True,
        "replay_checkpoint_id": state.get("replay_checkpoint_id"),
        "sportsbook_pairs_attached": 0,
        "historical_market_used": False,
        "actual_final_used_in_simulation": False,
    })
    return result


def evaluate_holdout(result: dict, truth: dict) -> dict:
    actual_a = _int(truth.get("away_final"))
    actual_h = _int(truth.get("home_final"))
    actual_total = actual_a + actual_h
    actual_home_margin = actual_h - actual_a
    expected_a = _num(result.get("expected_final_away"), 0.0)
    expected_h = _num(result.get("expected_final_home"), 0.0)
    expected_total = _num(result.get("expected_final_total"), expected_a + expected_h)
    expected_home_margin = _num(result.get("expected_final_home_margin"), expected_h - expected_a)
    home_p = _num(result.get("home_win_probability"), 0.5)
    away_p = _num(result.get("away_win_probability"), 0.5)

    actual_home_win = actual_h > actual_a
    actual_winner_p = home_p if actual_home_win else away_p
    predicted_home_win = home_p >= away_p
    winner_correct = predicted_home_win == actual_home_win
    brier = (home_p - (1.0 if actual_home_win else 0.0)) ** 2

    return {
        "actual_away": actual_a,
        "actual_home": actual_h,
        "actual_total": actual_total,
        "actual_home_margin": actual_home_margin,
        "expected_away": expected_a,
        "expected_home": expected_h,
        "expected_total": expected_total,
        "expected_home_margin": expected_home_margin,
        "away_score_error": expected_a - actual_a,
        "home_score_error": expected_h - actual_h,
        "mean_team_abs_error": (abs(expected_a - actual_a) + abs(expected_h - actual_h)) / 2.0,
        "total_error": expected_total - actual_total,
        "margin_error": expected_home_margin - actual_home_margin,
        "actual_winner_probability": actual_winner_p,
        "winner_call_correct": bool(winner_correct),
        "brier_score": brier,
    }


def replay_audit(state: dict, projection: dict, truth: dict) -> list[dict]:
    state_periods = sorted(
        set((state.get("away_lines") or {}).keys()) | set((state.get("home_lines") or {}).keys())
    )
    completed = _int(state.get("replay_completed_periods"))
    allowed_max = max(completed, _int(state.get("period")))
    future_periods = [p for p in state_periods if int(p) > allowed_max]
    checks = [
        (
            "Replay isolation",
            bool(state.get("replay_only")) and bool(state.get("preview_only")),
            "Completed game is marked replay-only/preview-only.",
        ),
        (
            "Future quarter leakage",
            not future_periods and not bool(state.get("future_truth_attached_to_state")),
            f"Model state periods={state_periods}; future scoring beyond checkpoint is absent.",
        ),
        (
            "Full final boxscore blocked",
            not bool(projection.get("future_boxscore_used"))
            and bool((projection.get("flow") or {}).get("replay_safe")),
            "Replay flow is SCORE/CLOCK ONLY; completed full-game efficiency is not used.",
        ),
        (
            "Actual final holdout",
            not bool(projection.get("actual_final_used_in_projection")),
            "Actual final truth is kept outside the projection object.",
        ),
        (
            "Historical availability blocked",
            not bool(projection.get("historical_availability_used")),
            "Current injury feed is not backdated into the historical replay.",
        ),
        (
            "Sportsbook/model boundary",
            not bool(projection.get("sportsbook_used_in_projection")),
            "No historical sportsbook pair or price is attached to replay projection.",
        ),
        (
            "Historical sample",
            bool(projection.get("ready")),
            f"Away history {projection.get('away_history_games',0)} • Home history {projection.get('home_history_games',0)}.",
        ),
    ]
    return [
        {"name": name, "pass": bool(ok), "detail": detail}
        for name, ok, detail in checks
    ]


def clear_cache():
    for fn in (replay_bundle, projection_for_replay):
        try:
            fn.clear()
        except Exception:
            pass
    try:
        preview.clear_cache()
    except Exception:
        pass
    try:
        history.clear_cache()
    except Exception:
        pass


__all__ = [
    "MODEL_VERSION",
    "replay_bundle",
    "projection_for_replay",
    "run_replay_5m",
    "evaluate_holdout",
    "replay_audit",
    "clear_cache",
]
