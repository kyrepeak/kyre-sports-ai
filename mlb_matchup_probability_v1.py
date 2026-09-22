"""Raw hit-probability engine for MLB Matchup Intelligence V2 Step 11.

Step 11 is the first V2 layer allowed to calculate game-level hit probabilities.
It combines certified Steps 1-10 into starter/bullpen per-PA hit probabilities,
plate-appearance exposure, an analytical Poisson-binomial point distribution and
an uncertainty-aware Monte Carlo distribution.

IMPORTANT: these are RAW, PRE-CALIBRATION probabilities. Step 12 owns backtest
calibration, missing-data penalties, final confidence, final fair odds and grades.
Frozen V1 Matchup, Daily Top 5 and Moneyline remain untouched.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

MONTE_CARLO_SIMS = 5_000_000
MONTE_CARLO_BATCH = 250_000
MONTE_CARLO_SEED = 110011
MIN_EXPECTED_PA = 2.50
MIN_BASE_HIT_PER_PA = 0.08
MAX_BASE_HIT_PER_PA = 0.40
MIN_COMPOSITE_DATA_SCORE = 45.0


def _finite(value: Any) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _rate(value: Any) -> float | None:
    val = _finite(value)
    if val is None:
        return None
    if abs(val) > 1.0:
        val /= 100.0
    return _clamp(val, 0.0, 1.0)


def _logit(probability: float) -> float:
    p = _clamp(probability, 1e-6, 1.0 - 1e-6)
    return math.log(p / (1.0 - p))


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def _score_shift(
    score: Any,
    coverage: Any,
    max_logit_shift: float,
    favorable_when_high: bool = True,
) -> float:
    """Convert a certified 0-100 descriptive score into a bounded logit shift."""
    s = _finite(score)
    if s is None:
        return 0.0
    c = _rate(coverage)
    if c is None:
        c = 1.0
    signal = _clamp((s - 50.0) / 25.0, -1.0, 1.0)
    if not favorable_when_high:
        signal *= -1.0
    return signal * _clamp(c, 0.0, 1.0) * float(max_logit_shift)


def _weighted_mean(values: list[tuple[float | None, float]]) -> float | None:
    used = [(float(v), float(w)) for v, w in values if v is not None and w > 0]
    total = sum(w for _, w in used)
    if total <= 0:
        return None
    return sum(v * w for v, w in used) / total


def base_hit_probability(
    hitter_profile: dict[str, Any] | None,
    opportunity_profile: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build a neutral hit-per-PA baseline from season results and expected contact."""
    hitter = hitter_profile or {}
    opportunity = opportunity_profile or {}
    season_hpp = _rate(hitter.get("hit_per_pa"))
    xba = _rate(hitter.get("xba"))
    ab_per_pa = _rate(opportunity.get("ab_per_pa"))
    xba_hpp = xba * ab_per_pa if xba is not None and ab_per_pa is not None else None

    # Season H/PA anchors the event probability. xBA is translated into PA space
    # through the hitter's own AB/PA rate and can refine, never replace, the anchor.
    baseline = _weighted_mean([(season_hpp, 0.70), (xba_hpp, 0.30)])
    if baseline is None:
        neutral_avg = _rate(hitter.get("neutral_hit_skill"))
        baseline = neutral_avg * ab_per_pa if neutral_avg is not None and ab_per_pa is not None else season_hpp
    if baseline is not None:
        baseline = _clamp(baseline, MIN_BASE_HIT_PER_PA, MAX_BASE_HIT_PER_PA)

    return {
        "base_hit_per_pa": baseline,
        "season_hit_per_pa": season_hpp,
        "xba_hit_per_pa": xba_hpp,
        "ab_per_pa": ab_per_pa,
    }


