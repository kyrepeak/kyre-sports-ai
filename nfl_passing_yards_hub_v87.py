"""NFL Passing Yards V87 — Page 2 compact placeholder transport repair.

Presentation-only transport wrapper over frozen V86. V86's approved compact
Page-2 transformation is correct, but the frozen V34 composition owner emits the
final selected-QB HTML through ``placeholder.markdown(...)`` after the capture
pipeline completes. V86 wrapped module-level ``st.markdown`` only, so that final
body bypassed the compact transform in production.

V87 changes only the Streamlit output transport for the duration of one Passing
Yards render. It wraps placeholders returned by ``st.empty()`` and applies the
frozen V86 transform only when a placeholder receives the selected-QB Page-2
HTML. All other placeholder methods and all non-Page-2 markdown pass through
unchanged.

No football value, projection, context, probability, market math, sportsbook,
provider, widget, navigation, cache, or stake behavior changes.
"""
from __future__ import annotations

import importlib
from threading import RLock
from typing import Any, Callable

MODEL_VERSION = "NFL PASSING YARDS V87 • PAGE 2 COMPACT PLACEHOLDER TRANSPORT REPAIR"
FROZEN_PRIOR = "nfl_passing_yards_hub_v86"
TRANSPORT_VERSION = "v87"
PRESENTATION_ONLY = True
TRANSPORT_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_CONTEXT_MATH = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_SPORTSBOOK_BEHAVIOR = False
MAY_MODIFY_DATA_PROVIDER_BEHAVIOR = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_NAVIGATION_STATE = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_TRANSPORT_RLOCK = RLock()


def _transform_final_body(body: Any) -> Any:
    """Apply frozen V86 only to the actual selected-QB final HTML body."""
    if not isinstance(body, str):
        return body

    prior = importlib.import_module(FROZEN_PRIOR)
    transformed = prior._compact_selected_analysis(body)
    if transformed == body:
        return body

    marker = 'data-passing-yards-page2-compact-ux="v86"'
    if marker in transformed and 'data-passing-yards-page2-compact-transport="v87"' not in transformed:
        transformed = transformed.replace(
            marker,
            marker + ' data-passing-yards-page2-compact-transport="v87"',
            1,
        )
    return transformed


class _PlaceholderProxy:
    """Transparent Streamlit placeholder proxy with one markdown transform seam."""

    def __init__(self, delegate: Any, transform: Callable[[Any], Any]) -> None:
        object.__setattr__(self, "_delegate", delegate)
        object.__setattr__(self, "_transform", transform)

    def markdown(self, body: Any, *args: Any, **kwargs: Any) -> Any:
        transformed = self._transform(body)
        return self._delegate.markdown(transformed, *args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in {"_delegate", "_transform"}:
            object.__setattr__(self, name, value)
            return
        setattr(self._delegate, name, value)


def _make_empty_bridge(delegate: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap placeholders while preserving the exact ``st.empty`` call contract."""
    if getattr(delegate, "_passing_yards_page2_v87_empty_bridge", False):
        return delegate

    def _bridge(*args: Any, **kwargs: Any) -> _PlaceholderProxy:
        placeholder = delegate(*args, **kwargs)
        if isinstance(placeholder, _PlaceholderProxy):
            return placeholder
        return _PlaceholderProxy(placeholder, _transform_final_body)

    _bridge._passing_yards_page2_v87_empty_bridge = True  # type: ignore[attr-defined]
    _bridge._passing_yards_page2_v87_delegate = delegate  # type: ignore[attr-defined]
    return _bridge


def render_nfl_passing_yards_hub() -> None:
    """Run frozen V86 with the final V34 placeholder transport intercepted."""
    st = importlib.import_module("streamlit")
    prior = importlib.import_module(FROZEN_PRIOR)

    with _TRANSPORT_RLOCK:
        original_empty = st.empty
        st.empty = _make_empty_bridge(original_empty)
        try:
            return prior.render_nfl_passing_yards_hub()
        finally:
            st.empty = original_empty


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V87 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "MAY_MODIFY_CONTEXT_MATH",
    "MAY_MODIFY_DATA_PROVIDER_BEHAVIOR",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_NAVIGATION_STATE",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_SPORTSBOOK_BEHAVIOR",
    "MAY_MODIFY_WIDGET_KEYS",
    "MODEL_VERSION",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "TRANSPORT_ONLY",
    "TRANSPORT_VERSION",
    "_PlaceholderProxy",
    "_make_empty_bridge",
    "_transform_final_body",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
