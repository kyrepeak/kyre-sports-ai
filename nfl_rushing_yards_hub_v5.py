"""NFL Rushing Yards V5 — Page Build Step 2 compact summary metrics.

Visual-only additive wrapper over certified Page Build Step 1 V4. V5 keeps the
V4 compact player card intact and appends a small at-a-glance metric strip
beneath each card using only already-certified projection and market outputs.

Permanent safety:
- V4/V3/V2/V1 runtime owners remain unchanged;
- exact ESPN event/team/athlete identity remains owned by prior certified layers;
- no fuzzy matching or synthetic IDs;
- no projection math, probability, EV, grading, ranking, recommendation,
  staking, or wagering behavior is introduced here;
- sportsbook projection influence remains exactly 0.0%.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any

import streamlit as st

import nfl_rushing_yards_hub_v4 as prior

MODEL_VERSION = "NFL RUSHING YARDS V5 • PAGE BUILD STEP 2 • COMPACT SUMMARY METRICS"
FROZEN_PRIOR = "nfl_rushing_yards_hub_v4"
PAGE_BUILD_STEP = 2
PAGE_BUILD_TOTAL = 6

_ORIGINAL_COMPACT_PLAYER_CARD_V4 = prior._compact_player_card

_SUMMARY_CSS = r'''
<style>
.krush5-player{min-width:0;display:flex;flex-direction:column;gap:6px}
.krush5-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px;padding:0 2px 2px}
.krush5-box{min-width:0;border:1px solid #203a2b;border-radius:9px;background:linear-gradient(180deg,#0a1711 0%,#08120e 100%);padding:6px 7px}
.krush5-box b{display:block;color:#edf7f0;font-size:.67rem;line-height:1.05;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.krush5-box span{display:block;color:#657b6d;font-size:.38rem;font-weight:900;letter-spacing:.035em;text-transform:uppercase;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.krush5-box.market{border-color:#2a4a36}.krush5-box.market b{color:#9addb1}
.krush5-box.off{border-color:#514b31}.krush5-box.off b{color:#d9c273}
@media(max-width:760px){.krush5-summary{grid-template-columns:repeat(2,minmax(0,1fr));gap:5px}.krush5-box{padding:6px 7px}}
</style>
'''


def _number(value: Any) -> float:
    try:
        out = float(value)
        return out if math.isfinite(out) else math.nan
    except Exception:
        return math.nan


def _fmt(value: Any, digits: int = 1) -> str:
    number = _number(value)
    if not math.isfinite(number):
        return "—"
    text = f"{number:.{digits}f}"
    return text.rstrip("0").rstrip(".") if digits else text


def _signed(value: Any) -> str:
    number = _number(value)
    return f"{number:+.1f}" if math.isfinite(number) else "—"


def _freshness_text(market_row: dict[str, Any]) -> str:
    if not market_row.get("ready"):
        return "—"
    age = _number(market_row.get("age_seconds"))
    if not math.isfinite(age):
        return "LIVE"
    age = max(age, 0.0)
    if age < 60:
        return f"{age:.0f}s"
    return f"{age / 60.0:.1f}m"


def _summary_metrics_html(
    projection_row: dict[str, Any],
    market_row: dict[str, Any],
) -> str:
    """Render six display-only boxes from certified projection/market outputs."""
    projection = _number(projection_row.get("projection_yards"))
    market_live = bool(market_row.get("ready"))
    line = _number(market_row.get("line")) if market_live else math.nan
    gap = projection - line if math.isfinite(projection) and math.isfinite(line) else math.nan
    freshness = _freshness_text(market_row)
    market_class = "market" if market_live else "off"

    boxes = (
        ("Projection", _fmt(projection, 1), ""),
        ("Live Line", _fmt(line, 1), market_class),
        ("Proj − Line", _signed(gap), ""),
        ("Exp Carries", _fmt(projection_row.get("expected_carries"), 1), ""),
        ("Exp YPC", _fmt(projection_row.get("expected_yards_per_carry"), 2), ""),
        ("Market Age", freshness, market_class),
    )
    return (
        '<div class="krush5-summary" aria-label="Rushing yards summary metrics">'
        + "".join(
            f'<div class="krush5-box{(" " + css_class) if css_class else ""}"><b>{escape(value)}</b><span>{escape(label)}</span></div>'
            for label, value, css_class in boxes
        )
        + "</div>"
    )


def _compact_player_card_v5(
    projection_row: dict[str, Any],
    team: dict[str, Any],
    opponent: dict[str, Any],
    market_row: dict[str, Any],
) -> str:
    """Keep the certified V4 card byte-for-byte via delegation, then add Step 2."""
    card = _ORIGINAL_COMPACT_PLAYER_CARD_V4(projection_row, team, opponent, market_row)
    summary = _summary_metrics_html(projection_row, market_row)
    return f'<div class="krush5-player">{card}{summary}</div>'


def render_nfl_rushing_yards_hub() -> None:
    """Render V4 unchanged except for the additive Step 2 summary strip."""
    st.markdown(_SUMMARY_CSS, unsafe_allow_html=True)
    original_card = prior._compact_player_card
    prior._compact_player_card = _compact_player_card_v5
    try:
        return prior.render_nfl_rushing_yards_hub()
    finally:
        prior._compact_player_card = original_card


def render_nfl_hub(market: str = "Rushing Yards") -> None:
    if str(market or "Rushing Yards") != "Rushing Yards":
        raise ValueError("NFL Rushing Yards V5 only renders the Rushing Yards market.")
    return render_nfl_rushing_yards_hub()


__all__ = [
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "PAGE_BUILD_STEP",
    "PAGE_BUILD_TOTAL",
    "_compact_player_card_v5",
    "_freshness_text",
    "_summary_metrics_html",
    "render_nfl_hub",
    "render_nfl_rushing_yards_hub",
]
