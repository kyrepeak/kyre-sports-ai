"""NBA PRA Page 2 role-runtime V4 — additive verified-minutes fallback.

This successor leaves the frozen V3 command-center byte-identical. It patches
only the shared Page-2 role/availability presentation helper at application
bootstrap. Verified USG% remains preferred; when it is temporarily unavailable,
verified recent game minutes can establish rotation role without fabricating a
usage percentage. No provider I/O or model/projection math is introduced.
"""
from __future__ import annotations

from html import escape
from statistics import mean
from typing import Any, Mapping

import nba_pra_page2_command_center_v1 as _v1
import nba_pra_page2_command_center_v3 as _v3
from nba_pra_page2_history_only_runtime_v1 import install as install_history_only_navigation


VERSION = "API2_NBA_PRA_PAGE2_ROLE_RUNTIME_V4"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out else None


def _role_availability_html(context: Mapping[str, Any], games: list[dict[str, Any]]) -> str:
    """Preserve V3 unless a verified-minutes role fallback is actually needed."""
    html = _v3._role_availability_html(context, games)
    profile = context.get("player") if isinstance(context.get("player"), Mapping) else {}
    if _num(profile.get("usage_pct")) is not None:
        return html

    recent_minutes = [_num(row.get("minutes")) for row in games[:5]]
    recent_minutes = [value for value in recent_minutes if value is not None]
    if not recent_minutes:
        return html

    avg_minutes = mean(recent_minutes)
    role = _v3._role_label(profile, games)
    card = (
        '<article class="p2cc-context-card">'
        '<small>ROLE & USAGE</small>'
        f'<b>{avg_minutes:.1f} MIN</b>'
        f'<span>{escape(role)} • USG% PENDING</span>'
        '<em>Verified recent game minutes • role fallback</em>'
        '</article>'
    )
    grid = '<div class="p2cc-context-grid">'
    if grid in html:
        html = html.replace(grid, grid + card, 1)
    html = html.replace('<span>Usage / team role not currently verified</span>', '', 1)
    html = html.replace('<div class="p2cc-data-gaps"><b>DATA GAPS</b></div>', '', 1)
    return html


def install() -> None:
    """Install the additive presentation and navigation successors idempotently."""
    _v1._role_availability_html = _role_availability_html
    install_history_only_navigation()
