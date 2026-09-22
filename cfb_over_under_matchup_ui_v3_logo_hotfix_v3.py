"""CFB Over/Under Intelligence V2 — ESPN logo recursion hotfix V3.

Additive presentation-only wrapper over permanently frozen logo hotfix V2.

Root cause fixed
----------------
During the full nested Upgrade Step 1 -> Step 2 -> Step 3 render chain, the
Step-2 wrapper temporarily replaces step1._enhanced_hero. Hotfix V2 called
that mutable symbol from inside its composite hero, so once the nested wrapper
was active the symbol pointed back to the composite hero itself and recursed.

V3 captures the certified original Step-1 enhanced hero exactly once at import
time and always calls that immutable function object. The ESPN resolver is still
forced only for that single Step-1 hero call, after which the original resolver
is restored.

No projection, probability, final selection, Top-5 ranking, reliability,
sportsbook, EV, or simulation behavior changes.
"""
from __future__ import annotations

import streamlit as st

import cfb_over_under_logo_resolver_v1 as logo_resolver
import cfb_over_under_matchup_ui_v1 as step1
import cfb_over_under_matchup_ui_v2 as step2
import cfb_over_under_matchup_ui_v3 as step3
import cfb_over_under_matchup_ui_v3_logo_hotfix_v2 as frozen_v2

MODEL_VERSION = "CFB O/U INTELLIGENCE V2 • ESPN LOGO RECURSION HOTFIX V3"
FROZEN_HOTFIX = "cfb_over_under_matchup_ui_v3_logo_hotfix_v2"
MARKET = "Over/Under"

# Immutable function-object captures made before nested wrappers temporarily
# rewrite public module symbols during a Streamlit render.
_FROZEN_STEP1_ENHANCED_HERO = step1._enhanced_hero
_FROZEN_STEP2_RANKINGS_PANEL = step2._rankings_panel
_FROZEN_STEP3_ENGINE_PANEL = step3._engine_panel


def _hero_with_nonrecursive_espn_logos(game, away, home) -> str:
    """Build the active composite hero without consulting mutable hero symbols."""
    original_visuals = step1._visuals_for_game
    step1._visuals_for_game = logo_resolver.resolve_visuals
    try:
        header = _FROZEN_STEP1_ENHANCED_HERO(game, away, home)
    finally:
        step1._visuals_for_game = original_visuals

    return (
        header
        + _FROZEN_STEP2_RANKINGS_PANEL(game, away, home)
        + _FROZEN_STEP3_ENGINE_PANEL(game, away, home)
    )


def render_over_under_hub(
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    st.caption("🏈 CFB O/U • ESPN logo recursion hotfix V3 ACTIVE")

    original_hero = step3._enhanced_hero_v3
    step3._enhanced_hero_v3 = _hero_with_nonrecursive_espn_logos
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
        raise ValueError(
            f"CFB O/U logo recursion hotfix V3 received unsupported market: {market}"
        )
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_HOTFIX",
    "MARKET",
    "MODEL_VERSION",
    "_FROZEN_STEP1_ENHANCED_HERO",
    "_hero_with_nonrecursive_espn_logos",
    "render_cfb_hub",
    "render_over_under_hub",
]
