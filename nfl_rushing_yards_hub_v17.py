"""NFL Rushing Yards V17 — compact mobile cleanup over frozen V16.

Presentation-only additive layer. V16 remains authoritative for exact-ID/live-
roster validation. V17 moves matchup navigation to the top, hides low/no-usage
rushers from display, and compresses opponent run-front + workload presentation.
Projection math, probability, grading, staking, and sportsbook influence remain
unchanged; sportsbook projection influence stays 0.0%.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any, Mapping

import pandas as pd
import streamlit as st

import nfl_rushing_yards_hub_v1 as base_page
import nfl_rushing_yards_hub_v2 as step3_page
import nfl_rushing_yards_hub_v3 as market_page
import nfl_rushing_yards_hub_v16 as prior
import nfl_rushing_yards_projection_v1 as projection

MODEL_VERSION = "NFL RUSHING YARDS V17 • COMPACT MOBILE CLEANUP"
FROZEN_PRIOR = "nfl_rushing_yards_hub_v16"
DISPLAY_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MIN_MEANINGFUL_CARRIES = 1.0
MAX_WORKLOAD_CARDS_PER_TEAM = 3

_ORIGINAL_ROOT_RENDER = base_page.render_nfl_rushing_yards_hub
_ORIGINAL_STEP2_BOARD = step3_page._ORIGINAL_CONTEXT_BOARD
_ORIGINAL_PROJECTION_BUILDER = projection.build_event_projections

_CSS = r'''
<style>
.krush17-hero{border:1px solid #31563f;border-radius:18px;background:linear-gradient(145deg,#0d1c16,#09130f);padding:14px 15px;margin:6px 0 10px}
.krush17-kicker{color:#8be2ac;font-size:.58rem;font-weight:950;letter-spacing:.11em;text-transform:uppercase}.krush17-title{color:#f6faf7;font-size:1.35rem;font-weight:950;line-height:1.08;margin-top:4px}.krush17-title span{color:#8be2ac}.krush17-sub{color:#8ca095;font-size:.66rem;line-height:1.42;margin-top:6px}
.krush17-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin:7px 0 10px}.krush17-pill{border:1px solid #20392b;border-radius:11px;background:#09140f;padding:7px 8px;min-width:0}.krush17-pill b{display:block;color:#eef7f1;font-size:.78rem}.krush17-pill span{display:block;color:#60776a;font-size:.42rem;font-weight:900;text-transform:uppercase;margin-top:2px}
.krush17-selected{border:1px solid #315940;border-radius:12px;background:#0d1b14;padding:9px 10px;margin:5px 0 10px;color:#b6d5c1;font-size:.61rem;font-weight:800}
.krush17-team{border:1px solid #294637;border-radius:14px;background:#0a1611;padding:10px 10px 8px;margin:8px 0}.krush17-teamtop{display:flex;justify-content:space-between;align-items:center;gap:8px}.krush17-teamname{color:#eef7f1;font-size:.78rem;font-weight:950}.krush17-meta{color:#657b6e;font-size:.47rem;font-weight:800}
.krush17-front-title{color:#a9c7b4;font-size:.52rem;font-weight:950;text-transform:uppercase;letter-spacing:.05em;margin:8px 0 5px}.krush17-front-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px}.krush17-front{border:1px solid #1d3427;border-radius:9px;background:#08130e;padding:6px 7px;min-width:0}.krush17-front b{display:block;color:#e7f2ea;font-size:.68rem}.krush17-front span{display:block;color:#62776a;font-size:.38rem;font-weight:900;text-transform:uppercase;line-height:1.25;margin-top:2px}
.krush17-workload{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin-top:7px}.krush17-player{border:1px solid #20382a;border-radius:10px;background:#09140f;padding:7px 8px;min-width:0}.krush17-player-name{color:#f0f7f2;font-size:.62rem;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.krush17-player-meta{color:#688073;font-size:.40rem;margin-top:2px}.krush17-player-stats{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:4px;margin-top:5px}.krush17-player-stats div{border-top:1px solid #1d3125;padding-top:4px}.krush17-player-stats b{display:block;color:#dce9e0;font-size:.58rem}.krush17-player-stats span{display:block;color:#5c7164;font-size:.34rem;text-transform:uppercase;font-weight:900}
.krush17-guard{border-left:3px solid #426d53;background:#0d1a13;border-radius:8px;padding:8px 9px;color:#86a391;font-size:.51rem;line-height:1.4;margin-top:9px}
@media(max-width:760px){.krush17-summary{grid-template-columns:repeat(4,minmax(0,1fr))}.krush17-pill{padding:6px 5px}.krush17-pill b{font-size:.68rem}.krush17-workload{grid-template-columns:1fr}.krush17-front-grid{grid-template-columns:repeat(4,minmax(0,1fr));gap:4px}.krush17-front{padding:5px}.krush17-front b{font-size:.60rem}.krush17-front span{font-size:.32rem}.krush17-hero{padding:12px}.krush17-title{font-size:1.2rem}}
</style>
'''


def _text(value: Any, default: str = "") -> str:
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
    rendered = f"{number:.{digits}f}"
    return rendered.rstrip("0").rstrip(".") if digits else rendered


def verified_game_options(games: pd.DataFrame) -> tuple[list[str], dict[str, str]]:
    if not isinstance(games, pd.DataFrame) or games.empty or "game_id" not in games.columns:
        return [], {}
    options: list[str] = []
    labels: dict[str, str] = {}
    for _, row in games.iterrows():
        event_id = _text(row.get("game_id"))
        if not event_id.isdigit():
            continue
        options.append(event_id)
        labels[event_id] = (
            f"{_text(row.get('away_abbr'), 'AWY')} @ {_text(row.get('home_abbr'), 'HME')}"
            f" • {_text(row.get('tip_et'), 'TBD')}"
        )
    return options, labels


def select_relevant_rushers(
    projections: list[dict[str, Any]],
    players: Mapping[str, Mapping[str, Any]],
    markets: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    ranked: list[tuple[tuple[int, float, int], dict[str, Any]]] = []
    for index, raw in enumerate(projections or []):
        if not isinstance(raw, dict):
            continue
        athlete_id = _text(raw.get("official_athlete_id"))
        if not athlete_id:
            continue
        player = players.get(athlete_id) or {}
        market = markets.get(athlete_id) or {}
        expected = _number(raw.get("expected_carries"))
        usage = _number(player.get("carries_per_game"))
        expected_value = expected if math.isfinite(expected) else 0.0
        usage_value = usage if math.isfinite(usage) else 0.0
        meaningful = expected_value >= MIN_MEANINGFUL_CARRIES or usage_value >= MIN_MEANINGFUL_CARRIES
        market_live = market.get("ready") is True
        if not meaningful and not market_live:
            continue
        workload = max(expected_value, usage_value)
        ranked.append(((0 if meaningful else 1, -workload, index), dict(raw)))
    ranked.sort(key=lambda item: item[0])
    return [row for _, row in ranked]


def run_front_strip_html(front: Mapping[str, Any]) -> str:
    if not isinstance(front, Mapping) or front.get("data_available") is not True:
        return '<div class="krush17-front-title">Opponent Run Front • verified sample unavailable</div>'
    metrics = (
        ("Rush Yds/G", _fmt(front.get("rush_yards_allowed_per_game"), 1)),
        ("YPC", _fmt(front.get("yards_per_carry_allowed"), 2)),
        ("Rush Att/G", _fmt(front.get("rush_attempts_allowed_per_game"), 1)),
        ("Rush TD/G", _fmt(front.get("rushing_touchdowns_allowed_per_game"), 2)),
    )
    cells = "".join(
        f'<div class="krush17-front"><b>{escape(value)}</b><span>{escape(label)}</span></div>'
        for label, value in metrics
    )
    return f'<div class="krush17-front-title">🧱 Opponent Run Front</div><div class="krush17-front-grid">{cells}</div>'


def _player_index(context: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for team in context.get("teams") or []:
        if not isinstance(team, Mapping):
            continue
        for player in team.get("players") or []:
            if not isinstance(player, Mapping):
                continue
            athlete_id = _text(player.get("official_athlete_id"))
            if athlete_id:
                out[athlete_id] = dict(player)
    return out


def _market_index(rows: list[dict[str, Any]], event_id: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not event_id.isdigit():
        return out
    try:
        event_market = market_page._load_rushing_market(event_id)
    except Exception:
        return out
    if event_market.get("ready") is not True or event_market.get("market_available") is not True:
        return out
    for row in rows:
        athlete_id = _text(row.get("official_athlete_id"))
        team_id = _text(row.get("official_team_id"))
        try:
            out[athlete_id] = dict(market_page.market_api.market_for_athlete(event_market, athlete_id, team_id) or {})
        except Exception:
            out[athlete_id] = {"ready": False}
    return out


def _filtered_projection_builder(context: dict[str, Any]) -> dict[str, Any]:
    result = _ORIGINAL_PROJECTION_BUILDER(context)
    if not isinstance(result, dict) or result.get("ready") is not True:
        return result
    rows = [dict(row) for row in result.get("projections") or [] if isinstance(row, dict)]
    event_id = _text(st.session_state.get("nfl_rushing_yards_step2_event"))
    selected = select_relevant_rushers(rows, _player_index(context), _market_index(rows, event_id))
    return {**result, "projections": selected, "projection_count": len(selected)}


def _player_card_html(player: Mapping[str, Any]) -> str:
    return (
        '<div class="krush17-player">'
        f'<div class="krush17-player-name">{escape(_text(player.get("player_name"), "Unknown rusher"))}</div>'
        f'<div class="krush17-player-meta">{escape(_text(player.get("position"), "RUSHER"))} • ESPN {_text(player.get("official_athlete_id"), "—")}</div>'
        '<div class="krush17-player-stats">'
        f'<div><b>{escape(_fmt(player.get("carries_per_game"), 1))}</b><span>Carries/G</span></div>'
        f'<div><b>{escape(_fmt(player.get("rushing_yards_per_game"), 1))}</b><span>Rush Yds/G</span></div>'
        f'<div><b>{escape(_fmt(player.get("yards_per_carry"), 2))}</b><span>YPC</span></div>'
        f'<div><b>{escape(_fmt(player.get("rushing_touchdowns"), 0))}</b><span>Rush TD</span></div>'
        '</div></div>'
    )


def _render_team_compact(team: dict[str, Any], relevant_ids: set[str]) -> None:
    team_name = _text(team.get("team_name"), _text(team.get("team_abbreviation"), "NFL Team"))
    abbr = _text(team.get("team_abbreviation"), "NFL").upper()
    side = _text(team.get("home_away"), "team").upper()
    st.markdown(
        '<section class="krush17-team">'
        f'<div class="krush17-teamtop"><span class="krush17-teamname">🏃 {escape(abbr)} • {escape(team_name)}</span>'
        f'<span class="krush17-meta">{escape(side)} • ESPN team {_text(team.get("official_team_id"), "—")}</span></div>'
        f'{run_front_strip_html(team.get("opponent_run_front") or {})}'
        '</section>',
        unsafe_allow_html=True,
    )
    players = [
        dict(player) for player in team.get("players") or []
        if isinstance(player, Mapping) and _text(player.get("official_athlete_id")) in relevant_ids
    ]
    players.sort(key=lambda player: -(_number(player.get("carries_per_game")) if math.isfinite(_number(player.get("carries_per_game"))) else 0.0))
    players = players[:MAX_WORKLOAD_CARDS_PER_TEAM]
    if players:
        st.markdown(
            '<div class="krush17-workload">' + "".join(_player_card_html(player) for player in players) + '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.caption("No carry-relevant current-roster rusher is verified for this team yet.")


def _render_selected_context_v17(games: pd.DataFrame) -> None:
    event_id = _text(st.session_state.get("nfl_rushing_yards_step2_event"))
    options, _labels = verified_game_options(games)
    if event_id not in options:
        return
    with st.spinner("🏃 Loading selected rushing matchup…"):
        context = base_page._load_rushing_context(event_id)
    if context.get("ready") is not True:
        st.warning(f"Rushing context failed closed: {context.get('reason') or 'verified context unavailable'}")
        return
    if context.get("data_available") is not True:
        st.info("No verified current-roster rushing workload is available for this matchup yet.")
        return

    raw_result = _ORIGINAL_PROJECTION_BUILDER(context)
    rows = [dict(row) for row in raw_result.get("projections") or [] if isinstance(row, dict)] if isinstance(raw_result, dict) else []
    selected = select_relevant_rushers(rows, _player_index(context), _market_index(rows, event_id))
    relevant_ids = {_text(row.get("official_athlete_id")) for row in selected}

    teams = [dict(team) for team in context.get("teams") or [] if isinstance(team, Mapping)]
    teams.sort(key=lambda item: 0 if _text(item.get("home_away")).lower() == "away" else 1)
    if not teams:
        return
    tabs = st.tabs([f"{_text(team.get('team_abbreviation'), 'NFL')} {_text(team.get('home_away')).upper()}" for team in teams])
    for tab, team in zip(tabs, teams):
        with tab:
            _render_team_compact(team, relevant_ids)


def _summary_html(games: pd.DataFrame) -> str:
    states = games.get("state", pd.Series(dtype=str)).astype(str) if isinstance(games, pd.DataFrame) and not games.empty else pd.Series(dtype=str)
    metrics = (
        ("Games", str(len(games) if isinstance(games, pd.DataFrame) else 0)),
        ("Upcoming", str(int((states == "pre").sum()))),
        ("Live", str(int((states == "in").sum()))),
        ("Final", str(int((states == "post").sum()))),
    )
    return '<div class="krush17-summary">' + "".join(
        f'<div class="krush17-pill"><b>{escape(value)}</b><span>{escape(label)}</span></div>'
        for label, value in metrics
    ) + '</div>'


def _compact_root_render_v17() -> None:
    st.html(_CSS)
    st.markdown(
        '<section class="krush17-hero"><div class="krush17-kicker">NFL • Rushing Yards</div>'
        '<div class="krush17-title">🏃 Ground Game <span>Lab</span></div>'
        '<div class="krush17-sub">Fast matchup navigation • carry-relevant rushers only • compact verified run-front context.</div></section>',
        unsafe_allow_html=True,
    )

    if "nfl_rushing_yards_v1_date" not in st.session_state:
        st.session_state["nfl_rushing_yards_v1_date"] = st.session_state.get("nfl_v1_date")
    selected_day = st.date_input(
        "📅 NFL slate",
        value=st.session_state.get("nfl_rushing_yards_v1_date") or st.session_state.get("nfl_v1_date"),
        key="nfl_rushing_yards_v1_date_input",
    )
    st.session_state["nfl_rushing_yards_v1_date"] = selected_day
    day_str = pd.to_datetime(selected_day).strftime("%Y-%m-%d")
    with st.spinner("🏈 Loading NFL matchups…"):
        games, diag = base_page.load_nfl_slate(day_str)

    if not diag.get("request_ok"):
        st.error("Verified NFL schedule is temporarily unavailable; no games were invented.")
        return
    options, labels = verified_game_options(games)
    if not options:
        st.info("No verified NFL matchup is available on this slate.")
        return
    current = _text(st.session_state.get("nfl_rushing_yards_step2_event"))
    if current not in options:
        st.session_state["nfl_rushing_yards_step2_event"] = options[0]
    selected_event = st.selectbox(
        "🏈 Game",
        options=options,
        format_func=lambda value: labels.get(value, value),
        key="nfl_rushing_yards_step2_event",
    )
    st.markdown(_summary_html(games), unsafe_allow_html=True)
    st.markdown(
        f'<div class="krush17-selected">Selected matchup: {escape(labels.get(str(selected_event), str(selected_event)))} • ESPN {escape(str(selected_event))}</div>',
        unsafe_allow_html=True,
    )

    base_page._render_context_board(games)
    st.markdown(
        '<div class="krush17-guard">🧊 V17 changes presentation and display eligibility only. V16 exact-ID/live-roster verification remains authoritative; projection math and sportsbook influence remain unchanged at 0.0%.</div>',
        unsafe_allow_html=True,
    )


def render_nfl_rushing_yards_hub() -> None:
    original_root = base_page.render_nfl_rushing_yards_hub
    original_step2 = step3_page._ORIGINAL_CONTEXT_BOARD
    original_builder = projection.build_event_projections
    base_page.render_nfl_rushing_yards_hub = _compact_root_render_v17
    step3_page._ORIGINAL_CONTEXT_BOARD = _render_selected_context_v17
    projection.build_event_projections = _filtered_projection_builder
    try:
        return prior.render_nfl_rushing_yards_hub()
    finally:
        projection.build_event_projections = original_builder
        step3_page._ORIGINAL_CONTEXT_BOARD = original_step2
        base_page.render_nfl_rushing_yards_hub = original_root


def render_nfl_hub(market: str = "Rushing Yards") -> None:
    if str(market or "Rushing Yards") != "Rushing Yards":
        raise ValueError("NFL Rushing Yards V17 only renders the Rushing Yards market.")
    return render_nfl_rushing_yards_hub()


__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "MIN_MEANINGFUL_CARRIES",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "run_front_strip_html",
    "select_relevant_rushers",
    "verified_game_options",
    "render_nfl_hub",
    "render_nfl_rushing_yards_hub",
]
