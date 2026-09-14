"""NFL Moneyline V11 — no-flash presentation execution over certified V10.

V11 changes presentation execution only. Frozen V8 still computes the complete
Moneyline analytical chain, V9 still owns the matchup-card presentation, and
V10 still owns the Kyre Sports API transport swap.

The production flash came from V9's disposable legacy render becoming visible
before it was cleared. V11 keeps that exact frozen render path intact but places
it inside a container hidden *before* V8 starts. The frozen engine therefore
runs natively (including Streamlit caches and wrapper hooks) while none of the
legacy step-first surface is visible to the browser. The disposable contents are
cleared before V9 continues with the certified matchup cards.
"""
from __future__ import annotations

import streamlit as st

import nfl_moneyline_hub_v9 as frozen_v9
import nfl_moneyline_hub_v10 as v10

MODEL_VERSION = "NFL MONEYLINE V11 • PRE-HIDDEN LEGACY EXECUTION • V10/V9/V8 FROZEN"
FROZEN_TRANSPORT = "nfl_moneyline_hub_v10"
FROZEN_PRESENTATION = "nfl_moneyline_hub_v9"
FROZEN_ENGINE = "nfl_moneyline_hub_v8"
PRESENTATION_EXECUTION_ONLY = True
LEGACY_UI_VISIBLE = False
SPORTSBOOK_MODEL_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

LEGACY_CONTAINER_KEY = "nfl_moneyline_v11_legacy_hidden"
LEGACY_CONTAINER_CLASS = f"st-key-{LEGACY_CONTAINER_KEY}"

_HIDDEN_LEGACY_CSS = f"""
<style>
.{LEGACY_CONTAINER_CLASS} {{
  display: none !important;
  visibility: hidden !important;
  opacity: 0 !important;
  pointer-events: none !important;
  height: 0 !important;
  min-height: 0 !important;
  max-height: 0 !important;
  overflow: hidden !important;
  margin: 0 !important;
  padding: 0 !important;
}}
</style>
"""


def _hidden_run_frozen_engine() -> None:
    """Run exact frozen V8 in a container hidden before any legacy child exists."""
    # The CSS delta is emitted before the keyed container delta. When the legacy
    # container enters the DOM, its class is already governed by display:none.
    st.markdown(_HIDDEN_LEGACY_CSS, unsafe_allow_html=True)

    hidden = st.container(key=LEGACY_CONTAINER_KEY)
    with hidden:
        legacy = st.empty()
        with legacy.container():
            frozen_v9.frozen.render_nfl_moneyline_hub()
        # Preserve V9's original disposable behavior after the frozen engine has
        # finished so the final DOM does not retain the hidden legacy surface.
        legacy.empty()


def render_nfl_hub(market: str = "Moneyline"):
    market = str(market or "Moneyline")
    if market != "Moneyline":
        raise RuntimeError("Moneyline V11 direct handler is Moneyline only.")

    original_runner = frozen_v9._run_frozen_engine
    frozen_v9._run_frozen_engine = _hidden_run_frozen_engine
    try:
        return v10.render_nfl_hub(market)
    finally:
        frozen_v9._run_frozen_engine = original_runner


__all__ = [
    "FROZEN_ENGINE",
    "FROZEN_PRESENTATION",
    "FROZEN_TRANSPORT",
    "LEGACY_CONTAINER_CLASS",
    "LEGACY_CONTAINER_KEY",
    "LEGACY_UI_VISIBLE",
    "MODEL_VERSION",
    "PRESENTATION_EXECUTION_ONLY",
    "SPORTSBOOK_MODEL_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_hidden_run_frozen_engine",
    "render_nfl_hub",
]