def starter_hit_probability(
    base_probability: float,
    starter_profile: dict[str, Any] | None,
    platoon_profile: dict[str, Any] | None,
    pitch_mix_profile: dict[str, Any] | None,
    batted_ball_profile: dict[str, Any] | None,
    environment_profile: dict[str, Any] | None,
    recent_profile: dict[str, Any] | None,
    starter_pa: float | None = None,
) -> dict[str, Any]:
    """Raw per-PA hit probability against the scheduled starter."""
    starter = starter_profile or {}
    platoon = platoon_profile or {}
    pitch = pitch_mix_profile or {}
    batted = batted_ball_profile or {}
    env = environment_profile or {}
    recent = recent_profile or {}

    shifts = {
        "starter_quality": _score_shift(
            starter.get("starter_strength_score"),
            starter.get("starter_strength_coverage"),
            0.26,
            favorable_when_high=False,
        ),
        "platoon_bvp": _score_shift(
            platoon.get("platoon_context_score"),
            platoon.get("platoon_context_coverage"),
            0.18,
            favorable_when_high=True,
        ),
        "pitch_mix": _score_shift(
            pitch.get("pitch_mix_score"),
            pitch.get("pitch_mix_coverage"),
            0.18,
            favorable_when_high=True,
        ),
        "batted_ball": _score_shift(
            batted.get("batted_ball_score"),
            batted.get("batted_ball_reliability"),
            0.10,
            favorable_when_high=True,
        ),
        "environment": _score_shift(
            env.get("environment_score"),
            env.get("environment_coverage"),
            0.10,
            favorable_when_high=True,
        ),
    }

    recent_coverage = _rate(recent.get("recent_form_coverage")) or 0.0
    stability = _rate((recent.get("stability_score") or 50) / 100.0) or 0.50
    recent_authority = recent_coverage * (0.50 + 0.50 * stability)
    shifts["recent_form"] = _score_shift(
        recent.get("recent_form_score"),
        recent_authority,
        0.08,
        favorable_when_high=True,
    )

    # TTO is small and only gets authority when the hitter is expected to receive
    # enough starter PA for a possible third look.
    tto_delta = _finite(starter.get("third_time_avg_delta"))
    tto_authority = _clamp(((float(starter_pa or 0.0) - 2.0) / 1.5), 0.0, 1.0)
    shifts["times_through_order"] = (
        _clamp(float(tto_delta) / 0.050, -1.0, 1.0) * 0.06 * tto_authority
        if tto_delta is not None else 0.0
    )

    total_shift = _clamp(sum(shifts.values()), -0.65, 0.65)
    probability = _sigmoid(_logit(base_probability) + total_shift)
    probability = _clamp(probability, 0.05, 0.45)
    return {
        "probability": probability,
        "total_logit_shift": total_shift,
        "shifts": shifts,
    }


def bullpen_hit_probability(
    base_probability: float,
    bullpen_profile: dict[str, Any] | None,
    batted_ball_profile: dict[str, Any] | None,
    environment_profile: dict[str, Any] | None,
    recent_profile: dict[str, Any] | None,
) -> dict[str, Any]:
    """Raw per-PA hit probability against the expected relief path."""
    bullpen = bullpen_profile or {}
    batted = batted_ball_profile or {}
    env = environment_profile or {}
    recent = recent_profile or {}

    bullpen_coverage = _rate(bullpen.get("bullpen_quality_coverage")) or 0.0
    availability_known = _rate(bullpen.get("availability_index"))
    if availability_known is not None:
        bullpen_coverage *= 0.80 + 0.20 * availability_known

    shifts = {
        "bullpen_path": _score_shift(
            bullpen.get("bullpen_path_score"),
            bullpen_coverage,
            0.26,
            favorable_when_high=False,
        ),
        "batted_ball": _score_shift(
            batted.get("batted_ball_score"),
            batted.get("batted_ball_reliability"),
            0.12,
            favorable_when_high=True,
        ),
        "environment": _score_shift(
            env.get("environment_score"),
            env.get("environment_coverage"),
            0.10,
            favorable_when_high=True,
        ),
    }

    recent_coverage = _rate(recent.get("recent_form_coverage")) or 0.0
    stability = _rate((recent.get("stability_score") or 50) / 100.0) or 0.50
    recent_authority = recent_coverage * (0.50 + 0.50 * stability)
    shifts["recent_form"] = _score_shift(
        recent.get("recent_form_score"),
        recent_authority,
        0.08,
        favorable_when_high=True,
    )

    total_shift = _clamp(sum(shifts.values()), -0.55, 0.55)
    probability = _sigmoid(_logit(base_probability) + total_shift)
    probability = _clamp(probability, 0.05, 0.45)
    return {
        "probability": probability,
        "total_logit_shift": total_shift,
        "shifts": shifts,
    }


