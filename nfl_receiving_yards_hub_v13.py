"""NFL Receiving Yards V13 — Matchup Tiers 2.0.

Additive presentation-only wrapper over frozen V12. It enriches the existing
V9 FAVORABLE / MEDIUM / TOUGH FanDuel matchup-tier cards with exact ESPN player
and team identity plus the already-certified market-blind receiving projection.
It does not change tier thresholds, projection math, sportsbook influence,
probability, EV, staking, or wager behavior.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any

import streamlit as st

import nfl_receiving_yards_hub_v9 as tier_page
import nfl_receiving_yards_hub_v12 as prior
import nfl_receiving_yards_projection_v1 as projection_engine
from nfl_receiving_yards_matchup_tiers_v2 import (
    headshot_url,
    projection_yards_for_athlete,
    team_logo_url,
)

MODEL_VERSION = "NFL RECEIVING YARDS V13 • MATCHUP TIERS 2.0 • IDENTITY + PROJECTION"
FROZEN_PRIOR = "nfl_receiving_yards_hub_v12"
FROZEN_MATCHUP_TIERS = "nfl_receiving_yards_hub_v9"
FROZEN_PROJECTION_ENGINE = "nfl_receiving_yards_projection_v1"
DISPLAY_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

_ORIGINAL_MATCHUP_BOARD_V9 = tier_page._lineup_board_html_v9

_STEP13_CSS = r'''
<style>
.krecv13-wrap{border:1px solid #3b4152;border-radius:18px;background:linear-gradient(145deg,#13151b,#101216);padding:12px;margin:8px 0 12px}
.krecv13-head{display:flex;align-items:flex-end;justify-content:space-between;gap:10px;margin-bottom:9px}.krecv13-title{color:#f5f7fb;font-size:.88rem;font-weight:950}.krecv13-sub{color:#8f98aa;font-size:.49rem;font-weight:800;line-height:1.45;margin-top:3px}.krecv13-count{border:1px solid #6254a2;background:#1b1730;color:#c8b8ff;border-radius:999px;padding:3px 7px;font-size:.42rem;font-weight:950;white-space:nowrap}
.krecv13-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.krecv13-card{border:1px solid #3d4654;border-radius:14px;background:#11151a;padding:9px;min-width:0}.krecv13-card.favorable{border-color:#3d7950;background:linear-gradient(145deg,#102119,#11151a)}.krecv13-card.medium{border-color:#806f35;background:linear-gradient(145deg,#211d10,#11151a)}.krecv13-card.tough{border-color:#844747;background:linear-gradient(145deg,#241313,#11151a)}
.krecv13-top{display:grid;grid-template-columns:48px minmax(0,1fr) 34px;gap:8px;align-items:center}.krecv13-face{width:48px;height:48px;border-radius:50%;object-fit:cover;border:1px solid #566275;background:#1a1f28}.krecv13-teamlogo{width:32px;height:32px;object-fit:contain}.krecv13-name{color:#f7f9fc;font-size:.72rem;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.krecv13-meta{color:#929cac;font-size:.43rem;font-weight:800;margin-top:2px;line-height:1.35}.krecv13-team{color:#bdc7d7;font-size:.42rem;font-weight:900;margin-top:2px}
.krecv13-badges{display:flex;gap:4px;flex-wrap:wrap;margin-top:6px}.krecv13-tier,.krecv13-state{border-radius:999px;padding:2px 6px;font-size:.37rem;font-weight:950;text-transform:uppercase}.krecv13-tier.favorable{border:1px solid #3d8751;background:#102719;color:#86e09d}.krecv13-tier.medium{border:1px solid #8a7432;background:#2a220d;color:#ead16a}.krecv13-tier.tough{border:1px solid #8a4545;background:#2b1111;color:#f09292}.krecv13-state{border:1px solid #6254a2;background:#1b1730;color:#c9baff}.krecv13-state.market{border-color:#846a32;background:#281f0c;color:#e2c66b}
.krecv13-matchup{border-top:1px solid #303846;margin-top:7px;padding-top:6px;color:#8e98a8;font-size:.40rem;line-height:1.4}.krecv13-matchup strong{color:#d6deeb}.krecv13-metrics{display:grid;grid-template-columns:1.15fr 1fr .8fr .8fr;gap:5px;margin-top:7px}.krecv13-metric{border:1px solid #28313d;border-radius:8px;padding:6px;min-width:0}.krecv13-metric.proj{border-color:#5b4b97;background:#171429}.krecv13-metric b{display:block;color:#f3f6fb;font-size:.67rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.krecv13-metric span{display:block;color:#788394;font-size:.34rem;font-weight:900;text-transform:uppercase;margin-top:2px}.krecv13-foot{border-top:1px solid #29313c;margin-top:7px;padding-top:5px;color:#778291;font-size:.39rem;line-height:1.4}.krecv13-foot strong{color:#c6cfdd}
@media(max-width:760px){.krecv13-grid{grid-template-columns:1fr}.krecv13-head{align-items:flex-start;flex-direction:column}.krecv13-metrics{grid-template-columns:1fr 1fr}.krecv13-top{grid-template-columns:44px minmax(0,1fr) 30px}.krecv13-face{width:44px;height:44px}.krecv13-teamlogo{width:28px;height:28px}}
</style>
'''


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _yards(value: Any) -> str:
    number = _finite(value)
    return f"{number:.1f}" if number is not None else "—"


def _line(value: Any) -> str:
    number = _finite(value)
    if number is None:
        return "—"
    return f"{number:.1f}".rstrip("0").rstrip(".")


def _american(value: Any) -> str:
    number = _finite(value)
    return f"{number:+.0f}" if number is not None else "—"


def _image(url: str, css_class: str, alt: str) -> str:
    if not url:
        return f'<span class="{escape(css_class)}" aria-hidden="true"></span>'
    return f'<img class="{escape(css_class)}" src="{escape(url, quote=True)}" alt="{escape(alt, quote=True)}">'


def _lineup_board_html_v13(context: dict[str, Any], event_market: dict[str, Any]) -> str:
    """Enrich frozen V9 classifications with exact-ID identity and projection display."""
    if not isinstance(event_market, dict):
        return ""
    if event_market.get("ready") is not True or event_market.get("market_available") is not True:
        return ""

    rows = tier_page._classified_prop_rows(context, event_market)
    if not rows:
        return ""

    cards: list[str] = []
    tier_counts = {"FAVORABLE": 0, "MEDIUM": 0, "TOUGH": 0}
    for item in rows:
        row = item.get("market") or {}
        team = item.get("team") or {}
        opponent = item.get("opponent") or {}
        grade = item.get("grade") or {}

        athlete_id = _safe(row.get("official_athlete_id"))
        team_id = _safe(row.get("official_team_id"))
        if not athlete_id.isdigit() or not team_id.isdigit():
            continue

        player_name = _safe(row.get("player_name"), "Verified receiver")
        position = _safe(row.get("position"), "REC")
        team_abbr = _safe(team.get("team_abbreviation"), f"ESPN {team_id}").upper()
        team_name = _safe(
            team.get("team_name"),
            _safe(team.get("display_name"), team_abbr),
        )
        opponent_abbr = _safe(opponent.get("team_abbreviation"), "OPP").upper()

        tier = _safe(grade.get("tier"), "MEDIUM").upper()
        if tier not in tier_counts:
            tier = "MEDIUM"
        tier_counts[tier] += 1
        tier_class = tier.lower()
        score = int(grade.get("score") or 0)
        signal_text = (
            f'{int(grade.get("favorable_signals") or 0)} favorable / '
            f'{int(grade.get("tough_signals") or 0)} tough signals'
            if grade.get("available") is True
            else _safe(grade.get("reason"), "verified context unavailable")
        )

        projection = None
        if item.get("has_projection") is True:
            projection = projection_yards_for_athlete(
                context,
                team,
                athlete_id,
                projection_engine.build_player_projection,
            )
        has_projection = projection is not None
        state_text = "CERTIFIED PROJECTION" if has_projection else "MARKET ONLY • NO PROJECTION"
        state_class = "" if has_projection else " market"

        face = headshot_url(athlete_id)
        logo = team_logo_url(team_abbr)
        cards.append(
            f'<article class="krecv13-card {escape(tier_class)}" data-athlete-id="{escape(athlete_id)}" '
            f'data-team-id="{escape(team_id)}" data-matchup-tier="{escape(tier)}" data-matchup-score="{score:+d}">'
            '<div class="krecv13-top">'
            f'{_image(face, "krecv13-face", player_name)}'
            '<div>'
            f'<div class="krecv13-name">{escape(player_name)}</div>'
            f'<div class="krecv13-meta">{escape(position)} • ESPN athlete {escape(athlete_id)}</div>'
            f'<div class="krecv13-team">{escape(team_name)} • {escape(team_abbr)}</div>'
            '</div>'
            f'{_image(logo, "krecv13-teamlogo", team_name + " logo")}'
            '</div>'
            '<div class="krecv13-badges">'
            f'<span class="krecv13-tier {escape(tier_class)}">{escape(tier)}</span>'
            f'<span class="krecv13-state{state_class}">{escape(state_text)}</span>'
            '</div>'
            f'<div class="krecv13-matchup">vs <strong>{escape(opponent_abbr)}</strong> • matchup score <strong>{score:+d}</strong> • {escape(signal_text)}</div>'
            '<div class="krecv13-metrics">'
            f'<div class="krecv13-metric proj"><b>{escape(_yards(projection))}</b><span>Projected Rec Yds</span></div>'
            f'<div class="krecv13-metric"><b>{escape(_line(row.get("line")))}</b><span>FanDuel Rec Yds</span></div>'
            f'<div class="krecv13-metric"><b>{escape(_american(row.get("over_odds")))}</b><span>Over</span></div>'
            f'<div class="krecv13-metric"><b>{escape(_american(row.get("under_odds")))}</b><span>Under</span></div>'
            '</div>'
            '<div class="krecv13-foot">Exact ESPN identity • frozen V9 matchup classification • '
            '<strong>projection influence 0.0%</strong></div>'
            '</article>'
        )

    if not cards:
        return ""
    summary = (
        f'{tier_counts["FAVORABLE"]} favorable • '
        f'{tier_counts["MEDIUM"]} medium • '
        f'{tier_counts["TOUGH"]} tough'
    )
    return (
        '<section class="krecv13-wrap" aria-label="Receiving Yards Matchup Tiers 2.0">'
        '<div class="krecv13-head"><div>'
        '<div class="krecv13-title">🎯 FanDuel Receiving Yards • Matchup Tiers 2.0</div>'
        f'<div class="krecv13-sub">Exact ESPN player faces + team identity + frozen market-blind projection • {escape(summary)} • tier math unchanged.</div>'
        '</div>'
        f'<span class="krecv13-count">{len(cards)} LIVE PROPS</span></div>'
        f'<div class="krecv13-grid">{"".join(cards)}</div>'
        '</section>'
    )


def render_nfl_receiving_yards_hub() -> None:
    st.markdown(_STEP13_CSS, unsafe_allow_html=True)
    original_board = tier_page._lineup_board_html_v9
    tier_page._lineup_board_html_v9 = _lineup_board_html_v13
    try:
        return prior.render_nfl_receiving_yards_hub()
    finally:
        tier_page._lineup_board_html_v9 = original_board


def render_nfl_hub(market: str = "Receiving Yards") -> None:
    if str(market or "Receiving Yards") != "Receiving Yards":
        raise ValueError("NFL Receiving Yards V13 only renders the Receiving Yards market.")
    return render_nfl_receiving_yards_hub()


__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_MATCHUP_TIERS",
    "FROZEN_PRIOR",
    "FROZEN_PROJECTION_ENGINE",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_lineup_board_html_v13",
    "render_nfl_hub",
    "render_nfl_receiving_yards_hub",
]
