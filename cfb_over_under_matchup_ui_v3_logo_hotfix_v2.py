"""CFB Over/Under Intelligence V2 — ESPN logo hotfix V2.

This wrapper fixes the remaining runtime logo-render path discovered after V1:
the ESPN resolver itself works live for Florida A&M @ Miami, but the previous
outer patch could be bypassed by the nested frozen Upgrade Step 1 -> 2 -> 3
hero wrapper chain.

V2 therefore patches the active Step-3 hero function directly and builds the
composite hero explicitly:
1. frozen Step-1 matchup header with the V1 ESPN resolver forced for that call,
2. frozen Step-2 rankings/conference/records panel,
3. frozen Step-3 offense-vs-defense panel.

No model, probability, selection, ranking, reliability, sportsbook, EV, or
simulation behavior is modified.
"""
from __future__ import annotations

import streamlit as st

import cfb_over_under_logo_resolver_v1 as logo_resolver
import cfb_over_under_matchup_ui_v1 as step1
import cfb_over_under_matchup_ui_v2 as step2
import cfb_over_under_matchup_ui_v3 as step3

MODEL_VERSION = "CFB O/U INTELLIGENCE V2 • ESPN LOGO HOTFIX V2"
FROZEN_UPGRADE = "cfb_over_under_matchup_ui_v3"
MARKET = "Over/Under"


def _hero_with_forced_espn_logos(game, away, home) -> str:
    """Build the active composite hero with ESPN logos resolved in-call.

    This avoids relying on an outer global monkey-patch surviving through the
    nested frozen wrapper chain.
    """
    original_visuals = step1._visuals_for_game
    step1._visuals_for_game = logo_resolver.resolve_visuals
    try:
        header = step1._enhanced_hero(game, away, home)
    finally:
        step1._visuals_for_game = original_visuals

    return (
        header
        + step2._rankings_panel(game, away, home)
        + step3._engine_panel(game, away, home)
    )


def render_over_under_hub(
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    st.caption("🏈 CFB O/U • ESPN team-logo resolver V2 ACTIVE")

    original_hero = step3._enhanced_hero_v3
    step3._enhanced_hero_v3 = _hero_with_forced_espn_logos
    try:
        return step3.render_over_under_hub(
            section_header,
            status_info,
            team_logo,
            h,
        )
    finally:
        step3._enhanced_hero_v3 = original_hero


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"CFB O/U logo hotfix V2 received unsupported market: {market}")
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_UPGRADE",
    "MARKET",
    "MODEL_VERSION",
    "_hero_with_forced_espn_logos",
    "render_cfb_hub",
    "render_over_under_hub",
]
