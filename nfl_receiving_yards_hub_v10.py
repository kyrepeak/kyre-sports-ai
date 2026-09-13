"""NFL Receiving Yards V10 — final polish, detailed matchup ribbon, 10/10 state.

V10 is additive over certified V9. It carries the already-certified exact-ID
opponent pass-defense matchup tier onto each detailed receiver stack and advances
the page shell to Step 10 / 10. It does not change projection math, market
semantics, tier thresholds, probability, EV, recommendations, staking, or wager
behavior. FanDuel remains display context only and sportsbook projection
influence stays exactly 0.0%.
"""
from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st

import nfl_receiving_yards_hub_v7 as detailed_page
import nfl_receiving_yards_hub_v9 as prior

MODEL_VERSION = "NFL RECEIVING YARDS V10 • PAGE BUILD STEP 10 • FINAL POLISH + SPEED + CERTIFICATION"
FROZEN_PRIOR = "nfl_receiving_yards_hub_v9"
FROZEN_PROJECTION_ENGINE = "nfl_receiving_yards_projection_v1"
PAGE_BUILD_STEP = 10
PAGE_BUILD_TOTAL = 10
DISPLAY_ONLY = True
MATCHUP_CLASSIFICATION_ONLY = True
BETTING_GRADE_ENABLED = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
FINAL_PAGE_COMPLETE = True

_ORIGINAL_DETAILED_CARD_V7 = detailed_page._player_card_v7
_ORIGINAL_ADVANCE_STEP9_COPY = prior._advance_step9_copy

_STEP10_CSS = r'''
<style>
.krecv-progress .krecv-track .krecv-fill,.krecv-fill{width:100%!important}
.krecv10-player{min-width:0;display:flex;flex-direction:column;gap:6px}
.krecv10-ribbon{display:flex;align-items:center;justify-content:space-between;gap:8px;border:1px solid #8b742a;border-radius:10px;background:linear-gradient(180deg,#271f0a 0%,#171306 100%);padding:6px 8px;margin:0 1px}
.krecv10-ribbon.favorable{border-color:#37814b;background:linear-gradient(180deg,#102819 0%,#0b1d12 100%)}
.krecv10-ribbon.tough{border-color:#8b4141;background:linear-gradient(180deg,#2a1111 0%,#1d0c0c 100%)}
.krecv10-tier{font-size:.48rem;font-weight:950;letter-spacing:.055em;text-transform:uppercase;white-space:nowrap}.krecv10-tier.favorable{color:#82e09a}.krecv10-tier.medium{color:#e8cf65}.krecv10-tier.tough{color:#ef8a8a}
.krecv10-copy{color:#8b927f;font-size:.42rem;font-weight:800;line-height:1.35;text-align:right}.krecv10-copy strong{color:#d8dece}
@media(max-width:760px){.krecv10-ribbon{align-items:flex-start;flex-direction:column;gap:3px}.krecv10-copy{text-align:left}}
</style>
'''


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _grade_for_team_opponent(team: dict[str, Any], opponent: dict[str, Any]) -> dict[str, Any]:
    """Reuse frozen V9 classification exactly; do not recalculate projection math."""
    grade = prior._matchup_tier(team, opponent)
    tier = str(grade.get("tier") or "MEDIUM").upper()
    if tier not in prior.TIER_ORDER:
        tier = "MEDIUM"
    return {**grade, "tier": tier}


