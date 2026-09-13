"""NFL Receiving Yards V8 — Page Build Step 8 FanDuel full standard lineup.

Additive visual-only market layer over certified Receiving Yards V7. V8 shows
every fresh exact-ID standard FanDuel Receiving Yards prop for the selected ESPN
event, including market-only athletes who do not have a certified projection.

Market-only rows are explicitly labeled NO PROJECTION. The frozen Step 6
projection engine is not changed and never receives sportsbook input.
Sportsbook projection influence remains exactly 0.0%.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any

import streamlit as st

import nfl_receiving_yards_hub_v2 as player_page
import nfl_receiving_yards_hub_v7 as prior
import nfl_receiving_yards_market_api_v1 as market_api
import nfl_receiving_yards_projection_v1 as projection_engine

MODEL_VERSION = "NFL RECEIVING YARDS V8 • PAGE BUILD STEP 8 • FANDUEL FULL LINEUP"
FROZEN_PRIOR = "nfl_receiving_yards_hub_v7"
FROZEN_PROJECTION_ENGINE = "nfl_receiving_yards_projection_v1"
PAGE_BUILD_STEP = 8
PAGE_BUILD_TOTAL = 10
DISPLAY_ONLY = True
MARKET_CONTEXT_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
NO_PROJECTION_LABEL = "NO PROJECTION"

_ORIGINAL_PLAYER_BOARD_V2 = player_page._render_player_board
_ORIGINAL_ADVANCE_STEP7_COPY = prior._advance_step7_copy

_STEP8_CSS = r'''
<style>
.krecv-progress .krecv-track .krecv-fill,.krecv-fill{width:80%!important}
.krecv8-wrap{border:1px solid #443b20;border-radius:17px;background:linear-gradient(145deg,#18150b 0%,#111008 100%);padding:11px 12px;margin:8px 0 12px}
.krecv8-head{display:flex;align-items:flex-end;justify-content:space-between;gap:10px;margin-bottom:8px}.krecv8-title{color:#f7e7aa;font-size:.83rem;font-weight:950;letter-spacing:.02em}.krecv8-sub{color:#9f936a;font-size:.49rem;font-weight:800;line-height:1.4;margin-top:2px}.krecv8-count{border:1px solid #71602d;border-radius:999px;background:#241e0d;color:#e2c85e;padding:3px 7px;font-size:.43rem;font-weight:950;white-space:nowrap}
.krecv8-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.krecv8-card{border:1px solid #4c4122;border-radius:12px;background:#121108;padding:8px 9px;min-width:0}.krecv8-top{display:flex;justify-content:space-between;align-items:flex-start;gap:7px}.krecv8-name{color:#fff8dd;font-size:.70rem;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.krecv8-meta{color:#8f8667;font-size:.44rem;font-weight:800;margin-top:2px;line-height:1.35}.krecv8-state{border:1px solid #5a8a66;border-radius:999px;background:#102016;color:#91d4a0;padding:2px 5px;font-size:.37rem;font-weight:950;text-transform:uppercase;white-space:nowrap}.krecv8-state.market{border-color:#7d6830;background:#251f0d;color:#e0c35f}
.krecv8-metrics{display:grid;grid-template-columns:1.15fr repeat(2,minmax(0,1fr));gap:5px;margin-top:7px}.krecv8-metric{border-top:1px solid #3c351e;padding-top:5px;min-width:0}.krecv8-metric b{display:block;color:#f7efd0;font-size:.70rem}.krecv8-metric span{display:block;color:#746c52;font-size:.38rem;font-weight:900;text-transform:uppercase;margin-top:2px}.krecv8-foot{border-top:1px solid #302b19;margin-top:6px;padding-top:5px;color:#756e56;font-size:.40rem;line-height:1.35}.krecv8-foot strong{color:#d6bf67}
@media(max-width:760px){.krecv8-head{align-items:flex-start;flex-direction:column}.krecv8-grid{grid-template-columns:1fr}.krecv8-metrics{grid-template-columns:1fr 1fr 1fr}}
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
    projected: set[str] = set()
    for team in context.get("teams") or []:
        if not isinstance(team, dict):
            continue
        for player in team.get("players") or []:
            if not isinstance(player, dict):
                continue
            athlete_id = _safe(player.get("official_athlete_id"), "")
            if not athlete_id.isdigit():
                continue
            row = projection_engine.build_player_projection(
                official_event_id=_safe(player.get("official_event_id"), _safe(context.get("official_event_id"), "")),
                team=team,
                player=player,
            )
            if isinstance(row, dict) and row.get("ready") is True:
                projected.add(athlete_id)
    return projected


@st.cache_data(ttl=30, show_spinner=False)
def _load_receiving_market(event_id: str) -> dict[str, Any]:
    return market_api.fetch_event_market(str(event_id))


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
        player_name = _safe(row.get("player_name"), "Verified receiver")
        position = _safe(row.get("position"), "REC")
        has_projection = athlete_id in projected_ids
        state_class = "" if has_projection else " market"
        state_text = "PROJECTION AVAILABLE" if has_projection else f"MARKET ONLY • {NO_PROJECTION_LABEL}"
        cards.append(
            '<article class="krecv8-card">'
            '<div class="krecv8-top"><div>'
            f'<div class="krecv8-name">{escape(player_name)}</div>'
            f'<div class="krecv8-meta">{escape(position)} • {escape(team_abbr)} • ESPN athlete {escape(athlete_id)}</div>'
            '</div>'
            f'<span class="krecv8-state{state_class}">{escape(state_text)}</span></div>'
            '<div class="krecv8-metrics">'
            f'<div class="krecv8-metric"><b>{escape(_line(row.get("line")))}</b><span>FanDuel Rec Yds</span></div>'
            f'<div class="krecv8-metric"><b>{escape(_american(row.get("over_odds")))}</b><span>Over</span></div>'
            f'<div class="krecv8-metric"><b>{escape(_american(row.get("under_odds")))}</b><span>Under</span></div>'
            '</div>'
            '<div class="krecv8-foot">'
            f'Exact ESPN team <strong>{escape(team_id)}</strong> • standard FanDuel Receiving Yards only • projection influence <strong>0.0%</strong>'
            '</div></article>'
        )

    if not cards:
        return ""
    age = _number(event_market.get("age_seconds"))
    age_text = f"{max(age, 0.0):.0f}s old" if math.isfinite(age) else "freshness verified"
    prop_label = "LIVE PROP" if len(cards) == 1 else "LIVE PROPS"
    return (
        '<section class="krecv8-wrap" aria-label="Full FanDuel Receiving Yards lineup">'
        '<div class="krecv8-head"><div>'
        '<div class="krecv8-title">🎯 FanDuel Receiving Yards • Full Standard Lineup</div>'
        f'<div class="krecv8-sub">Every fresh exact-ID standard FanDuel prop returned for this event • {escape(age_text)} • market-only players receive no invented projection.</div>'
        '</div>'
        f'<span class="krecv8-count">{len(cards)} {prop_label}</span></div>'
        f'<div class="krecv8-grid">{"".join(cards)}</div>'
        '</section>'
    )


def _render_player_board_v8(games: Any) -> None:
    lineup_slot = st.empty()
    _ORIGINAL_PLAYER_BOARD_V2(games)

    event_id = _safe(st.session_state.get("nfl_receiving_yards_step2_event"), "")
    if not event_id.isdigit():
        return
    context = player_page._load_receiving_context(event_id)
    event_market = _load_receiving_market(event_id)
    board = _lineup_board_html(context, event_market)
    if board:
        lineup_slot.markdown(board, unsafe_allow_html=True)


def _advance_step8_copy(body: Any) -> Any:
    out = _ORIGINAL_ADVANCE_STEP7_COPY(body)
    if not isinstance(out, str):
        return out
    replacements = (
        (
            "Step 7 adds descriptive Support + Concerns beneath the certified market-blind projection. It explains workload, evidence coverage, sample quality and player/opponent YPR counterweights without using a sportsbook line or changing projection math.",
            "Step 8 adds the fresh exact-ID FanDuel Receiving Yards full lineup as visual market context only. Market-only athletes are labeled NO PROJECTION and sportsbook influence on the frozen projection remains 0.0%.",
        ),
        (
            '<span class="krecv-chip">✅ SUPPORT + CONCERNS</span>',
            '<span class="krecv-chip">✅ SUPPORT + CONCERNS</span><span class="krecv-chip">✅ FANDUEL FULL LINEUP</span>',
        ),
        ("STEP 7 OF 10 • SUPPORT + CONCERNS LIVE", "STEP 8 OF 10 • FANDUEL FULL LINEUP LIVE"),
        (
            '<span class="krecv-stage">8 • MARKET</span>',
            '<span class="krecv-stage on">8 • MARKET ✅</span>',
        ),
    )
    for old, new in replacements:
        out = out.replace(old, new)
    return out


def render_nfl_receiving_yards_hub() -> None:
    st.markdown(_STEP8_CSS, unsafe_allow_html=True)
    original_player_board = player_page._render_player_board
    original_advance = prior._advance_step7_copy
    player_page._render_player_board = _render_player_board_v8
    prior._advance_step7_copy = _advance_step8_copy
    try:
        return prior.render_nfl_receiving_yards_hub()
    finally:
        player_page._render_player_board = original_player_board
        prior._advance_step7_copy = original_advance


def render_nfl_hub(market: str = "Receiving Yards") -> None:
    if str(market or "Receiving Yards") != "Receiving Yards":
        raise ValueError("NFL Receiving Yards V8 only renders the Receiving Yards market.")
    return render_nfl_receiving_yards_hub()


__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "FROZEN_PROJECTION_ENGINE",
    "MARKET_CONTEXT_ONLY",
    "MODEL_VERSION",
    "NO_PROJECTION_LABEL",
    "PAGE_BUILD_STEP",
    "PAGE_BUILD_TOTAL",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_advance_step8_copy",
    "_lineup_board_html",
    "_load_receiving_market",
    "_projected_athlete_ids",
    "_render_player_board_v8",
    "render_nfl_hub",
    "render_nfl_receiving_yards_hub",
]
