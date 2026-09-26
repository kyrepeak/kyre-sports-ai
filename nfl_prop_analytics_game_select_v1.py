"""NFL Prop Analytics V1 — Step 3 Game Selection + Matchup Handoff.

Consumes the frozen Step 2 schedule truth API. Owns only the user's verified
game selection and a small handoff payload for future Page 2 work. No roster,
player prop, sportsbook, projection, or Passing Yards logic lives here.
"""
from __future__ import annotations

from datetime import datetime
import html as html_lib
from typing import Any

import streamlit as st

from nfl_prop_analytics_schedule_v1 import load_schedule_truth

MODEL_VERSION = "NFL PROP ANALYTICS V1 • STEP 3 GAME SELECTION + MATCHUP HANDOFF"
STEP = 3
PAGE = 1
SELECTION_ONLY = True
PLAYER_PROP_LOGIC = False
ROSTER_LOGIC = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PASSING_YARDS = False
MAY_MODIFY_EXISTING_NFL_MARKETS = False

SESSION_KEY = "nfl_prop_analytics_selected_game_v1"
QUERY_KEY = "ks_pa_game"
HANDOFF_VERSION = "v1"


def _selection_key(game: dict[str, Any]) -> str:
    return f"{game['away']}-{game['home']}"


def _eligible_games(truth: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        game
        for game in truth.get("games", [])
        if bool(game.get("verified"))
        and game.get("away")
        and game.get("home")
    ]


def _game_label(game: dict[str, Any]) -> str:
    kickoff = game.get("kickoff_utc")
    kickoff_label = "Time TBD"
    if isinstance(kickoff, datetime):
        kickoff_label = kickoff.strftime("%-I:%M %p ET")
    network = str(game.get("network") or "Network TBD")
    return (
        f"{game['away']} {game.get('away_name', game['away'])} @ "
        f"{game['home']} {game.get('home_name', game['home'])} • "
        f"{kickoff_label} • {network}"
    )


def _resolve_initial_index(
    games: list[dict[str, Any]],
    requested_key: str | None,
    session_key: str | None,
) -> int:
    candidates = [
        str(requested_key or "").strip().upper(),
        str(session_key or "").strip().upper(),
    ]
    keys = [_selection_key(game).upper() for game in games]
    for candidate in candidates:
        if candidate in keys:
            return keys.index(candidate)
    return 0


def build_matchup_handoff(
    game: dict[str, Any],
    target_date: str,
) -> dict[str, Any]:
    kickoff = game.get("kickoff_utc")
    kickoff_iso = kickoff.isoformat() if isinstance(kickoff, datetime) else ""
    return {
        "version": HANDOFF_VERSION,
        "state": "ready",
        "selection_key": _selection_key(game),
        "away": game["away"],
        "home": game["home"],
        "away_name": game.get("away_name", game["away"]),
        "home_name": game.get("home_name", game["home"]),
        "target_date": target_date,
        "kickoff_utc": kickoff_iso,
        "week": game.get("week"),
        "network": game.get("network", ""),
        "venue": game.get("venue", ""),
        "game_id": game.get("game_id", ""),
        "sources": tuple(game.get("sources") or ()),
        "source_count": int(game.get("source_count") or 0),
        "verified": bool(game.get("verified")),
    }


def get_selected_game_handoff() -> dict[str, Any] | None:
    value = st.session_state.get(SESSION_KEY)
    if isinstance(value, dict) and value.get("state") == "ready":
        return dict(value)
    return None


def _query_param_value() -> str:
    try:
        raw = st.query_params.get(QUERY_KEY, "")
    except Exception:
        return ""
    if isinstance(raw, list):
        return str(raw[0] if raw else "")
    return str(raw or "")


def _persist_query(selection_key: str) -> None:
    try:
        st.query_params[QUERY_KEY] = selection_key
    except Exception:
        # Query persistence is useful for deep-link continuity but selection
        # remains authoritative in session state if Streamlit changes APIs.
        pass


