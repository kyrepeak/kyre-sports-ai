"""CFB Over/Under Clean Page V21 — readable Step 4 pace presentation.

Additive presentation wrapper over certified Clean Page V20. The active market
adapter, Step 5C market intelligence, Schedule V6 path, and frozen Steps 3-12
projection math are reused unchanged. V21 replaces only the generic Step 4 HTML
renderer with a readable view of the pace engine output already produced by the
frozen runtime slate.
"""
from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

import cfb_over_under_clean_page_v20 as frozen_page
import cfb_over_under_step4_readable_v1 as readable_step4

MODEL_VERSION = "CFB O/U CLEAN PAGE V21 • READABLE STEP 4 PACE"
MARKET = "Over/Under"
FROZEN_PAGE = "cfb_over_under_clean_page_v20"
ACTIVE_MARKET_ADAPTER = frozen_page.ACTIVE_MARKET_ADAPTER
ACTIVE_MARKET_INTELLIGENCE = frozen_page.ACTIVE_MARKET_INTELLIGENCE
ACTIVE_SCHEDULE = frozen_page.ACTIVE_SCHEDULE
FROZEN_RUNTIME_SLATE = frozen_page.FROZEN_RUNTIME_SLATE

# Keep the certified Step-6 marker visible so existing production verification
# continues proving the active market/freshness contract while V21 adds Step 4 UI.
_V21_MARKER = (
    "🟢 CFB O/U • CLEAN PAGE V20 ACTIVE • STEP 6 MARKET INTELLIGENCE LIVE • "
    "FRESHNESS FIREWALL ACTIVE • DISPLAY ONLY • 0.0% PROJECTION INFLUENCE • "
    "FROZEN PROJECTION MATH PRESERVED • READABLE STEP 4 PACE ACTIVE"
)


class _StreamlitV21Proxy:
    def __getattr__(self, name: str) -> Any:
        return getattr(st, name)

    def caption(self, body: Any, *args: Any, **kwargs: Any) -> Any:
        text = str(body or "")
        if "CFB O/U • CLEAN PAGE V18 ACTIVE" in text or "CFB O/U • CLEAN PAGE V19 ACTIVE" in text or "CFB O/U • CLEAN PAGE V20 ACTIVE" in text:
            body = _V21_MARKER
        return st.caption(body, *args, **kwargs)


class _FrozenPresentationProxy:
    """Delegate frozen V17 presentation helpers; replace only Step 4 rendering."""

    def __init__(self, base: Any) -> None:
        self._base = base

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base, name)

    def _model_step(self, step: int, title: str, engine: Mapping[str, Any]) -> str:
        if int(step) == 4:
            return readable_step4.render_step4(engine)
        return self._base._model_step(step, title, engine)


_BASE_PRESENTATION = frozen_page._RENDER_V20.__globals__["frozen_page"]
_PRESENTATION_PROXY = _FrozenPresentationProxy(_BASE_PRESENTATION)
_RENDER_V21 = frozen_page._clone_function(
    frozen_page._RENDER_V20,
    {
        "frozen_page": _PRESENTATION_PROXY,
        "st": _StreamlitV21Proxy(),
    },
)


def render_over_under_hub(
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    return _RENDER_V21(section_header, status_info, team_logo, h)


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Clean O/U Page V21 received unsupported market: {market}")
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
