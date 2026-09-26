"""NFL Prop Analytics V1 — Step 8 Prop Page Shell + Market Navigation.

Final build step for the current Prop Analytics foundation. This module creates
a true Page 3 from the frozen Step 7 exact-player handoff and exposes
position-aware prop-market navigation only.

It does NOT load sportsbook lines, prices, projections, probabilities,
recommendations, or betting decisions. The frozen Step 7 prop-analysis gate is
preserved exactly: PENDING players may open Page 3 for navigation, but the
analytics surface remains LOCKED until availability is AVAILABLE.
"""
from __future__ import annotations

from datetime import date
import html as html_lib
import math
from typing import Any

import streamlit as st

from nfl_prop_analytics_matchup_shell_v1 import resolve_matchup_handoff
from nfl_prop_analytics_game_select_v1 import _handoff_kickoff_label
from nfl_prop_analytics_schedule_v1 import team_logo_url
from nfl_prop_analytics_roster_truth_v1 import load_verified_roster_truth
from nfl_prop_analytics_availability_depth_v1 import load_availability_depth_truth
from nfl_prop_analytics_player_select_v1 import (
    QUERY_KEY as PLAYER_QUERY_KEY,
    build_player_handoff,
    eligible_players,
)
from nfl_prop_analytics_history_stats_v1 import (
    load_player_history,
    summarize_history,
)

MODEL_VERSION = "NFL PROP ANALYTICS V1 • STEP 8 PROP PAGE SHELL + MARKET NAVIGATION"
STEP = 8
PAGE = 3
SHELL_NAVIGATION_ONLY = True
PLAYER_PROP_LOGIC = False
SPORTSBOOK_ODDS_LOGIC = False
PROJECTION_LOGIC = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PASSING_YARDS = False
MAY_MODIFY_EXISTING_NFL_MARKETS = False

PAGE_QUERY_KEY = "ks_pa_page"
PAGE_QUERY_VALUE = "props"
MARKET_QUERY_KEY = "ks_pa_prop"
HISTORY_QUERY_KEY = "ks_pa_history"
PAGE3_POLISH_STEP = 1
PAGE3_HERO_VERSION = "v1"
PAGE3_NAV_STEP = 2
PAGE3_NAV_VERSION = "v1"
PAGE3_STATS_STEP = 3
PAGE3_STATS_VERSION = "v1"

HISTORY_WINDOWS = (
    ("H2H", "H2H"),
    ("L5", "L5"),
    ("L10", "L10"),
    ("L20", "L20"),
    ("2026", "2026"),
    ("2025", "2025"),
)
DEFAULT_HISTORY_KEY = "L10"

MARKET_NAV_LABELS = {
    "passing_yards": "PASS YDS",
    "passing_touchdowns": "PASS TD",
    "completions": "COMP",
    "attempts": "ATT",
    "interceptions": "INT",
    "rushing_yards": "RUSH",
    "carries": "CARRIES",
    "receptions": "REC",
    "receiving_yards": "REC YDS",
    "longest_reception": "LONG REC",
    "anytime_touchdown": "TD",
}

MARKETS_BY_POSITION = {
    "QB": (
        ("passing_yards", "Passing Yards"),
        ("passing_touchdowns", "Passing Touchdowns"),
        ("interceptions", "Interceptions"),
        ("completions", "Completions"),
        ("attempts", "Pass Attempts"),
        ("rushing_yards", "Rushing Yards"),
    ),
    "RB": (
        ("rushing_yards", "Rushing Yards"),
        ("carries", "Carries"),
        ("receptions", "Receptions"),
        ("receiving_yards", "Receiving Yards"),
        ("anytime_touchdown", "Anytime Touchdown"),
    ),
    "WR": (
        ("receptions", "Receptions"),
        ("receiving_yards", "Receiving Yards"),
        ("longest_reception", "Longest Reception"),
        ("anytime_touchdown", "Anytime Touchdown"),
    ),
    "TE": (
        ("receptions", "Receptions"),
        ("receiving_yards", "Receiving Yards"),
        ("longest_reception", "Longest Reception"),
        ("anytime_touchdown", "Anytime Touchdown"),
    ),
}


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _display_date(value: Any) -> str:
    raw = _text(value)
    if not raw:
        return "DATE TBD"
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return raw
    return f"{parsed.strftime('%a • %b').upper()} {parsed.day}"


def _player_headshot_url(player: dict[str, Any], player_id: str) -> str:
    explicit = _text(player.get("headshot_url"))
    if explicit:
        return explicit
    athlete_id = _text(player_id)
    if athlete_id.isdigit():
        return f"https://a.espncdn.com/i/headshots/nfl/players/full/{athlete_id}.png"
    return ""


def _query_value(key: str) -> str:
    try:
        raw = st.query_params.get(key, "")
    except Exception:
        return ""
    if isinstance(raw, list):
        return str(raw[0] if raw else "")
    return str(raw or "")


