"""NFL Passing Yards V39 — presentation-only Tough / Medium / Favorable grades.

Additive display-only wrapper over V38 and the V36 compact dashboard. V39 does
not recalculate matchup quality. It only translates directional labels already
present in certified Passing Yards HTML into FAVORABLE / MEDIUM / TOUGH badges
for Deep Evidence, Monster Projection, and Market + Edge.

All projection, probability, market/edge, API transport, ESPN identity, and
sportsbook-influence contracts remain frozen.
"""
from __future__ import annotations

from html import escape

import streamlit as st

import nfl_passing_yards_hub_v36 as dashboard
import nfl_passing_yards_hub_v38 as prior
from nfl_passing_yards_presentation_grade_v1 import grade_certified_html

MODEL_VERSION = "NFL PASSING YARDS V39 • PRESENTATION GRADES"
FROZEN_PRIOR = "nfl_passing_yards_hub_v38"
FROZEN_DASHBOARD = "nfl_passing_yards_hub_v36"
PRESENTATION_GRADES_ONLY = True
DISPLAY_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
GRADE_LABELS = ("FAVORABLE", "MEDIUM", "TOUGH")

_ORIGINAL_EVIDENCE_V36 = dashboard._evidence
_ORIGINAL_COMPACT_PLAYER_V36 = dashboard._compact_player

_GRADE_CSS = r'''
<style>
.kpass39-evidence-meta,.kpass39-metric-meta{display:flex;align-items:center;gap:5px;flex-wrap:wrap;justify-content:flex-end}
.kpass39-grade{font-size:.39rem!important;letter-spacing:.045em!important;padding:3px 6px!important}
.kpass39-grade.kpass36-tone-green{font-weight:950}.kpass39-grade.kpass36-tone-amber{font-weight:950}.kpass39-grade.kpass36-tone-red{font-weight:950}
</style>
'''


def _grade_chip(content: str, *, surface: str) -> str:
    grade = grade_certified_html(content, surface=surface)
    label = str(grade.get("label") or "MEDIUM")
    tone = str(grade.get("tone") or "amber")
    return (
        f'<span class="kpass36-chip kpass36-tone-{escape(tone)} kpass39-grade" '
        f'data-presentation-grade="{escape(label)}">{escape(label)}</span>'
    )


def _graded_evidence(label: str, hint: str, content: str, tone: str = "gray") -> str:
    body = content or dashboard._fallback(label)
    grade_chip = _grade_chip(content, surface="evidence")
    return (
        '<details class="kpass36-deep">'
        f'<summary><span>{escape(label)}</span><span class="kpass39-evidence-meta">'
        f'<span class="kpass36-evidencehint kpass36-tone-{escape(tone)}">{escape(hint)}</span>'
        f'{grade_chip}</span></summary>'
        f'<div class="kpass36-evidencebody">{body}</div>'
        '</details>'
    )


def _graded_compact_player(captured: dict[str, list[str]], index: int) -> str:
    html = _ORIGINAL_COMPACT_PLAYER_V36(captured, index)
    projection = dashboard._piece(captured, "projection", index)
    market = dashboard._piece(captured, "market", index)

    projection_old = (
        '<div class="kpass36-metrichead"><b>Monster Projection</b>'
        '<span class="kpass36-chip kpass36-tone-purple">MODEL</span></div>'
    )
    projection_new = (
        '<div class="kpass36-metrichead"><b>Monster Projection</b>'
        '<span class="kpass39-metric-meta">'
        '<span class="kpass36-chip kpass36-tone-purple">MODEL</span>'
        f'{_grade_chip(projection, surface="projection")}</span></div>'
    )
    market_old = (
        '<div class="kpass36-metrichead"><b>Market + Edge</b>'
        '<span class="kpass36-chip kpass36-tone-blue">MARKET CONTEXT</span></div>'
    )
    market_new = (
        '<div class="kpass36-metrichead"><b>Market + Edge</b>'
        '<span class="kpass39-metric-meta">'
        '<span class="kpass36-chip kpass36-tone-blue">MARKET CONTEXT</span>'
        f'{_grade_chip(market, surface="market")}</span></div>'
    )
    return html.replace(projection_old, projection_new, 1).replace(market_old, market_new, 1)


def render_nfl_passing_yards_hub() -> None:
    st.markdown(_GRADE_CSS, unsafe_allow_html=True)
    original_evidence = dashboard._evidence
    original_compact_player = dashboard._compact_player
    dashboard._evidence = _graded_evidence
    dashboard._compact_player = _graded_compact_player
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        dashboard._evidence = original_evidence
        dashboard._compact_player = original_compact_player


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V39 only renders the Passing Yards market.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_DASHBOARD",
    "FROZEN_PRIOR",
    "GRADE_LABELS",
    "MODEL_VERSION",
    "PRESENTATION_GRADES_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_graded_compact_player",
    "_graded_evidence",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
