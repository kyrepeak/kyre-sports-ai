"""NFL Passing Yards Step 8 — bounded context + uncertainty envelope.

Step 7 created the first sportsbook-free volume × efficiency baseline. Step 8
adds only context that can be translated without inventing an unsupported
coefficient, and it makes uncertainty visible instead of hiding it.

Central adjustment policy
-------------------------
Pressure is allowed one mechanical opportunity adjustment. The matchup sack
rate is the mean of verified offense sacks-allowed rate and opponent defensive
sack rate. We compare that matchup rate with the offense's own season sack rate,
cap the difference to ±5 percentage points, and translate only that difference
into pass-attempt opportunity. YPA is not numerically changed by pressure.

Personnel, weather, rest and site/travel remain qualitative in Step 8. Their
exact effect sizes have not been calibrated, so they may lower evidence-quality
confidence but cannot receive made-up yardage bonuses or penalties.

Uncertainty policy
------------------
The envelope is descriptive, not a probability interval. It uses two observable
sources when available:
1) recent-game passing-yard sample standard deviation (last five, minimum three),
2) Step 7 source-disagreement envelope from the min/max verified attempt and YPA
   components that fed the baseline.
When both exist, Step 8 displays the wider union so the page does not pretend to
know more than the underlying evidence.

No sportsbook line, price, market consensus, implied probability, no-vig input,
Monte Carlo probability, fair line, EV, ranking or recommendation is used here.
"""
from __future__ import annotations

import math
from statistics import stdev
from typing import Any

MODEL_VERSION = "NFL PASSING YARDS STEP 8 • CONTEXT + UNCERTAINTY V1"
MAX_SACK_RATE_DELTA_PCT = 5.0
MIN_RECENT_GAMES_FOR_BAND = 3
MAX_RECENT_GAMES_FOR_BAND = 5


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _num(value: Any):
    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("%", "").strip()
        out = float(value)
        return out if math.isfinite(out) else math.nan
    except Exception:
        return math.nan


def _finite(value: Any) -> bool:
    return math.isfinite(_num(value))


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _qb_hard_status(status: Any) -> bool:
    s = _safe(status).upper()
    return (
        s == "IR"
        or any(token in s for token in ("OUT", "INJURED RESERVE", " PUP", "PUP ", "RESERVE", "DOUBTFUL"))
    )


def pressure_opportunity_adjustment(step7: dict, pressure_ctx: dict) -> dict:
    """Translate only verified sack-rate delta into pass-attempt opportunity."""
    attempts = _num(step7.get("expected_attempts"))
    ypa = _num(step7.get("expected_ypa"))
    offense_rate = _num((pressure_ctx.get("offense") or {}).get("sack_rate_allowed"))
    defense_rate = _num((pressure_ctx.get("defense") or {}).get("sack_rate_generated"))

    base = {
        "ready": False,
        "reason": "verified offense/defense sack rates unavailable",
        "offense_sack_rate_pct": offense_rate,
        "defense_sack_rate_pct": defense_rate,
        "matchup_sack_rate_pct": math.nan,
        "raw_delta_pct_points": math.nan,
        "bounded_delta_pct_points": 0.0,
        "cap_hit": False,
        "attempt_adjustment": 0.0,
        "yard_adjustment": 0.0,
    }
    if not (_finite(attempts) and attempts > 0 and _finite(ypa) and ypa > 0):
        base["reason"] = "Step 7 attempts/YPA baseline unavailable"
        return base
    if not (pressure_ctx.get("ready") and _finite(offense_rate) and _finite(defense_rate)):
        return base

    matchup_rate = (offense_rate + defense_rate) / 2.0
    raw_delta = matchup_rate - offense_rate
    bounded_delta = _clamp(raw_delta, -MAX_SACK_RATE_DELTA_PCT, MAX_SACK_RATE_DELTA_PCT)
    attempt_adjustment = -(attempts * bounded_delta / 100.0)
    yard_adjustment = attempt_adjustment * ypa
    base.update({
        "ready": True,
        "reason": "",
        "matchup_sack_rate_pct": matchup_rate,
        "raw_delta_pct_points": raw_delta,
        "bounded_delta_pct_points": bounded_delta,
        "cap_hit": abs(raw_delta) > MAX_SACK_RATE_DELTA_PCT,
        "attempt_adjustment": attempt_adjustment,
        "yard_adjustment": yard_adjustment,
    })
    return base


