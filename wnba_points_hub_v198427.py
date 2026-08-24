"""WNBA Points V1.9.8.4.27 — Step 11 context-aware grade labels.

Builds on V1.9.8.4.26. The Step-11 evidence score and verdict math are preserved,
but the negative grade label now distinguishes true blowout risk from a low-
scoring market environment. A moderate spread with a depressed game total should
not be labeled BLOWOUT / SCRIPT WATCH when the actual blowout and fourth-quarter
minutes indicators are low/moderate and normal.

No Points projection, Monte Carlo probability, calibration, sportsbook transport,
market values, evidence score, verdict, or Top-5 ordering is changed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v198426 as prior

base = prior.base
v171 = base.v171
ui = base.ui
points = base.points

MODEL_VERSION = "WNBA POINTS V1.9.8.4.27 • STEP 11 CONTEXT-AWARE SCRIPT LABELS"
PRA_FROZEN_BRANCH = base.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = base.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = base.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = base.POINTS_FROZEN_COMMIT

_BASE_GRADE = getattr(prior, "_kyre_v198427_base_grade", prior._grade)
setattr(prior, "_kyre_v198427_base_grade", _BASE_GRADE)


def _num(value, default=np.nan):
    try:
        if value is None or value == "":
            return default
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _grade_context_aware(ctx: dict):
    grade, grade_class, verdict, score, evidence, reasons = _BASE_GRADE(ctx)

    # Preserve all data-limited, neutral and positive outcomes exactly.
    if str(ctx.get("state")) != "FRESH" or score >= 0:
        return grade, grade_class, verdict, score, evidence, reasons

    spread = _num(ctx.get("spread"), np.nan)
    total_delta = _num(ctx.get("total_delta"), np.nan)
    implied_delta = _num(ctx.get("implied_delta"), np.nan)
    abs_spread = abs(spread) if pd.notna(spread) else np.nan

    blowout_signal = pd.notna(abs_spread) and abs_spread >= 7.0
    hard_blowout = pd.notna(abs_spread) and abs_spread >= 10.0
    low_total_signal = pd.notna(total_delta) and total_delta <= -5.0
    low_team_total_signal = pd.notna(implied_delta) and implied_delta <= -4.0

    if score <= -3:
        if hard_blowout:
            return "HARD GAME SCRIPT", "hard", verdict, score, evidence, reasons
        if low_total_signal or low_team_total_signal:
            return "HARD SCORING ENVIRONMENT", "hard", verdict, score, evidence, reasons
        return "HARD GAME SCRIPT", "hard", verdict, score, evidence, reasons

    if blowout_signal:
        return "BLOWOUT / SCRIPT WATCH", "watch", verdict, score, evidence, reasons
    if low_total_signal or low_team_total_signal:
        return "LOW-SCORING SCRIPT", "watch", verdict, score, evidence, reasons
    return "SCRIPT WATCH", "watch", verdict, score, evidence, reasons


def _install() -> None:
    # Step 11 block resolves prior._grade dynamically at render time.
    prior._grade = _grade_context_aware
    prior._install()


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    st.caption(
        "🎬 Points V1.9.8.4.27 • Step 11 grade labels now separate blowout risk from low-scoring script • "
        "evidence score/verdict/model/ranking unchanged"
    )
    return prior.render_wnba_points_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    try:
        return getattr(prior, name)
    except AttributeError:
        return getattr(base, name)


__all__ = [
    "MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH",
    "POINTS_FROZEN_BRANCH", "POINTS_FROZEN_COMMIT", "v171", "ui", "points",
    "render_wnba_points_hub",
]
