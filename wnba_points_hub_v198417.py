"""WNBA Points V1.9.8.4.17 — Step 7 source-window labeling repair.

Presentation-only wrapper over V1.9.8.4.16. The verified ESPN fallback already
builds distinct season-to-date, L10 and L5 shooting profiles. V1.9.8.4.16 used
the L5 profile's SOURCE string for the shared source note, which could make a
valid season/L10/L5 card look as though every displayed number came from only
five games.

V1.9.8.4.17 changes only that source label. It explicitly displays the sample
size used for each window. No shooting calculation, grade, Points projection,
Monte Carlo probability, calibration or Top-5 ordering is changed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v198416 as prior

base = prior.base
v171 = base.v171
ui = base.ui
points = base.points

MODEL_VERSION = "WNBA POINTS V1.9.8.4.17 • STEP 7 SOURCE WINDOW LABEL REPAIR"
PRA_FROZEN_BRANCH = base.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = base.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = base.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = base.POINTS_FROZEN_COMMIT

_ORIGINAL_RENDER_STEP7 = prior._render_step7


def _gp(profile: dict) -> int:
    try:
        value = float((profile or {}).get("GP"))
        if pd.isna(value):
            return 0
        return max(0, int(round(value)))
    except Exception:
        return 0


def _render_step7(season_p: dict, l10_p: dict, l5_p: dict, source_note: str) -> str:
    note = str(source_note or "")
    if "ESPN WNBA verified box-score fallback" in note:
        season_n = _gp(season_p)
        l10_n = _gp(l10_p)
        l5_n = _gp(l5_p)
        note = (
            "ESPN WNBA verified box-score fallback"
            f" • season {season_n} G • L10 {l10_n} G • L5 {l5_n} G"
        )
    return _ORIGINAL_RENDER_STEP7(season_p, l10_p, l5_p, note)


def _install() -> None:
    # V1.9.8.4.16 resolves _render_step7 from its module globals when Step 7 is
    # rendered, so this replaces only the source-note presentation seam.
    prior._render_step7 = _render_step7


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    st.caption(
        "🎯 Points V1.9.8.4.17 • Step 7 source-window labels repaired • "
        "season/L10/L5 sample sizes explicit • protected model/ranking unchanged"
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