def segment_exposure(
    opportunity_profile: dict[str, Any] | None,
    bullpen_profile: dict[str, Any] | None,
) -> dict[str, Any]:
    """Resolve expected PA against starter and bullpen without inventing a split."""
    opportunity = opportunity_profile or {}
    bullpen = bullpen_profile or {}
    expected_pa = _finite(opportunity.get("expected_pa"))
    starter_pa = _finite(opportunity.get("nominal_starter_pa"))
    bullpen_pa = _finite(opportunity.get("nominal_bullpen_pa"))

    if expected_pa is None or expected_pa < MIN_EXPECTED_PA:
        return {"status": "GATED", "expected_pa": expected_pa, "starter_pa": None, "bullpen_pa": None, "basis": "expected PA unavailable"}

    if starter_pa is not None and bullpen_pa is not None and starter_pa + bullpen_pa > 0:
        scale = expected_pa / (starter_pa + bullpen_pa)
        return {
            "status": "VERIFIED",
            "expected_pa": expected_pa,
            "starter_pa": max(0.0, starter_pa * scale),
            "bullpen_pa": max(0.0, bullpen_pa * scale),
            "basis": "Step 9 nominal starter/bullpen PA exposure",
        }

    share = _rate(bullpen.get("bullpen_inning_share"))
    if share is not None:
        return {
            "status": "VERIFIED",
            "expected_pa": expected_pa,
            "starter_pa": expected_pa * (1.0 - share),
            "bullpen_pa": expected_pa * share,
            "basis": "Step 8 bullpen inning share applied to Step 9 expected PA",
        }

    return {"status": "GATED", "expected_pa": expected_pa, "starter_pa": None, "bullpen_pa": None, "basis": "starter/bullpen PA split unavailable"}


def _fractional_event_probabilities(expected_count: float, probability: float) -> list[float]:
    count = max(0.0, float(expected_count or 0.0))
    full = int(math.floor(count))
    frac = count - full
    events = [float(probability)] * full
    if frac > 1e-9:
        events.append(frac * float(probability))
    return events


def analytical_distribution(
    starter_pa: float,
    bullpen_pa: float,
    starter_probability: float,
    bullpen_probability: float,
) -> dict[str, Any]:
    """Point-estimate Poisson-binomial distribution with fractional-PA support."""
    event_probabilities = (
        _fractional_event_probabilities(starter_pa, starter_probability)
        + _fractional_event_probabilities(bullpen_pa, bullpen_probability)
    )
    if not event_probabilities:
        return {"distribution": {0: 1.0}, "expected_hits": 0.0, "p0": 1.0, "p1_plus": 0.0, "p2_plus": 0.0, "p_exactly_1": 0.0, "median_hits": 0, "mode_hits": 0}

    dist = np.array([1.0], dtype=float)
    for p in event_probabilities:
        p = _clamp(p, 0.0, 1.0)
        next_dist = np.zeros(len(dist) + 1, dtype=float)
        next_dist[:-1] += dist * (1.0 - p)
        next_dist[1:] += dist * p
        dist = next_dist

    distribution = {int(i): float(v) for i, v in enumerate(dist)}
    p0 = float(dist[0])
    p1 = float(dist[1]) if len(dist) > 1 else 0.0
    expected_hits = float(sum(i * v for i, v in distribution.items()))
    cdf = np.cumsum(dist)
    median_hits = int(np.argmax(cdf >= 0.50))
    mode_hits = int(np.argmax(dist))
    return {
        "distribution": distribution,
        "expected_hits": expected_hits,
        "p0": p0,
        "p1_plus": 1.0 - p0,
        "p2_plus": max(0.0, 1.0 - p0 - p1),
        "p_exactly_1": p1,
        "median_hits": median_hits,
        "mode_hits": mode_hits,
    }


