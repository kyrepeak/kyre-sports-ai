"""CFB Over/Under Intelligence V2 — Upgrade Step 12 final certification.

This is a read-only integrity layer above permanently frozen Upgrade Step 11.
It adds no prediction feature and changes no projection, probability, selection,
reliability, sigma, or qualification threshold.

The certifier validates:
- exact game identity/date gates,
- projected team-points arithmetic,
- probability mass/ranges,
- final-selection coherence with raw model output,
- frozen Step-9 selection thresholds,
- Step-11 apply/gate behavior,
- all analysis-line *_weight fields remain zero,
- no sportsbook/price/market-probability/EV/Monte Carlo flags are active.

A data-gated game may still PASS integrity certification. "DATA_GATED" means the
pipeline safely refused to produce a complete model output; it does not mean an
integrity failure.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping

import cfb_over_under_final_v1 as final_rules

MODEL_VERSION = "CFB O/U FINAL CERTIFICATION V1 • UPGRADE STEP 12"
FROZEN_STEP11_SLATE = "cfb_over_under_slate_v10"
CERTIFIED_UPGRADE_STEPS = tuple(range(1, 13))

PROJECTION_MATH_CHANGED = False
SELECTION_MATH_CHANGED = False
RELIABILITY_CHANGED = False
STRUCTURAL_SIGMA_CHANGED = False
QUALIFICATION_THRESHOLDS_CHANGED = False

_TOL = 1e-9
_MARKET_FLAGS = (
    "sportsbook_input_used",
    "market_price_used",
    "market_probability_used",
    "edge_or_ev_used",
    "monte_carlo_used",
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except Exception:
        return False


def _close(a: Any, b: Any, tol: float = _TOL) -> bool:
    if not _finite(a) or not _finite(b):
        return False
    return abs(float(a) - float(b)) <= float(tol)


def _identity(game: Mapping[str, Any]) -> str:
    return _clean(game.get("identity_key") or game.get("game_id"))


def _fingerprint(game: Mapping[str, Any], raw: Mapping[str, Any], final: Mapping[str, Any]) -> str:
    payload = {
        "identity": _identity(game),
        "away": raw.get("projected_away_points"),
        "home": raw.get("projected_home_points"),
        "total": raw.get("projected_total"),
        "sigma": raw.get("structural_total_sigma"),
        "line": raw.get("analysis_line"),
        "over": raw.get("over_probability"),
        "under": raw.get("under_probability"),
        "push": raw.get("push_probability"),
        "selection": final.get("selection"),
        "grade": final.get("grade"),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _zero_analysis_weight_fields(raw: Mapping[str, Any], final: Mapping[str, Any]) -> tuple[bool, list[str]]:
    bad: list[str] = []
    for label, obj in (("raw", raw), ("final", final)):
        for key, value in obj.items():
            k = _clean(key).lower()
            if "analysis_line" not in k or not k.endswith("_weight"):
                continue
            if not _finite(value) or abs(float(value)) > _TOL:
                bad.append(f"{label}.{key}={value!r}")
    return not bad, bad


def _market_firewall(raw: Mapping[str, Any], final: Mapping[str, Any]) -> tuple[bool, list[str]]:
    bad: list[str] = []
    for label, obj in (("raw", raw), ("final", final)):
        for key in _MARKET_FLAGS:
            if obj.get(key) is True:
                bad.append(f"{label}.{key}=True")
    return not bad, bad


def certify_result(result: Mapping[str, Any]) -> dict[str, Any]:
    game = dict(result.get("game") or {})
    raw = dict(result.get("raw") or {})
    final = dict(result.get("final") or {})
    step10_raw = dict(result.get("step10_raw") or {})
    form = dict(result.get("form_strength_engine") or {})

    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool | None, detail: str, *, blocking: bool = True) -> None:
        status = "SKIP" if passed is None else ("PASS" if passed else "FAIL")
        checks.append({
            "name": name,
            "status": status,
            "passed": passed,
            "blocking": bool(blocking),
            "detail": detail,
        })

    identity = _identity(game)
    add("game identity present", bool(identity), identity or "missing identity")

    if "identity_verified" in game:
        add(
            "schedule identity verified",
            game.get("identity_verified") is True,
            f"identity_verified={game.get('identity_verified')!r}",
        )
    else:
        add("schedule identity verified", None, "field unavailable in supplied result", blocking=False)

    if "date_matches_query" in game:
        add(
            "game date matches query",
            game.get("date_matches_query") is True,
            f"date_matches_query={game.get('date_matches_query')!r}",
        )
    else:
        add("game date matches query", None, "field unavailable in supplied result", blocking=False)

    raw_ready = raw.get("ready") is True
    final_ready = final.get("ready") is True
    add("raw model ready", raw_ready, f"ready={raw.get('ready')!r}", blocking=False)
    add("final synthesis ready", final_ready, f"ready={final.get('ready')!r}", blocking=False)

    if raw_ready:
        away = raw.get("projected_away_points")
        home = raw.get("projected_home_points")
        total = raw.get("projected_total")
        add(
            "projected total arithmetic",
            _finite(away) and _finite(home) and _finite(total)
            and _close(_f(away) + _f(home), total, 1e-7),
            f"away={away!r}, home={home!r}, total={total!r}",
        )

        sigma = raw.get("structural_total_sigma")
        add(
            "structural sigma valid",
            _finite(sigma) and float(sigma) > 0.0,
            f"sigma={sigma!r}",
        )

        probs = [raw.get("over_probability"), raw.get("under_probability"), raw.get("push_probability")]
        ranges_ok = all(_finite(p) and -_TOL <= float(p) <= 1.0 + _TOL for p in probs)
        add("probability ranges valid", ranges_ok, f"over/under/push={probs!r}")
        add(
            "probability mass equals 1",
            ranges_ok and _close(sum(float(p) for p in probs), 1.0, 1e-7),
            f"sum={sum(float(p) for p in probs) if ranges_ok else 'invalid'}",
        )

        reliability = raw.get("reliability")
        add(
            "reliability valid",
            _finite(reliability) and 0.0 <= float(reliability) <= 1.0,
            f"reliability={reliability!r}",
        )

        coverage = (raw.get("feature_coverage") or {}).get("score")
        add(
            "feature coverage valid",
            _finite(coverage) and 0.0 <= float(coverage) <= 1.0,
            f"coverage={coverage!r}",
        )
    else:
        for name in (
            "projected total arithmetic",
            "structural sigma valid",
            "probability ranges valid",
            "probability mass equals 1",
            "reliability valid",
            "feature coverage valid",
        ):
            add(name, None, "raw model data-gated", blocking=False)

    if raw_ready and final_ready:
        coherence = (
            _close(raw.get("projected_total"), final.get("projected_total"), 1e-7)
            and _close(raw.get("projected_away_points"), final.get("projected_away_points"), 1e-7)
            and _close(raw.get("projected_home_points"), final.get("projected_home_points"), 1e-7)
            and _close(raw.get("analysis_line"), final.get("analysis_line"), 1e-7)
            and _close(raw.get("over_probability"), final.get("over_probability"), 1e-7)
            and _close(raw.get("under_probability"), final.get("under_probability"), 1e-7)
        )
        add("raw/final projection coherence", coherence, "raw and final projection fields match")
        add(
            "final game identity coherence",
            _clean(final.get("game_identity")) == identity,
            f"final={final.get('game_identity')!r}, game={identity!r}",
        )
    else:
        add("raw/final projection coherence", None, "model/final data-gated", blocking=False)
        add("final game identity coherence", None, "model/final data-gated", blocking=False)

    selection_rule = dict(final.get("selection_rule") or {})
    if final_ready:
        expected_rule = {
            "minimum_probability": final_rules.MIN_SELECTION_PROBABILITY,
            "minimum_reliability": final_rules.MIN_SELECTION_RELIABILITY,
            "minimum_feature_coverage": final_rules.MIN_SELECTION_COVERAGE,
        }
        add(
            "frozen selection thresholds",
            selection_rule == expected_rule,
            f"rule={selection_rule!r}",
        )
    else:
        add("frozen selection thresholds", None, "final synthesis data-gated", blocking=False)

    weights_ok, bad_weights = _zero_analysis_weight_fields(raw, final)
    add(
        "analysis-line projection firewall",
        weights_ok,
        "all analysis_line *_weight fields are zero" if weights_ok else "; ".join(bad_weights),
    )

    market_ok, market_bad = _market_firewall(raw, final)
    add(
        "sportsbook/market/EV/Monte Carlo firewall",
        market_ok,
        "all market/firewall flags false" if market_ok else "; ".join(market_bad),
    )

    if form:
        engine_ready = form.get("model_ready") is True
        applied = raw.get("upgrade_step11_applied") is True
        add(
            "Step 11 gate/apply coherence",
            applied == engine_ready,
            f"engine_ready={engine_ready}, applied={applied}",
        )

        if not engine_ready and step10_raw:
            keys = (
                "projected_away_points",
                "projected_home_points",
                "projected_total",
                "structural_total_sigma",
                "over_probability",
                "under_probability",
                "push_probability",
                "reliability",
                "analysis_line",
            )
            unchanged = all(step10_raw.get(key) == raw.get(key) for key in keys)
            add(
                "Step 11 gated output preserves Step 10",
                unchanged,
                "gated projection/probability fields unchanged",
            )
        elif engine_ready:
            c = raw.get("components") or {}
            away_delta = _f(c.get("step11_away_form_adjustment"))
            home_delta = _f(c.get("step11_home_form_adjustment"))
            total_delta = _f(c.get("step11_total_form_adjustment"))
            bounded = (
                abs(away_delta) <= 1.250001
                and abs(home_delta) <= 1.250001
                and abs(total_delta) <= 2.000001
            )
            add(
                "Step 11 applied adjustment caps",
                bounded,
                f"away={away_delta:.4f}, home={home_delta:.4f}, total={total_delta:.4f}",
            )
        else:
            add("Step 11 gated output preserves Step 10", None, "Step 10 snapshot unavailable", blocking=False)
    else:
        add("Step 11 gate/apply coherence", False, "form_strength_engine missing")

    blocking_failures = [
        row for row in checks
        if row["blocking"] and row["status"] == "FAIL"
    ]
    passed = sum(row["status"] == "PASS" for row in checks)
    failed = sum(row["status"] == "FAIL" for row in checks)
    skipped = sum(row["status"] == "SKIP" for row in checks)
    integrity_passed = not blocking_failures

    if not integrity_passed:
        status = "INTEGRITY_FAIL"
    elif raw_ready and final_ready:
        status = "CERTIFIED"
    else:
        status = "DATA_GATED"

    return {
        "version": MODEL_VERSION,
        "status": status,
        "certified": status == "CERTIFIED",
        "integrity_passed": integrity_passed,
        "safe_to_display": integrity_passed,
        "model_ready": bool(raw_ready and final_ready),
        "selection_ready": bool(final.get("selection_ready")),
        "rank_eligible": bool(final.get("rank_eligible")),
        "certified_upgrade_steps": list(CERTIFIED_UPGRADE_STEPS),
        "completed_upgrade_count": len(CERTIFIED_UPGRADE_STEPS),
        "projection_fingerprint": _fingerprint(game, raw, final),
        "checks": checks,
        "checks_passed": passed,
        "checks_failed": failed,
        "checks_skipped": skipped,
        "blocking_failures": [dict(row) for row in blocking_failures],
        "projection_math_changed": PROJECTION_MATH_CHANGED,
        "selection_math_changed": SELECTION_MATH_CHANGED,
        "reliability_changed": RELIABILITY_CHANGED,
        "structural_sigma_changed": STRUCTURAL_SIGMA_CHANGED,
        "qualification_thresholds_changed": QUALIFICATION_THRESHOLDS_CHANGED,
        "sportsbook_input_used": False,
        "market_price_used": False,
        "market_probability_used": False,
        "edge_or_ev_used": False,
        "monte_carlo_used": False,
    }


__all__ = [
    "CERTIFIED_UPGRADE_STEPS",
    "FROZEN_STEP11_SLATE",
    "MODEL_VERSION",
    "PROJECTION_MATH_CHANGED",
    "QUALIFICATION_THRESHOLDS_CHANGED",
    "RELIABILITY_CHANGED",
    "SELECTION_MATH_CHANGED",
    "STRUCTURAL_SIGMA_CHANGED",
    "certify_result",
]
