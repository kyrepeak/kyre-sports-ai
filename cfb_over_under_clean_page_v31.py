"""CFB Over/Under Clean Page V31 — downstream official-identity bridge.

Additive wrapper over certified Clean Page V30. V31 preserves Schedule V7,
Market Adapter V2, readable Steps 4-12, qualification thresholds, and every
frozen projection engine. Its only active-path change is routing the inherited
runtime analysis call through Slate V15, which rehydrates verified official
identity before delegating unchanged projection work to frozen Slate V14.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import cfb_over_under_clean_page_v19 as clone_tools
import cfb_over_under_clean_page_v30 as frozen_page
import cfb_over_under_slate_v15_identity_bridge as runtime_bridge

MODEL_VERSION = "CFB O/U CLEAN PAGE V31 • DOWNSTREAM IDENTITY BRIDGE"
MARKET = "Over/Under"
FROZEN_PAGE = "cfb_over_under_clean_page_v30"
ACTIVE_MARKET_ADAPTER = frozen_page.ACTIVE_MARKET_ADAPTER
ACTIVE_MARKET_INTELLIGENCE = frozen_page.ACTIVE_MARKET_INTELLIGENCE
ACTIVE_SCHEDULE = frozen_page.ACTIVE_SCHEDULE
FROZEN_RUNTIME_SLATE = frozen_page.FROZEN_RUNTIME_SLATE
ACTIVE_RUNTIME_SLATE = "cfb_over_under_slate_v15_identity_bridge"

_V31_MARKER = (
    "🟢 CFB O/U • CLEAN PAGE V31 ACTIVE • DOWNSTREAM IDENTITY BRIDGE ACTIVE • "
    "FUTURE SLATE COVERAGE ACTIVE • OFFICIAL ESPN IDENTITY RECOVERY • "
    "NO FUZZY GAME MATCHING • NO SYNTHETIC IDS • FRESHNESS FIREWALL ACTIVE • "
    "DISPLAY ONLY • 0.0% SPORTSBOOK PROJECTION INFLUENCE • "
    "FROZEN V14 PROJECTION MATH PRESERVED • READABLE STEPS 4-12 ACTIVE"
)

# Preserve every effective V30 page dependency and replace only its inherited
# runtime_slate attribute. The underlying object remains the certified V30
# presentation proxy for all other attributes and render helpers.
_BASE_PAGE_GLOBAL = frozen_page._RENDER_V30.__globals__["frozen_page"]


class _RuntimeBridgePageProxy:
    def __getattr__(self, name: str) -> Any:
        if name == "runtime_slate":
            return runtime_bridge
        return getattr(_BASE_PAGE_GLOBAL, name)


class _StreamlitV31Proxy:
    """Delegate Streamlit while replacing only the inherited active-page marker."""

    def __getattr__(self, name: str) -> Any:
        return getattr(st, name)

    def caption(self, body: Any, *args: Any, **kwargs: Any) -> Any:
        text = str(body or "")
        if (
            "CFB O/U • CLEAN PAGE V18 ACTIVE" in text
            or "CFB O/U • CLEAN PAGE V19 ACTIVE" in text
            or "CFB O/U • CLEAN PAGE V20 ACTIVE" in text
            or "CFB O/U • CLEAN PAGE V30 ACTIVE" in text
            or "READABLE STEP 12 FINAL CERTIFICATION ACTIVE" in text
        ):
            body = _V31_MARKER
        return st.caption(body, *args, **kwargs)


_RENDER_V31 = clone_tools._clone_function(
    frozen_page._RENDER_V30,
    {
        "frozen_page": _RuntimeBridgePageProxy(),
        "st": _StreamlitV31Proxy(),
    },
)


def render_over_under_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    return _RENDER_V31(section_header, status_info, team_logo, h)


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"Clean O/U Page V31 received unsupported market: {market}")
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKET_ADAPTER",
    "ACTIVE_MARKET_INTELLIGENCE",
    "ACTIVE_RUNTIME_SLATE",
    "ACTIVE_SCHEDULE",
    "FROZEN_PAGE",
    "FROZEN_RUNTIME_SLATE",
    "MARKET",
    "MODEL_VERSION",
    "render_cfb_hub",
    "render_over_under_hub",
]
