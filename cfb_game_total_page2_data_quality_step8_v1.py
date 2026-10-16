"""MONSTER CFB Game Total Page 2 Step 8 — presentation-only data quality.

Normalizes already-owned display values and exposes explicit quality states.
No provider call, model/projection/probability recompute, ranking change,
selection change, or sportsbook influence is permitted here.
"""
from __future__ import annotations

from html import escape
from math import isfinite
from typing import Any

STEP8_MARKER = "MONSTER_CFB_GAME_TOTAL_PAGE2_DATA_QUALITY_STEP8_V1_ACTIVE"
FREEZE_TOKEN = "MONSTER_CFB_GAME_TOTAL_PAGE2_DATA_QUALITY_STEP8_V1_FROZEN"
MAY_MODIFY_PAGE1 = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MODEL = False
MAY_MODIFY_MARKET_OWNERSHIP = False
MAY_MODIFY_OTHER_SPORTS = False
NETWORK_CALLS_ADDED = 0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
GITHUB_ACTIONS_FALLBACK = 0

QUALITY_STATES = ("VERIFIED", "PARTIAL", "UNAVAILABLE")

DATA_QUALITY_CSS = r"""
<style>
.gtp2s8-quality{max-width:1180px;margin:0 auto 18px;padding:10px 12px;border:1px solid rgba(91,192,255,.22);border-radius:13px;background:rgba(7,27,41,.82);color:#9db4c2}
.gtp2s8-quality-title{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:8px}.gtp2s8-quality-title strong{color:#ecf9ff;font-size:9px;font-weight:1000}.gtp2s8-quality-title span{color:#6fdcff;font-size:7px;font-weight:950;letter-spacing:.08em;text-transform:uppercase}
.gtp2s8-quality-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:6px}.gtp2s8-quality-item{padding:7px 8px;border:1px solid rgba(111,160,181,.16);border-radius:9px;background:rgba(4,18,28,.65)}.gtp2s8-quality-item span{display:block;color:#7895a6;font-size:6.5px;font-weight:900;text-transform:uppercase}.gtp2s8-quality-item strong{display:block;margin-top:3px;font-size:8px;font-weight:1000}.gtp2s8-quality-item[data-quality="VERIFIED"] strong{color:#79eabe}.gtp2s8-quality-item[data-quality="PARTIAL"] strong{color:#ffd27c}.gtp2s8-quality-item[data-quality="UNAVAILABLE"] strong{color:#f19aa5}
.gtp2s8-quality-note{margin-top:7px;color:#7895a6;font-size:7px;font-weight:750;line-height:1.35}
@media(max-width:760px){.gtp2s8-quality-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:480px){.gtp2s8-quality{padding:9px}.gtp2s8-quality-grid{grid-template-columns:1fr 1fr}.gtp2s8-quality-title{align-items:flex-start;flex-direction:column;gap:3px}}
</style>
"""


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def format_optional_number(value: Any) -> str | None:
    """Return one-decimal display text while preserving missing versus zero."""
    number = _number(value)
    return None if number is None else f"{number:.1f}"


def format_optional_percent(value: Any) -> str | None:
    """Return percentage text from an already-owned rate or percentage."""
    number = _number(value)
    if number is None:
        return None
    if 0.0 <= number <= 1.0:
        number *= 100.0
    return f"{number:.1f}%"


def display_number(value: Any, *, missing: str) -> str:
    formatted = format_optional_number(value)
    return formatted if formatted is not None else escape(str(missing))


def pair_quality(left: Any, right: Any) -> str:
    left_ok = _number(left) is not None
    right_ok = _number(right) is not None
    if left_ok and right_ok:
        return "VERIFIED"
    if left_ok or right_ok:
        return "PARTIAL"
    return "UNAVAILABLE"


def market_quality(line: Any, *, identity_verified: bool, projection_weight: Any) -> str:
    line_ok = _number(line) is not None
    weight = _number(projection_weight)
    if line_ok and identity_verified is True and weight == 0.0:
        return "VERIFIED"
    if line_ok:
        return "PARTIAL"
    return "UNAVAILABLE"


def trends_quality(*, recent_available: bool, splits_available: bool) -> str:
    if recent_available and splits_available:
        return "VERIFIED"
    if recent_available or splits_available:
        return "PARTIAL"
    return "UNAVAILABLE"


def market_unavailable_rationale(lean: Any) -> str:
    side = str(lean or "").strip().upper()
    if side == "OVER":
        return "Model favors Over, but verified market data is unavailable, so no official bet is issued."
    if side == "UNDER":
        return "Model favors Under, but verified market data is unavailable, so no official bet is issued."
    return "Verified market data is unavailable, so no official bet is issued."


def _quality_item(label: str, state: str) -> str:
    clean_state = state if state in QUALITY_STATES else "UNAVAILABLE"
    return (
        f'<div class="gtp2s8-quality-item" data-quality="{clean_state}">'
        f'<span>{escape(label)}</span><strong>{clean_state.title()}</strong></div>'
    )


def build_data_quality_strip_html(*, market: str, pace: str, explosives: str, red_zone: str, trends: str) -> str:
    rows = (
        _quality_item("Market", market),
        _quality_item("Pace", pace),
        _quality_item("Explosives", explosives),
        _quality_item("Red Zone", red_zone),
        _quality_item("Trends", trends),
    )
    return f"""
{DATA_QUALITY_CSS}
<section class="gtp2s8-quality" data-testid="gtp2s8-data-quality" data-step8="{STEP8_MARKER}">
  <div class="gtp2s8-quality-title"><strong>Data Quality</strong><span>No missing values estimated</span></div>
  <div class="gtp2s8-quality-grid">{''.join(rows)}</div>
  <div class="gtp2s8-quality-note">Verified = complete owned evidence • Partial = some owned evidence • Unavailable = no verified value displayed.</div>
</section>
"""


__all__ = [
    "DATA_QUALITY_CSS",
    "FREEZE_TOKEN",
    "GITHUB_ACTIONS_FALLBACK",
    "MAY_MODIFY_MARKET_OWNERSHIP",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PAGE1",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "NETWORK_CALLS_ADDED",
    "QUALITY_STATES",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP8_MARKER",
    "build_data_quality_strip_html",
    "display_number",
    "format_optional_number",
    "format_optional_percent",
    "market_quality",
    "market_unavailable_rationale",
    "pair_quality",
    "trends_quality",
]
