"""WNBA Points V1.9.8.4.24 — Step 8 usage-delta display repair + Step 9 preserve.

Builds on V1.9.8.4.23.

Two presentation/render-chain issues are addressed together:
1) V1.9.8.4.23 preserves Step 9 at the final Top-5 card render boundary.
2) Step 8's RECENT USAGE DELTA was internally already a percentage-point
   difference (for example 21.5 - 21.3 = +0.2 pp) but the legacy _pct formatter
   could multiply a small delta by 100 again, displaying values such as +17.2%.
   V1.9.8.4.24 replaces only that rendered cell with the correctly normalized
   percentage-point delta.

The Step-8 opportunity grade already used the correct unformatted delta, so no
grade/model logic is changed. Projection, Monte Carlo, calibration, sportsbook
transport, injuries, usage inputs, and Top-5 ranking remain unchanged.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v198423 as prior
import wnba_points_hub_v198419 as step8clarity

base = prior.base
v171 = base.v171
ui = base.ui
points = base.points

MODEL_VERSION = "WNBA POINTS V1.9.8.4.24 • STEP 8 USAGE DELTA DISPLAY + STEP 9 RENDER REPAIR"
PRA_FROZEN_BRANCH = base.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = base.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = base.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = base.POINTS_FROZEN_COMMIT

_BASE_STEP8_CLARITY_BLOCK = getattr(
    step8clarity,
    "_kyre_v198424_base_step8_block",
    step8clarity._step8_block,
)
setattr(step8clarity, "_kyre_v198424_base_step8_block", _BASE_STEP8_CLARITY_BLOCK)


def _num(value, default=np.nan):
    try:
        if value is None or value == "":
            return default
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _usage_pct_points(value):
    """Normalize a usage value to percentage points exactly once."""
    x = _num(value, np.nan)
    if pd.isna(x):
        return np.nan
    return x * 100.0 if abs(x) <= 1.5 else x


def _step8_block_usage_delta_pp(day: str, data: dict) -> str:
    # Keep V1.9.8.4.19-.21's full Step-8 rendering/provenance behavior.
    html = _BASE_STEP8_CLARITY_BLOCK(day, data)

    # Use the currently installed handoff dynamically. V1.9.8.4.21 can replace
    # this function with its provider-safe Points-pipeline identity bridge.
    try:
        hydrated, _source = step8clarity._usage_handoff(day, data)
    except Exception:
        hydrated = dict(data or {})

    season = _usage_pct_points(hydrated.get("USG_PCT"))
    l10 = _usage_pct_points(hydrated.get("L10_USG_PCT"))
    l5 = _usage_pct_points(hydrated.get("L5_USG_PCT"))
    recent = l5 if pd.notna(l5) else l10
    delta = recent - season if pd.notna(recent) and pd.notna(season) else np.nan
    delta_text = "—" if pd.isna(delta) else f"{delta:+.1f} pp"

    # Replace only the rendered RECENT USAGE DELTA cell; all other Step-8 HTML,
    # values, source labels and opportunity grading are preserved byte-for-byte.
    pattern = r"(<small>RECENT USAGE Δ</small><strong>)[^<]*(</strong>)"
    return re.sub(pattern, rf"\g<1>{delta_text}\g<2>", html, count=1)


def _install() -> None:
    # Patch the V1.9.8.4.19 function before entering the nested render chain.
    # Its own installer later assigns this corrected function into V1.9.8.4.18.
    step8clarity._step8_block = _step8_block_usage_delta_pp
    prior._install()


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    st.caption(
        "🧮 Points V1.9.8.4.24 • Step 8 usage delta display repaired to percentage points • "
        "Step 9 final-render repair preserved • model/ranking unchanged"
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
