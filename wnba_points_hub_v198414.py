"""WNBA Points V1.9.8.4.14 — Step 6 Markdown-safe HTML rendering repair.

Presentation-only wrapper over V1.9.8.4.13. V1.9.8.4.13 correctly separated
verified audit pace from the protected model pace factor, but its multi-line
nested HTML contained blank lines inside a larger Streamlit Markdown card.
Markdown could terminate the raw-HTML block at those blank lines and interpret
subsequent indented <div> elements as a literal code block.

V1.9.8.4.14 compacts only the Step-6 HTML fragment before it is appended to the
Top-5 player card. No data, grade, projection, pace calculation, Monte Carlo,
probability, calibration, candidate ordering or readiness logic is changed.
"""
from __future__ import annotations

import streamlit as st

import wnba_points_hub_v198413 as prior

base = prior.base
v171 = base.v171
ui = base.ui
points = base.points

MODEL_VERSION = "WNBA POINTS V1.9.8.4.14 • STEP 6 HTML RENDER REPAIR"
PRA_FROZEN_BRANCH = base.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = base.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = base.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = base.POINTS_FROZEN_COMMIT

_ORIGINAL_STEP6_BLOCK = prior._step6_block


def _compact_html(fragment: str) -> str:
    """Collapse a raw HTML fragment to one Markdown-safe line.

    The Top-5 renderer ultimately sends the assembled card through
    st.markdown(..., unsafe_allow_html=True). A blank line can end a raw HTML
    block in Markdown, and a following indented <div> can then become a code
    block. Joining stripped non-empty lines prevents that parser transition
    while preserving all element text and CSS declarations.
    """
    if not fragment:
        return ""
    return "".join(line.strip() for line in str(fragment).splitlines() if line.strip())


def _step6_block(day: str, data: dict) -> str:
    return _compact_html(_ORIGINAL_STEP6_BLOCK(day, data))


def _install() -> None:
    # V1.9.8.4.13's renderer calls its own _install(), which resolves the module
    # global _step6_block at call time. Replace that seam only; protected model
    # modules and all numeric calculations remain untouched.
    prior._step6_block = _step6_block


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    st.caption(
        "🔧 Points V1.9.8.4.14 • Step 6 HTML rendering repair ACTIVE • "
        "audit/model pace separation preserved • protected model/ranking unchanged"
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
