"""NFL Passing Yards V75 — Failure-Proofing Step 6.

Additive reliability boundary over frozen V74. Healthy requests preserve the
entire frozen Step 5 result and add a compact reliability-status strip. If the
Step 5 additive selected-analysis layer raises unexpectedly, V75 contains that
failure and falls back to the frozen V73 selected analysis (Steps 1-4) with an
explicit DEGRADED notice instead of fabricating data or surfacing the additive
exception as a page-breaking error.

This layer does not alter projection, context math, probability, market math,
personnel math, environment math, provider collection, widget keys, navigation
state, or sportsbook handling.
"""
from __future__ import annotations

from html import escape
from typing import Any

import nfl_passing_yards_hub_v73 as step4_owner
import nfl_passing_yards_hub_v74 as prior

_FROZEN_SELECTED_ANALYSIS = prior._selected_analysis_v74
_FROZEN_STEP4_SELECTED_ANALYSIS = step4_owner._selected_analysis_v73

MODEL_VERSION = "NFL PASSING YARDS V75 • FAILURE-PROOFING STEP 6"
FROZEN_PRIOR = "nfl_passing_yards_hub_v74"
FROZEN_FALLBACK = "nfl_passing_yards_hub_v73"
FAILURE_PROOFING_VERSION = "v75"
NEW_PHASE_STEP = 6
PRESENTATION_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_CONTEXT_MATH = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_PERSONNEL_MATH = False
MAY_MODIFY_ENVIRONMENT_MATH = False
MAY_MODIFY_DATA_PROVIDER_BEHAVIOR = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_NAVIGATION_STATE = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_FAILURE_CSS = r"""
<style data-passing-yards-failure-proofing-css="v75">
.ks-py75,.ks-py75 *{box-sizing:border-box}
.ks-py75{
  margin:8px 0 12px;padding:9px 11px;border:1px solid var(--kyre-sem-border-soft);
  border-radius:11px;background:rgba(255,255,255,.012)
}
.ks-py75-head{display:flex;align-items:center;justify-content:space-between;gap:10px}
.ks-py75-title{font-size:.58rem;font-weight:950;letter-spacing:.055em;text-transform:uppercase;color:var(--kyre-sem-text-primary)}
.ks-py75-mode{flex:0 0 auto;border:1px solid var(--kyre-sem-border-medium);border-radius:999px;padding:4px 7px;font-size:.45rem;font-weight:950;color:var(--kyre-sem-text-accent-soft)}
.ks-py75-copy{margin-top:5px;font-size:.5rem;line-height:1.5;color:var(--kyre-sem-text-muted)}
@media(max-width:420px){.ks-py75-head{align-items:flex-start;flex-direction:column}.ks-py75-mode{align-self:flex-start}}
</style>
"""


def _failure_panel(mode: str, error_name: str = "") -> str:
    state = str(mode or "DEGRADED").upper()
    healthy = state == "HEALTHY"
    if healthy:
        title = "Failure-proofing active"
        copy = (
            "Optional-provider exceptions fail closed • Step 5 additive enrichment is isolated • "
            "fresh-session route cleanup is guarded • frozen certified baseline preserved."
        )
    else:
        title = "Failure contained"
        safe_error = escape(str(error_name or "UnexpectedError"))
        copy = (
            f"Availability/game-day additive enrichment was contained ({safe_error}). "
            "Frozen Steps 1-4 remain available • no unavailable evidence was synthesized."
        )
    return (
        '<section class="ks-py75" data-passing-yards-failure-proofing="v75" '
        f'data-failure-proofing-mode="{escape(state, quote=True)}">'
        '<div class="ks-py75-head">'
        f'<div class="ks-py75-title">{escape(title)}</div>'
        f'<div class="ks-py75-mode">{escape(state)}</div>'
        '</div>'
        f'<div class="ks-py75-copy">{copy}</div>'
        '</section>'
    )


def _insert_after_section(body: str, start_token: str, panel: str) -> str:
    text = str(body or "")
    start = text.find(start_token)
    if start < 0:
        return text
    end = text.find("</section>", start)
    if end < 0:
        return text
    end += len("</section>")
    return text[:end] + panel + text[end:]


def _inject_failure_proofing(body: str, mode: str = "HEALTHY", error_name: str = "") -> str:
    text = str(body or "")
    if (
        'data-passing-yards-qb-detail="v59"' not in text
        or 'data-passing-yards-failure-proofing="v75"' in text
    ):
        return text

    state = str(mode or "DEGRADED").upper()
    panel = _failure_panel(state, error_name)

    if state == "HEALTHY" and 'data-passing-yards-availability-game-day="v74"' in text:
        text = _insert_after_section(
            text,
            '<section class="ks-py74"',
            panel,
        )
        anchor = 'data-passing-yards-availability-game-day-ready="v74"'
    else:
        text = _insert_after_section(
            text,
            '<section class="ks-py73-market"',
            panel,
        )
        anchor = 'data-passing-yards-live-market-ready="v73"'

    ready = (
        ' data-passing-yards-failure-proofing-ready="v75"'
        f' data-passing-yards-failure-mode="{escape(state, quote=True)}"'
    )
    if anchor in text and 'data-passing-yards-failure-proofing-ready="v75"' not in text:
        text = text.replace(anchor, anchor + ready, 1)
    return _FAILURE_CSS + text


def _selected_analysis_v75(captured: dict[str, list[str]], slot: int) -> str:
    try:
        body = _FROZEN_SELECTED_ANALYSIS(captured, slot)
    except Exception as exc:
        body = _FROZEN_STEP4_SELECTED_ANALYSIS(captured, slot)
        return _inject_failure_proofing(body, "DEGRADED", type(exc).__name__)
    return _inject_failure_proofing(body, "HEALTHY")


def render_nfl_passing_yards_hub() -> None:
    original = prior._selected_analysis_v74
    prior._selected_analysis_v74 = _selected_analysis_v75
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        prior._selected_analysis_v74 = original


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V75 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "FAILURE_PROOFING_VERSION",
    "FROZEN_FALLBACK",
    "FROZEN_PRIOR",
    "MAY_MODIFY_CONTEXT_MATH",
    "MAY_MODIFY_DATA_PROVIDER_BEHAVIOR",
    "MAY_MODIFY_ENVIRONMENT_MATH",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_NAVIGATION_STATE",
    "MAY_MODIFY_PERSONNEL_MATH",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_WIDGET_KEYS",
    "MODEL_VERSION",
    "NEW_PHASE_STEP",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_inject_failure_proofing",
    "_selected_analysis_v75",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
