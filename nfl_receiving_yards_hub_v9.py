"""NFL Receiving Yards V9 — opponent matchup tiers with favorable-first sorting.

V9 is additive over certified V8. It changes only the visual full-lineup board:
each fresh exact-ID FanDuel Receiving Yards row receives a transparent opponent
pass-defense classification (FAVORABLE / MEDIUM / TOUGH), and cards are ordered
favorable first, then medium, then tough.

The classification uses only already-certified opponent pass-defense context:
receptions allowed/game, receiving yards allowed/game, yards/reception allowed,
and receiving TDs allowed/game. Optional target data is display context only and
is never required or inferred. Sportsbook lines/prices never enter the tier or
projection math. Exact ESPN IDs remain authoritative. This is matchup
classification only, not EV/value/recommendation grading. Sportsbook projection
influence stays exactly 0.0%.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any

import streamlit as st

import nfl_receiving_yards_hub_v8 as prior

MODEL_VERSION = "NFL RECEIVING YARDS V9 • PAGE BUILD STEP 9 • MATCHUP TIERS • FAVORABLE FIRST"
FROZEN_PRIOR = "nfl_receiving_yards_hub_v8"
FROZEN_PROJECTION_ENGINE = "nfl_receiving_yards_projection_v1"
PAGE_BUILD_STEP = 9
PAGE_BUILD_TOTAL = 10
DISPLAY_ONLY = True
MATCHUP_CLASSIFICATION_ONLY = True
BETTING_GRADE_ENABLED = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

_ORIGINAL_LINEUP_BOARD_V8 = prior._lineup_board_html
_ORIGINAL_ADVANCE_STEP8_COPY = prior._advance_step8_copy

# Transparent descriptive bands around normal NFL receiving-defense output.
# These are visual matchup bands only; they do not modify the frozen projection.
FAVORABLE_THRESHOLDS = {
    "receptions_allowed_per_game": 23.0,
    "receiving_yards_allowed_per_game": 240.0,
    "yards_per_reception_allowed": 11.0,
    "receiving_touchdowns_allowed_per_game": 1.5,
}
TOUGH_THRESHOLDS = {
    "receptions_allowed_per_game": 19.0,
    "receiving_yards_allowed_per_game": 195.0,
    "yards_per_reception_allowed": 9.5,
    "receiving_touchdowns_allowed_per_game": 0.9,
}
TIER_ORDER = {"FAVORABLE": 0, "MEDIUM": 1, "TOUGH": 2}

_STEP9_CSS = r'''
<style>
.krecv-progress .krecv-track .krecv-fill,.krecv-fill{width:90%!important}
.krecv9-wrap{border:1px solid #443b20;border-radius:17px;background:linear-gradient(145deg,#18150b 0%,#111008 100%);padding:11px 12px;margin:8px 0 12px}
.krecv9-head{display:flex;align-items:flex-end;justify-content:space-between;gap:10px;margin-bottom:8px}.krecv9-title{color:#f7e7aa;font-size:.83rem;font-weight:950;letter-spacing:.02em}.krecv9-sub{color:#9f936a;font-size:.49rem;font-weight:800;line-height:1.4;margin-top:2px}.krecv9-count{border:1px solid #71602d;border-radius:999px;background:#241e0d;color:#e2c85e;padding:3px 7px;font-size:.43rem;font-weight:950;white-space:nowrap}
.krecv9-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.krecv9-card{border:1px solid #4c4122;border-radius:12px;background:#121108;padding:8px 9px;min-width:0}.krecv9-card.favorable{border-color:#356c45;background:linear-gradient(145deg,#102017 0%,#111108 100%)}.krecv9-card.tough{border-color:#6c3e3e;background:linear-gradient(145deg,#211111 0%,#111008 100%)}
.krecv9-top{display:flex;justify-content:space-between;align-items:flex-start;gap:7px}.krecv9-name{color:#fff8dd;font-size:.70rem;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.krecv9-meta{color:#8f8667;font-size:.44rem;font-weight:800;margin-top:2px;line-height:1.35}.krecv9-badges{display:flex;gap:4px;align-items:center;justify-content:flex-end;flex-wrap:wrap}.krecv9-state,.krecv9-tier{border:1px solid #5a8a66;border-radius:999px;background:#102016;color:#91d4a0;padding:2px 5px;font-size:.37rem;font-weight:950;text-transform:uppercase;white-space:nowrap}.krecv9-state.market{border-color:#7d6830;background:#251f0d;color:#e0c35f}.krecv9-tier.favorable{border-color:#37814b;background:#0f2517;color:#82e09a}.krecv9-tier.medium{border-color:#8b742a;background:#271f0a;color:#e8cf65}.krecv9-tier.tough{border-color:#8b4141;background:#281010;color:#ef8a8a}
.krecv9-matchup{margin-top:6px;border-top:1px solid #39331d;padding-top:5px;color:#83795c;font-size:.40rem;line-height:1.35}.krecv9-matchup strong{color:#e6d07a}.krecv9-metrics{display:grid;grid-template-columns:1.15fr repeat(2,minmax(0,1fr));gap:5px;margin-top:7px}.krecv9-metric{border-top:1px solid #3c351e;padding-top:5px;min-width:0}.krecv9-metric b{display:block;color:#f7efd0;font-size:.70rem}.krecv9-metric span{display:block;color:#746c52;font-size:.38rem;font-weight:900;text-transform:uppercase;margin-top:2px}.krecv9-foot{border-top:1px solid #302b19;margin-top:6px;padding-top:5px;color:#756e56;font-size:.40rem;line-height:1.35}.krecv9-foot strong{color:#d6bf67}
@media(max-width:760px){.krecv9-head{align-items:flex-start;flex-direction:column}.krecv9-grid{grid-template-columns:1fr}.krecv9-metrics{grid-template-columns:1fr 1fr 1fr}.krecv9-top{gap:5px}.krecv9-badges{max-width:48%}}
</style>
'''


def _finite(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _verified_pass_defense(team: dict[str, Any], opponent: dict[str, Any]) -> dict[str, Any] | None:
    team_id = prior._safe(team.get("official_team_id"), "")
    opponent_id = prior._safe(team.get("opponent_official_team_id"), "")
    opponent_team_id = prior._safe(opponent.get("official_team_id"), "")
    if not team_id.isdigit() or not opponent_id.isdigit() or team_id == opponent_id:
        return None
    if opponent_team_id != opponent_id:
        return None
    defense = team.get("opponent_pass_defense")
    if not isinstance(defense, dict):
        return None
    if prior._safe(defense.get("official_team_id"), "") != opponent_id:
        return None
    return defense


def _matchup_tier(team: dict[str, Any], opponent: dict[str, Any]) -> dict[str, Any]:
    """Classify one exact opponent pass defense without touching projection math."""
    defense = _verified_pass_defense(team, opponent)
    if not defense:
        return {
            "tier": "MEDIUM",
            "score": 0,
            "favorable_signals": 0,
            "tough_signals": 0,
            "available": False,
            "reason": "insufficient verified opponent pass-defense context",
        }

    score = 0
    favorable = 0
    tough = 0
    for key in FAVORABLE_THRESHOLDS:
        value = _finite(defense.get(key))
        if value is None:
            return {
                "tier": "MEDIUM",
                "score": 0,
                "favorable_signals": 0,
                "tough_signals": 0,
                "available": False,
                "reason": "incomplete verified opponent pass-defense context",
            }
        if value >= FAVORABLE_THRESHOLDS[key]:
            score += 1
            favorable += 1
        elif value <= TOUGH_THRESHOLDS[key]:
            score -= 1
            tough += 1

    tier = "FAVORABLE" if score >= 2 else "TOUGH" if score <= -2 else "MEDIUM"
    return {
        "tier": tier,
        "score": score,
        "favorable_signals": favorable,
        "tough_signals": tough,
        "available": True,
        "reason": "verified opponent pass-defense classification",
    }


def _classified_prop_rows(context: dict[str, Any], event_market: dict[str, Any]) -> list[dict[str, Any]]:
    teams = prior._team_map(context)
    projected_ids = prior._projected_athlete_ids(context)
    rows: list[dict[str, Any]] = []
    for raw in event_market.get("props") or []:
        if not isinstance(raw, dict):
            continue
        athlete_id = prior._safe(raw.get("official_athlete_id"), "")
        team_id = prior._safe(raw.get("official_team_id"), "")
        if not athlete_id.isdigit() or not team_id.isdigit():
            continue
        team = teams.get(team_id)
        if not isinstance(team, dict):
            continue
        opponent_id = prior._safe(team.get("opponent_official_team_id"), "")
        opponent = teams.get(opponent_id)
        if not opponent_id.isdigit() or not isinstance(opponent, dict):
            grade = {
                "tier": "MEDIUM",
                "score": 0,
                "favorable_signals": 0,
                "tough_signals": 0,
                "available": False,
                "reason": "opponent identity unavailable",
            }
            opponent = {}
        else:
            grade = _matchup_tier(team, opponent)
        rows.append(
            {
                "market": raw,
                "team": team,
                "opponent": opponent,
                "grade": grade,
                "has_projection": athlete_id in projected_ids,
            }
        )

    # ESPN IDs remain authoritative. Player names are never used as matching keys.
    rows.sort(
        key=lambda item: (
            TIER_ORDER.get(str(item["grade"].get("tier")), 1),
            prior._safe(item["market"].get("official_team_id"), ""),
            prior._safe(item["market"].get("official_athlete_id"), ""),
        )
    )
    return rows


def _lineup_board_html_v9(context: dict[str, Any], event_market: dict[str, Any]) -> str:
    if not isinstance(event_market, dict):
        return ""
    if event_market.get("ready") is not True or event_market.get("market_available") is not True:
        return ""

    rows = _classified_prop_rows(context, event_market)
    if not rows:
        return ""

    cards: list[str] = []
    tier_counts = {"FAVORABLE": 0, "MEDIUM": 0, "TOUGH": 0}
    for item in rows:
        row = item["market"]
        team = item["team"]
        opponent = item["opponent"]
        grade = item["grade"]
        athlete_id = prior._safe(row.get("official_athlete_id"), "")
        team_id = prior._safe(row.get("official_team_id"), "")
        team_abbr = prior._safe(team.get("team_abbreviation"), f"ESPN {team_id}").upper()
        opponent_abbr = prior._safe(opponent.get("team_abbreviation"), "OPP").upper()
        player_name = prior._safe(row.get("player_name"), "Verified receiver")
        position = prior._safe(row.get("position"), "REC")
        has_projection = bool(item["has_projection"])
        state_class = "" if has_projection else " market"
        state_text = "PROJECTION AVAILABLE" if has_projection else f"MARKET ONLY • {prior.NO_PROJECTION_LABEL}"
        tier = str(grade.get("tier") or "MEDIUM").upper()
        if tier not in tier_counts:
            tier = "MEDIUM"
        tier_counts[tier] += 1
        tier_class = tier.lower()
        score = int(grade.get("score") or 0)
        signal_text = (
            f'{int(grade.get("favorable_signals") or 0)} favorable / {int(grade.get("tough_signals") or 0)} tough signals'
            if grade.get("available") is True
            else prior._safe(grade.get("reason"), "verified context unavailable")
        )
        cards.append(
            f'<article class="krecv8-card krecv9-card {escape(tier_class)}" data-matchup-tier="{escape(tier)}" data-matchup-score="{score:+d}">'
            '<div class="krecv9-top"><div>'
            f'<div class="krecv9-name">{escape(player_name)}</div>'
            f'<div class="krecv9-meta">{escape(position)} • {escape(team_abbr)} • ESPN athlete {escape(athlete_id)}</div>'
            '</div><div class="krecv9-badges">'
            f'<span class="krecv9-tier {escape(tier_class)}">{escape(tier)}</span>'
            f'<span class="krecv9-state{state_class}">{escape(state_text)}</span>'
            '</div></div>'
            f'<div class="krecv9-matchup">vs <strong>{escape(opponent_abbr)}</strong> • matchup score <strong>{score:+d}</strong> • {escape(signal_text)}</div>'
            '<div class="krecv9-metrics">'
            f'<div class="krecv9-metric"><b>{escape(prior._line(row.get("line")))}</b><span>FanDuel Rec Yds</span></div>'
            f'<div class="krecv9-metric"><b>{escape(prior._american(row.get("over_odds")))}</b><span>Over</span></div>'
            f'<div class="krecv9-metric"><b>{escape(prior._american(row.get("under_odds")))}</b><span>Under</span></div>'
            '</div>'
            '<div class="krecv9-foot">'
            f'Exact ESPN team <strong>{escape(team_id)}</strong> • matchup classification only • projection influence <strong>0.0%</strong>'
            '</div></article>'
        )

    age = prior._number(event_market.get("age_seconds"))
    age_text = f"{max(age, 0.0):.0f}s old" if math.isfinite(age) else "freshness verified"
    count_label = "LIVE PROP" if len(cards) == 1 else "LIVE PROPS"
    summary = (
        f'{tier_counts["FAVORABLE"]} favorable • '
        f'{tier_counts["MEDIUM"]} medium • '
        f'{tier_counts["TOUGH"]} tough'
    )
    return (
        '<section class="krecv9-wrap" aria-label="Full FanDuel Receiving Yards lineup with matchup tiers">'
        '<div class="krecv9-head"><div>'
        '<div class="krecv9-title">🎯 FanDuel Receiving Yards • Matchup Tiers</div>'
        f'<div class="krecv9-sub">Favorable First • FAVORABLE → MEDIUM → TOUGH • {escape(summary)} • {escape(age_text)} • tiers use verified opponent pass-defense context only.</div>'
        '</div>'
        f'<span class="krecv9-count">{len(cards)} {count_label}</span></div>'
        f'<div class="krecv9-grid">{"".join(cards)}</div>'
        '</section>'
    )


def _advance_step9_copy(body: Any) -> Any:
    out = _ORIGINAL_ADVANCE_STEP8_COPY(body)
    if not isinstance(out, str):
        return out
    replacements = (
        (
            "Step 8 adds the fresh exact-ID FanDuel Receiving Yards full lineup as visual market context only. Market-only athletes are labeled NO PROJECTION and sportsbook influence on the frozen projection remains 0.0%.",
            "Step 9 adds transparent FAVORABLE / MEDIUM / TOUGH opponent pass-defense tiers and favorable-first sorting. Tiers are descriptive matchup classification only and never use FanDuel line or price.",
        ),
        (
            '<span class="krecv-chip">✅ FANDUEL FULL LINEUP</span>',
            '<span class="krecv-chip">✅ FANDUEL FULL LINEUP</span><span class="krecv-chip">✅ MATCHUP TIERS</span>',
        ),
        ("STEP 8 OF 10 • FANDUEL FULL LINEUP LIVE", "STEP 9 OF 10 • MATCHUP TIERS LIVE"),
    )
    for old, new in replacements:
        out = out.replace(old, new)
    return out


def render_nfl_receiving_yards_hub() -> None:
    st.markdown(_STEP9_CSS, unsafe_allow_html=True)
    original_board = prior._lineup_board_html
    original_advance = prior._advance_step8_copy
    prior._lineup_board_html = _lineup_board_html_v9
    prior._advance_step8_copy = _advance_step9_copy
    try:
        return prior.render_nfl_receiving_yards_hub()
    finally:
        prior._lineup_board_html = original_board
        prior._advance_step8_copy = original_advance


def render_nfl_hub(market: str = "Receiving Yards") -> None:
    if str(market or "Receiving Yards") != "Receiving Yards":
        raise ValueError("NFL Receiving Yards V9 only renders the Receiving Yards market.")
    return render_nfl_receiving_yards_hub()


__all__ = [
    "BETTING_GRADE_ENABLED",
    "DISPLAY_ONLY",
    "FAVORABLE_THRESHOLDS",
    "FROZEN_PRIOR",
    "FROZEN_PROJECTION_ENGINE",
    "MATCHUP_CLASSIFICATION_ONLY",
    "MODEL_VERSION",
    "PAGE_BUILD_STEP",
    "PAGE_BUILD_TOTAL",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "TIER_ORDER",
    "TOUGH_THRESHOLDS",
    "_advance_step9_copy",
    "_classified_prop_rows",
    "_finite",
    "_lineup_board_html_v9",
    "_matchup_tier",
    "_verified_pass_defense",
    "render_nfl_hub",
    "render_nfl_receiving_yards_hub",
]