def is_prop_page() -> bool:
    return _query_value(PAGE_QUERY_KEY).strip().lower() == PAGE_QUERY_VALUE


def market_options(position: str) -> tuple[tuple[str, str], ...]:
    return MARKETS_BY_POSITION.get(_text(position).upper(), ())


def _market_key_valid(position: str, market_key: str) -> bool:
    return _text(market_key) in {key for key, _ in market_options(position)}


def _resolve_market_key(position: str, requested: str | None) -> str:
    options = market_options(position)
    if not options:
        return ""
    requested = _text(requested)
    if _market_key_valid(position, requested):
        return requested
    return options[0][0]


def _history_key_valid(value: str) -> bool:
    return _text(value) in {key for key, _ in HISTORY_WINDOWS}


def _resolve_history_key(requested: str | None) -> str:
    requested = _text(requested)
    if _history_key_valid(requested):
        return requested
    return DEFAULT_HISTORY_KEY


def _market_nav_label(market_key: str, fallback: str) -> str:
    return MARKET_NAV_LABELS.get(_text(market_key), _text(fallback).upper())


def _anchor_season(matchup: dict[str, Any]) -> int:
    raw = _text(matchup.get("target_date"))
    if len(raw) >= 4 and raw[:4].isdigit():
        return int(raw[:4])
    for record in matchup.get("source_records") or []:
        if not isinstance(record, dict):
            continue
        try:
            season = int(record.get("season") or 0)
        except (TypeError, ValueError):
            season = 0
        if season >= 2000:
            return season
    return 0


def _format_stat(value: Any, *, average: bool = False) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(number):
        return "—"
    if average:
        return f"{number:.1f}"
    if abs(number - round(number)) < 1e-9:
        return str(int(round(number)))
    return f"{number:.1f}"


def resolve_prop_page_context() -> dict[str, Any]:
    matchup = resolve_matchup_handoff()
    if not matchup or matchup.get("state") != "ready":
        return {"state": "fail-closed", "reason": "verified matchup handoff missing"}

    roster = load_verified_roster_truth(matchup)
    if roster.get("state") != "live":
        return {
            "state": "fail-closed",
            "reason": "frozen Step 5 roster truth not live",
            "matchup": matchup,
        }

    step6 = load_availability_depth_truth(matchup, roster)
    if step6.get("state") != "live":
        return {
            "state": "fail-closed",
            "reason": "frozen Step 6 availability/depth truth not live",
            "matchup": matchup,
            "roster": roster,
        }

    players = eligible_players(step6)
    requested_player = _query_value(PLAYER_QUERY_KEY)
    selected = next(
        (row for row in players if _text(row.get("espn_id")) == requested_player),
        None,
    )
    if selected is None:
        return {
            "state": "fail-closed",
            "reason": "exact Step 7 player id is not eligible",
            "matchup": matchup,
            "step6": step6,
            "candidate_count": len(players),
        }

    player_handoff = build_player_handoff(matchup, step6, selected)
    position = player_handoff["position"]
    options = market_options(position)
    if not options:
        return {
            "state": "fail-closed",
            "reason": "position has no Step 8 market navigation contract",
            "matchup": matchup,
            "step6": step6,
            "player_handoff": player_handoff,
        }

    market_key = _resolve_market_key(position, _query_value(MARKET_QUERY_KEY))
    market_label = dict(options)[market_key]
    history_key = _resolve_history_key(_query_value(HISTORY_QUERY_KEY))
    history_label = dict(HISTORY_WINDOWS)[history_key]
    return {
        "state": "ready",
        "matchup": matchup,
        "step6": step6,
        "player_handoff": player_handoff,
        "selected_player": selected,
        "market_key": market_key,
        "market_label": market_label,
        "markets": options,
        "market_count": len(options),
        "history_key": history_key,
        "history_label": history_label,
        "history_windows": HISTORY_WINDOWS,
    }


def open_prop_page(player_handoff: dict[str, Any]) -> None:
    st.query_params[PAGE_QUERY_KEY] = PAGE_QUERY_VALUE
    st.query_params[PLAYER_QUERY_KEY] = _text(player_handoff.get("player_id"))
    options = market_options(_text(player_handoff.get("position")))
    if options:
        st.query_params[MARKET_QUERY_KEY] = options[0][0]
    st.query_params[HISTORY_QUERY_KEY] = DEFAULT_HISTORY_KEY
    st.rerun()


def return_to_player_page() -> None:
    st.query_params[PAGE_QUERY_KEY] = "matchup"
    try:
        del st.query_params[MARKET_QUERY_KEY]
    except Exception:
        st.query_params[MARKET_QUERY_KEY] = ""
    try:
        del st.query_params[HISTORY_QUERY_KEY]
    except Exception:
        st.query_params[HISTORY_QUERY_KEY] = ""
    st.rerun()


