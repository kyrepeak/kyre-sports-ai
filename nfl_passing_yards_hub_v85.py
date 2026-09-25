"""NFL Passing Yards V85 — bounded V74 presentation cleanup.

Presentation-only wrapper over frozen V84. The frozen V74 availability/game-day
panel reads values from already-rendered certified evidence. Its legacy metric
regex can cross earlier </b> boundaries and accidentally capture unrelated
market/model HTML before the requested label. V85 replaces only that temporary
HTML extractor during the Passing Yards render with a bounded, fail-closed
reader.

No provider call, football value, projection, context, probability, market,
sportsbook, widget, navigation, cache, or transport behavior changes.
"""
from __future__ import annotations

import re
from html import unescape
from threading import RLock

import streamlit as st

import nfl_passing_yards_hub_v74 as availability_v74
import nfl_passing_yards_hub_v84 as prior

MODEL_VERSION = "NFL PASSING YARDS V85 • V74 BOUNDED PRESENTATION CLEANUP"
FROZEN_PRIOR = "nfl_passing_yards_hub_v84"
CLEANUP_VERSION = "v85"
PRESENTATION_ONLY = True
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

MAX_METRIC_VALUE_CHARS = 120
_PROCESS_CLEANUP_RLOCK = RLock()
_BOUNDED_B_VALUE = rf"((?:(?!</b>).){{0,{MAX_METRIC_VALUE_CHARS}}})"
_RAW_DUMP_TOKENS = (
    "Market Decision Detail",
    "How to read this clean detail",
    "Projection Detail",
    "Context + Uncertainty Detail",
    "Distribution + Probability Detail",
    "sportsbook projection influence",
    "Model Confidence",
    "Model Over / Under",
)


def _plain(value: object) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""), flags=re.S)
    return " ".join(unescape(text).replace("&nbsp;", " ").split()).strip()


def _bounded_metric(body: str, label: str) -> str:
    """Read only the adjacent bold value for one V74 label.

    The negative </b> boundary prevents the match from walking backward through
    earlier cards/sections. Oversized or obviously cross-section values fail
    closed to the same empty value V74 already understands.
    """
    pattern = re.compile(
        rf"<b[^>]*>\s*{_BOUNDED_B_VALUE}\s*</b>\s*"
        rf"<span[^>]*>\s*{re.escape(str(label or ''))}\s*</span>",
        flags=re.I | re.S,
    )
    match = pattern.search(str(body or ""))
    if not match:
        return ""
    value = _plain(match.group(1))
    if not value or len(value) > MAX_METRIC_VALUE_CHARS:
        return ""
    if any(token.lower() in value.lower() for token in _RAW_DUMP_TOKENS):
        return ""
    return value


def render_nfl_passing_yards_hub() -> None:
    st.markdown(
        '<span data-passing-yards-visible-cleanup-owner="v85" '
        'data-passing-yards-v74-bounded-metric="true" '
        'style="display:none" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )
    with _PROCESS_CLEANUP_RLOCK:
        original_metric = availability_v74._metric
        availability_v74._metric = _bounded_metric
        try:
            return prior.render_nfl_passing_yards_hub()
        finally:
            availability_v74._metric = original_metric


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V85 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "CLEANUP_VERSION",
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "MAX_METRIC_VALUE_CHARS",
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
    "_bounded_metric",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
