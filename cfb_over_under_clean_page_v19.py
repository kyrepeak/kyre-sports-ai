"""CFB Over/Under Clean Page V19 — Step 5B freshness activation.

Additive wrapper over permanently frozen Clean Page V18.

V19 executes the already-certified V18 rendering contract with Market Adapter V2
in an isolated function-global context. Frozen V18 module globals are never
mutated, so concurrent Streamlit sessions cannot leak adapter state across page
versions.

Market Adapter V2 adds the Step 5A freshness/safety firewall. Frozen V1 still
owns official ESPN event-ID-only attachment. Frozen Steps 3-12 projection math
remain unchanged and sportsbook projection weight remains 0%.
"""
from __future__ import annotations

from types import FunctionType
from typing import Any, Callable

import streamlit as st

import cfb_over_under_clean_page_v18 as frozen_page
import cfb_over_under_market_adapter_v2 as market_adapter

MODEL_VERSION = "CFB O/U CLEAN PAGE V19 • STEP 5B FRESHNESS ACTIVE"
MARKET = "Over/Under"
FROZEN_PAGE = "cfb_over_under_clean_page_v18"
ACTIVE_MARKET_ADAPTER = "cfb_over_under_market_adapter_v2"
ACTIVE_SCHEDULE = frozen_page.ACTIVE_SCHEDULE
FROZEN_RUNTIME_SLATE = frozen_page.FROZEN_RUNTIME_SLATE

_V18_MARKER = "CFB O/U • CLEAN PAGE V18 ACTIVE"
_V19_MARKER = (
    "🟢 CFB O/U • CLEAN PAGE V19 ACTIVE • FRESHNESS FIREWALL ACTIVE • "
    "FROZEN PROJECTION MATH PRESERVED"
)


class _StreamlitV19Proxy:
    """Delegate Streamlit calls while replacing only V18's active-page marker."""

    def __getattr__(self, name: str) -> Any:
        return getattr(st, name)

    def caption(self, body: Any, *args: Any, **kwargs: Any) -> Any:
        text = str(body or "")
        if _V18_MARKER in text:
            body = _V19_MARKER
        return st.caption(body, *args, **kwargs)


def _clone_function(
    fn: Callable[..., Any],
    replacements: dict[str, Any],
) -> Callable[..., Any]:
    """Clone a function with isolated globals; never mutate the frozen module."""
    globals_copy = dict(fn.__globals__)
    globals_copy.update(replacements)
    cloned = FunctionType(
        fn.__code__,
        globals_copy,
        name=fn.__name__,
        argdefs=fn.__defaults__,
        closure=fn.__closure__,
    )
    cloned.__kwdefaults__ = getattr(fn, "__kwdefaults__", None)
    cloned.__doc__ = fn.__doc__
    return cloned


_market_caption = _clone_function(
    frozen_page._market_caption,
    {"market_adapter": market_adapter},
)
_line_board = _clone_function(
    frozen_page._line_board,
    {"market_adapter": market_adapter},
)
_RENDER_V19 = _clone_function(
    frozen_page.render_over_under_hub,
    {
        "market_adapter": market_adapter,
        "_market_caption": _market_caption,
        "_line_board": _line_board,
        "st": _StreamlitV19Proxy(),
    },
)


def render_over_under_hub(
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    return _RENDER_V19(
        section_header,
        status_info,
        team_logo,
        h,
    )


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(
            f"Clean O/U Page V19 received unsupported market: {market}"
        )
    return render_over_under_hub(
        section_header,
        status_info,
        team_logo,
        h,
    )


__all__ = [
    "ACTIVE_MARKET_ADAPTER",
    "ACTIVE_SCHEDULE",
    "FROZEN_PAGE",
    "FROZEN_RUNTIME_SLATE",
    "MARKET",
    "MODEL_VERSION",
    "_line_board",
    "_market_caption",
    "render_cfb_hub",
    "render_over_under_hub",
]
