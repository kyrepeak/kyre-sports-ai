'''NBA PRA Page 2 exact Page 1 handoff renderer.'''
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping

from nba_pra_page2_api_only_v1 import load_page2_snapshot_v1
from nba_pra_page2_context_v1 import build_page2_context
from nba_pra_page2_line_lab_v1 import evaluate_line, line_steps
from nba_pra_page2_matchup_api_v1 import load_kyre_sports_api_nba_pra_matchup
from nba_pra_page2_matchup_v1 import build_matchup_summary
from nba_pra_page2_v1 import _baseline_model, _css, build_page2_html, default_line_for_context
from nba_pra_runtime_v2 import (
    SESSION_ANALYSIS_HANDOFF,
    SESSION_LINE_LAB,
    SESSION_SELECTED_QUOTE,
    clear_page2_state,
    selected_player_key,
)

MODEL_VERSION = "NBA PRA PAGE 2 SYNC V1 • EXACT PAGE 1 HANDOFF"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _same_number(left: Any, right: Any) -> bool:
    try:
        return abs(float(left) - float(right)) < 1e-9
    except (TypeError, ValueError):
        return False


def resolve_initial_analysis(
    profile: Mapping[str, Any],
    handoff: Mapping[str, Any] | None,
    player_key: str,
    active_line: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    '''Use Page 1's exact model/grade only for the same player and same quote line.'''
    model = _baseline_model(profile)
    payload = dict(handoff or {})
    quote = dict(payload.get("quote") or {})
    if (
        _text(payload.get("player_key")) == _text(player_key)
        and _same_number(quote.get("line"), active_line)
        and isinstance(payload.get("model"), Mapping)
        and isinstance(payload.get("grade"), Mapping)
    ):
        handed_model = deepcopy(dict(payload.get("model") or {}))
        handed_grade = deepcopy(dict(payload.get("grade") or {}))
        if handed_model and handed_grade:
            return handed_model, handed_grade
    return model, evaluate_line(model.get("projection"), model.get("sigma"), float(active_line))


def render_nba_pra_page2_sync_v1() -> None:
    import streamlit as st

    st.markdown(_css(), unsafe_allow_html=True)
    st.markdown('<a class="ks-p2-top" href="#ks-nba-pra-page2-top">↑ TOP</a>', unsafe_allow_html=True)
    if st.button("← Back to PRA Board", key="nba-pra-p2-sync-back", use_container_width=False):
        clear_page2_state(st.session_state)
        st.rerun()

    key = selected_player_key(st.session_state)
    if key is None:
        st.warning("No verified player selection. Return to the PRA board.")
        return

    now = datetime.now(timezone.utc)
    with st.spinner("Loading selected NBA PRA intelligence…"):
        snapshot = load_page2_snapshot_v1(key, now=now)

    selected = st.session_state.get(SESSION_SELECTED_QUOTE)
    context = build_page2_context(snapshot, key, selected_quote=selected if isinstance(selected, Mapping) else None)
    if context.get("state") not in {"ready", "line_moved"}:
        st.warning("Selected player or PRA market is no longer available. Return to the PRA board.")
        return

    profile = context.get("player") or {}
    default_line = default_line_for_context(context)
    if default_line is None:
        st.warning("Verified PRA line unavailable. No test line was invented.")
        return

    handoff = st.session_state.get(SESSION_ANALYSIS_HANDOFF)
    initial_model, initial_result = resolve_initial_analysis(
        profile,
        handoff if isinstance(handoff, Mapping) else None,
        key,
        float(default_line),
    )

    matchup_raw = load_kyre_sports_api_nba_pra_matchup(_text(context.get("opponent")), now_utc=now)
    matchup = build_matchup_summary(matchup_raw)
    options = line_steps(float(default_line), width=10.0)
    prior = st.session_state.get(SESSION_LINE_LAB)
    default = prior if prior in options else default_line if default_line in options else min(options, key=lambda value: abs(value - default_line))

    @st.fragment
    def _render_synced_line_lab() -> None:
        active_line = st.select_slider(
            "PRA Line Lab",
            options=options,
            value=default,
            key=SESSION_LINE_LAB,
            help="The sportsbook line opens with the exact Page 1 analysis. Alternate thresholds recalculate locally without a provider fetch.",
        )
        if _same_number(active_line, default_line):
            model = initial_model
            result = initial_result
        else:
            model = initial_model
            result = evaluate_line(model.get("projection"), model.get("sigma"), float(active_line))
        st.caption("⚡ SAME SNAPSHOT • Page 1 ↔ Page 2 exact at sportsbook line • 0 external fetches per slider move")
        st.markdown(
            '<div class="p2-wrap">' + build_page2_html(context, model, result, matchup, active_line=float(active_line)) + '</div>',
            unsafe_allow_html=True,
        )

    _render_synced_line_lab()
