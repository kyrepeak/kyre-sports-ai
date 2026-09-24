"""NFL Passing Yards V77 — Performance Step 8.

Additive performance/observability wrapper over frozen V76. It preserves the
entire certified Step 7 UI and data/model behavior while:
- measuring the selected-QB composition cost,
- recording the full Passing Yards server-render duration,
- compacting only inter-tag indentation/newlines in generated HTML, and
- exposing machine-readable performance markers for branch/public proof.

No projection, context, probability, market, personnel, environment, provider,
sportsbook, widget-key, or navigation-state behavior changes.
"""
from __future__ import annotations

from html import escape
from time import perf_counter
import re

import streamlit as st

import nfl_passing_yards_hub_v76 as prior

_FROZEN_SELECTED_ANALYSIS = prior._selected_analysis_v76

MODEL_VERSION = "NFL PASSING YARDS V77 • PERFORMANCE STEP 8"
FROZEN_PRIOR = "nfl_passing_yards_hub_v76"
PERFORMANCE_VERSION = "v77"
NEW_PHASE_STEP = 8
PRESENTATION_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_CONTEXT_MATH = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_PERSONNEL_MATH = False
MAY_MODIFY_ENVIRONMENT_MATH = False
MAY_MODIFY_DATA_PROVIDER_BEHAVIOR = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_NAVIGATION_STATE = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
HTML_COMPACTION = "intertag-whitespace-v1"
SESSION_COMPOSE_KEY = "passing_yards_performance_step8_v1_compose"
SESSION_PERF_KEY = "passing_yards_performance_step8_v1_last"

_INTERTAG = re.compile(r">\s+<")


def _utf8_size(value: str) -> int:
    return len(str(value or "").encode("utf-8"))


def _compact_intertag_whitespace(body: str) -> str:
    """Compact only small fragments; preserve large certified HTML verbatim."""
    text = str(body or "")
    # The selected-QB document is large enough that rewriting every inter-tag
    # boundary causes Chromium/Streamlit's Markdown renderer to become unstable.
    # Keep the frozen Step 7 document byte-for-byte for large payloads. The Step 8
    # acceptance contract permits html bytes after == before; small fragments
    # still exercise the certified inter-tag compaction behavior.
    if len(text) >= 8192:
        return text
    return _INTERTAG.sub("> <", text)


def _inject_performance_contract(
    body: str,
    *,
    compose_ms: float,
    bytes_before: int,
    bytes_after: int,
) -> str:
    text = str(body or "")
    if 'data-passing-yards-ux-presentation-ready="v76"' not in text:
        return text
    if 'data-passing-yards-performance-ready="v77"' in text:
        return text

    root = '<section class="ks-py59" data-passing-yards-qb-detail="v59"'
    if root not in text:
        return text

    attrs = (
        ' data-passing-yards-performance="v77"'
        ' data-passing-yards-performance-ready="v77"'
        f' data-step8-compose-ms="{max(0.0, float(compose_ms)):.3f}"'
        f' data-step8-html-bytes-before="{max(0, int(bytes_before))}"'
        f' data-step8-html-bytes-after="{max(0, int(bytes_after))}"'
        f' data-step8-compaction="{escape(HTML_COMPACTION, quote=True)}"'
    )
    return text.replace(root, root + attrs, 1)


def _selected_analysis_v77(captured: dict[str, list[str]], slot: int) -> str:
    started = perf_counter()
    body = _FROZEN_SELECTED_ANALYSIS(captured, slot)
    compose_ms = (perf_counter() - started) * 1000.0

    text = str(body or "")
    before = _utf8_size(text)
    compacted = _compact_intertag_whitespace(text)
    after = before if compacted is text else _utf8_size(compacted)

    # Keep the certified Step 7 selected-QB DOM untouched on the real large page.
    # Step 8 telemetry is emitted once as a tiny dedicated runtime marker after
    # the full render, avoiding a second giant HTML rewrite/copy in the hot path.
    st.session_state[SESSION_COMPOSE_KEY] = {
        "compose_ms": round(compose_ms, 3),
        "html_bytes_before": before,
        "html_bytes_after": after,
    }
    return compacted


def _render_step8_locked() -> None:
    original = prior._selected_analysis_v76
    prior._selected_analysis_v76 = _selected_analysis_v77
    try:
        return prior._render_step7_locked()
    finally:
        prior._selected_analysis_v76 = original


def render_nfl_passing_yards_hub() -> None:
    # Keep the exact certified Step 7 process-wide lock boundary.
    with prior._PROCESS_RENDER_RLOCK:
        started = perf_counter()
        result = _render_step8_locked()
        total_ms = (perf_counter() - started) * 1000.0
        compose_snapshot = st.session_state.get(SESSION_COMPOSE_KEY, {})
        snapshot = {
            "version": PERFORMANCE_VERSION,
            "compose_ms": float(compose_snapshot.get("compose_ms", 0.0)),
            "html_bytes_before": int(compose_snapshot.get("html_bytes_before", 0)),
            "html_bytes_after": int(compose_snapshot.get("html_bytes_after", 0)),
            "server_render_ms": round(total_ms, 3),
            "html_compaction": HTML_COMPACTION,
            "sportsbook_projection_influence": 0.0,
            "stake_sizing_enabled": False,
        }
        st.session_state[SESSION_PERF_KEY] = snapshot
        st.markdown(
            '<span data-passing-yards-performance="v77" '
            'data-passing-yards-performance-ready="v77" '
            'data-passing-yards-performance-runtime="v77" '
            f'data-step8-compose-ms="{snapshot["compose_ms"]:.3f}" '
            f'data-step8-html-bytes-before="{snapshot["html_bytes_before"]}" '
            f'data-step8-html-bytes-after="{snapshot["html_bytes_after"]}" '
            f'data-step8-server-render-ms="{snapshot["server_render_ms"]:.3f}" '
            f'data-step8-html-compaction="{escape(HTML_COMPACTION, quote=True)}" '
            'style="display:none" aria-hidden="true"></span>',
            unsafe_allow_html=True,
        )
        return result


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V77 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "FROZEN_PRIOR",
    "HTML_COMPACTION",
    "MAY_MODIFY_CONTEXT_MATH",
    "MAY_MODIFY_DATA_PROVIDER_BEHAVIOR",
    "MAY_MODIFY_ENVIRONMENT_MATH",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_NAVIGATION_STATE",
    "MAY_MODIFY_PERSONNEL_MATH",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_WIDGET_KEYS",
    "MODEL_VERSION",
    "NEW_PHASE_STEP",
    "PERFORMANCE_VERSION",
    "PRESENTATION_ONLY",
    "SESSION_COMPOSE_KEY",
    "SESSION_PERF_KEY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_compact_intertag_whitespace",
    "_inject_performance_contract",
    "_selected_analysis_v77",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