def _segment_sigma(data_scores: list[Any], projected: bool, stability_score: Any) -> float:
    values = [_finite(v) for v in data_scores]
    values = [v for v in values if v is not None]
    quality = sum(values) / len(values) if values else 50.0
    stability = _finite(stability_score)
    stability = 50.0 if stability is None else _clamp(stability, 0.0, 100.0)
    sigma = 0.10 + (1.0 - quality / 100.0) * 0.24 + (1.0 - stability / 100.0) * 0.08
    if projected:
        sigma += 0.06
    return _clamp(sigma, 0.10, 0.42)


def monte_carlo_distribution(
    starter_pa: float,
    bullpen_pa: float,
    starter_probability: float,
    bullpen_probability: float,
    starter_sigma: float,
    bullpen_sigma: float,
    simulations: int = MONTE_CARLO_SIMS,
    seed: int = MONTE_CARLO_SEED,
    batch_size: int = MONTE_CARLO_BATCH,
) -> dict[str, Any]:
    """Uncertainty-aware Monte Carlo distribution with fixed seed and batch diagnostics."""
    sims = max(1, int(simulations))
    batch = max(1, min(int(batch_size), sims))
    rng = np.random.default_rng(int(seed))
    max_hits = max(12, int(math.ceil(starter_pa + bullpen_pa)) + 2)
    counts = np.zeros(max_hits + 1, dtype=np.int64)
    total_hits = 0.0
    batch_p1: list[float] = []

    s_floor = int(math.floor(max(0.0, starter_pa)))
    b_floor = int(math.floor(max(0.0, bullpen_pa)))
    s_frac = max(0.0, starter_pa) - s_floor
    b_frac = max(0.0, bullpen_pa) - b_floor
    s_logit = _logit(starter_probability)
    b_logit = _logit(bullpen_probability)

    remaining = sims
    while remaining > 0:
        n = min(batch, remaining)
        ps = 1.0 / (1.0 + np.exp(-(s_logit + rng.normal(0.0, float(starter_sigma), n))))
        pb = 1.0 / (1.0 + np.exp(-(b_logit + rng.normal(0.0, float(bullpen_sigma), n))))
        ns = np.full(n, s_floor, dtype=np.int16)
        nb = np.full(n, b_floor, dtype=np.int16)
        if s_frac > 1e-12:
            ns += (rng.random(n) < s_frac).astype(np.int16)
        if b_frac > 1e-12:
            nb += (rng.random(n) < b_frac).astype(np.int16)
        hs = rng.binomial(ns, ps)
        hb = rng.binomial(nb, pb)
        hits = hs + hb
        binc = np.bincount(hits, minlength=max_hits + 1)
        if len(binc) > len(counts):
            counts = np.pad(counts, (0, len(binc) - len(counts)))
        counts[: len(binc)] += binc
        total_hits += float(hits.sum())
        batch_p1.append(float(np.mean(hits >= 1)))
        remaining -= n

    probs = counts.astype(float) / float(sims)
    distribution = {int(i): float(v) for i, v in enumerate(probs) if v > 0.0}
    p0 = float(probs[0])
    p1 = float(probs[1]) if len(probs) > 1 else 0.0
    p1_plus = 1.0 - p0
    p2_plus = max(0.0, 1.0 - p0 - p1)
    cdf = np.cumsum(probs)
    median_hits = int(np.argmax(cdf >= 0.50))
    mode_hits = int(np.argmax(probs))
    se = math.sqrt(max(p1_plus * (1.0 - p1_plus), 0.0) / sims)
    max_batch_diff = (max(batch_p1) - min(batch_p1)) if len(batch_p1) >= 2 else 0.0
    convergence = bool(se <= 0.0005 and max_batch_diff <= 0.006)

    return {
        "distribution": distribution,
        "expected_hits": total_hits / float(sims),
        "p0": p0,
        "p1_plus": p1_plus,
        "p2_plus": p2_plus,
        "p_exactly_1": p1,
        "median_hits": median_hits,
        "mode_hits": mode_hits,
        "simulations": sims,
        "batches": len(batch_p1),
        "seed": int(seed),
        "mc_se_p1_plus": se,
        "max_batch_difference": max_batch_diff,
        "converged": convergence,
    }


