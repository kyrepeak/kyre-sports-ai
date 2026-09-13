"""NFL Rushing Yards V12 — full standard FanDuel lineup board.

V12 is additive over certified display-repair owner V11. It adds one visual-only
board above the compact projection cards showing every fresh exact-ID standard
FanDuel Rushing Yards prop returned by the certified market client for the
selected ESPN event, including market-only players who do not currently have a
certified projection row.

Market-only rows are explicitly labeled NO PROJECTION. No sportsbook value is
fed into projection math. Exact ESPN IDs remain authoritative; player names are
display-only. Sportsbook projection influence remains exactly 0.0%.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any

import streamlit as st

import nfl_rushing_yards_hub_v2 as projection_page
import nfl_rushing_yards_hub_v3 as market_page
import nfl_rushing_yards_hub_v4 as compact_page
import nfl_rushing_yards_hub_v11 as prior

MODEL_VERSION = "NFL RUSHING YARDS V12 • FANDUEL FULL STANDARD LINEUP V1"
FROZEN_PRIOR = "nfl_rushing_yards_hub_v11"
DISPLAY_ONLY = True
MARKET_CONTEXT_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

_ORIGINAL_CONTEXT_BOARD_V4 = compact_page._render_context_board_v4

_LINEUP_CSS = r'''
<style>
.krush12-wrap{border:1px solid #443b20;border-radius:17px;background:linear-gradient(145deg,#18150b 0%,#111008 100%);padding:11px 12px;margin:8px 0 12px}
.krush12-head{display:flex;align-items:flex-end;justify-content:space-between;gap:10px;margin-bottom:8px}.krush12-title{color:#f7e7aa;font-size:.83rem;font-weight:950;letter-spacing:.02em}.krush12-sub{color:#9f936a;font-size:.49rem;font-weight:800;line-height:1.4;margin-top:2px}.krush12-count{border:1px solid #71602d;border-radius:999px;background:#241e0d;color:#e2c85e;padding:3px 7px;font-size:.43rem;font-weight:950;white-space:nowrap}
.krush12-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.krush12-card{border:1px solid #4c4122;border-radius:12px;background:#121108;padding:8px 9px;min-width:0}.krush12-top{display:flex;justify-content:space-between;align-items:flex-start;gap:7px}.krush12-name{color:#fff8dd;font-size:.70rem;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.krush12-meta{color:#8f8667;font-size:.44rem;font-weight:800;margin-top:2px;line-height:1.35}.krush12-state{border:1px solid #5a8a66;border-radius:999px;background:#102016;color:#91d4a0;padding:2px 5px;font-size:.37rem;font-weight:950;text-transform:uppercase;white-space:nowrap}.krush12-state.market{border-color:#7d6830;background:#251f0d;color:#e0c35f}
.krush12-metrics{display:grid;grid-template-columns:1.15fr repeat(2,minmax(0,1fr));gap:5px;margin-top:7px}.krush12-metric{border-top:1px solid #3c351e;padding-top:5px;min-width:0}.krush12-metric b{display:block;color:#f7efd0;font-size:.70rem}.krush12-metric span{display:block;color:#746c52;font-size:.38rem;font-weight:900;text-transform:uppercase;margin-top:2px}.krush12-foot{border-top:1px solid #302b19;margin-top:6px;padding-top:5px;color:#756e56;font-size:.40rem;line-height:1.35}.krush12-foot strong{color:#d6bf67}
@media(max-width:760px){.krush12-head{align-items:flex-start;flex-direction:column}.krush12-grid{grid-template-columns:1fr}.krush12-metrics{grid-template-columns:1fr 1fr 1fr}}
</style>
'''


def _safe(value: Any, default: str = "—") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _number(value: Any) -> float:
    try:
        out = float(value)
        return out if math.isfinite(out) else math.nan
    except (TypeError, ValueError):
        return math.nan


def _line(value: Any) -> str:
    number = _number(value)
    if not math.isfinite(number):
        return "—"
    text = f"{number:.1f}"
    return text.rstrip("0").rstrip(".")


def _american(value: Any) -> str:
    number = _number(value)
    return f"{number:+.0f}" if math.isfinite(number) else "—"


def _team_map(context: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for team in (context or {}).get("teams") or []:
        if not isinstance(team, dict):
            continue
        team_id = _safe(team.get("official_team_id"), "")
        if team_id.isdigit():
            out[team_id] = team
    return out


def _projected_athlete_ids(context: dict[str, Any]) -> set[str]:
    if not isinstance(context, dict) or context.get("ready") is not True:
        return set()
    result = projection_page.projection.build_event_projections(context)
    if result.get("ready") is not True:
        return set()
    return {
        _safe(row.get("official_athlete_id"), "")
        for row in result.get("projections") or []
        if isinstance(row, dict) and _safe(row.get("official_athlete_id"), "").isdigit()
    }


def _lineup_board_html(context: dict[str, Any], event_market: dict[str, Any]) -> str:
    if not isinstance(event_market, dict):
        return ""
    if event_market.get("ready") is not True or event_market.get("market_available") is not True:
        return ""

    props = [row for row in event_market.get("props") or [] if isinstance(row, dict)]
    if not props:
        return ""

    teams = _team_map(context)
    projected_ids = _projected_athlete_ids(context)
    props.sort(key=lambda row: (_safe(row.get("official_team_id"), ""), _safe(row.get("player_name"), "")))
    cards: list[str] = []
    for row in props:
        athlete_id = _safe(row.get("official_athlete_id"), "")
        team_id = _safe(row.get("official_team_id"), "")
        if not athlete_id.isdigit() or not team_id.isdigit():
            continue
        team = teams.get(team_id, {})
        team_abbr = _safe(team.get("team_abbreviation"), f"ESPN {team_id}").upper()
        player_name = _safe(row.get("player_name"), "Verified rusher")
        position = _safe(row.get("position"), "RUSHER")
        has_projection = athlete_id in projected_ids
        state_class = "" if has_projection else " market"
        state_text = "PROJECTION AVAILABLE" if has_projection else "MARKET ONLY • NO PROJECTION"
        cards.append(
            '<article class="krush12-card">'
            '<div class="krush12-top">'
            '<div>'
            f'<div class="krush12-name">{escape(player_name)}</div>'
            f'<div class="krush12-meta">{escape(position)} • {escape(team_abbr)} • ESPN athlete {escape(athlete_id)}</div>'
            '</div>'
            f'<span class="krush12-state{state_class}">{escape(state_text)}</span>'
            '</div>'
            '<div class="krush12-metrics">'
            f'<div class="krush12-metric"><b>{escape(_line(row.get("line")))}</b><span>FanDuel Rush Yds</span></div>'
            f'<div class="krush12-metric"><b>{escape(_american(row.get("over_odds")))}</b><span>Over</span></div>'
            f'<div class="krush12-metric"><b>{escape(_american(row.get("under_odds")))}</b><span>Under</span></div>'
            '</div>'
            '<div class="krush12-foot">'
            f'Exact ESPN team <strong>{escape(team_id)}</strong> • standard FanDuel Rushing Yards only • projection influence <strong>0.0%</strong>'
            '</div>'
            '</article>'
        )

    if not cards:
        return ""
    age = _number(event_market.get("age_seconds"))
    age_text = f"{max(age, 0.0):.0f}s old" if math.isfinite(age) else "freshness verified"
    return (
        '<section class="krush12-wrap" aria-label="Full FanDuel Rushing Yards lineup">'
        '<div class="krush12-head"><div>'
        '<div class="krush12-title">🏈 FanDuel Rushing Yards • Full Standard Lineup</div>'
        f'<div class="krush12-sub">Every fresh exact-ID standard FanDuel prop returned for this event • {escape(age_text)} • market-only players receive no invented projection.</div>'
        '</div>'
        f'<span class="krush12-count">{len(cards)} LIVE PROP{'' if len(cards) == 1 else 'S'}</span>'
        '</div>'
        f'<div class="krush12-grid">{"".join(cards)}</div>'
        '</section>'
    )


def _render_context_board_v12(games: Any) -> None:
    lineup_slot = st.empty()
    _ORIGINAL_CONTEXT_BOARD_V4(games)

    event_id = _safe(st.session_state.get("nfl_rushing_yards_step2_event"), "")
    if not event_id.isdigit():
        return
    context = projection_page.prior._load_rushing_context(event_id)
    event_market = market_page._load_rushing_market(event_id)
    board = _lineup_board_html(context, event_market)
    if board:
        lineup_slot.markdown(board, unsafe_allow_html=True)


def render_nfl_rushing_yards_hub() -> None:
    st.markdown(_LINEUP_CSS, unsafe_allow_html=True)
    original_context_board = compact_page._render_context_board_v4
    compact_page._render_context_board_v4 = _render_context_board_v12
    try:
        return prior.render_nfl_rushing_yards_hub()
    finally:
        compact_page._render_context_board_v4 = original_context_board


def render_nfl_hub(market: str = "Rushing Yards") -> None:
    if str(market or "Rushing Yards") != "Rushing Yards":
        raise ValueError("NFL Rushing Yards V12 only renders the Rushing Yards market.")
    return render_nfl_rushing_yards_hub()


__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "MARKET_CONTEXT_ONLY",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_lineup_board_html",
    "_projected_athlete_ids",
    "_render_context_board_v12",
    "render_nfl_hub",
    "render_nfl_rushing_yards_hub",
]
