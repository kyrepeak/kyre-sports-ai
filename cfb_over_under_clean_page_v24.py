"""CFB Over/Under Clean Page V24 — readable Step 7 third-down presentation.

Additive presentation wrapper over certified Clean Page V23. V24 preserves
readable Steps 4-6, market freshness/intelligence contracts, and frozen Steps
3-12 projection math while replacing only generic Step 7 presentation.
"""
from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

import cfb_over_under_clean_page_v23 as frozen_page
import cfb_over_under_step7_readable_v1 as readable_step7

MODEL_VERSION = "CFB O/U CLEAN PAGE V24 • READABLE STEP 7 THIRD DOWN"
MARKET = "Over/Under"
FROZEN_PAGE = "cfb_over_under_clean_page_v23"
ACTIVE_MARKET_ADAPTER = frozen_page.ACTIVE_MARKET_ADAPTER
ACTIVE_MARKET_INTELLIGENCE = frozen_page.ACTIVE_MARKET_INTELLIGENCE
ACTIVE_SCHEDULE = frozen_page.ACTIVE_SCHEDULE
FROZEN_RUNTIME_SLATE = frozen_page.FROZEN_RUNTIME_SLATE

_V24_MARKER = (
    "🟢 CFB O/U • CLEAN PAGE V20 ACTIVE • STEP 6 MARKET INTELLIGENCE LIVE • "
    "FRESHNESS FIREWALL ACTIVE • DISPLAY ONLY • 0.0% PROJECTION INFLUENCE • "
    "FROZEN PROJECTION MATH PRESERVED • READABLE STEP 4 PACE ACTIVE • "
    "READABLE STEP 5 EXPLOSIVE ACTIVE • READABLE STEP 6 RED ZONE ACTIVE • "
    "READABLE STEP 7 THIRD DOWN ACTIVE"
)


class _StreamlitV24Proxy:
    def __getattr__(self, name: str) -> Any:
        return getattr(st, name)

    def caption(self, body: Any, *args: Any, **kwargs: Any) -> Any:
        text = str(body or "")
        if (
            "CFB O/U • CLEAN PAGE V18 ACTIVE" in text
            or "CFB O/U • CLEAN PAGE V19 ACTIVE" in text
            or "CFB O/U • CLEAN PAGE V20 ACTIVE" in text
        ):
            body = _V24_MARKER
        return st.caption(body, *args, **kwargs)


class _PresentationProxyV24:
    """Delegate V23 presentation; replace only Step 7 rendering."""

    def __init__(self, base: Any) -> None:
        self._base = base

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base, name)

    def _model_step(self, step: int, title: str, engine: Mapping[str, Any]) -> str:
        if int(step) == 7:
            return readable_step7.render_step7(engine)
        return self._base._model_step(step, title, engine)


_BASE_PRESENTATION = frozen_page._RENDER_V23.__globals__["frozen_page"]
_PRESENTATION_PROXY = _PresentationProxyV24(_BASE_PRESENTATION)
_RENDER_V24 = frozen_page.frozen_page.frozen_page.frozen_page._clone_function(
    frozen_page._RENDER_V23,
    {
        "frozen_page": _PRESENTATION_PROXY,
        "st": _StreamlitV24Proxy(),
    },
)


def render_over_under_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    return _RENDER_V24(section_header, status_info, team_logo, h)


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"Clean O/U Page V24 received unsupported market: {market}")
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKET_ADAPTER", "ACTIVE_MARKET_INTELLIGENCE", "ACTIVE_SCHEDULE",
    "FROZEN_PAGE", "FROZEN_RUNTIME_SLATE", "MARKET", "MODEL_VERSION",
    "render_cfb_hub", "render_over_under_hub",
]
