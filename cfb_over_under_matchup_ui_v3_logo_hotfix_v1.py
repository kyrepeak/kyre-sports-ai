"""CFB Over/Under Intelligence V2 — ESPN logo hotfix wrapper.

Additive presentation-only wrapper over permanently frozen Upgrade Step 3.
It replaces only the frozen Step-1 logo resolver during render, then restores it.
"""
from __future__ import annotations

import streamlit as st

import cfb_over_under_logo_resolver_v1 as logo_resolver
import cfb_over_under_matchup_ui_v3 as frozen_v3

MODEL_VERSION = "CFB O/U INTELLIGENCE V2 • ESPN LOGO HOTFIX V1"
FROZEN_UPGRADE = "cfb_over_under_matchup_ui_v3"
MARKET = "Over/Under"

_STEP1_UI = frozen_v3.frozen_v2.frozen_v1


def render_over_under_hub(
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    st.caption("🏈 CFB O/U • ESPN team-logo resolver hotfix ACTIVE")

    original = _STEP1_UI._visuals_for_game
    _STEP1_UI._visuals_for_game = logo_resolver.resolve_visuals
    try:
        return frozen_v3.render_over_under_hub(
            section_header,
            status_info,
            team_logo,
            h,
        )
    finally:
        _STEP1_UI._visuals_for_game = original


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"CFB O/U logo hotfix received unsupported market: {market}")
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_UPGRADE",
    "MARKET",
    "MODEL_VERSION",
    "render_cfb_hub",
    "render_over_under_hub",
]
