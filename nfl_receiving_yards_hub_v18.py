"""NFL Receiving Yards V18 — compact matchup-first relevance cleanup.

Additive presentation/controller wrapper over frozen Receiving Yards V17.
It keeps the certified identity/projection/history/matchup stack intact while:
- moving exact game selection to the top of the page;
- hiding build/debug-only presentation;
- limiting the default player pool to market/projection/meaningful-usage options;
- limiting the market board to the same relevant exact-ID athletes.

Sportsbook availability is display relevance only. It never enters projection
math. Sportsbook projection influence remains exactly 0.0%.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from html import escape
import math
from typing import Any, Callable

import pandas as pd
import streamlit as st

import nfl_receiving_yards_hub_v17 as prior
import nfl_receiving_yards_hub_v2 as base_page
import nfl_receiving_yards_hub_v3 as summary_page
import nfl_receiving_yards_hub_v8 as market_page
import nfl_receiving_yards_projection_v1 as projection_engine
from nfl_receiving_yards_phoenix_time_v1 import format_research_matchup_label

MODEL_VERSION = "NFL RECEIVING YARDS V18 • MATCHUP-FIRST RELEVANCE CLEANUP"
FROZEN_PRIOR = "nfl_receiving_yards_hub_v17"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
DISPLAY_ONLY_RELEVANCE_FILTER = True
MAX_RELEVANT_PER_TEAM = 5
MIN_USAGE_YARDS_PER_GAME = 20.0
MIN_USAGE_RECEPTIONS_PER_GAME = 1.5
TOP_MATCHUP_LABEL = "🏈 Choose matchup"
EVENT_KEY = "nfl_receiving_yards_step2_event"

_ORIGINAL_LOAD_V17 = prior._load_receiving_context_step7
_ORIGINAL_LINEUP_HTML_V8 = market_page._lineup_board_html

_CSS = r'''
<style>
.krecv18-hero{border:1px solid #315940;border-radius:18px;background:linear-gradient(145deg,#0c1a14,#09140f);padding:14px 15px;margin:7px 0 10px}
.krecv18-kicker{font-size:.58rem;font-weight:950;letter-spacing:.11em;color:#83dca4;text-transform:uppercase}
.krecv18-title{font-size:1.35rem;font-weight:950;color:#f3f9f5;line-height:1.1;margin-top:3px}.krecv18-title span{color:#83dca4}
.krecv18-sub{color:#8aa093;font-size:.66rem;line-height:1.45;margin-top:5px}
.krecv18-match{border:1px solid #294a37;border-radius:14px;background:#0b1711;padding:10px 11px;margin:8px 0 10px}
.krecv18-match b{color:#f1f8f3;font-size:.76rem}.krecv18-match span{display:block;color:#738b7b;font-size:.50rem;margin-top:3px}
.krecv18-slate-note{color:#718679;font-size:.52rem;line-height:1.4;margin:3px 0 7px}
@media(max-width:760px){.krecv18-hero{padding:12px}.krecv18-title{font-size:1.18rem}}
</style>
'''


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _num(value: Any) -> float:
    try:
        out = float(value)
        return out if math.isfinite(out) else math.nan
    except Exception:
        return math.nan


def _market_ids(event_market: dict[str, Any]) -> set[str]:
    if not isinstance(event_market, dict) or event_market.get("ready") is not True:
        return set()
    return {
        _safe(row.get("official_athlete_id"))
        for row in (event_market.get("props") or [])
        if isinstance(row, dict) and _safe(row.get("official_athlete_id")).isdigit()
    }


def _meaningful_usage(player: dict[str, Any]) -> bool:
    ypg = _num(player.get("receiving_yards_per_game"))
    rpg = _num(player.get("receptions_per_game"))
    return bool(
        (math.isfinite(ypg) and ypg >= MIN_USAGE_YARDS_PER_GAME)
        or (math.isfinite(rpg) and rpg >= MIN_USAGE_RECEPTIONS_PER_GAME)
    )


def _projection_ready(team: dict[str, Any], player: dict[str, Any], event_id: str) -> tuple[bool, float]:
    try:
        row = projection_engine.build_player_projection(
            official_event_id=_safe(player.get("official_event_id"), event_id),
            team=team,
            player=player,
        )
    except Exception:
        return False, math.nan
    return row.get("ready") is True, _num(row.get("projection_yards"))


def _filter_context_for_relevant_players(
    context: dict[str, Any],
    event_market: dict[str, Any],
    *,
    max_per_team: int = MAX_RELEVANT_PER_TEAM,
) -> dict[str, Any]:
    if not isinstance(context, dict):
        return context
    out = deepcopy(context)
    event_id = _safe(context.get("official_event_id"))
    market_ids = _market_ids(event_market)
    total = 0

    for team in out.get("teams") or []:
        if not isinstance(team, dict):
            continue
        ranked: list[tuple[tuple[float, ...], dict[str, Any]]] = []
        for player in team.get("players") or []:
            if not isinstance(player, dict):
                continue
            athlete_id = _safe(player.get("official_athlete_id"))
            if not athlete_id.isdigit():
                continue
            has_market = athlete_id in market_ids
            has_projection, projection = _projection_ready(team, player, event_id)
            usage = _meaningful_usage(player)
            if not (has_market or has_projection or usage):
                continue
            ypg = _num(player.get("receiving_yards_per_game"))
            rpg = _num(player.get("receptions_per_game"))
            rank = (
                1.0 if has_market else 0.0,
                1.0 if has_projection else 0.0,
                projection if math.isfinite(projection) else -1.0,
                ypg if math.isfinite(ypg) else -1.0,
                rpg if math.isfinite(rpg) else -1.0,
            )
            ranked.append((rank, player))
        ranked.sort(key=lambda item: item[0], reverse=True)
        selected = [player for _, player in ranked[: max(1, int(max_per_team))]]
        team["players"] = selected
        total += len(selected)

    out["data_available"] = total > 0
    out["relevance_filter_applied"] = True
    out["relevant_player_count"] = total
    out["sportsbook_influence"] = 0.0
    return out


def _matchup_labels(games: pd.DataFrame) -> dict[str, str]:
    labels: dict[str, str] = {}
    if not isinstance(games, pd.DataFrame) or games.empty or "game_id" not in games.columns:
        return labels
    for _, row in games.iterrows():
        event_id = _safe(row.get("game_id"))
        if not event_id.isdigit():
            continue
        raw = (
            f"{_safe(row.get('away_abbr'), 'AWY')} @ {_safe(row.get('home_abbr'), 'HME')}"
            f" • {_safe(row.get('tip_et'), 'TBD')} • ESPN {event_id}"
        )
        try:
            game_date = date.fromisoformat(_safe(row.get("game_date"))[:10])
            labels[event_id] = format_research_matchup_label(raw, game_date)
        except Exception:
            labels[event_id] = raw
    return labels


def _render_compact_hero() -> None:
    st.markdown(
        _CSS
        + '<section class="krecv18-hero">'
        + '<div class="krecv18-kicker">NFL • RECEIVING YARDS</div>'
        + '<div class="krecv18-title">Receiver <span>Matchup Lab</span></div>'
        + '<div class="krecv18-sub">Choose a game first. The page then shows the receiving options that matter most, while keeping the certified projection and matchup analysis unchanged.</div>'
        + '</section>',
        unsafe_allow_html=True,
    )


def _render_compact_schedule(games: pd.DataFrame, day_str: str, diag: dict[str, Any]) -> str:
    if not diag.get("request_ok"):
        st.error("NFL schedule provider did not return a verified slate. Receiving Yards stays fail-closed.")
        return ""
    labels = _matchup_labels(games)
    if not labels:
        st.info("No verified NFL matchup is available for this date.")
        return ""
    options = list(labels)
    current = _safe(st.session_state.get(EVENT_KEY))
    index = options.index(current) if current in options else 0
    selected = st.selectbox(
        TOP_MATCHUP_LABEL,
        options=options,
        index=index,
        format_func=lambda value: labels.get(str(value), str(value)),
        key=EVENT_KEY,
    )
    selected = _safe(selected)
    st.session_state[EVENT_KEY] = selected
    st.markdown(
        f'<div class="krecv18-slate-note">Verified NFL slate • {escape(day_str)} • exact ESPN event IDs • Phoenix kickoff display</div>',
        unsafe_allow_html=True,
    )
    return selected


def _selected_event_row(games: pd.DataFrame, event_id: str) -> dict[str, Any]:
    if not isinstance(games, pd.DataFrame) or games.empty or "game_id" not in games.columns:
        return {}
    matches = games[games["game_id"].astype(str).str.strip() == str(event_id)]
    return matches.iloc[0].to_dict() if not matches.empty else {}


def _render_clean_player_board(games: pd.DataFrame) -> None:
    event_id = _safe(st.session_state.get(EVENT_KEY))
    if not event_id.isdigit():
        return
    context = base_page._load_receiving_context(event_id)
    if context.get("ready") is not True:
        st.warning("Receiving Yards context is not ready for this matchup. No player values were guessed.")
        return
    if context.get("data_available") is not True:
        st.info("No meaningful verified Receiving Yards player options are available for this matchup yet.")
        return

    event_row = _selected_event_row(games, event_id)
    st.markdown(
        '<div class="krecv18-match">'
        f'<b>{escape(_safe(event_row.get("away_team"), _safe(event_row.get("away_abbr"), "Away")))} @ '
        f'{escape(_safe(event_row.get("home_team"), _safe(event_row.get("home_abbr"), "Home")))}</b>'
        f'<span>{escape(_safe(event_row.get("game_date"), ""))} • ESPN {escape(event_id)} • key receiving options only</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    teams = [team for team in (context.get("teams") or []) if isinstance(team, dict)]
    teams.sort(key=lambda item: 0 if _safe(item.get("home_away")).lower() == "away" else 1)
    team_lookup = base_page._team_map(context)
    for team in teams:
        team_id = _safe(team.get("official_team_id"))
        opponent = team_lookup.get(_safe(team.get("opponent_official_team_id")), {})
        abbr = _safe(team.get("team_abbreviation"), "NFL").upper()
        name = _safe(team.get("team_name"), abbr)
        players = [player for player in (team.get("players") or []) if isinstance(player, dict)]
        st.markdown(
            '<div class="krecv2-teamhead"><div>'
            f'<b>{escape(abbr)} • {escape(name)}</b>'
            f'<span>{len(players)} key receiving option{"s" if len(players) != 1 else ""}</span>'
            '</div></div>',
            unsafe_allow_html=True,
        )
        if not players:
            continue
        cards = "".join(base_page._player_card(player, team, opponent) for player in players)
        st.markdown(f'<div class="krecv2-grid">{cards}</div>', unsafe_allow_html=True)


def _make_clean_markdown(delegate: Callable[..., Any]) -> Callable[..., Any]:
    def clean(body: Any, *args: Any, **kwargs: Any):
        if isinstance(body, str):
            if (
                'krecv2-banner' in body
                or 'Receiver Player Cards' in body
                or 'krecv2-guard' in body
            ):
                return None
            body = body.replace('<span class="krecv7-badge">Page Step 7 / 10</span>', '')
        return delegate(body, *args, **kwargs)
    return clean


def _relevant_lineup_board_html(context: dict[str, Any], event_market: dict[str, Any]) -> str:
    allowed = {
        _safe(player.get("official_athlete_id"))
        for team in (context or {}).get("teams") or []
        if isinstance(team, dict)
        for player in team.get("players") or []
        if isinstance(player, dict) and _safe(player.get("official_athlete_id")).isdigit()
    }
    reduced = dict(event_market or {})
    reduced["props"] = [
        dict(row)
        for row in (event_market or {}).get("props") or []
        if isinstance(row, dict) and _safe(row.get("official_athlete_id")) in allowed
    ]
    if not reduced["props"]:
        return ""
    html = _ORIGINAL_LINEUP_HTML_V8(context, reduced)
    return html.replace("Full FanDuel Receiving Yards lineup", "Key Receiving Yards lines").replace(
        "Full Standard Lineup", "Key Receiving Yards Lines"
    )


def _load_relevant_context(event_id: str) -> dict[str, Any]:
    context = _ORIGINAL_LOAD_V17(str(event_id))
    try:
        event_market = market_page._load_receiving_market(str(event_id))
    except Exception:
        event_market = {}
    return _filter_context_for_relevant_players(context, event_market)


def render_nfl_receiving_yards_hub() -> None:
    original_hero = base_page._render_hero_v2
    original_schedule = base_page.prior._render_schedule
    original_loader = prior._load_receiving_context_step7
    original_board = market_page._ORIGINAL_PLAYER_BOARD_V2
    original_lineup = market_page._lineup_board_html
    original_markdown = summary_page._ORIGINAL_MARKDOWN

    base_page._render_hero_v2 = _render_compact_hero
    base_page.prior._render_schedule = _render_compact_schedule
    prior._load_receiving_context_step7 = _load_relevant_context
    market_page._ORIGINAL_PLAYER_BOARD_V2 = _render_clean_player_board
    market_page._lineup_board_html = _relevant_lineup_board_html
    summary_page._ORIGINAL_MARKDOWN = _make_clean_markdown(original_markdown)
    try:
        return prior.render_nfl_receiving_yards_hub()
    finally:
        summary_page._ORIGINAL_MARKDOWN = original_markdown
        market_page._lineup_board_html = original_lineup
        market_page._ORIGINAL_PLAYER_BOARD_V2 = original_board
        prior._load_receiving_context_step7 = original_loader
        base_page.prior._render_schedule = original_schedule
        base_page._render_hero_v2 = original_hero


def render_nfl_hub(market: str = "Receiving Yards") -> None:
    if str(market or "Receiving Yards") != "Receiving Yards":
        raise ValueError("NFL Receiving Yards V18 only renders the Receiving Yards market.")
    return render_nfl_receiving_yards_hub()


__all__ = [
    "DISPLAY_ONLY_RELEVANCE_FILTER",
    "EVENT_KEY",
    "FROZEN_PRIOR",
    "MAX_RELEVANT_PER_TEAM",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "TOP_MATCHUP_LABEL",
    "_filter_context_for_relevant_players",
    "_make_clean_markdown",
    "_matchup_labels",
    "_relevant_lineup_board_html",
    "_render_compact_schedule",
    "render_nfl_hub",
    "render_nfl_receiving_yards_hub",
]
