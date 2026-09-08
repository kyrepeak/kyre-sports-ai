"""MLB Moneyline V17.8 — Step 12 final synthesis + bounded probability calibration.

Final additive pregame layer over permanently frozen V17.7 Step 11.

Step 12 combines two already-certified, model-owned probability views:

1. Frozen V16/V16.1 Moneyline probability (run simulation + bounded history layer)
2. Step 10's expected-run distribution, converted into an independent game-win
   probability by convolving the two overdispersed team run distributions.

The two views overlap in upstream baseball evidence, so Step 12 deliberately
uses only a small reliability-weighted logit blend and caps the change from the
frozen probability. This is a structural consistency calibration, not a claim
of retrospective Platt/isotonic calibration from an out-of-sample forecast
archive.

Step 11 FanDuel market intelligence remains OUTSIDE the probability formula.
It is used only after the final model probability is produced to show no-vig
market comparison, quoted-price EV, and agreement/divergence.

Critical boundaries:
- Steps 1-11 remain immutable.
- FanDuel price has zero probability weight.
- No fuzzy game matching.
- No hidden line-movement claim.
- Step 5L live-game model remains untouched.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any, Mapping

import streamlit as st

import mlb_moneyline_hub_v177 as prior
import mlb_moneyline_hub_v176 as step10
import mlb_moneyline_hub_v170 as pregame

MODEL_VERSION = "V17.8 • MONEYLINE STEP 12 • FINAL SYNTHESIS + BOUNDED CALIBRATION"
FROZEN_MONEYLINE_PRESENTATION = "mlb_moneyline_hub_v177"
FROZEN_MODEL_CHAIN = prior.FROZEN_MODEL_CHAIN
SEASON = prior.SEASON

SCRIPT_BLEND_MAX = 0.20
MAX_CALIBRATION_DELTA = 0.035
PROB_FLOOR = 0.03
PROB_CEILING = 0.97
SCRIPT_MAX_RUNS = 20
MIN_SCRIPT_DATA_SCORE = 75

_STEP12_CSS = r"""
<style>
.ml178-final{grid-area:identity;margin-top:8px;padding:11px 12px;border:1px solid rgba(91,235,169,.34);border-radius:14px;background:linear-gradient(145deg,rgba(7,35,27,.98),rgba(7,17,28,.98));box-shadow:inset 4px 0 #5beaa9,0 8px 22px rgba(0,0,0,.13)}
.ml178-head{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:9px}
.ml178-title{font-size:.60rem;font-weight:950;letter-spacing:.08em;text-transform:uppercase;color:#a6f3cf}
.ml178-grade{display:inline-flex;align-items:center;border-radius:999px;padding:5px 8px;font-size:.50rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;border:1px solid #4e675d;background:#162720;color:#d5e9df}
.ml178-grade.elite{border-color:#21865f;background:#073823;color:#83efb7}.ml178-grade.strong{border-color:#34775d;background:#0d3025;color:#9ce9c1}.ml178-grade.lean{border-color:#75621e;background:#30290d;color:#f4dc78}.ml178-grade.thin{border-color:#6a5a45;background:#2c2317;color:#e8cfaa}.ml178-grade.limited{border-color:#555e65;background:#20272c;color:#c8d0d5}
.ml178-hero{display:grid;grid-template-columns:1.25fr .85fr .85fr;gap:7px}.ml178-pick{border:1px solid rgba(91,235,169,.24);border-radius:11px;background:#081d18;padding:9px}.ml178-pick small{display:block;color:#7fa99a;font-size:.42rem;text-transform:uppercase;font-weight:850}.ml178-pick strong{display:block;color:#f4fffa;font-size:.90rem;line-height:1.15;margin-top:3px}.ml178-pick b{display:block;color:#8be9bb;font-size:1.45rem;line-height:1;margin-top:5px}.ml178-tile{border:1px solid rgba(91,235,169,.16);border-radius:10px;background:#091722;padding:8px;text-align:center}.ml178-tile b{display:block;color:#f1f7f4;font-size:.76rem}.ml178-tile span{display:block;color:#718b80;font-size:.40rem;margin-top:2px;text-transform:uppercase}
.ml178-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:8px}.ml178-cell{border:1px solid rgba(91,235,169,.13);border-radius:9px;background:#091722;padding:7px 5px;text-align:center}.ml178-cell b{display:block;color:#edf7f2;font-size:.59rem}.ml178-cell span{display:block;color:#71857c;font-size:.39rem;margin-top:2px;text-transform:uppercase}
.ml178-note{margin-top:7px;border:1px solid rgba(91,235,169,.14);border-radius:8px;padding:7px 8px;background:#0a1d18;color:#afc2b9;font-size:.45rem;line-height:1.46}.ml178-note b{color:#e0f7eb}
.ml178-pills{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px}.ml178-pill{display:inline-flex;border-radius:999px;padding:4px 7px;border:1px solid rgba(91,235,169,.22);background:#0e281f;color:#b6ecd2;font-size:.45rem;font-weight:850}.ml178-source{margin-top:6px;color:#708696;font-size:.42rem;line-height:1.42}
@media(max-width:640px){.ml178-hero{grid-template-columns:1fr 1fr}.ml178-pick{grid-column:1/-1}.ml178-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.ml178-final{padding:10px}}
</style>
"""


def _f(value: Any) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except (TypeError, ValueError):
        return None


def _i(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError, OverflowError):
        return 0


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _logit(p: float) -> float:
    x = _clamp(p, 1e-6, 1.0 - 1e-6)
    return math.log(x / (1.0 - x))


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _prob_to_american(probability: Any) -> int | None:
    p = _f(probability)
    if p is None or not 0.0 < p < 1.0:
        return None
    if p >= 0.5:
        return int(round(-100.0 * p / (1.0 - p)))
    return int(round(100.0 * (1.0 - p) / p))


def _american_text(value: Any) -> str:
    try:
        x = int(value)
    except Exception:
        return "N/A"
    return f"+{x}" if x > 0 else str(x)


def _decimal_odds(american: Any) -> float | None:
    try:
        price = int(american)
    except Exception:
        return None
    if price == 0:
        return None
    if price > 0:
        return 1.0 + price / 100.0
    return 1.0 + 100.0 / (-price)


def _pct(value: Any, digits: int = 1) -> str:
    x = _f(value)
    return "N/A" if x is None else f"{100.0 * x:.{digits}f}%"


def _distribution_vector(mean: Any) -> list[float] | None:
    mu = _f(mean)
    if mu is None or mu <= 0:
        return None
    dist = step10._nb_distribution(mu, max_runs=SCRIPT_MAX_RUNS)
    probs = [float(x) for x in list(dist.get("probs") or [])]
    if not probs:
        return None
    probs.append(float(dist.get("tail") or 0.0))
    total = sum(probs)
    if total <= 0:
        return None
    return [x / total for x in probs]


def _script_home_probability(step10_context: Mapping[str, Any] | None) -> float | None:
    """Convert Step 10 team-run distributions into a game-win probability.

    The terminal tail bucket is treated as one shared 21+ bucket. Its tiny
    residual mass therefore contributes 50/50 only when both sides land there.
    """
    ctx = dict(step10_context or {})
    away = ctx.get("away") or {}
    home = ctx.get("home") or {}
    away_score = _i(away.get("data_score"))
    home_score = _i(home.get("data_score"))
    away_mu = _f(away.get("expected_runs"))
    home_mu = _f(home.get("expected_runs"))
    if (
        away_score < MIN_SCRIPT_DATA_SCORE
        or home_score < MIN_SCRIPT_DATA_SCORE
        or away_mu is None
        or home_mu is None
    ):
        return None

    away_probs = _distribution_vector(away_mu)
    home_probs = _distribution_vector(home_mu)
    if not away_probs or not home_probs:
        return None

    p_home = 0.0
    p_tie = 0.0
    for h_runs, hp in enumerate(home_probs):
        for a_runs, ap in enumerate(away_probs):
            mass = hp * ap
            if h_runs > a_runs:
                p_home += mass
            elif h_runs == a_runs:
                p_tie += mass

    return _clamp(p_home + 0.5 * p_tie, PROB_FLOOR, PROB_CEILING)


def _frozen_home_probability(result: Mapping[str, Any]) -> float | None:
    direct = _f(result.get("final_home"))
    if direct is not None and 0.0 < direct < 1.0:
        return direct

    win = _f(result.get("win_prob"))
    side = str(result.get("selected_side") or "").lower()
    if win is None or not 0.0 < win < 1.0:
        return None
    if side == "home":
        return win
    if side == "away":
        return 1.0 - win
    return None


def _calibrate_home_probability(
    result: Mapping[str, Any],
    step10_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    frozen_home = _frozen_home_probability(result)
    if frozen_home is None:
        return {
            "status": "PENDING",
            "frozen_home": None,
            "script_home": None,
            "final_home": None,
            "script_weight": 0.0,
            "delta": None,
            "reason": "Frozen Moneyline home probability unavailable.",
        }

    script_home = _script_home_probability(step10_context)
    if script_home is None:
        return {
            "status": "BASELINE_ONLY",
            "frozen_home": frozen_home,
            "script_home": None,
            "final_home": frozen_home,
            "script_weight": 0.0,
            "delta": 0.0,
            "reason": "Step 10 run distribution did not clear the final calibration gate; frozen probability preserved.",
        }

    ctx = dict(step10_context or {})
    away_q = _i((ctx.get("away") or {}).get("data_score"))
    home_q = _i((ctx.get("home") or {}).get("data_score"))
    reliability = _clamp(min(away_q, home_q) / 100.0, 0.0, 1.0)
    weight = SCRIPT_BLEND_MAX * reliability

    blended = _sigmoid(
        (1.0 - weight) * _logit(frozen_home)
        + weight * _logit(script_home)
    )
    raw_delta = blended - frozen_home
    delta = _clamp(raw_delta, -MAX_CALIBRATION_DELTA, MAX_CALIBRATION_DELTA)
    final_home = _clamp(frozen_home + delta, PROB_FLOOR, PROB_CEILING)

    return {
        "status": "FINAL_READY",
        "frozen_home": frozen_home,
        "script_home": script_home,
        "final_home": final_home,
        "script_weight": weight,
        "delta": delta,
        "reason": "",
    }


def _market_for_final_side(
    market_context: Mapping[str, Any] | None,
    final_side: str,
) -> dict[str, Any]:
    market = dict(market_context or {})
    if market.get("status") != "VERIFIED":
        return {
            "status": "PENDING",
            "no_vig_probability": None,
            "odds": None,
            "edge": None,
            "ev": None,
            "reason": "Verified Step 11 market context unavailable.",
        }

    selected_side = str(market.get("selected_side") or "").lower()
    no_vig_selected = _f(market.get("no_vig_probability"))
    if selected_side not in {"home", "away"} or no_vig_selected is None:
        return {
            "status": "PENDING",
            "no_vig_probability": None,
            "odds": None,
            "edge": None,
            "ev": None,
            "reason": "Step 11 selected-side market identity unavailable.",
        }

    if final_side == selected_side:
        no_vig = no_vig_selected
        price = market.get("selected_odds")
    else:
        no_vig = 1.0 - no_vig_selected
        price = market.get("opponent_odds")

    return {
        "status": "VERIFIED",
        "no_vig_probability": no_vig,
        "odds": price,
        "edge": None,
        "ev": None,
        "reason": "",
    }


def _strength(probability: Any, ready: bool) -> tuple[str, str]:
    p = _f(probability)
    if p is None:
        return "FINAL MONEYLINE PENDING", "limited"
    if not ready:
        return "FROZEN BASELINE PRESERVED", "limited"
    if p >= 0.64:
        return "ELITE MONEYLINE EDGE", "elite"
    if p >= 0.60:
        return "STRONG MONEYLINE EDGE", "strong"
    if p >= 0.56:
        return "MONEYLINE LEAN", "lean"
    return "THIN MODEL EDGE", "thin"


def _final_context(
    result: Mapping[str, Any],
    step10_context: Mapping[str, Any] | None,
    market_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    cal = _calibrate_home_probability(result, step10_context)
    final_home = _f(cal.get("final_home"))
    if final_home is None:
        return {
            "status": "PENDING",
            "grade": "FINAL MONEYLINE PENDING",
            "grade_cls": "limited",
            "reason": cal.get("reason") or "Final probability unavailable.",
        }

    final_away = 1.0 - final_home
    if final_home >= final_away:
        final_side = "home"
        final_prob = final_home
        final_team = str(result.get("home_name") or "Home")
        opponent = str(result.get("away_name") or "Away")
    else:
        final_side = "away"
        final_prob = final_away
        final_team = str(result.get("away_name") or "Away")
        opponent = str(result.get("home_name") or "Home")

    market = _market_for_final_side(market_context, final_side)
    market_prob = _f(market.get("no_vig_probability"))
    market_odds = market.get("odds")
    edge = final_prob - market_prob if market_prob is not None else None
    decimal_price = _decimal_odds(market_odds)
    ev = final_prob * decimal_price - 1.0 if decimal_price is not None else None
    market["edge"] = edge
    market["ev"] = ev

    ready = cal.get("status") == "FINAL_READY"
    grade, grade_cls = _strength(final_prob, ready)
    fair = _prob_to_american(final_prob)

    frozen_home = _f(cal.get("frozen_home"))
    frozen_selected = (
        frozen_home if final_side == "home"
        else (1.0 - frozen_home if frozen_home is not None else None)
    )
    script_home = _f(cal.get("script_home"))
    script_selected = (
        script_home if final_side == "home"
        else (1.0 - script_home if script_home is not None else None)
    )
    delta_selected = (
        final_prob - frozen_selected
        if frozen_selected is not None
        else None
    )

    if market_prob is None:
        market_read = "MARKET CHECK PENDING"
    elif edge is not None and edge >= 0.04:
        market_read = "MODEL > MARKET"
    elif edge is not None and edge <= -0.04:
        market_read = "MARKET > MODEL"
    else:
        market_read = "MODEL + MARKET CLOSE"

    return {
        "status": cal.get("status"),
        "grade": grade,
        "grade_cls": grade_cls,
        "final_side": final_side,
        "final_team": final_team,
        "opponent": opponent,
        "final_probability": final_prob,
        "final_home": final_home,
        "final_away": final_away,
        "final_fair_odds": fair,
        "frozen_selected_probability": frozen_selected,
        "script_selected_probability": script_selected,
        "calibration_delta": delta_selected,
        "script_weight": cal.get("script_weight"),
        "market": market,
        "market_read": market_read,
        "reason": cal.get("reason") or "",
        "market_probability_weight": 0.0,
    }


def _html(context: Mapping[str, Any]) -> str:
    if not context:
        context = {
            "status": "PENDING",
            "grade": "FINAL MONEYLINE PENDING",
            "grade_cls": "limited",
            "reason": "Final synthesis context unavailable.",
        }

    market = context.get("market") or {}
    delta = _f(context.get("calibration_delta"))
    delta_text = "N/A" if delta is None else f"{delta * 100:+.1f} pts"
    edge = _f(market.get("edge"))
    edge_text = "N/A" if edge is None else f"{edge * 100:+.1f} pts"
    ev = _f(market.get("ev"))
    ev_text = "N/A" if ev is None else f"{ev * 100:+.1f}%"
    weight = _f(context.get("script_weight"))
    weight_text = "N/A" if weight is None else f"{weight * 100:.0f}%"

    return (
        '<div class="ml178-final">'
        '<div class="ml178-head">'
        '<span class="ml178-title">STEP 12 • FINAL MONEYLINE SYNTHESIS + BOUNDED CALIBRATION</span>'
        f'<span class="ml178-grade {escape(str(context.get("grade_cls") or "limited"))}">{escape(str(context.get("grade") or "FINAL MONEYLINE PENDING"))}</span>'
        '</div>'
        '<div class="ml178-hero">'
        '<div class="ml178-pick">'
        '<small>Final model side</small>'
        f'<strong>{escape(str(context.get("final_team") or "Pending"))}</strong>'
        f'<b>{escape(_pct(context.get("final_probability")))}</b>'
        f'<small>Fair moneyline {_american_text(context.get("final_fair_odds"))}</small>'
        '</div>'
        f'<div class="ml178-tile"><b>{escape(_pct(context.get("script_selected_probability")))}</b><span>Step 10 run-script win</span></div>'
        f'<div class="ml178-tile"><b>{escape(delta_text)}</b><span>Calibration vs frozen</span></div>'
        '</div>'
        '<div class="ml178-grid">'
        f'<div class="ml178-cell"><b>{escape(_pct(context.get("frozen_selected_probability")))}</b><span>Frozen model</span></div>'
        f'<div class="ml178-cell"><b>{escape(weight_text)}</b><span>Run-script blend weight</span></div>'
        f'<div class="ml178-cell"><b>{escape(_pct(market.get("no_vig_probability")))}</b><span>FanDuel no-vig</span></div>'
        f'<div class="ml178-cell"><b>{escape(edge_text)}</b><span>Final model - market</span></div>'
        '</div>'
        '<div class="ml178-grid">'
        f'<div class="ml178-cell"><b>{_american_text(market.get("odds"))}</b><span>FanDuel quote</span></div>'
        f'<div class="ml178-cell"><b>{escape(ev_text)}</b><span>EV at quote</span></div>'
        f'<div class="ml178-cell"><b>{escape(str(context.get("market_read") or "MARKET CHECK PENDING"))}</b><span>Market cross-check</span></div>'
        f'<div class="ml178-cell"><b>{escape(str(context.get("status") or "PENDING"))}</b><span>Final readiness</span></div>'
        '</div>'
        '<div class="ml178-note">'
        '<b>Final probability method:</b> reliability-weighted logit blend of the permanently frozen Moneyline probability '
        'and Step 10 run-distribution win probability. Because those views share upstream baseball evidence, the Step 10 '
        f'weight is capped at {SCRIPT_BLEND_MAX * 100:.0f}% and the probability move is hard-capped at ±{MAX_CALIBRATION_DELTA * 100:.1f} points.'
        '</div>'
        '<div class="ml178-pills">'
        '<span class="ml178-pill">MARKET WEIGHT • 0%</span>'
        '<span class="ml178-pill">MAX CALIBRATION • ±3.5 PTS</span>'
        '<span class="ml178-pill">NO FUZZY MATCHING</span>'
        '<span class="ml178-pill">PREGAME FINAL MODEL</span>'
        '</div>'
        f'<div class="ml178-source">FanDuel is a downstream price/EV cross-check only and never enters the final probability formula. '
        f'This is structural model-consistency calibration, not retrospective outcome calibration. {escape(str(context.get("reason") or ""))}</div>'
        '</div>'
    )


def _inject(card: str, html: str) -> str:
    text = str(card or "")
    if not html or "ks-pick-card" not in text or "ml178-final" in text:
        return text
    return text[:-6] + html + "</div>" if text.endswith("</div>") else text + html


_FROZEN_STEP11_RENDERER = prior._renderer


def _renderer(original, rows, lineups):
    step11_renderer = _FROZEN_STEP11_RENDERER(original, rows, lineups)

    def wrapped(results, status_info, team_logo, h):
        ordered = list(results or [])[:5]
        step10_contexts: dict[int, dict[str, Any]] = {}
        market_contexts: dict[int, dict[str, Any]] = {}

        original_compose = step10._compose
        original_market_builder = prior._build_market_context
        original_markdown = st.markdown

        def capture_compose(result, row, **kwargs):
            ctx = original_compose(result, row, **kwargs)
            pk = _i((result or {}).get("game_pk"))
            if pk:
                step10_contexts[pk] = ctx
            return ctx

        def capture_market(result, state):
            ctx = original_market_builder(result, state)
            pk = _i((result or {}).get("game_pk"))
            if pk:
                market_contexts[pk] = ctx
            return ctx

        cursor = {"i": 0}

        def capture_markdown(body: Any, *args: Any, **kwargs: Any):
            text = str(body or "")
            if "ks-pick-card" in text and cursor["i"] < len(ordered):
                result = ordered[cursor["i"]]
                cursor["i"] += 1
                pk = _i(result.get("game_pk"))
                final = _final_context(
                    result,
                    step10_contexts.get(pk) or {},
                    market_contexts.get(pk) or {},
                )
                text = _inject(text, _html(final))
            return original_markdown(text, *args, **kwargs)

        step10._compose = capture_compose
        prior._build_market_context = capture_market
        st.markdown = capture_markdown
        try:
            return step11_renderer(results, status_info, team_logo, h)
        finally:
            step10._compose = original_compose
            prior._build_market_context = original_market_builder
            st.markdown = original_markdown

    return wrapped


def _render_pregame_with_step12(games_df, section_header, status_info, team_logo, h):
    original_renderer = pregame._renderer
    pregame._renderer = _renderer
    try:
        return pregame.render_moneyline_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        pregame._renderer = original_renderer


def render_moneyline_hub(games_df, section_header, status_info, team_logo, h):
    """Preserve frozen Step 5L live mode while adding final pregame synthesis."""
    st.markdown(_STEP12_CSS, unsafe_allow_html=True)
    original_step11_pregame = prior._render_pregame_with_step11
    prior._render_pregame_with_step11 = _render_pregame_with_step12
    try:
        return prior.render_moneyline_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        prior._render_pregame_with_step11 = original_step11_pregame


__all__ = [
    "FROZEN_MODEL_CHAIN",
    "FROZEN_MONEYLINE_PRESENTATION",
    "MAX_CALIBRATION_DELTA",
    "MIN_SCRIPT_DATA_SCORE",
    "MODEL_VERSION",
    "PROB_CEILING",
    "PROB_FLOOR",
    "SCRIPT_BLEND_MAX",
    "SCRIPT_MAX_RUNS",
    "_calibrate_home_probability",
    "_final_context",
    "_market_for_final_side",
    "_script_home_probability",
    "render_moneyline_hub",
]