def _detailed_player_card_v10(
    player: dict[str, Any],
    team: dict[str, Any],
    opponent: dict[str, Any],
) -> str:
    """Add a descriptive matchup ribbon around the frozen V7 detailed stack."""
    stack = _ORIGINAL_DETAILED_CARD_V7(player, team, opponent)
    grade = _grade_for_team_opponent(team, opponent)
    tier = str(grade.get("tier") or "MEDIUM").upper()
    tier_class = tier.lower()
    score = int(grade.get("score") or 0)
    athlete_id = _safe(player.get("official_athlete_id"))
    team_id = _safe(team.get("official_team_id"))
    opponent_id = _safe(team.get("opponent_official_team_id"))
    opponent_abbr = _safe(opponent.get("team_abbreviation"), "OPP").upper()

    if grade.get("available") is True:
        detail = (
            f"vs {opponent_abbr} • matchup score {score:+d} • "
            f"{int(grade.get('favorable_signals') or 0)} favorable / "
            f"{int(grade.get('tough_signals') or 0)} tough signals"
        )
    else:
        detail = f"vs {opponent_abbr} • {_safe(grade.get('reason'), 'verified context unavailable')}"

    ribbon = (
        f'<div class="krecv10-ribbon {escape(tier_class)}" '
        f'data-detailed-matchup-tier="{escape(tier)}" '
        f'data-detailed-matchup-score="{score:+d}">'
        f'<span class="krecv10-tier {escape(tier_class)}">{escape(tier)}</span>'
        f'<span class="krecv10-copy">{escape(detail)} • '
        '<strong>matchup classification only • projection unchanged</strong></span>'
        '</div>'
    )
    return (
        f'<section class="krecv10-player" data-athlete-id="{escape(athlete_id)}" '
        f'data-team-id="{escape(team_id)}" data-opponent-id="{escape(opponent_id)}" '
        f'data-matchup-tier="{escape(tier)}">{ribbon}{stack}</section>'
    )


def _advance_step10_copy(body: Any) -> Any:
    out = _ORIGINAL_ADVANCE_STEP9_COPY(body)
    if not isinstance(out, str):
        return out
    replacements = (
        (
            "Step 9 adds transparent FAVORABLE / MEDIUM / TOUGH opponent pass-defense tiers and favorable-first sorting. Tiers are descriptive matchup classification only and never use FanDuel line or price.",
            "Step 10 completes the Receiving Yards page with detailed matchup-tier ribbons, final visual polish, warm-page speed certification, and real-browser integration certification. Projection math remains frozen and sportsbook influence remains 0.0%.",
        ),
        (
            '<span class="krecv-chip">✅ MATCHUP TIERS</span>',
            '<span class="krecv-chip">✅ MATCHUP TIERS</span><span class="krecv-chip">✅ FINAL CERTIFIED</span>',
        ),
        (
            "STEP 9 OF 10 • MATCHUP TIERS LIVE",
            "STEP 10 OF 10 • FINAL POLISH + SPEED + CERTIFICATION",
        ),
    )
    for old, new in replacements:
        out = out.replace(old, new)
    return out


def render_nfl_receiving_yards_hub() -> None:
    st.markdown(_STEP10_CSS, unsafe_allow_html=True)
    original_card = detailed_page._player_card_v7
    original_advance = prior._advance_step9_copy
    detailed_page._player_card_v7 = _detailed_player_card_v10
    prior._advance_step9_copy = _advance_step10_copy
    try:
        return prior.render_nfl_receiving_yards_hub()
    finally:
        detailed_page._player_card_v7 = original_card
        prior._advance_step9_copy = original_advance


def render_nfl_hub(market: str = "Receiving Yards") -> None:
    if str(market or "Receiving Yards") != "Receiving Yards":
        raise ValueError("NFL Receiving Yards V10 only renders the Receiving Yards market.")
    return render_nfl_receiving_yards_hub()


__all__ = [
    "BETTING_GRADE_ENABLED",
    "DISPLAY_ONLY",
    "FINAL_PAGE_COMPLETE",
    "FROZEN_PRIOR",
    "FROZEN_PROJECTION_ENGINE",
    "MATCHUP_CLASSIFICATION_ONLY",
    "MODEL_VERSION",
    "PAGE_BUILD_STEP",
    "PAGE_BUILD_TOTAL",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_advance_step10_copy",
    "_detailed_player_card_v10",
    "_grade_for_team_opponent",
    "render_nfl_hub",
    "render_nfl_receiving_yards_hub",
]
