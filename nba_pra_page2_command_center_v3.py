'''NBA PRA Page 2 S-tier command center V3 — data-completeness successor.

Presentation successor only. It keeps V2 visual/model behavior while replacing
V1's lossy history selector and role/availability card with completeness-aware
versions. No provider I/O and no sportsbook-shaped projection logic.
'''
from __future__ import annotations

from html import escape
from statistics import mean
from typing import Any, Mapping

import nba_pra_page2_command_center_v1 as _v1
import nba_pra_page2_command_center_v2 as _v2
from nba_pra_page2_data_completeness_v1 import combined_verified_games


VERSION = "API2_NBA_PRA_PAGE2_S_TIER_COMMAND_CENTER_V3"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def _text(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out else None


def _role_label(profile: Mapping[str, Any], games: list[dict[str, Any]]) -> str:
    rank = profile.get("usage_rank")
    usage = _num(profile.get("usage_pct"))
    recent_minutes = [_num(row.get("minutes")) for row in games[:5]]
    recent_minutes = [value for value in recent_minutes if value is not None]
    avg_minutes = mean(recent_minutes) if recent_minutes else None
    if rank == 1:
        return "PRIMARY USAGE ROLE"
    if isinstance(rank, (int, float)) and int(rank) <= 3:
        return "HIGH-USAGE CORE ROLE"
    if usage is not None and usage >= 20.0:
        return "CORE SCORING ROLE"
    if avg_minutes is not None and avg_minutes >= 24.0:
        return "CORE ROTATION ROLE"
    if avg_minutes is not None:
        return "ROTATION ROLE"
    return "ROLE VERIFIED BY USAGE"


def _role_availability_html(context: Mapping[str, Any], games: list[dict[str, Any]]) -> str:
    profile = context.get("player") if isinstance(context.get("player"), Mapping) else {}
    team = _text(context.get("team"))
    opponent = _text(context.get("opponent")).upper()
    cards: list[str] = []
    gaps: list[str] = []

    usage = _num(profile.get("usage_pct"))
    if usage is not None:
        rank = profile.get("usage_rank")
        rank_text = f"#{int(rank)} ON {team}" if isinstance(rank, (int, float)) and team else "TEAM RANK NOT VERIFIED"
        period = _text(profile.get("usage_period")) or "Verified usage period"
        source = _text(profile.get("usage_source")) or "Verified usage source"
        role = _role_label(profile, games)
        cards.append(
            '<article class="p2cc-context-card">'
            '<small>ROLE & USAGE</small>'
            f'<b>{usage:.1f}%</b>'
            f'<span>{escape(rank_text)} • {escape(role)}</span>'
            f'<em>{escape(period)} • {escape(source)}</em>'
            '</article>'
        )
    else:
        gaps.append("Usage / team role not currently verified")

    status = _text(context.get("availability")).upper()
    verification = _text(context.get("availability_verification")).upper()
    if status and status not in _v1._UNVERIFIED:
        reason = _text(context.get("availability_reason"))
        source = _text(context.get("availability_source")) or "Verified availability source"
        detail = reason or ("Official report checked; player has no listed designation." if "NO OFFICIAL" in status else "Verified availability state")
        cards.append(
            '<article class="p2cc-context-card">'
            '<small>PLAYER AVAILABILITY</small>'
            f'<b>{escape(status)}</b>'
            f'<span>{escape(detail)}</span>'
            f'<em>{escape(source)}</em>'
            '</article>'
        )
    else:
        gaps.append("Player availability not currently verified")

    teammates = context.get("teammate_injuries") if isinstance(context.get("teammate_injuries"), list) else []
    if verification == "VERIFIED":
        if teammates:
            labels: list[str] = []
            for raw in teammates[:4]:
                if not isinstance(raw, Mapping):
                    continue
                name = _text(raw.get("player_name")) or "Teammate"
                flag = _text(raw.get("status")).upper() or "FLAGGED"
                labels.append(f"{name}: {flag}")
            extra = len(teammates) - len(labels)
            summary = " • ".join(labels) + (f" • +{extra} MORE" if extra > 0 else "")
            cards.append(
                '<article class="p2cc-context-card">'
                '<small>TEAMMATE AVAILABILITY</small>'
                f'<b>{len(teammates)} FLAGGED</b>'
                f'<span>{escape(summary)}</span>'
                '<em>NBA Official Injury Report</em>'
                '</article>'
            )
        else:
            cards.append(
                '<article class="p2cc-context-card">'
                '<small>TEAMMATE AVAILABILITY</small>'
                '<b>NO VERIFIED FLAGS</b>'
                '<span>No same-team injury designation was returned in the verified report.</span>'
                '<em>NBA Official Injury Report</em>'
                '</article>'
            )
    else:
        gaps.append("Teammate injury impact not currently verified")

    exact = [row for row in games if opponent and _text(row.get("opponent")).upper() == opponent]
    if exact:
        latest = exact[0]
        cards.append(
            '<article class="p2cc-context-card">'
            '<small>PRIOR MATCHUP</small>'
            f'<b>{len(exact)} VERIFIED GAME{"S" if len(exact) != 1 else ""}</b>'
            f'<span>Latest: {_v1._fmt(latest.get("pra"))} PRA vs {escape(opponent)}</span>'
            '<em>Exact opponent history only</em>'
            '</article>'
        )
    else:
        gaps.append("No verified prior matchup sample")

    if not games:
        gaps.append("Recent verified game history unavailable")
    gap_html = ''.join(f'<span>{escape(item)}</span>' for item in gaps)
    return (
        '<section class="p2cc-panel" data-ks-section="role">'
        '<div class="p2cc-section-kicker">ROLE & AVAILABILITY</div>'
        f'<div class="p2cc-context-grid">{"".join(cards)}</div>'
        + (f'<div class="p2cc-data-gaps"><b>DATA GAPS</b>{gap_html}</div>' if gaps else '')
        + '</section>'
    )


# V2 delegates these two helpers to V1 at render time. Patch the shared helper
# slots once at import so every Page-2 player uses the same completeness rules.
_v1._verified_games = combined_verified_games
_v1._role_availability_html = _role_availability_html

_css = _v2._css
build_page2_html = _v2.build_page2_html