def render_game_selection_handoff() -> dict[str, Any] | None:
    truth = load_schedule_truth()
    games = _eligible_games(truth)

    if not games:
        st.session_state.pop(SESSION_KEY, None)
        st.markdown(
            """
<section data-nfl-prop-analytics-step3-selection="v1"
         data-prop-selection-state="fail-closed"
         data-prop-handoff-state="not-ready">
  <div class="ks-pa3-empty">
    <strong>No verified matchup is selectable.</strong>
    <span>Step 3 fails closed until Step 2 supplies a verified game.</span>
  </div>
</section>
""",
            unsafe_allow_html=True,
        )
        return None

    prior = st.session_state.get(SESSION_KEY) or {}
    index = _resolve_initial_index(
        games,
        _query_param_value(),
        prior.get("selection_key") if isinstance(prior, dict) else "",
    )

    options = list(range(len(games)))
    chosen_index = st.selectbox(
        "Choose verified game",
        options=options,
        index=index,
        format_func=lambda idx: _game_label(games[idx]),
        key="nfl_prop_analytics_game_picker_v1",
    )
    selected = games[int(chosen_index)]
    handoff = build_matchup_handoff(selected, str(truth.get("target_date") or ""))
    st.session_state[SESSION_KEY] = handoff
    _persist_query(handoff["selection_key"])

    sources = " • ".join(handoff["sources"])
    network = handoff["network"] or "Network TBD"
    venue = handoff["venue"] or "Venue TBD"

    st.markdown(
        f"""
<section class="ks-pa3-selection"
         data-nfl-prop-analytics-step3-selection="v1"
         data-prop-selection-state="selected"
         data-prop-handoff-state="ready"
         data-prop-handoff-version="{HANDOFF_VERSION}"
         data-prop-selected-game="{html_lib.escape(handoff['selection_key'])}"
         data-prop-selected-away="{html_lib.escape(handoff['away'])}"
         data-prop-selected-home="{html_lib.escape(handoff['home'])}"
         data-prop-selected-date="{html_lib.escape(handoff['target_date'])}"
         data-prop-selected-source-count="{handoff['source_count']}">
  <div class="ks-pa3-eyebrow">STEP 3 • GAME SELECTION</div>
  <div class="ks-pa3-matchup">
    <div class="ks-pa3-team">
      <b>{html_lib.escape(handoff['away'])}</b>
      <span>{html_lib.escape(str(handoff['away_name']))}</span>
    </div>
    <div class="ks-pa3-arrow">→</div>
    <div class="ks-pa3-team ks-pa3-home">
      <b>{html_lib.escape(handoff['home'])}</b>
      <span>{html_lib.escape(str(handoff['home_name']))}</span>
    </div>
  </div>
  <div class="ks-pa3-meta">
    <span>{html_lib.escape(network)}</span>
    <span>{html_lib.escape(venue)}</span>
    <span>{html_lib.escape(sources)}</span>
  </div>
  <div class="ks-pa3-ready">
    <strong>Matchup handoff ready</strong>
    <span>Verified game context is locked for the next page.</span>
  </div>
</section>
<style data-nfl-prop-analytics-step3-css="v1">
.ks-pa3-selection{{
  width:100%;min-width:0;overflow-x:clip;margin:12px 0 24px;padding:14px;
  border:1px solid rgba(125,211,252,.20);border-radius:15px;
  background:linear-gradient(145deg,rgba(7,14,24,.98),rgba(10,22,38,.95));
}}
.ks-pa3-eyebrow{{font-size:.67rem;font-weight:900;letter-spacing:.14em;color:#7dd3fc}}
.ks-pa3-matchup{{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);align-items:center;gap:10px;margin:13px 0}}
.ks-pa3-team{{display:flex;flex-direction:column;min-width:0}}
.ks-pa3-team b{{font-size:1.22rem;color:#f8fafc;line-height:1}}
.ks-pa3-team span{{margin-top:4px;color:#a8bad0;font-size:.75rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.ks-pa3-home{{text-align:right;align-items:flex-end}}
.ks-pa3-arrow{{color:#38bdf8;font-weight:900}}
.ks-pa3-meta{{display:flex;flex-wrap:wrap;gap:6px;color:#8297b0;font-size:.66rem}}
.ks-pa3-meta span{{padding:5px 7px;border:1px solid rgba(148,163,184,.11);border-radius:999px}}
.ks-pa3-ready{{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-top:12px;padding-top:11px;border-top:1px solid rgba(148,163,184,.10)}}
.ks-pa3-ready strong{{color:#bae6fd;font-size:.74rem}}
.ks-pa3-ready span{{color:#7890ab;font-size:.67rem;text-align:right}}
.ks-pa3-empty{{padding:14px;border:1px solid rgba(248,113,113,.3);border-radius:14px;background:rgba(127,29,29,.12);display:flex;flex-direction:column;gap:4px}}
.ks-pa3-empty strong{{color:#fecaca}}.ks-pa3-empty span{{color:#cbd5e1;font-size:.8rem}}
@media(max-width:520px){{
  .ks-pa3-selection{{padding:12px}}
  .ks-pa3-ready{{align-items:flex-start;flex-direction:column}}
  .ks-pa3-ready span{{text-align:left}}
}}
</style>
""",
        unsafe_allow_html=True,
    )
    return handoff


__all__ = [
    "HANDOFF_VERSION",
    "MAY_MODIFY_EXISTING_NFL_MARKETS",
    "MAY_MODIFY_PASSING_YARDS",
    "MODEL_VERSION",
    "PAGE",
    "PLAYER_PROP_LOGIC",
    "ROSTER_LOGIC",
    "SELECTION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP",
    "build_matchup_handoff",
    "get_selected_game_handoff",
    "render_game_selection_handoff",
]