def render_prop_page_open_control(player_handoff: dict[str, Any] | None) -> None:
    if not isinstance(player_handoff, dict) or player_handoff.get("state") != "ready":
        return
    if st.button(
        "Open prop page",
        key="nfl_prop_analytics_open_prop_page_v1",
        use_container_width=True,
    ):
        open_prop_page(player_handoff)


def render_prop_page_shell() -> dict[str, Any]:
    context = resolve_prop_page_context()

    nav_left, nav_spacer, nav_right = st.columns([1.05, 5.0, 1.6])
    with nav_left:
        if st.button(
            "✕",
            key="nfl_prop_analytics_page3_close_v1",
            use_container_width=True,
        ):
            return_to_player_page()
    with nav_right:
        if st.button(
            "Matchup ›",
            key="nfl_prop_analytics_page3_matchup_v1",
            use_container_width=True,
        ):
            return_to_player_page()

    if context.get("state") != "ready":
        st.markdown(
            f"""
<section data-nfl-prop-analytics-step8-prop-page="v1"
         data-prop-step8-state="fail-closed">
  <div class="ks-pa8-empty">
    <strong>Prop page context is not ready.</strong>
    <span>{html_lib.escape(str(context.get('reason') or 'Frozen handoff chain is incomplete.'))}</span>
  </div>
</section>
""",
            unsafe_allow_html=True,
        )
        return context

    handoff = context["player_handoff"]
    player = context.get("selected_player") or {}
    matchup = context["matchup"]
    options = list(context["markets"])
    keys = [key for key, _ in options]
    labels = dict(options)
    selected_key = context["market_key"]
    initial_label = labels[selected_key]

    player_team = _text(handoff.get("team")).upper()
    away = _text(matchup.get("away")).upper()
    home = _text(matchup.get("home")).upper()
    if player_team == away:
        opponent = home
        player_team_name = _text(matchup.get("away_name")) or away
        opponent_name = _text(matchup.get("home_name")) or home
    else:
        opponent = away
        player_team_name = _text(matchup.get("home_name")) or home
        opponent_name = _text(matchup.get("away_name")) or away

    headshot = _player_headshot_url(player, handoff["player_id"])
    player_logo = team_logo_url(player_team)
    opponent_logo = team_logo_url(opponent)
    kickoff = _handoff_kickoff_label(matchup)
    display_date = _display_date(matchup.get("target_date"))
    network = _text(matchup.get("network")) or "Network TBD"
    venue = _text(matchup.get("venue")) or "Venue TBD"
    gate_open = bool(handoff.get("prop_analysis_gate_open"))
    gate_state = "OPEN" if gate_open else "CLOSED"
    analytics_state = "READY" if gate_open else "LOCKED"

    st.markdown(
        f"""
<section class="ks-pa3-hero"
         data-prop-page3-step1-hero="{PAGE3_HERO_VERSION}"
         data-prop-page3-player-id="{html_lib.escape(handoff['player_id'])}"
         data-prop-page3-player-team="{html_lib.escape(player_team)}"
         data-prop-page3-opponent="{html_lib.escape(opponent)}"
         data-prop-page3-kickoff="{html_lib.escape(kickoff)}"
         data-prop-page3-market-label="{html_lib.escape(initial_label)}">
  <div class="ks-pa3-hero-glow ks-pa3-hero-glow-left"></div>
  <div class="ks-pa3-hero-glow ks-pa3-hero-glow-right"></div>

  <div class="ks-pa3-team ks-pa3-team-left">
    <img class="ks-pa3-team-logo"
         data-prop-page3-team-logo="player"
         src="{html_lib.escape(player_logo)}"
         alt="{html_lib.escape(player_team_name)} logo">
    <div class="ks-pa3-team-copy">
      <span>{html_lib.escape(player_team)}</span>
      <strong>{html_lib.escape(player_team_name)}</strong>
    </div>
  </div>

  <div class="ks-pa3-player">
    <div class="ks-pa3-headshot-wrap">
      <img class="ks-pa3-headshot"
           data-prop-page3-player-headshot="{PAGE3_HERO_VERSION}"
           src="{html_lib.escape(headshot)}"
           alt="{html_lib.escape(handoff['player_name'])} headshot">
      <img class="ks-pa3-headshot-logo"
           src="{html_lib.escape(player_logo)}"
           alt="">
    </div>
    <div class="ks-pa3-player-copy">
      <div class="ks-pa3-player-line">
        <h1>{html_lib.escape(handoff['player_name'])}</h1>
        <span>{html_lib.escape(handoff['position'])}</span>
      </div>
      <p>{html_lib.escape(handoff['player_name'])} • {html_lib.escape(initial_label)}</p>
      <div class="ks-pa3-player-meta">
        <span>{html_lib.escape(handoff['depth_role'])}</span>
        <span>ESPN ID {html_lib.escape(handoff['player_id'])}</span>
        <span class="ks-pa3-gate-pill">ANALYSIS {gate_state}</span>
      </div>
    </div>
  </div>

  <div class="ks-pa3-team ks-pa3-team-right">
    <div class="ks-pa3-team-copy">
      <span>{html_lib.escape(opponent)}</span>
      <strong>{html_lib.escape(opponent_name)}</strong>
    </div>
    <img class="ks-pa3-team-logo"
         data-prop-page3-team-logo="opponent"
         src="{html_lib.escape(opponent_logo)}"
         alt="{html_lib.escape(opponent_name)} logo">
  </div>

  <div class="ks-pa3-matchup-strip">
    <span>{html_lib.escape(display_date)}</span>
    <strong>{html_lib.escape(kickoff)}</strong>
    <span>{html_lib.escape(network)}</span>
    <span>{html_lib.escape(venue)}</span>
  </div>
</section>
""",
        unsafe_allow_html=True,
    )

    history_options = list(context["history_windows"])
    history_keys = [key for key, _ in history_options]
    history_labels = dict(history_options)
    selected_history_key = context["history_key"]
    selected_history_label = history_labels[selected_history_key]

    st.markdown(
        f"""
<div class="ks-pa3-nav-marker"
     data-prop-page3-step2-navigation="{PAGE3_NAV_VERSION}"
     data-prop-page3-step2-market="{html_lib.escape(selected_key)}"
     data-prop-page3-step2-history="{html_lib.escape(selected_history_key)}"
     data-prop-page3-step2-market-count="{len(keys)}"
     data-prop-page3-step2-history-count="{len(history_keys)}">
</div>
""",
        unsafe_allow_html=True,
    )

    chosen_history_label = st.segmented_control(
        "History window",
        options=[history_labels[key] for key in history_keys],
        default=selected_history_label,
        selection_mode="single",
        key="nfl_prop_analytics_page3_step2_history_nav_v1",
    )
    chosen_history_label = (
        chosen_history_label
        if chosen_history_label in history_labels.values()
        else selected_history_label
    )
    chosen_history_key = next(
        key for key, label in history_options if label == chosen_history_label
    )
    try:
        st.query_params[HISTORY_QUERY_KEY] = chosen_history_key
    except Exception:
        pass

    market_nav_labels = {
        key: _market_nav_label(key, labels[key])
        for key in keys
    }
    chosen_market_nav_label = st.segmented_control(
        "Prop category",
        options=[market_nav_labels[key] for key in keys],
        default=market_nav_labels[selected_key],
        selection_mode="single",
        key="nfl_prop_analytics_page3_step2_market_nav_v1",
    )
    chosen_market_nav_label = (
        chosen_market_nav_label
        if chosen_market_nav_label in market_nav_labels.values()
        else market_nav_labels[selected_key]
    )
    chosen_key = next(
        key for key in keys if market_nav_labels[key] == chosen_market_nav_label
    )
    chosen_label = labels[chosen_key]
    try:
        st.query_params[MARKET_QUERY_KEY] = chosen_key
    except Exception:
        pass

    st.markdown(
        f"""
<div class="ks-pa3-nav-state"
     data-prop-page3-step2-nav-state="ready"
     data-prop-page3-step2-active-market="{html_lib.escape(chosen_key)}"
     data-prop-page3-step2-active-history="{html_lib.escape(chosen_history_key)}"
     data-prop-page3-step2-market-options="{html_lib.escape(','.join(keys))}"
     data-prop-page3-step2-history-options="{html_lib.escape(','.join(history_keys))}">
</div>
""",
        unsafe_allow_html=True,
    )

    history_payload = load_player_history(
        official_event_id=handoff["event_id"],
        official_athlete_id=handoff["player_id"],
        player_team=player_team,
        opponent=opponent,
        anchor_season=_anchor_season(matchup),
        history_key=chosen_history_key,
        market_key=chosen_key,
    )
    history_summary = summarize_history(history_payload.get("games") or [])
    history_ready = (
        history_payload.get("ready") is True
        and history_payload.get("data_available") is True
        and history_summary.get("ready") is True
    )
    history_state = "ready" if history_ready else "unavailable"
    sample_size = int(history_summary.get("sample_size") or 0)
    source_note = _text(history_payload.get("source")) or "ESPN exact-ID completed game books"
    history_reason = _text(history_payload.get("reason"))

    if history_ready:
        hit_state = _text(history_summary.get("hit_rate_state")) or "awaiting-line"
        hit_value = (
            f"{float(history_summary['hit_rate_pct']):.0f}%"
            if history_summary.get("hit_rate_pct") is not None
            else "—"
        )
        hit_note = (
            f"{int(history_summary['hit_count'])}/{sample_size} OVER"
            if history_summary.get("hit_count") is not None
            else "LINE REQUIRED • STEP 4"
        )
        st.markdown(
            f"""
<section class="ks-pa3-stats"
         data-prop-page3-step3-stats="{PAGE3_STATS_VERSION}"
         data-prop-page3-step3-state="ready"
         data-prop-page3-step3-market="{html_lib.escape(chosen_key)}"
         data-prop-page3-step3-history="{html_lib.escape(chosen_history_key)}"
         data-prop-page3-step3-sample="{sample_size}"
         data-prop-page3-step3-hit-rate-state="{html_lib.escape(hit_state)}">
  <div class="ks-pa3-stats-head">
    <div>
      <span>HISTORICAL STATISTICS</span>
      <strong>{html_lib.escape(chosen_label)} • {html_lib.escape(history_labels[chosen_history_key])}</strong>
    </div>
    <em>HISTORICAL ONLY • {html_lib.escape(source_note)}</em>
  </div>
  <div class="ks-pa3-stat-grid">
    <article><span>GAMES</span><strong>{sample_size}</strong><small>VERIFIED SAMPLE</small></article>
    <article><span>AVERAGE</span><strong>{_format_stat(history_summary.get("average"), average=True)}</strong><small>{html_lib.escape(chosen_label.upper())}</small></article>
    <article><span>MEDIAN</span><strong>{_format_stat(history_summary.get("median"), average=True)}</strong><small>MIDDLE RESULT</small></article>
    <article><span>HIGH</span><strong>{_format_stat(history_summary.get("high"))}</strong><small>SAMPLE HIGH</small></article>
    <article><span>LOW</span><strong>{_format_stat(history_summary.get("low"))}</strong><small>SAMPLE LOW</small></article>
    <article class="ks-pa3-hit-card"
             data-prop-page3-step3-hit-rate="awaiting-line">
      <span>HIT RATE</span><strong>{hit_value}</strong><small>{html_lib.escape(hit_note)}</small>
    </article>
  </div>
</section>
""",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
<section class="ks-pa3-stats ks-pa3-stats-unavailable"
         data-prop-page3-step3-stats="{PAGE3_STATS_VERSION}"
         data-prop-page3-step3-state="unavailable"
         data-prop-page3-step3-market="{html_lib.escape(chosen_key)}"
         data-prop-page3-step3-history="{html_lib.escape(chosen_history_key)}"
         data-prop-page3-step3-sample="0"
         data-prop-page3-step3-hit-rate-state="no-data">
  <div class="ks-pa3-stats-head">
    <div>
      <span>HISTORICAL STATISTICS</span>
      <strong>Exact-ID history unavailable</strong>
    </div>
    <em>FAIL CLOSED</em>
  </div>
  <p>{html_lib.escape(history_reason or "No exact-ID completed game-book rows for this player/window/market.")}</p>
</section>
""",
            unsafe_allow_html=True,
        )

    market_keys = ",".join(keys)

    st.markdown(
        f"""
<section class="ks-pa8-page"
         data-nfl-prop-analytics-step8-prop-page="v1"
         data-prop-step8-state="ready"
         data-prop-step8-page="3"
         data-prop-step8-selection="{html_lib.escape(handoff['selection_key'])}"
         data-prop-step8-event-id="{html_lib.escape(handoff['event_id'])}"
         data-prop-step8-player-id="{html_lib.escape(handoff['player_id'])}"
         data-prop-step8-player-team="{html_lib.escape(handoff['team'])}"
         data-prop-step8-player-position="{html_lib.escape(handoff['position'])}"
         data-prop-step8-availability="{html_lib.escape(handoff['availability_state'])}"
         data-prop-step8-prop-gate="{gate_state}"
         data-prop-step8-analytics-state="{analytics_state}"
         data-prop-step8-market="{html_lib.escape(chosen_key)}"
         data-prop-step8-market-label="{html_lib.escape(chosen_label)}"
         data-prop-step8-market-count="{len(options)}"
         data-prop-step8-market-keys="{html_lib.escape(market_keys)}"
         data-prop-page3-step2-history="{html_lib.escape(chosen_history_key)}"
         data-prop-page3-step3-history-state="{html_lib.escape(history_state)}"
         data-prop-page3-step3-sample="{sample_size}">
  <div class="ks-pa8-eyebrow">PAGE 3 • PLAYER PROP HUB</div>

  <div class="ks-pa8-market">
    <div>
      <span class="ks-pa8-kicker">SELECTED MARKET</span>
      <strong>{html_lib.escape(chosen_label)}</strong>
    </div>
    <span>{len(options)} markets available for {html_lib.escape(handoff['position'])} navigation</span>
  </div>

  <div class="ks-pa8-shell"
       data-prop-step8-shell-content="navigation-only">
    <div class="ks-pa8-shell-head">
      <strong>{html_lib.escape(chosen_label)} analytics shell</strong>
      <span>{analytics_state}</span>
    </div>
    <p>
      {"Player is game-day cleared. Analytics data is intentionally not implemented in Step 8."
       if gate_open
       else "Game-day availability is still pending. Market navigation is available, but analytics remain locked."}
    </p>
    <div class="ks-pa8-zero-data"
         data-prop-step8-sportsbook-lines="0"
         data-prop-step8-odds="0"
         data-prop-step8-projections="0"
         data-prop-step8-recommendations="0">
      No sportsbook lines • No odds • No projections • No recommendations
    </div>
  </div>
</section>

<style data-nfl-prop-analytics-page8-css="v1">
.ks-route,.ks-prop-analytics-v1{{display:none!important}}
.ks-pa3-nav-marker,.ks-pa3-nav-state{{display:none!important}}
div[data-testid="stSegmentedControl"]{{margin:.08rem 0 .4rem}}
div[data-testid="stSegmentedControl"] [role="radiogroup"]{{
  display:flex;gap:3px;width:100%;padding:4px;
  border:1px solid rgba(125,211,252,.16);border-radius:13px;
  background:linear-gradient(180deg,rgba(5,13,24,.96),rgba(4,10,18,.98));
  box-shadow:inset 0 1px 0 rgba(255,255,255,.025);
}}
div[data-testid="stSegmentedControl"] button{{
  min-height:42px!important;flex:1 1 0!important;
  border-radius:9px!important;border:1px solid transparent!important;
  color:#91a4bc!important;background:transparent!important;
  font-size:.69rem!important;font-weight:850!important;letter-spacing:.035em!important;
}}
div[data-testid="stSegmentedControl"] button[aria-checked="true"]{{
  color:#effaff!important;border-color:rgba(56,189,248,.65)!important;
  background:linear-gradient(180deg,rgba(14,165,233,.26),rgba(2,132,199,.13))!important;
  box-shadow:0 0 0 1px rgba(56,189,248,.18),0 0 18px rgba(14,165,233,.16)!important;
}}
div[data-testid="stSegmentedControl"] label{{color:#7990aa!important;font-size:.58rem!important;font-weight:850!important;letter-spacing:.08em!important;text-transform:uppercase!important}}

.ks-pa3-hero{{
  position:relative;isolation:isolate;overflow:hidden;
  width:100%;max-width:100%;min-width:0;margin:6px 0 14px;
  padding:18px 20px 14px;border:1px solid rgba(125,211,252,.22);
  border-radius:20px;
  background:
    linear-gradient(180deg,rgba(4,12,23,.90),rgba(3,10,18,.98)),
    radial-gradient(circle at 50% -20%,rgba(14,165,233,.18),transparent 46%);
  box-shadow:0 16px 44px rgba(0,0,0,.22),inset 0 1px 0 rgba(255,255,255,.035);
  display:grid;grid-template-columns:minmax(150px,.75fr) minmax(280px,1.8fr) minmax(150px,.75fr);
  align-items:center;gap:16px;
}}
.ks-pa3-hero-glow{{position:absolute;z-index:-1;top:0;width:38%;height:3px;filter:blur(.2px)}}
.ks-pa3-hero-glow-left{{left:0;background:linear-gradient(90deg,#0ea5e9,transparent)}}
.ks-pa3-hero-glow-right{{right:0;background:linear-gradient(270deg,#38bdf8,transparent)}}
.ks-pa3-team{{display:flex;align-items:center;gap:10px;min-width:0}}
.ks-pa3-team-right{{justify-content:flex-end;text-align:right}}
.ks-pa3-team-logo{{width:58px;height:58px;object-fit:contain;flex:0 0 58px;filter:drop-shadow(0 7px 12px rgba(0,0,0,.30))}}
.ks-pa3-team-copy{{display:flex;flex-direction:column;min-width:0}}
.ks-pa3-team-copy span{{color:#7dd3fc;font-size:.63rem;font-weight:900;letter-spacing:.09em}}
.ks-pa3-team-copy strong{{margin-top:2px;color:#e8f1fb;font-size:.82rem;line-height:1.05}}
.ks-pa3-player{{display:flex;align-items:center;justify-content:center;gap:14px;min-width:0}}
.ks-pa3-headshot-wrap{{position:relative;flex:0 0 76px;width:76px;height:76px;border-radius:50%;padding:3px;background:linear-gradient(135deg,#22d3ee,#2563eb 55%,#7c3aed);box-shadow:0 0 0 4px rgba(14,165,233,.08),0 0 28px rgba(14,165,233,.20)}}
.ks-pa3-headshot{{width:100%;height:100%;object-fit:cover;object-position:top center;border-radius:50%;background:#08111e}}
.ks-pa3-headshot-logo{{position:absolute;right:-7px;bottom:-3px;width:31px;height:31px;object-fit:contain;filter:drop-shadow(0 4px 6px rgba(0,0,0,.45))}}
.ks-pa3-player-copy{{min-width:0}}
.ks-pa3-player-line{{display:flex;align-items:flex-end;gap:8px;min-width:0}}
.ks-pa3-player-line h1{{margin:0;color:#f8fafc;font-size:clamp(1.55rem,3.4vw,2.45rem);line-height:.95;letter-spacing:-.04em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.ks-pa3-player-line>span{{color:#a9bbcf;font-size:.76rem;font-weight:900}}
.ks-pa3-player-copy p{{margin:5px 0 0;color:#a9bbcf;font-size:.78rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.ks-pa3-player-meta{{display:flex;flex-wrap:wrap;gap:5px;margin-top:8px}}
.ks-pa3-player-meta span{{padding:4px 7px;border:1px solid rgba(125,211,252,.12);border-radius:999px;color:#7890ab;background:rgba(14,165,233,.035);font-size:.52rem;font-weight:800}}
.ks-pa3-player-meta .ks-pa3-gate-pill{{color:#bae6fd;border-color:rgba(56,189,248,.24)}}
.ks-pa3-matchup-strip{{grid-column:1/-1;display:flex;justify-content:center;flex-wrap:wrap;gap:6px;margin-top:4px;padding-top:10px;border-top:1px solid rgba(148,163,184,.08)}}
.ks-pa3-matchup-strip span,.ks-pa3-matchup-strip strong{{padding:4px 7px;border-radius:999px;font-size:.55rem}}
.ks-pa3-matchup-strip span{{color:#7288a2;background:rgba(15,23,42,.34)}}
.ks-pa3-matchup-strip strong{{color:#d9f3ff;background:rgba(14,165,233,.07)}}

.ks-pa3-stats{{
  width:100%;max-width:100%;min-width:0;margin:10px 0 12px;padding:13px;
  border:1px solid rgba(125,211,252,.15);border-radius:15px;
  background:linear-gradient(180deg,rgba(6,15,27,.95),rgba(3,10,18,.98));
}}
.ks-pa3-stats-head{{display:flex;align-items:flex-end;justify-content:space-between;gap:10px;margin-bottom:10px}}
.ks-pa3-stats-head>div{{display:flex;flex-direction:column;gap:2px;min-width:0}}
.ks-pa3-stats-head span{{color:#6f839c;font-size:.54rem;font-weight:900;letter-spacing:.12em}}
.ks-pa3-stats-head strong{{color:#e5f5ff;font-size:.82rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.ks-pa3-stats-head em{{color:#60758d;font-size:.49rem;font-style:normal;font-weight:800;text-align:right}}
.ks-pa3-stat-grid{{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:6px}}
.ks-pa3-stat-grid article{{min-width:0;padding:10px 8px;border:1px solid rgba(148,163,184,.09);border-radius:11px;background:rgba(15,23,42,.42);display:flex;flex-direction:column;gap:3px}}
.ks-pa3-stat-grid article>span{{color:#6f839c;font-size:.48rem;font-weight:900;letter-spacing:.08em}}
.ks-pa3-stat-grid article>strong{{color:#f8fafc;font-size:1.18rem;line-height:1}}
.ks-pa3-stat-grid article>small{{color:#60758d;font-size:.44rem;font-weight:800;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.ks-pa3-stat-grid .ks-pa3-hit-card{{border-color:rgba(56,189,248,.20);background:linear-gradient(180deg,rgba(14,165,233,.09),rgba(15,23,42,.42))}}
.ks-pa3-stat-grid .ks-pa3-hit-card>strong{{color:#7dd3fc}}
.ks-pa3-stats-unavailable{{border-color:rgba(248,113,113,.16)}}
.ks-pa3-stats-unavailable p{{margin:0;color:#8295aa;font-size:.62rem;line-height:1.45}}

.ks-pa8-page{{
  width:100%;max-width:100%;min-width:0;overflow-x:clip;
  margin:8px 0 34px;padding:clamp(16px,2.6vw,26px);
  border:1px solid rgba(125,211,252,.22);border-radius:19px;
  background:
    radial-gradient(circle at 91% 7%,rgba(14,165,233,.12),transparent 20rem),
    linear-gradient(145deg,rgba(5,12,21,.99),rgba(8,20,35,.97));
}}
.ks-pa8-eyebrow{{color:#7dd3fc;font-size:.68rem;font-weight:900;letter-spacing:.15em}}
.ks-pa8-market{{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-top:10px;padding:12px;border:1px solid rgba(125,211,252,.12);border-radius:13px;background:rgba(3,10,18,.42)}}
.ks-pa8-market div{{display:flex;flex-direction:column;gap:2px}}
.ks-pa8-kicker{{color:#6f839c;font-size:.55rem;font-weight:900;letter-spacing:.12em}}
.ks-pa8-market strong{{color:#e0f2fe;font-size:.9rem}}.ks-pa8-market>span{{color:#7890ab;font-size:.63rem;text-align:right}}
.ks-pa8-shell{{margin-top:12px;padding:16px;border:1px solid rgba(148,163,184,.10);border-radius:14px;background:rgba(15,23,42,.42)}}
.ks-pa8-shell-head{{display:flex;justify-content:space-between;gap:10px}}
.ks-pa8-shell-head strong{{color:#f1f5f9;font-size:.8rem}}.ks-pa8-shell-head span{{color:#7dd3fc;font-size:.63rem;font-weight:900}}
.ks-pa8-shell p{{margin:8px 0;color:#91a4bc;font-size:.72rem;line-height:1.5}}
.ks-pa8-zero-data{{padding-top:9px;border-top:1px solid rgba(148,163,184,.09);color:#657b94;font-size:.6rem}}
.ks-pa8-empty{{padding:15px;border:1px solid rgba(248,113,113,.3);border-radius:14px;background:rgba(127,29,29,.12);display:flex;flex-direction:column;gap:4px}}
.ks-pa8-empty strong{{color:#fecaca}}.ks-pa8-empty span{{color:#cbd5e1;font-size:.78rem}}

@media(max-width:760px){{
  .ks-pa3-stat-grid{{grid-template-columns:repeat(3,minmax(0,1fr))}}
  .ks-pa3-hero{{grid-template-columns:1fr minmax(250px,1.5fr) 1fr;gap:10px;padding:15px 12px 12px}}
  .ks-pa3-team-logo{{width:46px;height:46px;flex-basis:46px}}
  .ks-pa3-team-copy strong{{font-size:.68rem}}
  .ks-pa3-headshot-wrap{{width:64px;height:64px;flex-basis:64px}}
}}
@media(max-width:760px){{
  div[data-testid="stSegmentedControl"] button{{min-height:44px!important;font-size:.62rem!important;padding-left:.42rem!important;padding-right:.42rem!important}}
}}
@media(max-width:560px){{
  .ks-pa3-stats-head{{align-items:flex-start;flex-direction:column}}
  .ks-pa3-stats-head em{{text-align:left}}
  .ks-pa3-stat-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}
  div[data-testid="stSegmentedControl"] [role="radiogroup"]{{overflow-x:auto;justify-content:flex-start}}
  div[data-testid="stSegmentedControl"] button{{flex:0 0 auto!important;min-width:58px!important;min-height:46px!important}}
  .ks-pa3-hero{{grid-template-columns:1fr 1fr;padding:14px 11px}}
  .ks-pa3-player{{grid-column:1/-1;grid-row:1;justify-content:flex-start}}
  .ks-pa3-team{{grid-row:2;margin-top:5px}}
  .ks-pa3-team-right{{justify-content:flex-end}}
  .ks-pa3-matchup-strip{{grid-row:3}}
  .ks-pa3-player-line h1{{font-size:1.48rem}}
  .ks-pa3-player-copy p{{font-size:.7rem}}
  .ks-pa3-team-logo{{width:40px;height:40px;flex-basis:40px}}
  .ks-pa8-market{{align-items:flex-start;flex-direction:column}}
  .ks-pa8-market>span{{text-align:left}}
}}
</style>
""",
        unsafe_allow_html=True,
    )
    return {
        **context,
        "market_key": chosen_key,
        "market_label": chosen_label,
        "history_key": chosen_history_key,
        "history_label": history_labels[chosen_history_key],
        "history_payload": history_payload,
        "history_summary": history_summary,
        "prop_analysis_gate_open": gate_open,
        "analytics_state": analytics_state,
    }


__all__ = [
    "HISTORY_QUERY_KEY",
    "HISTORY_WINDOWS",
    "MARKETS_BY_POSITION",
    "MARKET_QUERY_KEY",
    "MARKET_NAV_LABELS",
    "MAY_MODIFY_EXISTING_NFL_MARKETS",
    "MAY_MODIFY_PASSING_YARDS",
    "MODEL_VERSION",
    "PAGE",
    "PAGE_QUERY_KEY",
    "PAGE_QUERY_VALUE",
    "PAGE3_HERO_VERSION",
    "PAGE3_NAV_STEP",
    "PAGE3_NAV_VERSION",
    "PAGE3_POLISH_STEP",
    "PAGE3_STATS_STEP",
    "PAGE3_STATS_VERSION",
    "PLAYER_PROP_LOGIC",
    "PROJECTION_LOGIC",
    "SHELL_NAVIGATION_ONLY",
    "SPORTSBOOK_ODDS_LOGIC",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP",
    "is_prop_page",
    "market_options",
    "open_prop_page",
    "render_prop_page_open_control",
    "render_prop_page_shell",
    "resolve_prop_page_context",
    "return_to_player_page",
]
