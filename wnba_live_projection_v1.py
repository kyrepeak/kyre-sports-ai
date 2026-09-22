"""WNBA Live Games Step 6 — live projection + 5M Monte Carlo engine.

Model contract
--------------
- Anchor every simulation to the frozen Step-1 verified score/period/clock.
- Use Step-3 live pace/efficiency as a REGRESSED current-game signal.
- Use Step-4 completed regular-season Q3/Q4/second-half profiles as the historical prior.
- Use Step-5 source/availability coverage only to widen uncertainty; V1 does NOT
  invent player-value point adjustments and does NOT use H2H as a mean input.
- Sportsbook prices/no-vig probabilities are excluded from the projection.
- Fresh Step-2 exact spread/total lines may be evaluated AFTER the statistical
  distribution exists; the line never changes the mean/variance.
- Simulate regulation/current-OT remainder from the exact current state, then
  simulate additional 5-minute overtime periods when the simulated score is tied.
- Standard production run: 5,000,000 draws in bounded batches with convergence,
  standard-error and seed reporting.

No edge, EV, qualification, ranking or recommendation is created here. Those
belong to Step 7.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
import time
import zlib
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

import wnba_live_context_v1 as context
import wnba_live_flow_v1 as flow
import wnba_live_second_half_v14 as history

MODEL_VERSION = "WNBA LIVE PROJECTION V1 • STEP 6 • 5M STATE-CONDITIONAL MC"
SIMULATIONS = 5_000_000
BATCH_SIZE = 250_000
LEAGUE_PACE_PRIOR = 79.0
DEFAULT_TEAM_PPM = 2.00
MIN_HISTORY_GAMES = 4
CONVERGENCE_MAX_BATCH_RANGE_PP = 0.80
MAX_STATE_AGE_SECONDS = 45


def _num(value: Any, default=None):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _int(value: Any, default=0):
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _clip(value: float, lo: float, hi: float) -> float:
    return max(float(lo), min(float(hi), float(value)))


def _clock_seconds(clock: Any, period: int) -> int:
    text = str(clock or "").strip()
    default = 300 if period > 4 else 600
    if not text:
        return default
    try:
        if ":" in text:
            mm, ss = text.split(":", 1)
            return max(0, int(mm) * 60 + int(float(ss)))
        return max(0, int(float(text)))
    except Exception:
        return default


def state_age_seconds(game: dict, now: datetime | None = None) -> float | None:
    raw = game.get("captured_at")
    if not raw:
        return None
    try:
        captured = pd.to_datetime(raw, utc=True).to_pydatetime()
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return max(0.0, (now.astimezone(timezone.utc) - captured.astimezone(timezone.utc)).total_seconds())
    except Exception:
        return None


def state_key(game: dict) -> str:
    away_lines = tuple(sorted((game.get("away_lines") or {}).items()))
    home_lines = tuple(sorted((game.get("home_lines") or {}).items()))
    raw = "|".join([
        str(game.get("espn_event_id") or ""),
        str(game.get("away_team_id") or ""), str(game.get("home_team_id") or ""),
        str(game.get("away_score") or 0), str(game.get("home_score") or 0),
        str(game.get("period") or 0), str(game.get("clock") or ""),
        repr(away_lines), repr(home_lines),
    ])
    return raw


def market_signature(pairs: list[dict]) -> str:
    pieces = []
    for row in pairs or []:
        if not row.get("model_eligible_later"):
            continue
        pieces.append("|".join([
            str(row.get("book") or ""), str(row.get("market") or ""),
            str(row.get("left_side") or ""), str(row.get("left_line") or ""),
            str(row.get("right_side") or ""), str(row.get("right_line") or ""),
        ]))
    return "||".join(sorted(set(pieces)))


def run_key(game: dict, pairs: list[dict]) -> str:
    return state_key(game) + "||MARKETS||" + market_signature(pairs)


def fair_american(probability: float | None):
    p = _num(probability)
    if p is None or p <= 0 or p >= 1:
        return None
    if p >= 0.5:
        return int(round(-100.0 * p / (1.0 - p)))
    return int(round(100.0 * (1.0 - p) / p))


def _avg_valid(values, default=None):
    clean = [_num(v) for v in values]
    clean = [v for v in clean if v is not None]
    return (sum(clean) / len(clean)) if clean else default


def _historical_rate(team_profile: dict, opponent_profile: dict, period: int) -> float:
    """Expected team points/minute from own scoring + opponent allowance."""
    if period == 3:
        points = _avg_valid([team_profile.get("q3_for"), opponent_profile.get("q3_against")])
        minutes = 10.0
    elif period >= 4:
        points = _avg_valid([team_profile.get("q4_for"), opponent_profile.get("q4_against")])
        minutes = 10.0
    else:
        points = _avg_valid([team_profile.get("h2_for"), opponent_profile.get("h2_against")])
        minutes = 20.0
    if points is None:
        return DEFAULT_TEAM_PPM
    return _clip(float(points) / minutes, 1.25, 2.85)


def _live_team_rate(team_metrics: dict, score: float, elapsed_min: float, pace40: float | None) -> float:
    ppp = _num((team_metrics or {}).get("ppp"))
    pace = _num(pace40)
    if ppp is not None and pace is not None and pace > 0:
        return _clip(ppp * pace / 40.0, 1.10, 3.10)
    if elapsed_min > 0:
        return _clip(float(score) / elapsed_min, 1.10, 3.10)
    return DEFAULT_TEAM_PPM


def _quarter_elapsed_seconds(game: dict) -> int:
    period = max(1, _int(game.get("period"), 1))
    duration = 300 if period > 4 else 600
    return max(0, duration - min(duration, _clock_seconds(game.get("clock"), period)))


def _quarter_team_rate(game: dict, side: str) -> float | None:
    period = max(1, _int(game.get("period"), 1))
    elapsed = _quarter_elapsed_seconds(game)
    if elapsed < 45:
        return None
    try:
        points = float((game.get(f"{side}_lines") or {}).get(period) or 0)
    except Exception:
        return None
    return _clip(points / (elapsed / 60.0), 0.70, 3.70)


def _remaining_segments(game: dict) -> list[tuple[int, float]]:
    period = max(1, _int(game.get("period"), 1))
    phase = str(game.get("phase") or "").upper()
    segments: list[tuple[int, float]] = []
    if period > 4:
        left = min(300, _clock_seconds(game.get("clock"), period)) / 60.0
        if left > 0:
            segments.append((period, left))
        return segments

    if "HALF" in phase:
        return [(3, 10.0), (4, 10.0)]

    left = min(600, _clock_seconds(game.get("clock"), period)) / 60.0
    if left > 0:
        segments.append((period, left))
    for p in range(period + 1, 5):
        segments.append((p, 10.0))
    return segments


def _live_weight(elapsed_seconds: int, quality: str) -> float:
    fraction = _clip(float(elapsed_seconds) / 2400.0, 0.0, 1.0)
    weight = 0.10 + 0.40 * fraction
    if str(quality).upper() != "HIGH":
        weight *= 0.68
    return _clip(weight, 0.07, 0.50)


def _endgame_multiplier(game: dict) -> float:
    period = _int(game.get("period"), 0)
    if period != 4:
        return 1.0
    left = _clock_seconds(game.get("clock"), period)
    if left > 180:
        return 1.0
    margin = abs(_int(game.get("away_score"), 0) - _int(game.get("home_score"), 0))
    if margin <= 5:
        return 1.12
    if margin <= 10:
        return 1.07
    if margin >= 15:
        return 0.96
    return 1.02


def _availability_uncertainty(ctx: dict, away_id: int, home_id: int) -> tuple[float, dict]:
    av = ctx.get("availability") or {}
    coverage = {int(k): bool(v) for k, v in (av.get("team_status_coverage") or {}).items()}
    covered = bool(coverage.get(int(away_id))) and bool(coverage.get(int(home_id)))
    injuries = av.get("injuries") or []
    active_designations = 0
    for row in injuries:
        text = str(row.get("DESIGNATION") or "").upper()
        if text and text not in {"NO DESIGNATION", "ACTIVE", "AVAILABLE"}:
            active_designations += 1
    multiplier = 1.0
    if not covered:
        multiplier *= 1.06
    if active_designations:
        # V1 does not pretend to know player-specific point value. Current
        # designations only widen the distribution modestly.
        multiplier *= min(1.08, 1.0 + 0.012 * active_designations)
    return multiplier, {
        "both_teams_covered": covered,
        "active_designations": active_designations,
        "team_feeds_connected": int(av.get("team_feeds_connected") or 0),
    }


def _history_uncertainty(away_profile: dict, home_profile: dict) -> float:
    def one(profile):
        r = str(profile.get("reliability") or "THIN").upper()
        return {"HIGH": 1.00, "MEDIUM": 1.04, "LOW": 1.09, "THIN": 1.15}.get(r, 1.12)
    return math.sqrt(one(away_profile) * one(home_profile))


def _segment_projection(
    game: dict,
    flow_data: dict,
    away_profile: dict,
    home_profile: dict,
) -> tuple[list[dict], float, float, float, float]:
    elapsed = _int(flow_data.get("elapsed_seconds"), 0)
    elapsed_min = elapsed / 60.0 if elapsed > 0 else 0.0
    quality = str(flow_data.get("data_quality") or "SCORE/CLOCK ONLY")
    live_w = _live_weight(elapsed, quality)
    pace40 = _num(flow_data.get("pace40"))
    away_live = _live_team_rate(flow_data.get("away") or {}, _int(game.get("away_score"), 0), elapsed_min, pace40)
    home_live = _live_team_rate(flow_data.get("home") or {}, _int(game.get("home_score"), 0), elapsed_min, pace40)
    away_q = _quarter_team_rate(game, "away")
    home_q = _quarter_team_rate(game, "home")
    q_elapsed = _quarter_elapsed_seconds(game)
    q_duration = 300 if _int(game.get("period"), 1) > 4 else 600
    q_weight = min(0.16, 0.16 * q_elapsed / max(1, q_duration)) if q_elapsed >= 45 else 0.0
    current_period = _int(game.get("period"), 1)
    endgame = _endgame_multiplier(game)

    rows = []
    away_mu = home_mu = 0.0
    for period, minutes in _remaining_segments(game):
        away_hist = _historical_rate(away_profile, home_profile, period)
        home_hist = _historical_rate(home_profile, away_profile, period)
        is_current = int(period) == int(current_period)
        qw = q_weight if is_current and away_q is not None and home_q is not None else 0.0
        lw = min(live_w, 0.62 - qw)
        prior_w = max(0.0, 1.0 - lw - qw)
        away_rate = prior_w * away_hist + lw * away_live + (qw * away_q if qw else 0.0)
        home_rate = prior_w * home_hist + lw * home_live + (qw * home_q if qw else 0.0)
        if is_current:
            away_rate *= endgame
            home_rate *= endgame
        away_rate = _clip(away_rate, 0.95, 3.35)
        home_rate = _clip(home_rate, 0.95, 3.35)
        away_pts = away_rate * float(minutes)
        home_pts = home_rate * float(minutes)
        away_mu += away_pts
        home_mu += home_pts
        rows.append({
            "period": int(period), "minutes": float(minutes),
            "away_hist_rate": away_hist, "home_hist_rate": home_hist,
            "away_live_rate": away_live, "home_live_rate": home_live,
            "away_projected_rate": away_rate, "home_projected_rate": home_rate,
            "away_points": away_pts, "home_points": home_pts,
            "live_weight": lw, "quarter_weight": qw,
            "endgame_multiplier": endgame if is_current else 1.0,
        })
    return rows, away_mu, home_mu, away_live, home_live


@st.cache_data(ttl=10, show_spinner=False, max_entries=12)
def projection_for_game(game: dict) -> dict:
    flow_data = flow.analyze_game(game)
    hist = history.profiles_for_game(game)
    ctx = context.context_for_game(game)
    away_profile = hist.get("away") or {}
    home_profile = hist.get("home") or {}
    away_id = _int(game.get("away_team_id"), 0)
    home_id = _int(game.get("home_team_id"), 0)

    segments, mu_a, mu_h, live_rate_a, live_rate_h = _segment_projection(
        game, flow_data, away_profile, home_profile
    )
    current_a = _int(game.get("away_score"), 0)
    current_h = _int(game.get("home_score"), 0)

    history_mult = _history_uncertainty(away_profile, home_profile)
    availability_mult, availability_meta = _availability_uncertainty(ctx, away_id, home_id)
    flow_mult = 1.0 if str(flow_data.get("data_quality") or "").upper() == "HIGH" else 1.08
    uncertainty_mult = _clip(history_mult * availability_mult * flow_mult, 1.0, 1.35)

    sd_a = max(0.85, math.sqrt(max(0.25, mu_a) * 1.35) * uncertainty_mult)
    sd_h = max(0.85, math.sqrt(max(0.25, mu_h) * 1.35) * uncertainty_mult)
    pace40 = _num(flow_data.get("pace40"), LEAGUE_PACE_PRIOR)
    rho = _clip(0.10 + (float(pace40) - LEAGUE_PACE_PRIOR) / 120.0, 0.04, 0.18)

    away_games = _int(away_profile.get("games"), 0)
    home_games = _int(home_profile.get("games"), 0)
    enough_history = away_games >= MIN_HISTORY_GAMES and home_games >= MIN_HISTORY_GAMES
    has_state = (
        game.get("away_score") is not None and game.get("home_score") is not None
        and _int(game.get("period"), 0) > 0 and bool(segments)
    )
    ready = bool(has_state and enough_history)

    if str(flow_data.get("data_quality") or "").upper() == "HIGH" and min(away_games, home_games) >= 8 and availability_meta["both_teams_covered"]:
        quality = "HIGH"
    elif enough_history:
        quality = "MEDIUM"
    else:
        quality = "LOW"

    # Overtime rate prior uses the same Q4 own/offense + opponent/defense blend,
    # with current-game scoring regressed in. It does not use sportsbook data.
    live_w = _live_weight(_int(flow_data.get("elapsed_seconds"), 0), str(flow_data.get("data_quality") or ""))
    ot_hist_a = _historical_rate(away_profile, home_profile, 4)
    ot_hist_h = _historical_rate(home_profile, away_profile, 4)
    ot_rate_a = _clip((1.0 - live_w) * ot_hist_a + live_w * live_rate_a, 1.0, 3.2)
    ot_rate_h = _clip((1.0 - live_w) * ot_hist_h + live_w * live_rate_h, 1.0, 3.2)

    return {
        "model_version": MODEL_VERSION,
        "state_key": state_key(game),
        "ready": ready,
        "data_quality": quality,
        "flow": flow_data,
        "history": hist,
        "context": ctx,
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
    }


def _unique_specs(pairs: list[dict]):
    spreads, totals = {}, {}
    for row in pairs or []:
        if not row.get("model_eligible_later"):
            continue
        market = str(row.get("market") or "").upper()
        if market == "SPREAD":
            line = _num(row.get("left_line"))
            if line is not None:
                spreads[f"SPREAD:{line:+.2f}"] = float(line)
        elif market == "TOTAL":
            line = _num(row.get("left_line"))
            if line is not None:
                totals[f"TOTAL:{line:.2f}"] = float(line)
    return spreads, totals


def _batch_probability_range(values: list[float]) -> float:
    clean = [float(x) for x in values if x is not None and math.isfinite(float(x))]
    return (max(clean) - min(clean)) * 100.0 if len(clean) >= 2 else 0.0


def _simulate_extra_periods(
    rng: np.random.Generator,
    away_final: np.ndarray,
    home_final: np.ndarray,
    tied_idx: np.ndarray,
    projection: dict,
):
    """Resolve simulated ties with up to 3 stochastic 5-minute OT periods."""
    if tied_idx.size == 0:
        return away_final, home_final
    mu_a = float(projection.get("ot_rate_away") or DEFAULT_TEAM_PPM) * 5.0
    mu_h = float(projection.get("ot_rate_home") or DEFAULT_TEAM_PPM) * 5.0
    mult = float(projection.get("uncertainty_multiplier") or 1.0)
    sd_a = max(1.6, math.sqrt(max(0.5, mu_a) * 1.35) * mult)
    sd_h = max(1.6, math.sqrt(max(0.5, mu_h) * 1.35) * mult)
    rho = float(projection.get("residual_correlation") or 0.10)
    root = math.sqrt(max(1e-9, 1.0 - rho * rho))

    unresolved = tied_idx
    for _ in range(3):
        if unresolved.size == 0:
            break
        z1 = rng.standard_normal(unresolved.size)
        z2 = rho * z1 + root * rng.standard_normal(unresolved.size)
        oa = np.maximum(0.0, np.rint(mu_a + sd_a * z1)).astype(np.int16)
        oh = np.maximum(0.0, np.rint(mu_h + sd_h * z2)).astype(np.int16)
        away_final[unresolved] += oa
        home_final[unresolved] += oh
        still = away_final[unresolved] == home_final[unresolved]
        unresolved = unresolved[still]

    # Basketball cannot end tied. Extremely rare residual ties after 3 OTs are
    # resolved symmetrically by one final point so ML probabilities sum to 100%.
    if unresolved.size:
        coin = rng.integers(0, 2, unresolved.size)
        away_final[unresolved[coin == 0]] += 1
        home_final[unresolved[coin == 1]] += 1
    return away_final, home_final


def simulate_5m(game: dict, projection: dict, eligible_pairs: list[dict]) -> dict:
    if not projection.get("ready"):
        raise ValueError("Step-6 projection is not model-ready for this live state.")

    total_n = SIMULATIONS
    batch_size = BATCH_SIZE
    batches = int(math.ceil(total_n / batch_size))
    seed = zlib.crc32(state_key(game).encode("utf-8")) & 0xFFFFFFFF
    rng = np.random.default_rng(seed)

    current_a = _int(game.get("away_score"), 0)
    current_h = _int(game.get("home_score"), 0)
    mu_a = float(projection.get("projected_remaining_away") or 0.0)
    mu_h = float(projection.get("projected_remaining_home") or 0.0)
    sd_a = float(projection.get("remaining_sd_away") or 1.0)
    sd_h = float(projection.get("remaining_sd_home") or 1.0)
    rho = float(projection.get("residual_correlation") or 0.10)
    root = math.sqrt(max(1e-9, 1.0 - rho * rho))

    spreads, totals = _unique_specs(eligible_pairs)
    counts = {
        "away_win": 0, "home_win": 0, "extra_period": 0,
        "spread": {k: {"left": 0, "right": 0, "push": 0} for k in spreads},
        "total": {k: {"over": 0, "under": 0, "push": 0} for k in totals},
    }
    batch_series = {"HOME_ML": []}
    for key in spreads:
        batch_series[key] = []
    for key in totals:
        batch_series[key] = []

    sum_a = sum_h = 0.0
    sum_total = sum_margin_home = 0.0
    done = 0
    start = time.perf_counter()

    for _batch in range(batches):
        n = min(batch_size, total_n - done)
        if n <= 0:
            break
        z1 = rng.standard_normal(n)
        z2 = rho * z1 + root * rng.standard_normal(n)
        rem_a = np.maximum(0.0, np.rint(mu_a + sd_a * z1)).astype(np.int16)
        rem_h = np.maximum(0.0, np.rint(mu_h + sd_h * z2)).astype(np.int16)
        final_a = (rem_a + current_a).astype(np.int16)
        final_h = (rem_h + current_h).astype(np.int16)

        tied = np.flatnonzero(final_a == final_h)
        counts["extra_period"] += int(tied.size)
        if tied.size:
            final_a, final_h = _simulate_extra_periods(rng, final_a, final_h, tied, projection)

        away_win = final_a > final_h
        home_win = final_h > final_a
        aw = int(np.count_nonzero(away_win))
        hw = int(np.count_nonzero(home_win))
        counts["away_win"] += aw
        counts["home_win"] += hw
        batch_series["HOME_ML"].append(hw / n)

        final_total = final_a.astype(np.int32) + final_h.astype(np.int32)
        home_margin = final_h.astype(np.int32) - final_a.astype(np.int32)
        sum_a += float(final_a.sum(dtype=np.int64))
        sum_h += float(final_h.sum(dtype=np.int64))
        sum_total += float(final_total.sum(dtype=np.int64))
        sum_margin_home += float(home_margin.sum(dtype=np.int64))

        for key, line in spreads.items():
            # Step-2 spread parser always stores the AWAY side as left_side.
            graded = final_a.astype(np.float32) + float(line) - final_h.astype(np.float32)
            left = int(np.count_nonzero(graded > 1e-9))
            push = int(np.count_nonzero(np.abs(graded) <= 1e-9))
            right = n - left - push
            counts["spread"][key]["left"] += left
            counts["spread"][key]["right"] += right
            counts["spread"][key]["push"] += push
            denom = n - push
            batch_series[key].append(left / denom if denom > 0 else 0.5)

        for key, line in totals.items():
            graded = final_total.astype(np.float32) - float(line)
            over = int(np.count_nonzero(graded > 1e-9))
            push = int(np.count_nonzero(np.abs(graded) <= 1e-9))
            under = n - over - push
            counts["total"][key]["over"] += over
            counts["total"][key]["under"] += under
            counts["total"][key]["push"] += push
            denom = n - push
            batch_series[key].append(over / denom if denom > 0 else 0.5)

        done += n

    elapsed_seconds = time.perf_counter() - start
    n = max(1, done)
    away_p = counts["away_win"] / n
    home_p = counts["home_win"] / n
    extra_p = counts["extra_period"] / n
    home_se = math.sqrt(max(0.0, home_p * (1.0 - home_p) / n))

    spread_results = {}
    for key, line in spreads.items():
        c = counts["spread"][key]
        left_p = c["left"] / n
        right_p = c["right"] / n
        push_p = c["push"] / n
        non_push = max(1, n - c["push"])
        left_np = c["left"] / non_push
        right_np = c["right"] / non_push
        spread_results[key] = {
            "away_line": line,
            "away_cover_probability": left_p,
            "home_cover_probability": right_p,
            "push_probability": push_p,
            "away_no_push_cover_probability": left_np,
            "home_no_push_cover_probability": right_np,
            "away_fair_odds": fair_american(left_np),
            "home_fair_odds": fair_american(right_np),
            "mc_se": math.sqrt(max(0.0, left_np * (1.0 - left_np) / non_push)),
            "batch_range_pp": _batch_probability_range(batch_series[key]),
        }

    total_results = {}
    for key, line in totals.items():
        c = counts["total"][key]
        over_p = c["over"] / n
        under_p = c["under"] / n
        push_p = c["push"] / n
        non_push = max(1, n - c["push"])
        over_np = c["over"] / non_push
        under_np = c["under"] / non_push
        total_results[key] = {
            "line": line,
            "over_probability": over_p,
            "under_probability": under_p,
            "push_probability": push_p,
            "over_no_push_probability": over_np,
            "under_no_push_probability": under_np,
            "over_fair_odds": fair_american(over_np),
            "under_fair_odds": fair_american(under_np),
            "mc_se": math.sqrt(max(0.0, over_np * (1.0 - over_np) / non_push)),
            "batch_range_pp": _batch_probability_range(batch_series[key]),
        }

    convergence_ranges = {k: _batch_probability_range(v) for k, v in batch_series.items()}
    max_batch_range = max(convergence_ranges.values()) if convergence_ranges else 0.0
    convergence = "PASS" if max_batch_range <= CONVERGENCE_MAX_BATCH_RANGE_PP else "CHECK"

    return {
        "model_version": MODEL_VERSION,
        "run_key": run_key(game, eligible_pairs),
        "state_key": state_key(game),
        "market_signature": market_signature(eligible_pairs),
        "simulations": done,
        "batches": batches,
        "batch_size": batch_size,
        "seed": seed,
        "runtime_seconds": elapsed_seconds,
        "away_win_probability": away_p,
        "home_win_probability": home_p,
        "away_fair_odds": fair_american(away_p),
        "home_fair_odds": fair_american(home_p),
        "extra_period_probability": extra_p,
        "home_ml_mc_se": home_se,
        "expected_final_away": sum_a / n,
        "expected_final_home": sum_h / n,
        "expected_final_total": sum_total / n,
        "expected_final_home_margin": sum_margin_home / n,
        "spread_results": spread_results,
        "total_results": total_results,
        "convergence": convergence,
        "convergence_threshold_pp": CONVERGENCE_MAX_BATCH_RANGE_PP,
        "max_batch_range_pp": max_batch_range,
        "batch_ranges_pp": convergence_ranges,
        "sportsbook_used_in_projection": False,
        "edge_calculated": False,
        "ev_calculated": False,
        "qualification_calculated": False,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


def clear_cache():
    try:
        projection_for_game.clear()
    except Exception:
        pass
    try:
        flow.clear_cache()
    except Exception:
        pass
    try:
        history.clear_cache()
    except Exception:
        pass
    try:
        context.clear_cache()
    except Exception:
        pass


__all__ = [
    "MODEL_VERSION", "SIMULATIONS", "BATCH_SIZE", "MAX_STATE_AGE_SECONDS",
    "projection_for_game", "simulate_5m", "state_age_seconds", "state_key",
    "market_signature", "run_key", "fair_american", "clear_cache",
]
