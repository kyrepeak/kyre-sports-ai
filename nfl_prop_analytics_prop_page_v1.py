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

import html as html_lib
from typing import Any

import streamlit as st

from nfl_prop_analytics_matchup_shell_v1 import resolve_matchup_handoff
from nfl_prop_analytics_roster_truth_v1 import load_verified_roster_truth
from nfl_prop_analytics_availability_depth_v1 import load_availability_depth_truth
from nfl_prop_analytics_player_select_v1 import (
    QUERY_KEY as PLAYER_QUERY_KEY,
    build_player_handoff,
    eligible_players,
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
    return {
        "state": "ready",
        "matchup": matchup,
        "step6": step6,
        "player_handoff": player_handoff,
        "market_key": market_key,
        "market_label": market_label,
        "markets": options,
        "market_count": len(options),
    }


def open_prop_page(player_handoff: dict[str, Any]) -> None:
    st.query_params[PAGE_QUERY_KEY] = PAGE_QUERY_VALUE
    st.query_params[PLAYER_QUERY_KEY] = _text(player_handoff.get("player_id"))
    options = market_options(_text(player_handoff.get("position")))
    if options:
        st.query_params[MARKET_QUERY_KEY] = options[0][0]
    st.rerun()


def return_to_player_page() -> None:
    st.query_params[PAGE_QUERY_KEY] = "matchup"
    try:
        del st.query_params[MARKET_QUERY_KEY]
    except Exception:
        st.query_params[MARKET_QUERY_KEY] = ""
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

    if st.button(
        "← Back to player selection",
        key="nfl_prop_analytics_back_to_player_v1",
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
    options = list(context["markets"])
    keys = [key for key, _ in options]
    labels = dict(options)
    selected_key = context["market_key"]
    index = keys.index(selected_key)

    chosen_key = st.selectbox(
        "Prop market",
        options=keys,
        index=index,
        format_func=lambda key: labels[key],
        key="nfl_prop_analytics_step8_market_picker_v1",
    )
    chosen_key = _text(chosen_key)
    chosen_label = labels[chosen_key]
    try:
        st.query_params[MARKET_QUERY_KEY] = chosen_key
    except Exception:
        pass

    gate_open = bool(handoff.get("prop_analysis_gate_open"))
    gate_state = "OPEN" if gate_open else "CLOSED"
    analytics_state = "READY" if gate_open else "LOCKED"
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
         data-prop-step8-market-keys="{html_lib.escape(market_keys)}">
  <div class="ks-pa8-eyebrow">PAGE 3 • PLAYER PROP HUB</div>

  <div class="ks-pa8-hero">
    <div>
      <h2>{html_lib.escape(handoff['player_name'])}</h2>
      <div class="ks-pa8-meta">
        <span>{html_lib.escape(handoff['team'])}</span>
        <span>{html_lib.escape(handoff['position'])}</span>
        <span>{html_lib.escape(handoff['depth_role'])}</span>
        <span>ESPN ID {html_lib.escape(handoff['player_id'])}</span>
        <span>Event {html_lib.escape(handoff['event_id'])}</span>
      </div>
    </div>
    <div class="ks-pa8-gate">
      <strong>ANALYSIS GATE {gate_state}</strong>
      <span>{html_lib.escape(handoff['availability_state'])}</span>
    </div>
  </div>

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

<style data-nfl-prop-analytics-step8-css="v1">
.ks-pa8-page{{
  width:100%;max-width:100%;min-width:0;overflow-x:clip;
  margin:8px 0 34px;padding:clamp(16px,2.6vw,26px);
  border:1px solid rgba(125,211,252,.22);border-radius:19px;
  background:
    radial-gradient(circle at 91% 7%,rgba(14,165,233,.12),transparent 20rem),
    linear-gradient(145deg,rgba(5,12,21,.99),rgba(8,20,35,.97));
}}
.ks-pa8-eyebrow{{color:#7dd3fc;font-size:.68rem;font-weight:900;letter-spacing:.15em}}
.ks-pa8-hero{{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-top:10px}}
.ks-pa8-hero h2{{margin:0 0 8px;color:#f8fafc;font-size:clamp(1.55rem,4vw,2.25rem);line-height:1}}
.ks-pa8-meta{{display:flex;flex-wrap:wrap;gap:6px}}
.ks-pa8-meta span{{padding:5px 8px;border:1px solid rgba(148,163,184,.11);border-radius:999px;color:#8fa4bd;font-size:.62rem}}
.ks-pa8-gate{{display:flex;flex-direction:column;align-items:flex-end;gap:4px;text-align:right}}
.ks-pa8-gate strong{{color:#bae6fd;font-size:.73rem}}.ks-pa8-gate span{{color:#71869f;font-size:.64rem}}
.ks-pa8-market{{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-top:16px;padding:12px;border:1px solid rgba(125,211,252,.12);border-radius:13px;background:rgba(3,10,18,.42)}}
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
@media(max-width:620px){{
  .ks-pa8-hero,.ks-pa8-market{{align-items:flex-start;flex-direction:column}}
  .ks-pa8-gate{{align-items:flex-start;text-align:left}}
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
        "prop_analysis_gate_open": gate_open,
        "analytics_state": analytics_state,
    }


__all__ = [
    "MARKETS_BY_POSITION",
    "MARKET_QUERY_KEY",
    "MAY_MODIFY_EXISTING_NFL_MARKETS",
    "MAY_MODIFY_PASSING_YARDS",
    "MODEL_VERSION",
    "PAGE",
    "PAGE_QUERY_KEY",
    "PAGE_QUERY_VALUE",
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
