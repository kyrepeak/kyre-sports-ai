"""NFL Rushing Yards V4 — Page Build Step 1 compact player cards.

Visual-only additive wrapper over certified Rushing Yards V3. V4 inserts a
compact player-first board above the existing evidence stack after the exact
selected event has loaded. It reuses the already-certified Step 2 context,
Step 3 market-blind projection, and Step 4 post-projection market context.

Permanent safety:
- V3/V2/V1 runtime owners remain unchanged;
- exact ESPN event/team/athlete identity only;
- ESPN headshots and team logos are display-only and derived from exact IDs;
- player names never provide identity authority;
- no fuzzy matching or synthetic IDs;
- no projection, probability, EV, grading, ranking, recommendation, staking,
  or wagering behavior is introduced here;
- sportsbook projection influence remains exactly 0.0%.
"""
from __future__ import annotations

from html import escape
import math
import re
from typing import Any

import streamlit as st

import nfl_rushing_yards_hub_v2 as step3
import nfl_rushing_yards_hub_v3 as prior

MODEL_VERSION = "NFL RUSHING YARDS V4 • PAGE BUILD STEP 1 • COMPACT PLAYER CARDS"
FROZEN_PRIOR = "nfl_rushing_yards_hub_v3"
PAGE_BUILD_STEP = 1
PAGE_BUILD_TOTAL = 6

_ORIGINAL_CONTEXT_BOARD_V2 = step3._render_context_board_v2
_TEAM_ABBR_RE = re.compile(r"^[A-Z]{2,4}$")

_COMPACT_CSS = r'''
<style>
.krush4-wrap{margin:4px 0 12px}
.krush4-section{display:flex;align-items:flex-end;justify-content:space-between;gap:10px;margin:10px 0 7px}
.krush4-section h3{margin:0;color:#f5faf7;font-size:.98rem;line-height:1.1}.krush4-section span{color:#789083;font-size:.51rem;font-weight:900;letter-spacing:.06em;text-transform:uppercase}
.krush4-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}
.krush4-card{position:relative;overflow:hidden;border:1px solid #2b4b39;border-radius:17px;background:linear-gradient(145deg,#0b1712 0%,#0a1411 70%,#0d1a14 100%);padding:10px 11px;min-width:0}
.krush4-card:after{content:"";position:absolute;right:-28px;bottom:-55px;width:130px;height:130px;border:1px solid rgba(139,226,172,.055);border-radius:50%;box-shadow:0 0 0 18px rgba(139,226,172,.018)}
.krush4-top{position:relative;z-index:1;display:flex;align-items:center;gap:9px;min-width:0}
.krush4-head{width:50px;height:50px;flex:0 0 50px;border:1px solid #355b45;border-radius:50%;overflow:hidden;background:#09140f;display:flex;align-items:flex-end;justify-content:center}
.krush4-head img{width:100%;height:100%;object-fit:cover;object-position:center top;display:block}
.krush4-ident{min-width:0;flex:1}.krush4-name{color:#f6faf7;font-size:.81rem;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.krush4-meta{color:#7d9285;font-size:.51rem;line-height:1.4;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.krush4-teamlogo{width:35px;height:35px;flex:0 0 35px;border:1px solid #284334;border-radius:10px;background:#09150f;padding:4px;box-sizing:border-box;object-fit:contain}
.krush4-badge{display:inline-flex;align-items:center;border:1px solid #3c6a4d;background:#0f2418;color:#8be2ac;border-radius:999px;padding:3px 6px;font-size:.43rem;font-weight:950;letter-spacing:.04em;margin-top:4px}
.krush4-badge.off{border-color:#6d613a;background:#241f12;color:#dcc06d}
.krush4-main{position:relative;z-index:1;display:grid;grid-template-columns:1.15fr repeat(2,minmax(0,1fr));gap:6px;margin-top:9px}
.krush4-metric{border:1px solid #1e3528;border-radius:10px;background:#09140f;padding:7px 8px;min-width:0}.krush4-metric b{display:block;color:#f0f7f2;font-size:.83rem;line-height:1.05}.krush4-metric span{display:block;color:#62786a;font-size:.43rem;text-transform:uppercase;font-weight:900;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.krush4-subgrid{position:relative;z-index:1;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin-top:6px}.krush4-sub{border-top:1px solid #1c3024;padding-top:6px}.krush4-sub b{display:block;color:#dce9e0;font-size:.63rem}.krush4-sub span{display:block;color:#617568;font-size:.41rem;text-transform:uppercase;font-weight:900;margin-top:2px}
.krush4-foot{position:relative;z-index:1;border-top:1px solid #1a2d22;margin-top:7px;padding-top:6px;color:#6f8477;font-size:.46rem;line-height:1.45}.krush4-foot strong{color:#91cda4}
@media(max-width:760px){.krush4-grid{grid-template-columns:1fr}.krush4-card{padding:9px 10px}.krush4-head{width:46px;height:46px;flex-basis:46px}.krush4-main{grid-template-columns:1fr 1fr}.krush4-main>.krush4-metric:first-child{grid-column:1/-1}.krush4-section{align-items:flex-start;flex-direction:column;gap:3px}}
</style>
'''