def recent_variability_band(qb_profile: dict, central_yards: Any) -> dict:
    central = _num(central_yards)
    games = qb_profile.get("recent_games") or []
    values = []
    for row in games[:MAX_RECENT_GAMES_FOR_BAND]:
        value = _num((row or {}).get("passing_yards"))
        if _finite(value):
            values.append(value)
    base = {
        "ready": False,
        "games": len(values),
        "sample_std_yards": math.nan,
        "lower": math.nan,
        "upper": math.nan,
        "basis": f"needs at least {MIN_RECENT_GAMES_FOR_BAND} verified recent games",
    }
    if not _finite(central) or len(values) < MIN_RECENT_GAMES_FOR_BAND:
        return base
    spread = float(stdev(values))
    base.update({
        "ready": True,
        "sample_std_yards": spread,
        "lower": max(0.0, central - spread),
        "upper": central + spread,
        "basis": f"last {len(values)} verified QB games ± one observed sample SD; descriptive only",
    })
    return base


def source_disagreement_band(step7: dict, central_yards: Any) -> dict:
    """Envelope implied by the verified Step 7 source inputs, not a CI."""
    central = _num(central_yards)
    attempts = [_num(row.get("value")) for row in (step7.get("attempt_components") or [])]
    ypas = [_num(row.get("value")) for row in (step7.get("ypa_components") or [])]
    attempts = [x for x in attempts if _finite(x) and x > 0]
    ypas = [x for x in ypas if _finite(x) and x > 0]
    base = {"ready": False, "lower": math.nan, "upper": math.nan, "basis": "Step 7 source components incomplete"}
    if not _finite(central) or not attempts or not ypas:
        return base
    low = min(attempts) * min(ypas)
    high = max(attempts) * max(ypas)
    base.update({
        "ready": True,
        "lower": min(low, central),
        "upper": max(high, central),
        "min_attempt_input": min(attempts),
        "max_attempt_input": max(attempts),
        "min_ypa_input": min(ypas),
        "max_ypa_input": max(ypas),
        "basis": "min/max verified Step 7 attempt × YPA source disagreement; descriptive only",
    })
    return base


def combined_uncertainty_band(step7: dict, qb_profile: dict, central_yards: Any) -> dict:
    recent = recent_variability_band(qb_profile, central_yards)
    source = source_disagreement_band(step7, central_yards)
    bands = [band for band in (recent, source) if band.get("ready")]
    if not bands:
        return {
            "ready": False,
            "lower": math.nan,
            "upper": math.nan,
            "recent": recent,
            "source": source,
            "basis": "no verified uncertainty envelope available",
            "band_type": "DESCRIPTIVE ENVELOPE — NOT A PROBABILITY INTERVAL",
        }
    return {
        "ready": True,
        "lower": min(_num(band.get("lower")) for band in bands),
        "upper": max(_num(band.get("upper")) for band in bands),
        "recent": recent,
        "source": source,
        "basis": "wider union of available recent-variability and source-disagreement envelopes",
        "band_type": "DESCRIPTIVE ENVELOPE — NOT A PROBABILITY INTERVAL",
    }


def evidence_confidence(step7: dict, pressure_adj: dict, personnel_ctx: dict, environment_ctx: dict, side: str, uncertainty: dict) -> tuple[str, str]:
    """Qualitative evidence quality; never interpreted as hit probability."""
    if not step7.get("ready"):
        return "CHECK", "Step 7 baseline is not ready"

    qb_status = _safe(personnel_ctx.get("qb_status"), "No listed injury")
    if _qb_hard_status(qb_status):
        return "CHECK", f"verified QB status is {qb_status}"

    flags = []
    coverage = _safe(step7.get("coverage_grade"), "CHECK").upper()
    personnel = _safe(personnel_ctx.get("personnel_label"), "CHECK").upper()
    weather = _safe(environment_ctx.get("weather_label"), "CHECK").upper()
    rest = environment_ctx.get(f"{_safe(side).lower()}_rest") or {}
    turnaround = _num(rest.get("turnaround_days"))

    if coverage != "GREEN":
        flags.append("Step 7 coverage not GREEN")
    if not pressure_adj.get("ready"):
        flags.append("pressure adjustment unavailable")
    if personnel in {"HURT", "MIXED", "WATCH", "CHECK"}:
        flags.append(f"personnel {personnel}")
    if weather in {"WATCH", "CHECK"}:
        flags.append(f"weather {weather}")
    if _finite(turnaround) and turnaround <= 5:
        flags.append("short turnaround")
    if not uncertainty.get("ready"):
        flags.append("uncertainty envelope unavailable")

    severe = personnel in {"HURT", "MIXED"} or weather == "WATCH"
    if severe:
        return "LOW", " • ".join(flags) if flags else "meaningful contextual uncertainty"
    if flags:
        return "MEDIUM", " • ".join(flags)
    return "HIGH", "verified baseline, pressure and uncertainty evidence with no active personnel/weather/rest warning"


