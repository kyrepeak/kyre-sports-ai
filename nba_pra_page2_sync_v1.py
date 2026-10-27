'''NBA PRA Page 2 exact Page 1 handoff renderer.'''
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping

from nba_pra_page2_api_only_v1 import load_page2_snapshot_v1
from nba_pra_page2_context_v2 import build_page2_context
from nba_pra_page2_line_lab_v1 import evaluate_line, line_steps
from nba_pra_page2_matchup_api_v1 import load_kyre_sports_api_nba_pra_matchup
from nba_pra_page2_matchup_v1 import build_matchup_summary
from nba_pra_page2_v1 import _baseline_model, default_line_for_context
from nba_pra_page2_command_center_v4 import _css, build_page2_html
# Legacy presentation activation proof retained byte-for-byte for prior regressions:
# from nba_pra_page2_command_center_v3 import _css, build_page2_html
from nba_pra_runtime_v2 import (
    SESSION_ANALYSIS_HANDOFF,
    SESSION_LINE_LAB,
    SESSION_SELECTED_QUOTE,
    clear_page2_state,
    render_page2_loading_screen,
    selected_player_key,
)

MODEL_VERSION = "NBA PRA PAGE 2 SYNC V4 • MONSTER S-TIER DECISION TERMINAL"
_UNVERIFIED_AVAILABILITY = {
    "",
    "UNVERIFIED",
    "NO VERIFIED INJURY FLAG",
    "NOT CURRENTLY VERIFIED",
    "UNKNOWN",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _same_number(left: Any, right: Any) -> bool:
    try:
        return abs(float(left) - float(right)) < 1e-9
    except (TypeError, ValueError):
        return False


def apply_handoff_context(
    context: Mapping[str, Any],
    handoff: Mapping[str, Any] | None,
    player_key: str,
) -> dict[str, Any]:
    '''Reuse only genuinely verified same-player Page 1 context when refresh is blank.'''
    out = dict(context or {})
    payload = dict(handoff or {})
    if _text(payload.get("player_key")) != _text(player_key):
        return out
    current = _text(out.get("availability")).upper()
    handed = _text(payload.get("availability"))
    handed_state = handed.upper()
    if current in {"", "UNVERIFIED"} and handed_state not in _UNVERIFIED_AVAILABILITY:
        out["availability"] = handed
    return out


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


def build_handoff_loader_kwargs(
    player_key: str,
    handoff: Mapping[str, Any] | None,
    selected_quote: Mapping[str, Any] | None,
    *,
    now: datetime,
) -> dict[str, Any]:
    """Forward Page 1 evidence only when it belongs to this exact player."""
    kwargs: dict[str, Any] = {"now": now}
    payload = dict(handoff or {})
    if _text(payload.get("player_key")) != _text(player_key):
        return kwargs
    quote = (
        dict(selected_quote)
        if isinstance(selected_quote, Mapping)
        else dict(payload.get("quote") or {})
        if isinstance(payload.get("quote"), Mapping)
        else None
    )
    kwargs.update(
        selected_player_name=_text(payload.get("player_name")) or None,
        selected_team=_text(payload.get("team")) or None,
        selected_quote=quote,
    )
    return kwargs


def render_nba_pra_page2_sync_v1(*, show_loading_overlay: bool = False) -> None:
    import streamlit as st

    handoff = st.session_state.get(SESSION_ANALYSIS_HANDOFF)
    handoff_map = handoff if isinstance(handoff, Mapping) else None
    loading_placeholder = st.empty()
    if show_loading_overlay:
        player_name = _text((handoff_map or {}).get("player_name")) or "player"
        loading_placeholder.markdown(render_page2_loading_screen(player_name), unsafe_allow_html=True)

    st.markdown(_css(), unsafe_allow_html=True)
    st.markdown('<a class="ks-p2-top" href="#ks-nba-pra-page2-top">↑ TOP</a>', unsafe_allow_html=True)
    if st.button("← Back to PRA Board", key="nba-pra-p2-sync-back", use_container_width=False):
        if show_loading_overlay:
            loading_placeholder.empty()
        clear_page2_state(st.session_state)
        st.rerun()

    key = selected_player_key(st.session_state)
    if key is None:
        if show_loading_overlay:
            loading_placeholder.empty()
        st.warning("No verified player selection. Return to the PRA board.")
        return

    now = datetime.now(timezone.utc)
    selected = st.session_state.get(SESSION_SELECTED_QUOTE)
    selected_map = selected if isinstance(selected, Mapping) else None
    snapshot = load_page2_snapshot_v1(
        key,
        **build_handoff_loader_kwargs(key, handoff_map, selected_map, now=now),
    )

    context = build_page2_context(snapshot, key, selected_quote=selected_map)
    context = apply_handoff_context(context, handoff_map, key)
    if context.get("state") not in {"ready", "line_moved"}:
        if show_loading_overlay:
            loading_placeholder.empty()
        st.warning("Selected player or PRA market is no longer available. Return to the PRA board.")
        return

    profile = context.get("player") or {}
    default_line = default_line_for_context(context)
    if default_line is None:
        if show_loading_overlay:
            loading_placeholder.empty()
        st.warning("Verified PRA line unavailable. No test line was invented.")
        return

    initial_model, initial_result = resolve_initial_analysis(
        profile,
        handoff_map,
        key,
        float(default_line),
    )

    matchup_raw = load_kyre_sports_api_nba_pra_matchup(_text(context.get("opponent")), now_utc=now)
    matchup = build_matchup_summary(matchup_raw)
    if show_loading_overlay:
        loading_placeholder.empty()

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
