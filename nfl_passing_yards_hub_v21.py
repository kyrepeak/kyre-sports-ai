"""NFL Passing Yards V21 — exact-ID team-logo presentation overlay.

Visual-only wrapper over certified V20. V21 does not change projection math,
probabilities, fair odds, no-vig math, EV, grading, market semantics, or the
Kyre Sports API bridge. It captures the same already-verified ESPN matchup/QB
identity used by V20 and decorates Step 10 Market Evaluation card headers with
the quarterback team's ESPN logo.

Identity rules remain strict:
- exact verified ESPN team context only;
- exact verified ESPN QB athlete ID must also be present for the slot;
- card linkage uses the certified away/home index order already used by V20;
- no fuzzy matching;
- no player-name identity authority;
- no synthetic IDs;
- missing/invalid visual identity fails soft and renders the original V20 card.

Sportsbook projection influence remains 0.0%. Stake sizing remains OFF.
"""
from __future__ import annotations

from html import escape
import re
from typing import Any

import streamlit as st

import nfl_passing_yards_hub_v11 as step10_ui
import nfl_passing_yards_hub_v20 as prior
import nfl_passing_yards_hub_v8 as step7_ui

MODEL_VERSION = "NFL PASSING YARDS V21 • EXACT ESPN TEAM LOGOS • V20 FROZEN"
FROZEN_PRIOR = "nfl_passing_yards_hub_v20"

_VISUAL_CSS = r"""
<style>
.kpy21-team-logo-slot{width:38px;height:38px;flex:0 0 38px;border:1px solid #28475d;background:#071722;border-radius:11px;display:flex;align-items:center;justify-content:center;padding:4px;box-sizing:border-box;margin-top:1px}
.kpy21-team-logo{width:100%;height:100%;object-fit:contain;display:block}
.kpy10-top>.kpy21-team-logo-slot+div{flex:1;min-width:0}
@media(max-width:820px){.kpy21-team-logo-slot{width:34px;height:34px;flex-basis:34px}}
</style>
"""

_TEAM_ABBR_RE = re.compile(r"^[A-Z]{2,4}$")
_CARD_TOP = '<div class="kpy10-top">'


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _exact_team_visuals(identity_result: dict) -> list[dict]:
    """Return away/home visual slots only when exact ESPN identity is verified."""
    out: list[dict] = []
    for side in ("away", "home"):
        ctx = (identity_result or {}).get(side) or {}
        qb = ctx.get("qb1") or {}
        team_id = _safe(ctx.get("team_id"))
        athlete_id = _safe(qb.get("athlete_id"))
        abbr = _safe(ctx.get("abbr")).upper()
        verified = bool(
            ctx.get("identity_verified")
            and team_id.isdigit()
            and athlete_id.isdigit()
            and _TEAM_ABBR_RE.fullmatch(abbr)
        )
        out.append({
            "ready": verified,
            "side": side,
            "team_id": team_id if verified else "",
            "team_abbr": abbr if verified else "",
            "team_name": _safe(ctx.get("team"), abbr) if verified else "",
            "athlete_id": athlete_id if verified else "",
        })
    return out


def _team_logo_url(visual: dict) -> str:
    """Build ESPN CDN logo URL only from an already-verified ESPN abbreviation."""
    if not (visual or {}).get("ready"):
        return ""
    abbr = _safe((visual or {}).get("team_abbr")).upper()
    if _TEAM_ABBR_RE.fullmatch(abbr) is None:
        return ""
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{abbr.lower()}.png"


def _inject_team_logo(card_html: str, visual: dict) -> str:
    """Decorate the frozen V11 card HTML; return it unchanged on any visual miss."""
    logo_url = _team_logo_url(visual)
    if not logo_url or _CARD_TOP not in card_html:
        return card_html
    team_name = escape(_safe((visual or {}).get("team_name"), (visual or {}).get("team_abbr") or "NFL team"), quote=True)
    team_abbr = escape(_safe((visual or {}).get("team_abbr"), "NFL"), quote=True)
    slot = (
        f'<div class="kpy21-team-logo-slot" title="{team_name}">'
        f'<img class="kpy21-team-logo" src="{logo_url}" alt="{team_abbr} logo" '
        'loading="lazy" decoding="async" onerror="this.parentElement.style.display=\'none\'">'
        '</div>'
    )
    return card_html.replace(_CARD_TOP, _CARD_TOP + slot, 1)


def render_nfl_passing_yards_hub() -> None:
    st.markdown(_VISUAL_CSS, unsafe_allow_html=True)

    visuals: list[dict] = []
    card_index = 0

    original_identity_builder = step7_ui.identity.resolve_matchup_identity
    original_market_card = step10_ui._market_card

    def capture_identity(*args, **kwargs):
        result = original_identity_builder(*args, **kwargs)
        visuals[:] = _exact_team_visuals(result or {})
        return result

    def market_card_with_team_logo(row: dict) -> str:
        nonlocal card_index
        html = original_market_card(row)
        idx = card_index
        card_index += 1
        visual = visuals[idx] if 0 <= idx < len(visuals) else {}
        return _inject_team_logo(html, visual)

    # V20 will wrap the identity function again for its exact-ID market bridge.
    # That nested call preserves the same away/home order, so this visual layer
    # reuses the certified index linkage without introducing name matching.
    step7_ui.identity.resolve_matchup_identity = capture_identity
    step10_ui._market_card = market_card_with_team_logo
    try:
        prior.render_nfl_passing_yards_hub()
    finally:
        step7_ui.identity.resolve_matchup_identity = original_identity_builder
        step10_ui._market_card = original_market_card

    st.caption(
        f"{MODEL_VERSION} • visual-only team logos from exact verified ESPN identity • V20 market/model protections preserved • sportsbook projection influence = 0.0% • stake sizing OFF"
    )


__all__ = [
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "_exact_team_visuals",
    "_inject_team_logo",
    "_team_logo_url",
    "render_nfl_passing_yards_hub",
]
