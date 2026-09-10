"""CFB Over/Under Clean Page V30 — official future-slate coverage.

Additive wrapper over certified Clean Page V29. V30 changes only the schedule
provider used by the already-certified render function: Schedule V6 is replaced
with additive Schedule V7. Readable Steps 4-12, Market Adapter V2, the frozen
projection engines, and all qualification thresholds remain unchanged.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import cfb_over_under_clean_page_v19 as clone_tools
import cfb_over_under_clean_page_v29 as frozen_page
import cfb_schedule_v7_future_slate as schedule_v7

MODEL_VERSION = "CFB O/U CLEAN PAGE V30 • OFFICIAL FUTURE SLATE COVERAGE"
MARKET = "Over/Under"
FROZEN_PAGE = "cfb_over_under_clean_page_v29"
ACTIVE_MARKET_ADAPTER = frozen_page.ACTIVE_MARKET_ADAPTER
ACTIVE_MARKET_INTELLIGENCE = frozen_page.ACTIVE_MARKET_INTELLIGENCE
ACTIVE_SCHEDULE = "cfb_schedule_v7_future_slate"
FROZEN_RUNTIME_SLATE = frozen_page.FROZEN_RUNTIME_SLATE

_V30_MARKER = (
    "🟢 CFB O/U • CLEAN PAGE V30 ACTIVE • FUTURE SLATE COVERAGE ACTIVE • "
    "OFFICIAL ESPN IDENTITY RECOVERY • NO FUZZY MATCHING • NO SYNTHETIC IDS • "
    "FRESHNESS FIREWALL ACTIVE • DISPLAY ONLY • 0.0% PROJECTION INFLUENCE • "
    "FROZEN PROJECTION MATH PRESERVED • READABLE STEPS 4-12 ACTIVE"
)


class _StreamlitV30Proxy:
    """Delegate Streamlit while replacing only the inherited active-page marker."""

    def __getattr__(self, name: str) -> Any:
        return getattr(st, name)

    def caption(self, body: Any, *args: Any, **kwargs: Any) -> Any:
        text = str(body or "")
        if "READABLE STEP 12 FINAL CERTIFICATION ACTIVE" in text:
            body = _V30_MARKER
        return st.caption(body, *args, **kwargs)


_RENDER_V30 = clone_tools._clone_function(
    frozen_page._RENDER_V29,
    {
        "schedule_v6": schedule_v7,
        "st": _StreamlitV30Proxy(),
    },
)


def render_over_under_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    return _RENDER_V30(section_header, status_info, team_logo, h)


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"Clean O/U Page V30 received unsupported market: {market}")
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKET_ADAPTER",
    "ACTIVE_MARKET_INTELLIGENCE",
    "ACTIVE_SCHEDULE",
    "FROZEN_PAGE",
    "FROZEN_RUNTIME_SLATE",
    "MARKET",
    "MODEL_VERSION",
    "render_cfb_hub",
    "render_over_under_hub",
]
