"""NFL Passing Yards V22 — exact-ID quarterback headshot presentation overlay.

Visual-only wrapper over certified V21. V22 does not change projection math,
probabilities, fair odds, no-vig math, EV, grading, market semantics, team-logo
identity, or the Kyre Sports API bridge. It captures the same already-verified
ESPN matchup/QB identity and decorates Step 10 Market Evaluation card headers
with the quarterback's ESPN headshot.

Identity rules remain strict:
- exact verified ESPN QB athlete ID only;
- exact verified ESPN team context must also be present for the slot;
- card linkage uses the certified away/home index order already used by V20/V21;
- player names are display text only and never identity authority;
- no fuzzy matching;
- no synthetic IDs;
- missing/invalid headshots fail soft and preserve the certified V21 card.

Sportsbook projection influence remains 0.0%. Stake sizing remains OFF.
"""
from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st

import nfl_passing_yards_hub_v11 as step10_ui
import nfl_passing_yards_hub_v21 as prior
import nfl_passing_yards_hub_v8 as step7_ui

MODEL_VERSION = "NFL PASSING YARDS V22 • EXACT ESPN QB HEADSHOTS • V21/V20 FROZEN"
FROZEN_PRIOR = "nfl_passing_yards_hub_v21"

_VISUAL_CSS = r"""
<style>
.kpy22-player-headshot-slot{width:46px;height:46px;flex:0 0 46px;border:1px solid #31516a;background:linear-gradient(180deg,#0b1c2a,#06111b);border-radius:50%;display:flex;align-items:flex-end;justify-content:center;overflow:hidden;box-sizing:border-box;margin-top:-3px}
.kpy22-player-headshot{width:100%;height:100%;object-fit:cover;object-position:center top;display:block}
.kpy10-top>.kpy22-player-headshot-slot+div{flex:1;min-width:0}
@media(max-width:820px){.kpy22-player-headshot-slot{width:42px;height:42px;flex-basis:42px}}
</style>
"""

_CARD_TOP = '<div class="kpy10-top">'


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _exact_player_visuals(identity_result: dict) -> list[dict]:
    """Return away/home QB visual slots only from exact verified ESPN identity."""
    out: list[dict] = []
    for side in ("away", "home"):
        ctx = (identity_result or {}).get(side) or {}
        qb = ctx.get("qb1") or {}
        athlete_id = _safe(qb.get("athlete_id"))
        team_id = _safe(ctx.get("team_id"))
        verified = bool(
            ctx.get("identity_verified")
            and athlete_id.isdigit()
            and team_id.isdigit()
        )
        out.append({
            "ready": verified,
            "side": side,
            "athlete_id": athlete_id if verified else "",
            "player_name": _safe(qb.get("name"), "Quarterback") if verified else "",
            "team_id": team_id if verified else "",
            "team_abbr": _safe(ctx.get("abbr")).upper() if verified else "",
        })
    return out


def _player_headshot_url(visual: dict) -> str:
    """Build ESPN CDN player headshot URL only from an exact verified athlete ID."""
    if not (visual or {}).get("ready"):
        return ""
    athlete_id = _safe((visual or {}).get("athlete_id"))
    if not athlete_id.isdigit():
        return ""
    return f"https://a.espncdn.com/i/headshots/nfl/players/full/{athlete_id}.png"


def _inject_player_headshot(card_html: str, visual: dict) -> str:
    """Decorate frozen card HTML; return it unchanged on any visual miss."""
    headshot_url = _player_headshot_url(visual)
    if not headshot_url or _CARD_TOP not in card_html:
        return card_html
    player_name = escape(_safe((visual or {}).get("player_name"), "Quarterback"), quote=True)
    athlete_id = escape(_safe((visual or {}).get("athlete_id")), quote=True)
    slot = (
        f'<div class="kpy22-player-headshot-slot" title="{player_name} • ESPN athlete {athlete_id}">'
        f'<img class="kpy22-player-headshot" src="{headshot_url}" alt="{player_name} headshot" '
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
        visuals[:] = _exact_player_visuals(result or {})
        return result

    def market_card_with_player_headshot(row: dict) -> str:
        nonlocal card_index
        html = original_market_card(row)
        idx = card_index
        card_index += 1
        visual = visuals[idx] if 0 <= idx < len(visuals) else {}
        return _inject_player_headshot(html, visual)

    # V21 nests another exact-identity capture for team logos. Both wrappers use
    # the same certified away/home ordering and neither changes model/market data.
    step7_ui.identity.resolve_matchup_identity = capture_identity
    step10_ui._market_card = market_card_with_player_headshot
    try:
        prior.render_nfl_passing_yards_hub()
    finally:
        step7_ui.identity.resolve_matchup_identity = original_identity_builder
        step10_ui._market_card = original_market_card

    st.caption(
        f"{MODEL_VERSION} • visual-only QB headshots from exact verified ESPN athlete IDs • V21/V20 market/model protections preserved • sportsbook projection influence = 0.0% • stake sizing OFF"
    )


__all__ = [
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "_exact_player_visuals",
    "_inject_player_headshot",
    "_player_headshot_url",
    "render_nfl_passing_yards_hub",
]
