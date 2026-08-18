"""MLB Daily Game Picks V2.0.7 — market-neutral anti-saturation normalization.

Preserves all seven production engines, sportsbook-line gates, matchup identity
firewalls, per-game Step 5 selection, and Step 6 Daily Master Card rules.

Only the Step 3 cross-market normalization transform is updated. The previous
linear/clamped rare-event transform could let naturally low-baseline Home Run
markets max both major score components too easily. V2.0.7 replaces that with a
smooth standardized uplift plus an explicit blend with the event's real absolute
probability, so unlike markets remain comparable without forcing market diversity.
"""
from __future__ import annotations

import math
import streamlit as st

import mlb_daily_game_picks_v206 as previous

# V2.0.6 -> V2.0.5 -> V2.0.4 -> V2.0 Step-5 core.
bridge = previous.bridge
core = bridge.core
step3 = core.step3

VERSION = "MLB Daily Game Picks V2.0.7 • MARKET-NEUTRAL NORMALIZATION"
ABSOLUTE_PROB_WEIGHT = 0.60
RELATIVE_PROB_WEIGHT = 0.40
EDGE_SIGMOID_SCALE = 1.15


def _clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, float(x)))


def _sigmoid(z):
    # Numerically stable enough for the bounded probabilities used here.
    z = max(-12.0, min(12.0, float(z)))
    return 1.0 / (1.0 + math.exp(-z))


def normalize_candidate(*, market, probability=None, reliability=None, data_quality=None,
                        confirmed=False, uncertainty=None, stale=False):
    """Market-neutral Step 3 score using only real connected production inputs.

    Production probabilities are never modified. This function only transforms
    them into the shared 0-100 ranking scale.
    """
    rule = step3.MARKET_RULES.get(str(market))
    if not rule or probability is None or reliability is None or data_quality is None:
        return {
            "status": "UNSCORED",
            "score": None,
            "reason": "verified production probability/reliability/data-quality input not connected",
        }

    try:
        p = _clamp(probability, .001, .999)
        rel = _clamp(reliability)
        dq = _clamp(data_quality)
        unc = float(uncertainty if uncertainty is not None else rule["uncertainty"])
    except Exception:
        return {"status": "UNSCORED", "score": None, "reason": "invalid normalization input"}

    b = float(rule["baseline"])
    denom = max(.05, unc)

    # Standardize the candidate's lift within its own market, but use a smooth
    # sigmoid instead of a hard clamp. This prevents rare-event markets from
    # instantly saturating their major score components.
    z = (p - b) / denom
    relative = _sigmoid(z)
    edge = _sigmoid(z / EDGE_SIGMOID_SCALE)

    # Keep absolute event probability visible in the shared ranking. This is what
    # prevents a 25-30% rare event from automatically outranking a 70-80% event
    # solely because the rare event's market anchor is low.
    probability_strength = _clamp(
        ABSOLUTE_PROB_WEIGHT * p + RELATIVE_PROB_WEIGHT * relative
    )

    confirmation = 1.0 if confirmed else .55
    uncertainty_score = 1.0 - _clamp(unc / .25)
    w = step3.WEIGHTS

    score100 = 100.0 * (
        w["probability_strength"] * probability_strength +
        w["market_relative_edge"] * edge +
        w["model_reliability"] * rel +
        w["data_quality"] * dq +
        w["confirmation"] * confirmation +
        w["uncertainty"] * uncertainty_score
    )

    if stale:
        score100 -= 8.0
    if rel < float(rule["min_rel"]):
        score100 -= 10.0 * (float(rule["min_rel"]) - rel) / max(.01, float(rule["min_rel"]))

    score100 = max(0.0, min(100.0, score100))
    return {
        "status": "SCORED",
        "score": score100,
        "probability": p,
        "baseline": b,
        "probability_strength_component": probability_strength,
        "relative_component": relative,
        "edge_component": edge,
        "standardized_edge_z": z,
        "reliability": rel,
        "data_quality": dq,
        "confirmation": confirmation,
        "uncertainty": unc,
        "stale": bool(stale),
        "normalization_version": "V1.3 anti-saturation",
    }


# All Step-5/Step-6 candidate builders call this module function at render time,
# so existing cached production outputs are rescored without rerunning any model.
step3.normalize_candidate = normalize_candidate


def render_daily_game_picks(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    step3.normalize_candidate = normalize_candidate
    st.caption(
        "⚖️ V2.0.7 normalization audit: smooth market-relative uplift + 60/40 absolute/relative probability blend • no forced market diversity • production probabilities unchanged."
    )
    return previous.render_daily_game_picks(games_df, section_header, status_info, team_logo, h)
