"""WNBA Points V1.9.8.4.30 — cards-first page + single authoritative 5M control.

Presentation/control-order wrapper over V1.9.8.4.29.

The protected Points projection, SportsGameOdds transport, 5M/10M Monte Carlo,
calibration, candidate hierarchy, persistence, readiness gates, sanity quarantine,
and completed Top-5 Step 2–12 evidence stack are unchanged.

This wrapper repairs two UI-routing problems only:
1) V1.9.8.2 replaced the older visual header that used to call the H2H renderer,
   so the completed Top-5 Player-vs-Team History cards could be fully installed
   but have no live cards-first call site in the active header path.
2) the one real 5M production control lived far below the engine/preflight audit.
   The same protected button function is now rendered exactly once immediately
   after the Top-5 cards, using the exact same fail-closed V1.9.8.4.29 readiness
   object. The inherited later call is suppressed to avoid a duplicate widget.

No gate is bypassed. If exact Points markets or any protected readiness check is
not ready, the 5M button remains disabled exactly as before.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import wnba_points_hub_v198429 as prior
import wnba_points_hub_v1982 as visual_core
import wnba_points_hub_v194 as h2h

base = prior.base
v171 = base.v171
v17 = v171.base
ui = base.ui
points = ui.points

MODEL_VERSION = "WNBA POINTS V1.9.8.4.30 • CARDS FIRST + SINGLE 5M CONTROL"
PRA_FROZEN_BRANCH = base.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = base.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = base.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = base.POINTS_FROZEN_COMMIT

# Preserve the genuine renderers once across Streamlit hot reloads.
_BASE_MATCHUP_RENDER = getattr(
    visual_core.visual,
    "_kyre_v198430_base_matchup_render",
    visual_core.visual._render_matchup_cards,
)
setattr(
    visual_core.visual,
    "_kyre_v198430_base_matchup_render",
    _BASE_MATCHUP_RENDER,
)

_BASE_PRODUCTION_RENDER = getattr(
    ui,
    "_kyre_v198430_base_production_render",
    ui._render_production,
)
setattr(
    ui,
    "_kyre_v198430_base_production_render",
    _BASE_PRODUCTION_RENDER,
)

_EARLY_PRODUCTION_DAY = ""


def _day(value) -> str:
    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except Exception:
        return str(value or "")


def _exact_readiness(day: str) -> dict:
    """Build the same readiness object the inherited V1.7 button receives."""
    try:
        _pool, pdiag = points.corrected_player_pool(day)
        pdiag = pdiag if isinstance(pdiag, dict) else {}
    except Exception:
        pdiag = {}

    try:
        info = v17._readiness_snapshot(day, pdiag)
    except TypeError:
        # Compatibility fallback only. The active V1.9.8.4.29 route accepts
        # (day, pdiag), but keep this wrapper safe if an older worker is draining.
        try:
            info = v17._readiness_snapshot(day)
        except Exception as exc:
            return {"ready": False, "error": f"{type(exc).__name__}: {exc}"}
    except Exception as exc:
        return {"ready": False, "error": f"{type(exc).__name__}: {exc}"}

    return info if isinstance(info, dict) else {"ready": False}


def _cards_control_then_matchups(day: str) -> None:
    """Cards first, then the one protected production control, then game cards."""
    global _EARLY_PRODUCTION_DAY

    day_str = _day(day)

    # Resolve this symbol dynamically. The Step 2→12 installers replace the
    # v1.9.4 H2H hook before the live visual header is entered, so this call
    # receives the completed same-card evidence stack rather than a stale base.
    h2h._render_h2h_cards(day_str)

    # Render the exact existing production control with the exact current
    # fail-closed readiness contract. This moves the control; it does not clone
    # or reimplement Monte Carlo execution.
    readiness = _exact_readiness(day_str)
    _EARLY_PRODUCTION_DAY = day_str
    _BASE_PRODUCTION_RENDER(day_str, readiness)

    # Keep the existing matchup-card context, only after the requested Top-5
    # history/evidence cards and simulation control.
    _BASE_MATCHUP_RENDER(day_str)


def _production_once(day: str, readiness: dict):
    """Suppress only the inherited second copy of the same production widget."""
    if _EARLY_PRODUCTION_DAY == _day(day):
        return None
    return _BASE_PRODUCTION_RENDER(day, readiness)


def _install() -> None:
    # V1.9.8.2's live header calls visual._render_matchup_cards. Use that exact
    # seam to restore the authoritative H2H/card renderer before engine-room UI.
    visual_core.visual._render_matchup_cards = _cards_control_then_matchups

    # V1.7 later calls ui._render_production again. Keep exactly one button/result
    # board per rerun so Streamlit never sees a duplicate button key.
    ui._render_production = _production_once


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    global _EARLY_PRODUCTION_DAY
    _EARLY_PRODUCTION_DAY = ""
    _install()
    st.caption(
        "🧭 Points V1.9.8.4.30 • Top-5 Player-vs-Team History cards first • "
        "Steps 2–12 stay embedded • one authoritative 5M control • all protected gates unchanged"
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