def american_fair_odds(probability: Any) -> int | None:
    """Raw mathematical fair odds only; Step 12 will own calibrated final fair odds."""
    p = _rate(probability)
    if p is None or p <= 0.0 or p >= 1.0:
        return None
    if p >= 0.5:
        return int(round(-100.0 * p / (1.0 - p)))
    return int(round(100.0 * (1.0 - p) / p))


def _composite_data_score(profiles: list[tuple[dict[str, Any] | None, str]]) -> float:
    values = []
    for profile, key in profiles:
        value = _finite((profile or {}).get(key))
        if value is not None:
            values.append(_clamp(value, 0.0, 100.0))
    return sum(values) / len(values) if values else 0.0


def build_probability_profile(
    foundation: dict[str, Any] | None,
    hitter_profile: dict[str, Any] | None,
    starter_profile: dict[str, Any] | None,
    platoon_profile: dict[str, Any] | None,
    pitch_mix_profile: dict[str, Any] | None,
    batted_ball_profile: dict[str, Any] | None,
    environment_profile: dict[str, Any] | None,
    bullpen_profile: dict[str, Any] | None,
    opportunity_profile: dict[str, Any] | None,
    recent_profile: dict[str, Any] | None,
    simulations: int = MONTE_CARLO_SIMS,
) -> dict[str, Any]:
    """Combine certified Steps 1-10 into raw Step 11 hit probabilities."""
    foundation = foundation or {}
    hitter = hitter_profile or {}
    starter = starter_profile or {}
    platoon = platoon_profile or {}
    pitch = pitch_mix_profile or {}
    batted = batted_ball_profile or {}
    env = environment_profile or {}
    bullpen = bullpen_profile or {}
    opportunity = opportunity_profile or {}
    recent = recent_profile or {}

    base = base_hit_probability(hitter, opportunity)
    exposure = segment_exposure(opportunity, bullpen)
    base_p = base.get("base_hit_per_pa")

    composite_data = _composite_data_score([
        (hitter, "hitter_profile_score"),
        (starter, "starter_profile_score"),
        (platoon, "matchup_data_score"),
        (pitch, "pitch_mix_data_score"),
        (batted, "batted_ball_data_score"),
        (env, "environment_data_score"),
        (bullpen, "bullpen_data_score"),
        (opportunity, "opportunity_data_score"),
        (recent, "recent_data_score"),
    ])

    gates: list[str] = []
    if not foundation.get("valid_slot"):
        gates.append("valid batting-order slot required")
    if not foundation.get("starter_id"):
        gates.append("opposing starter identity required")
    if base_p is None:
        gates.append("neutral hit-per-PA baseline unavailable")
    if exposure.get("status") != "VERIFIED":
        gates.append(str(exposure.get("basis") or "starter/bullpen exposure unavailable"))
    if composite_data < MIN_COMPOSITE_DATA_SCORE:
        gates.append(f"composite Step 2-10 data score below {int(MIN_COMPOSITE_DATA_SCORE)}")

    if gates:
        return {
            **foundation,
            **base,
            **exposure,
            "probability_status": "GATED",
            "probability_gates": gates,
            "composite_data_score": composite_data,
            "starter_hit_per_pa": None,
            "bullpen_hit_per_pa": None,
            "p0": None,
            "p1_plus": None,
            "p2_plus": None,
            "p_exactly_1": None,
            "expected_hits": None,
            "median_hits": None,
            "mode_hits": None,
            "raw_fair_odds_1_plus": None,
            "point_distribution": {},
            "monte_carlo_distribution": {},
            "calibration_status": "DEFERRED_TO_STEP12",
        }

    starter_pa = float(exposure["starter_pa"])
    bullpen_pa = float(exposure["bullpen_pa"])
    starter_result = starter_hit_probability(base_p, starter, platoon, pitch, batted, env, recent, starter_pa)
    bullpen_result = bullpen_hit_probability(base_p, bullpen, batted, env, recent)

    projected = bool(foundation.get("projected")) and not bool(foundation.get("confirmed"))
    starter_sigma = _segment_sigma(
        [
            starter.get("starter_profile_score"),
            platoon.get("matchup_data_score"),
            pitch.get("pitch_mix_data_score"),
            batted.get("batted_ball_data_score"),
            env.get("environment_data_score"),
            recent.get("recent_data_score"),
        ],
        projected,
        recent.get("stability_score"),
    )
    bullpen_sigma = _segment_sigma(
        [
            bullpen.get("bullpen_data_score"),
            batted.get("batted_ball_data_score"),
            env.get("environment_data_score"),
            recent.get("recent_data_score"),
        ],
        projected,
        recent.get("stability_score"),
    )

    point = analytical_distribution(
        starter_pa,
        bullpen_pa,
        float(starter_result["probability"]),
        float(bullpen_result["probability"]),
    )
    mc = monte_carlo_distribution(
        starter_pa,
        bullpen_pa,
        float(starter_result["probability"]),
        float(bullpen_result["probability"]),
        starter_sigma,
        bullpen_sigma,
        simulations=int(simulations),
    )

    if foundation.get("confirmed") and composite_data >= 75 and mc.get("converged"):
        status = "READY_RAW"
    elif composite_data >= MIN_COMPOSITE_DATA_SCORE:
        status = "PROVISIONAL_RAW"
    else:
        status = "GATED"

    return {
        **foundation,
        **base,
        **exposure,
        "probability_status": status,
        "probability_gates": [],
        "composite_data_score": composite_data,
        "starter_hit_per_pa": starter_result.get("probability"),
        "bullpen_hit_per_pa": bullpen_result.get("probability"),
        "starter_total_logit_shift": starter_result.get("total_logit_shift"),
        "bullpen_total_logit_shift": bullpen_result.get("total_logit_shift"),
        "starter_adjustments": starter_result.get("shifts") or {},
        "bullpen_adjustments": bullpen_result.get("shifts") or {},
        "starter_probability_sigma": starter_sigma,
        "bullpen_probability_sigma": bullpen_sigma,
        "point_distribution": point,
        "monte_carlo_distribution": mc.get("distribution") or {},
        "point_p1_plus": point.get("p1_plus"),
        "point_expected_hits": point.get("expected_hits"),
        "p0": mc.get("p0"),
        "p1_plus": mc.get("p1_plus"),
        "p2_plus": mc.get("p2_plus"),
        "p_exactly_1": mc.get("p_exactly_1"),
        "expected_hits": mc.get("expected_hits"),
        "median_hits": mc.get("median_hits"),
        "mode_hits": mc.get("mode_hits"),
        "raw_fair_odds_1_plus": american_fair_odds(mc.get("p1_plus")),
        "simulations": mc.get("simulations"),
        "batches": mc.get("batches"),
        "random_seed": mc.get("seed"),
        "mc_se_p1_plus": mc.get("mc_se_p1_plus"),
        "max_batch_difference": mc.get("max_batch_difference"),
        "monte_carlo_converged": mc.get("converged"),
        "calibration_status": "DEFERRED_TO_STEP12",
    }


__all__ = [
    "MAX_BASE_HIT_PER_PA",
    "MIN_BASE_HIT_PER_PA",
    "MIN_COMPOSITE_DATA_SCORE",
    "MIN_EXPECTED_PA",
    "MONTE_CARLO_BATCH",
    "MONTE_CARLO_SEED",
    "MONTE_CARLO_SIMS",
    "american_fair_odds",
    "analytical_distribution",
    "base_hit_probability",
    "build_probability_profile",
    "bullpen_hit_probability",
    "monte_carlo_distribution",
    "segment_exposure",
    "starter_hit_probability",
]