def _safe(value: Any, default: str = "—") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _number(value: Any) -> float:
    try:
        out = float(value)
        return out if math.isfinite(out) else math.nan
    except Exception:
        return math.nan


def _fmt(value: Any, digits: int = 1) -> str:
    number = _number(value)
    if not math.isfinite(number):
        return "—"
    text = f"{number:.{digits}f}"
    return text.rstrip("0").rstrip(".") if digits else text


def _american(value: Any) -> str:
    number = _number(value)
    return f"{number:+.0f}" if math.isfinite(number) else "—"


def _signed(value: Any) -> str:
    number = _number(value)
    return f"{number:+.1f}" if math.isfinite(number) else "—"


def _headshot_url(athlete_id: Any) -> str:
    athlete_id = _safe(athlete_id, "")
    if not athlete_id.isdigit():
        return ""
    return f"https://a.espncdn.com/i/headshots/nfl/players/full/{athlete_id}.png"


def _team_logo_url(abbr: Any) -> str:
    abbr = _safe(abbr, "").upper()
    if _TEAM_ABBR_RE.fullmatch(abbr) is None:
        return ""
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{abbr.lower()}.png"


def _team_map(context: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for team in context.get("teams") or []:
        if not isinstance(team, dict):
            continue
        team_id = _safe(team.get("official_team_id"), "")
        if team_id.isdigit():
            out[team_id] = team
    return out


def _player_position(team: dict[str, Any], athlete_id: str) -> str:
    for player in team.get("players") or []:
        if not isinstance(player, dict):
            continue
        if _safe(player.get("official_athlete_id"), "") == athlete_id:
            return _safe(player.get("position"), "RUSHER")
    return "RUSHER"


def _compact_player_card(
    projection_row: dict[str, Any],
    team: dict[str, Any],
    opponent: dict[str, Any],
    market_row: dict[str, Any],
) -> str:
    athlete_id = _safe(projection_row.get("official_athlete_id"), "")
    team_id = _safe(projection_row.get("official_team_id"), "")
    player_name = _safe(projection_row.get("player_name"), "Unknown rusher")
    team_abbr = _safe(team.get("team_abbreviation"), "NFL").upper()
    opponent_abbr = _safe(opponent.get("team_abbreviation"), "OPP").upper()
    position = _player_position(team, athlete_id)
    headshot = _headshot_url(athlete_id)
    logo = _team_logo_url(team_abbr)

    projection = _number(projection_row.get("projection_yards"))
    line = _number(market_row.get("line")) if market_row.get("ready") else math.nan
    gap = projection - line if math.isfinite(projection) and math.isfinite(line) else math.nan
    market_live = bool(market_row.get("ready"))
    age = _number(market_row.get("age_seconds")) if market_live else math.nan
    age_text = f"{max(age, 0.0):.0f}s old" if math.isfinite(age) else "market unavailable"
    badge_text = "EXACT-ID LIVE" if market_live else "MARKET CHECK"
    badge_class = "" if market_live else " off"

    head_html = (
        f'<div class="krush4-head"><img src="{escape(headshot, quote=True)}" alt="{escape(player_name, quote=True)} headshot" loading="lazy" decoding="async" onerror="this.style.display=\'none\'"></div>'
        if headshot else '<div class="krush4-head"></div>'
    )
    logo_html = (
        f'<img class="krush4-teamlogo" src="{escape(logo, quote=True)}" alt="{escape(team_abbr, quote=True)} logo" loading="lazy" decoding="async" onerror="this.style.display=\'none\'">'
        if logo else ""
    )

    return f'''
    <article class="krush4-card">
      <div class="krush4-top">
        {head_html}
        <div class="krush4-ident">
          <div class="krush4-name">{escape(player_name)}</div>
          <div class="krush4-meta">{escape(position)} • {escape(team_abbr)} vs {escape(opponent_abbr)} • ESPN athlete {escape(athlete_id)}</div>
          <span class="krush4-badge{badge_class}">{escape(badge_text)}</span>
        </div>
        {logo_html}
      </div>
      <div class="krush4-main">
        <div class="krush4-metric"><b>{escape(_fmt(projection, 1))}</b><span>Projected Rush Yards</span></div>
        <div class="krush4-metric"><b>{escape(_fmt(line, 1))}</b><span>FanDuel Line</span></div>
        <div class="krush4-metric"><b>{escape(_signed(gap))}</b><span>Projection − Line</span></div>
      </div>
      <div class="krush4-subgrid">
        <div class="krush4-sub"><b>{escape(_fmt(projection_row.get('expected_carries'), 1))}</b><span>Expected Carries</span></div>
        <div class="krush4-sub"><b>{escape(_fmt(projection_row.get('expected_yards_per_carry'), 2))}</b><span>Expected YPC</span></div>
        <div class="krush4-sub"><b>{escape(_american(market_row.get('over_odds')) if market_live else '—')}</b><span>Over Price</span></div>
      </div>
      <div class="krush4-foot">ESPN team <strong>{escape(team_id)}</strong> • {escape(age_text)} • sportsbook projection influence <strong>0.0%</strong> • probability/EV/grade OFF</div>
    </article>
    '''


def _compact_board_html(context: dict[str, Any], event_id: str) -> str:
    result = step3.projection.build_event_projections(context)
    if not result.get("ready"):
        return ""

    teams = _team_map(context)
    event_market = prior._load_rushing_market(event_id)
    cards: list[str] = []
    for row in result.get("projections") or []:
        team_id = _safe(row.get("official_team_id"), "")
        opponent_id = _safe(row.get("opponent_official_team_id"), "")
        team = teams.get(team_id, {})
        opponent = teams.get(opponent_id, {})
        market_row = {"ready": False, "reason": "market unavailable"}
        if event_market.get("ready") and event_market.get("market_available"):
            market_row = prior.market_api.market_for_athlete(
                event_market,
                _safe(row.get("official_athlete_id"), ""),
                team_id,
            )
        cards.append(_compact_player_card(row, team, opponent, market_row))

    if not cards:
        return ""
    return (
        '<div class="krush4-wrap">'
        '<div class="krush4-section"><h3>🏃 Compact Rusher Cards</h3><span>PAGE BUILD 1 OF 6 • PLAYER-FIRST VIEW</span></div>'
        f'<div class="krush4-grid">{"".join(cards)}</div>'
        '</div>'
    )


def _render_context_board_v4(games) -> None:
    """Reserve the top slot, render certified V2/V3 evidence, then fill the slot."""
    compact_slot = st.empty()
    _ORIGINAL_CONTEXT_BOARD_V2(games)

    event_id = _safe(st.session_state.get("nfl_rushing_yards_step2_event"), "")
    if not event_id.isdigit():
        return
    context = step3.prior._load_rushing_context(event_id)
    if context.get("ready") is not True or context.get("data_available") is not True:
        return
    board = _compact_board_html(context, event_id)
    if board:
        compact_slot.markdown(board, unsafe_allow_html=True)


def render_nfl_rushing_yards_hub() -> None:
    """Render certified V3 with visual-only compact player cards above evidence."""
    st.markdown(_COMPACT_CSS, unsafe_allow_html=True)
    original_context = step3._render_context_board_v2
    step3._render_context_board_v2 = _render_context_board_v4
    try:
        return prior.render_nfl_rushing_yards_hub()
    finally:
        step3._render_context_board_v2 = original_context


def render_nfl_hub(market: str = "Rushing Yards") -> None:
    if str(market or "Rushing Yards") != "Rushing Yards":
        raise ValueError("NFL Rushing Yards V4 only renders the Rushing Yards market.")
    return render_nfl_rushing_yards_hub()


__all__ = [
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "PAGE_BUILD_STEP",
    "PAGE_BUILD_TOTAL",
    "_compact_board_html",
    "_compact_player_card",
    "_headshot_url",
    "_render_context_board_v4",
    "_team_logo_url",
    "render_nfl_hub",
    "render_nfl_rushing_yards_hub",
]
