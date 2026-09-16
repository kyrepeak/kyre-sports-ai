"""NFL Passing Yards V36 — Compact Dashboard First presentation layer.

Additive display-only wrapper over certified V35. V36 reorganizes already-rendered
V34/V35 identity, projection, context, distribution and market fragments into a
compact decision-first dashboard. No analytical value is recomputed or mutated.
"""
from __future__ import annotations

import streamlit as st

import nfl_passing_yards_compact_ui_v1 as compact_ui
import nfl_passing_yards_hub_v34 as composition
import nfl_passing_yards_hub_v35 as prior

MODEL_VERSION = "NFL PASSING YARDS V36 • COMPACT DASHBOARD FIRST"
FROZEN_PRIOR = "nfl_passing_yards_hub_v35"
FROZEN_COMPOSITION = "nfl_passing_yards_hub_v34"
FROZEN_PASSING_ENGINE = "nfl_passing_yards_hub_v28"
DISPLAY_ONLY = True
COMPACT_DASHBOARD_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False


def _compact_cards(captured: dict[str, list[str]]) -> str:
    matchup_label = str(st.session_state.get("nfl_passing_yards_v8_matchup") or "")
    return compact_ui.compact_dashboard_html(captured, matchup_label=matchup_label)


def render_nfl_passing_yards_hub() -> None:
    """Render frozen V35 values through the compact V36 composition only."""
    original_css = composition._PLAYER_CARD_CSS
    original_combined = composition._combined_player_cards_html
    original_banner = composition._visual_build_banner_v34

    composition._PLAYER_CARD_CSS = compact_ui.COMPACT_DASHBOARD_CSS
    composition._combined_player_cards_html = _compact_cards
    composition._visual_build_banner_v34 = compact_ui.compact_banner_html
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        composition._PLAYER_CARD_CSS = original_css
        composition._combined_player_cards_html = original_combined
        composition._visual_build_banner_v34 = original_banner


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V36 only renders the Passing Yards market.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "COMPACT_DASHBOARD_ONLY",
    "DISPLAY_ONLY",
    "FROZEN_COMPOSITION",
    "FROZEN_PASSING_ENGINE",
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_compact_cards",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
