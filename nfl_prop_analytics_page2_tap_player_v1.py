"""NFL Prop Analytics Page 2 Polish Step 4 — tap-player selection presentation.

Presentation-only bridge over the frozen Step 7 eligibility + handoff contract.
"""
from __future__ import annotations

import html as html_lib
from typing import Any

import streamlit as st

from nfl_prop_analytics_player_select_v1 import (
    QUERY_KEY,
    SESSION_KEY,
    build_player_handoff,
    eligible_players,
)

MODEL_VERSION = "NFL PROP ANALYTICS PAGE 2 POLISH STEP 4 • TAP PLAYER + PAGE 3 HANDOFF"
STEP = 4
PAGE = 2
PRESENTATION_ONLY = True
MAY_MODIFY_PASSING_YARDS = False
MAY_MODIFY_EXISTING_NFL_MARKETS = False
TAP_KEY_PREFIX = "nfl_prop_analytics_page2_tap_player_v1"


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _requested_player_id() -> str:
    try:
        raw = st.query_params.get(QUERY_KEY, "")
    except Exception:
        return ""
    if isinstance(raw, list):
        return _text(raw[0] if raw else "")
    return _text(raw)


def _persist_player(player_id: str) -> None:
    try:
        st.query_params[QUERY_KEY] = player_id
    except Exception:
        pass


def render_tap_player_handoff(
    matchup_handoff: dict[str, Any],
    step6_truth: dict[str, Any],
) -> dict[str, Any] | None:
    players = eligible_players(step6_truth)
    if not players:
        st.session_state.pop(SESSION_KEY, None)
        st.markdown(
            '<div data-prop-page2-tap-player="v1" data-prop-page2-tap-state="fail-closed" '
            'data-prop-page2-tap-candidate-count="0"></div>',
            unsafe_allow_html=True,
        )
        return None

    by_id = {_text(row.get("espn_id")): row for row in players}
    prior = st.session_state.get(SESSION_KEY)
    prior_id = _text(prior.get("player_id")) if isinstance(prior, dict) else ""
    requested = _requested_player_id()
    selected_id = requested if requested in by_id else prior_id if prior_id in by_id else _text(players[0].get("espn_id"))

    st.markdown(
        f"""
<section class="ks-pa4-tap"
 data-prop-page2-tap-player="v1"
 data-prop-page2-tap-state="ready"
 data-prop-page2-tap-candidate-count="{len(players)}"
 data-prop-page2-tap-selected-id="{html_lib.escape(selected_id)}">
 <div class="ks-pa4-kicker">SELECT A PLAYER</div>
 <div class="ks-pa4-copy">Tap a verified player to lock the exact Step 7 handoff, then open Page 3.</div>
</section>
<style data-prop-page2-tap-player-css="v1">
.ks-pa4-tap{{margin:10px 0 8px;padding:11px 13px;border:1px solid rgba(125,211,252,.16);border-radius:13px;background:rgba(7,18,31,.72)}}
.ks-pa4-kicker{{color:#7dd3fc;font-size:.64rem;font-weight:900;letter-spacing:.13em}}
.ks-pa4-copy{{margin-top:3px;color:#8298b2;font-size:.68rem}}
</style>
""",
        unsafe_allow_html=True,
    )

    cols = st.columns(2)
    for index, row in enumerate(players):
        player_id = _text(row.get("espn_id"))
        label = f"{row.get('team','')} • {row.get('position','')} • {row.get('name','')} • {row.get('depth_role','')}"
        with cols[index % 2]:
            if st.button(
                label,
                key=f"{TAP_KEY_PREFIX}_{player_id}",
                use_container_width=True,
                type="primary" if player_id == selected_id else "secondary",
            ):
                selected_id = player_id
                _persist_player(selected_id)

    selected = by_id[selected_id]
    handoff = build_player_handoff(matchup_handoff, step6_truth, selected)
    st.session_state[SESSION_KEY] = handoff
    _persist_player(handoff["player_id"])

    gate = "OPEN" if handoff["prop_analysis_gate_open"] else "CLOSED"
    st.markdown(
        f'<div data-prop-page2-tap-handoff="v1" data-prop-page2-tap-handoff-player-id="{html_lib.escape(handoff["player_id"])}" '
        f'data-prop-page2-tap-handoff-team="{html_lib.escape(handoff["team"])}" '
        f'data-prop-page2-tap-handoff-position="{html_lib.escape(handoff["position"])}" '
        f'data-prop-page2-tap-handoff-availability="{html_lib.escape(handoff["availability_state"])}" '
        f'data-prop-page2-tap-handoff-prop-gate="{gate}"></div>',
        unsafe_allow_html=True,
    )
    return handoff


__all__ = [
    "MAY_MODIFY_EXISTING_NFL_MARKETS",
    "MAY_MODIFY_PASSING_YARDS",
    "MODEL_VERSION",
    "PAGE",
    "PRESENTATION_ONLY",
    "STEP",
    "TAP_KEY_PREFIX",
    "render_tap_player_handoff",
]
