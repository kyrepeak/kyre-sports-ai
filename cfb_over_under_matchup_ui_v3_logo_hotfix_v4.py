"""CFB Over/Under Intelligence V2 — multi-source logo hotfix V4.

Additive presentation-only wrapper over permanently frozen recursion hotfix V3.

The active hero now resolves missing college logos from a provider chain:
ESPN -> official athletics website -> Wikipedia/Wikimedia -> Wikimedia Commons.

The V3 immutable Step-1 hero capture is preserved so the nested wrapper chain
cannot recurse.
"""
from __future__ import annotations

import streamlit as st

import cfb_over_under_logo_resolver_v2 as logo_resolver
import cfb_over_under_matchup_ui_v3_logo_hotfix_v3 as frozen_v3

MODEL_VERSION = "CFB O/U INTELLIGENCE V2 • MULTI-SOURCE LOGO HOTFIX V4"
FROZEN_HOTFIX = "cfb_over_under_matchup_ui_v3_logo_hotfix_v3"
MARKET = "Over/Under"

step1 = frozen_v3.step1
step3 = frozen_v3.step3

_FROZEN_STEP1_ENHANCED_HERO = frozen_v3._FROZEN_STEP1_ENHANCED_HERO
_FROZEN_STEP2_RANKINGS_PANEL = frozen_v3._FROZEN_STEP2_RANKINGS_PANEL
_FROZEN_STEP3_ENGINE_PANEL = frozen_v3._FROZEN_STEP3_ENGINE_PANEL


def _hero_with_multisource_logos(game, away, home) -> str:
    original_visuals = step1._visuals_for_game
    step1._visuals_for_game = logo_resolver.resolve_visuals
    try:
        header = _FROZEN_STEP1_ENHANCED_HERO(game, away, home)
    finally:
        step1._visuals_for_game = original_visuals

    header = header.replace(
        "Logos are presentation-only ESPN scoreboard metadata.",
        "Logos are presentation-only multi-source identity assets: ESPN first, then official athletics websites, Wikipedia/Wikimedia, and Wikimedia Commons fallbacks.",
    )

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
    st.caption(
        "🏈 CFB O/U • MULTI-SOURCE TEAM-LOGO RESOLVER V4 ACTIVE • "
        "ESPN + official athletics + Wikipedia/Wikimedia"
    )

    original_hero = step3._enhanced_hero_v3
    step3._enhanced_hero_v3 = _hero_with_multisource_logos
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
            f"CFB O/U multi-source logo hotfix V4 received unsupported market: {market}"
        )
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_HOTFIX",
    "MARKET",
    "MODEL_VERSION",
    "_hero_with_multisource_logos",
    "render_cfb_hub",
    "render_over_under_hub",
]
