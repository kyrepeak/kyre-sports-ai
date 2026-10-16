"""MONSTER CFB Game Total Page 2 Step 8 — data quality + number formatting.

Presentation-only wrapper over the frozen selected-event Page-2 runtime. Missing
or unverified values are labeled explicitly and already-owned numeric values are
formatted for display. This module adds no provider/network calls and does not
recompute model, projection, probability, ranking, selection, or sportsbook
inputs.
"""
from __future__ import annotations

from contextlib import contextmanager
from html import escape
from math import isfinite
from threading import RLock
from typing import Any, Iterator

import cfb_game_total_page2_step8_final_runtime_v1 as frozen_runtime

MODEL_VERSION = "MONSTER CFB GAME TOTAL PAGE2 STEP8 • DATA QUALITY V1"
MARKET = frozen_runtime.MARKET
STEP8_MARKER = "MONSTER_CFB_GAME_TOTAL_PAGE2_STEP8_DATA_QUALITY_V1_ACTIVE"
FREEZE_TOKEN = "MONSTER_CFB_GAME_TOTAL_PAGE2_STEP8_DATA_QUALITY_V1_FROZEN"
MAY_MODIFY_PAGE1 = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MODEL = False
MAY_MODIFY_MARKET_OWNERSHIP = False
MAY_MODIFY_OTHER_SPORTS = False
NETWORK_CALLS_ADDED = 0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
GITHUB_ACTIONS_FALLBACK = 0

_BASE_HEADER = frozen_runtime.build_page2_header_html
_BASE_BODY = frozen_runtime.build_page2_body_html
_PATCH_LOCK = RLock()

DATA_QUALITY_CSS = r"""
<style>
.gtp2s11-quality{max-width:1180px;margin:-7px auto 18px;padding:9px 12px;border:1px solid rgba(91,192,255,.22);border-radius:12px;background:rgba(8,31,45,.72);color:#93b2c3;font-size:8px;font-weight:800;line-height:1.45;text-align:center}
.gtp2s11-quality strong{color:#77dcff;font-weight:1000}
@media(max-width:480px){.gtp2s11-quality{margin-top:-5px;padding:8px 9px;font-size:7px}}
</style>
"""


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def format_number(value: Any, *, decimals: int = 1, fallback: str = "Data unavailable") -> str:
    """Format an already-owned numeric value; never derive a replacement value."""
    number = _number(value)
    if number is None:
        text = str(value or "").strip()
        return escape(text) if text else fallback
    if decimals <= 0:
        return f"{number:.0f}"
    return f"{number:.{decimals}f}"


def format_percent(value: Any, *, fallback: str = "Data unavailable") -> str:
    number = _number(value)
    if number is None:
        text = str(value or "").strip()
        if not text or text in {"—", "-", "N/A", "n/a", "None", "nan"}:
            return fallback
        return escape(text)
    if 0.0 <= number <= 1.0:
        number *= 100.0
    return f"{number:.1f}%"


def format_driver(value: Any, kind: str) -> Any:
    """Format only known display units; preserve unknown strings verbatim."""
    if value in (None, ""):
        return None
    number = _number(value)
    if number is None:
        return value
    if kind == "explosive" and 0.0 <= number <= 1.0:
        return f"{number * 100.0:.1f}%"
    if kind == "red_zone":
        return format_percent(number)
    return f"{number:.1f}"


def _polish_missing_copy(html: str) -> str:
    """Replace ambiguous presentation placeholders only; never invent evidence."""
    polished = str(html or "")
    polished = polished.replace(">—</strong>", ">Data unavailable</strong>")
    polished = polished.replace("Favorable: —", "Favorable: Not verified")
    polished = polished.replace("No verified tough matchup • —", "No verified tough matchup • Evidence unavailable")
    polished = polished.replace("No verified favorable matchup • —", "No verified favorable matchup • Evidence unavailable")
    return polished


def build_data_quality_html() -> str:
    return (
        DATA_QUALITY_CSS
        + f'<div class="gtp2s11-quality" data-testid="gtp2s11-data-quality" '
        f'data-step8="{STEP8_MARKER}" data-no-estimation="true">'
        '<strong>Data quality:</strong> unavailable or unverified fields are labeled explicitly; '
        'display numbers use consistent units and precision. No missing value is estimated.'
        '</div>'
    )


@contextmanager
def _presentation_patch() -> Iterator[None]:
    """Temporarily polish the frozen snapshot builder, then restore it."""
    original_snapshot = frozen_runtime.step5.build_team_snapshot_key_drivers_html

    def snapshot_wrapper(**kwargs: Any) -> str:
        clean = dict(kwargs)
        for side in ("away", "home"):
            clean[f"{side}_pace"] = format_driver(clean.get(f"{side}_pace"), "pace")
            clean[f"{side}_explosive"] = format_driver(clean.get(f"{side}_explosive"), "explosive")
            clean[f"{side}_red_zone"] = format_driver(clean.get(f"{side}_red_zone"), "red_zone")
            clean[f"{side}_defense"] = format_driver(clean.get(f"{side}_defense"), "defense")
        return _polish_missing_copy(original_snapshot(**clean))

    frozen_runtime.step5.build_team_snapshot_key_drivers_html = snapshot_wrapper
    try:
        yield
    finally:
        frozen_runtime.step5.build_team_snapshot_key_drivers_html = original_snapshot


def build_page2_header_html(payload: Any) -> str:
    with _presentation_patch():
        return _polish_missing_copy(_BASE_HEADER(payload))


def build_page2_body_html(payload: Any) -> str:
    with _presentation_patch():
        html = _polish_missing_copy(_BASE_BODY(payload))
    marker = '<div class="gtp2s8-cert"'
    quality = build_data_quality_html()
    return html.replace(marker, quality + marker, 1) if marker in html else html + quality


def build_page2_final_html(payload: Any) -> str:
    return build_page2_header_html(payload) + build_page2_body_html(payload)


def render_step6_cert_surface() -> Any:
    return frozen_runtime.render_step6_cert_surface()


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    with _PATCH_LOCK:
        original_header = frozen_runtime.build_page2_header_html
        original_body = frozen_runtime.build_page2_body_html
        frozen_runtime.build_page2_header_html = build_page2_header_html
        frozen_runtime.build_page2_body_html = build_page2_body_html
        try:
            return frozen_runtime.render_game_total_hub(section_header, status_info, team_logo, h)
        finally:
            frozen_runtime.build_page2_header_html = original_header
            frozen_runtime.build_page2_body_html = original_body


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"Page2 Step8 data-quality wrapper received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "DATA_QUALITY_CSS",
    "FREEZE_TOKEN",
    "GITHUB_ACTIONS_FALLBACK",
    "MARKET",
    "MAY_MODIFY_MARKET_OWNERSHIP",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PAGE1",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "NETWORK_CALLS_ADDED",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP8_MARKER",
    "build_data_quality_html",
    "build_page2_body_html",
    "build_page2_final_html",
    "build_page2_header_html",
    "format_driver",
    "format_number",
    "format_percent",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