def build_context_projection(
    step7: dict,
    qb_profile: dict,
    pressure_ctx: dict,
    personnel_ctx: dict,
    environment_ctx: dict,
    side: str,
    preseason: bool = False,
) -> dict:
    baseline = _num(step7.get("projection_yards"))
    expected_attempts = _num(step7.get("expected_attempts"))
    expected_ypa = _num(step7.get("expected_ypa"))
    qb_status = _safe(personnel_ctx.get("qb_status"), "No listed injury")

    result = {
        "ready": False,
        "reason": "",
        "qb_name": _safe(step7.get("qb_name"), "Unresolved QB1"),
        "baseline_yards": baseline,
        "context_projection_yards": math.nan,
        "baseline_attempts": expected_attempts,
        "context_attempts": math.nan,
        "expected_ypa": expected_ypa,
        "pressure_adjustment_yards": 0.0,
        "personnel_adjustment_yards": 0.0,
        "weather_adjustment_yards": 0.0,
        "rest_adjustment_yards": 0.0,
        "sportsbook_influence": 0.0,
        "monte_carlo_enabled": False,
        "probability_enabled": False,
    }
    if preseason:
        result["reason"] = "preseason workload remains uncertified"
        return result
    if not step7.get("ready") or not (_finite(baseline) and _finite(expected_attempts) and _finite(expected_ypa)):
        result["reason"] = "Step 7 verified baseline is required"
        return result
    if _qb_hard_status(qb_status):
        result["reason"] = f"verified QB status {qb_status} blocks a full-game contextual projection"
        return result

    pressure_adj = pressure_opportunity_adjustment(step7, pressure_ctx)
    attempt_adj = _num(pressure_adj.get("attempt_adjustment")) if pressure_adj.get("ready") else 0.0
    yard_adj = _num(pressure_adj.get("yard_adjustment")) if pressure_adj.get("ready") else 0.0
    context_attempts = max(0.0, expected_attempts + attempt_adj)
    central = max(0.0, baseline + yard_adj)
    uncertainty = combined_uncertainty_band(step7, qb_profile, central)
    confidence, confidence_basis = evidence_confidence(step7, pressure_adj, personnel_ctx, environment_ctx, side, uncertainty)

    result.update({
        "ready": True,
        "reason": "",
        "context_projection_yards": central,
        "context_attempts": context_attempts,
        "pressure_adjustment_yards": yard_adj,
        "pressure": pressure_adj,
        "uncertainty": uncertainty,
        "uncertainty_lower": uncertainty.get("lower"),
        "uncertainty_upper": uncertainty.get("upper"),
        "confidence": confidence,
        "confidence_basis": confidence_basis,
        "personnel_context": _safe(personnel_ctx.get("personnel_label"), "CHECK"),
        "weather_context": _safe(environment_ctx.get("weather_label"), "CHECK"),
        "rest_context": _safe((environment_ctx.get(f"{_safe(side).lower()}_rest") or {}).get("rest_label"), "CHECK"),
        "central_adjustment_policy": "PRESSURE OPPORTUNITY ONLY; PERSONNEL/WEATHER/REST NUMERIC EFFECTS = 0.0",
    })
    return result


__all__ = [
    "MAX_SACK_RATE_DELTA_PCT",
    "MIN_RECENT_GAMES_FOR_BAND",
    "MODEL_VERSION",
    "build_context_projection",
    "combined_uncertainty_band",
    "evidence_confidence",
    "pressure_opportunity_adjustment",
    "recent_variability_band",
    "source_disagreement_band",
]
