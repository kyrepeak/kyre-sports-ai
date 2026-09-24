"""NFL Passing Yards V81 — full-analysis payload deduplication.

Speed Phase Step 5. The frozen full-analysis chain already presents the selected
quarterback's profile, opponent defense, pressure/protection, personnel, and
environment evidence in the dedicated analysis sections. Frozen V67 then embeds
those same captured HTML payloads a second time inside Deep Evidence.

V81 preserves the certified evidence sections and V67 selectors/provenance while
replacing only that duplicate second copy with a compact pointer. No model,
projection, probability, context, market, provider, sportsbook, widget-key, or
navigation calculations are changed.
"""
from __future__ import annotations

from html import escape
from threading import RLock

import streamlit as st

import nfl_passing_yards_hub_v67 as deep_v67
import nfl_passing_yards_hub_v80 as prior

MODEL_VERSION = "NFL PASSING YARDS V81 • SPEED STEP 5 PAYLOAD DEDUPE"
FROZEN_PRIOR = "nfl_passing_yards_hub_v80"
SPEED_PHASE_STEP = 5
PAYLOAD_DEDUPE_VERSION = "v81"
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

_PROCESS_DEDUPE_RLOCK = RLock()


def _piece(captured: dict[str, list[str]], key: str, index: int) -> str:
    rows = captured.get(key) or []
    if key == "environment":
        return str(rows[0]) if rows else ""
    return str(rows[index]) if index < len(rows) else ""


def _duplicate_payload_bytes(captured: dict[str, list[str]], slot: int) -> int:
    index = max(0, int(slot) - 1)
    total = 0
    for key in ("profile", "defense", "pressure", "personnel", "environment"):
        total += len(_piece(captured, key, index).encode("utf-8"))
    return total


def build_compact_deep_evidence(captured: dict[str, list[str]], slot: int) -> str:
    avoided = _duplicate_payload_bytes(captured, slot)
    labels = (
        "Recent QB Games + Profile",
        "Opponent Pass-Defense Evidence",
        "Protection + Pressure Evidence",
        "Personnel + Availability Evidence",
        "Game Environment Evidence",
    )
    chips = "".join(
        f'<span class="ks-py67-badge">{escape(label)}</span>' for label in labels
    )
    return (
        '<section class="ks-py67-deep" data-passing-yards-deep-evidence="v67" '
        'data-passing-yards-payload-dedupe="v81" '
        'data-passing-yards-payload-dedupe-ready="v81" '
        f'data-step5-avoided-duplicate-bytes="{avoided}">'
        '<div class="ks-py67-head"><div>'
        '<div class="ks-py67-kicker">Receipts behind the analysis</div>'
        '<div class="ks-py67-title">Deep Evidence</div>'
        '</div><div class="ks-py67-badge">FROZEN EVIDENCE • SINGLE COPY</div></div>'
        '<div class="ks-py67-provenance" data-passing-yards-evidence-provenance="v67">'
        '<strong>Evidence preserved without duplicate payload:</strong> the certified '
        'profile, defense, pressure, personnel, and environment evidence remains in '
        'the original analysis sections above. Step 5 removes only V67\'s second raw '
        'HTML copy to reduce full-analysis transfer and render cost.</div>'
        f'<div class="ks-py67-head" style="margin-top:10px;justify-content:flex-start;flex-wrap:wrap">{chips}</div>'
        '<details class="ks-py67-method" data-passing-yards-deep-evidence-method="v67">'
        '<summary>What Speed Step 5 changes</summary>'
        '<p>Presentation transport only. No evidence builder, projection, probability, '
        'context, market, sportsbook, provider, or navigation calculation changes. '
        'Sportsbook projection influence remains 0.0%.</p></details>'
        '</section>'
    )


def render_nfl_passing_yards_hub() -> None:
    st.markdown(
        '<span data-passing-yards-payload-dedupe-owner="v81" '
        'style="display:none" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )
    with _PROCESS_DEDUPE_RLOCK:
        original = deep_v67.build_deep_evidence
        deep_v67.build_deep_evidence = build_compact_deep_evidence
        try:
            return prior.render_nfl_passing_yards_hub()
        finally:
            deep_v67.build_deep_evidence = original


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V81 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "DISPLAY_ONLY","FROZEN_PRIOR","MAY_MODIFY_CONTEXT_MATH",
    "MAY_MODIFY_DATA_PROVIDER_BEHAVIOR","MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_NAVIGATION_STATE","MAY_MODIFY_PROBABILITY","MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_SPORTSBOOK_BEHAVIOR","MAY_MODIFY_WIDGET_KEYS","MODEL_VERSION",
    "PAYLOAD_DEDUPE_VERSION","PRESENTATION_ONLY","SPEED_PHASE_STEP",
    "SPORTSBOOK_PROJECTION_INFLUENCE","STAKE_SIZING_ENABLED",
    "_duplicate_payload_bytes","_piece","build_compact_deep_evidence",
    "render_nfl_hub","render_nfl_passing_yards_hub",
]
