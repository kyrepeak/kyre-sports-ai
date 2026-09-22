"""NFL Passing Yards V42 — Step 7 render-time player identity gate.

Additive over frozen V41. The exact-event/current-roster QB identity gate stays
frozen. The live Passing Yards surface also exposes one explicit full-slate
matchup navigator so mobile users can switch every verified game on the
selected NFL date without depending on the buried legacy V8 selector.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import nfl_hub_v25 as nfl
import nfl_passing_yards_hub_v40 as phoenix_display
import nfl_passing_yards_hub_v41 as prior
import nfl_passing_yards_identity_v1 as identity
import nfl_passing_yards_full_slate_router_v1 as full_slate
from nfl_prop_app_eligibility_v1 import guard_passing_identity

MODEL_VERSION = "NFL PASSING YARDS V42 • STEP 7 APP IDENTITY FAIL-CLOSED"
FROZEN_PRIOR = "nfl_passing_yards_hub_v41"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

VISIBLE_MATCHUP_KEY = "nfl_passing_yards_v42_visible_matchup"
_ORIGINAL_RESOLVE = identity.resolve_matchup_identity
_ORIGINAL_LOAD_NFL_SLATE = nfl.load_nfl_slate


def _load_full_slate(day_str: str):
    return full_slate.load_full_slate(
        day_str,
        primary_loader=_ORIGINAL_LOAD_NFL_SLATE,
    )


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _resolve_matchup_identity_step7(game: dict, season_year: int) -> dict:
    resolved = _ORIGINAL_RESOLVE(game, season_year)
    return guard_passing_identity(game, resolved)


def _verified_matchup_labels(selected_day) -> tuple[list[str], dict[str, Any]]:
    """Return the same full verified slate V8 uses for its matchup lookup."""
    day_str = selected_day.isoformat()
    games, diag = nfl.load_nfl_slate(day_str)
    labels: list[str] = []
    if not diag.get("request_ok") or games.empty:
        return labels, diag

    for _, row in games.iterrows():
        labels.append(
            f"{_safe(row.get('away_team'), 'Away')} @ "
            f"{_safe(row.get('home_team'), 'Home')} • "
            f"{_safe(row.get('tip_et'), 'TBD')}"
        )
    return labels, diag


def _render_visible_matchup_navigation(original_selectbox) -> str | None:
    """Expose one durable full-day selector before the compact player cards."""
    selected_day = prior._selected_date()
    labels, diag = _verified_matchup_labels(selected_day)
    if not labels:
        return None

    legacy_value = _safe(st.session_state.get(prior.V8_MATCHUP_KEY))
    visible_value = _safe(st.session_state.get(VISIBLE_MATCHUP_KEY))
    if visible_value not in labels:
        st.session_state.pop(VISIBLE_MATCHUP_KEY, None)
        if legacy_value in labels:
            st.session_state[VISIBLE_MATCHUP_KEY] = legacy_value

    st.markdown(
        '<div style="margin:.2rem 0 .15rem;font-size:.72rem;font-weight:900;'
        'letter-spacing:.035em;color:#cbd5e1">🏈 TODAY\'S PASSING YARDS GAMES</div>',
        unsafe_allow_html=True,
    )
    chosen = original_selectbox(
        f"Choose matchup • {len(labels)} verified game{'s' if len(labels) != 1 else ''}",
        labels,
        key=VISIBLE_MATCHUP_KEY,
        format_func=lambda option: phoenix_display._phoenix_matchup_option(
            option,
            selected_day,
        ),
        label_visibility="visible",
    )
    st.caption(
        f"{len(labels)} verified NFL game{'s' if len(labels) != 1 else ''} "
        f"available for {selected_day.isoformat()}."
    )

    # V8's legacy selector is suppressed below, so this key is safe to own as
    # plain session state and keeps downstream frozen lookup behavior intact.
    st.session_state[prior.V8_MATCHUP_KEY] = chosen
    return chosen


def render_nfl_passing_yards_hub() -> None:
    original_resolve = identity.resolve_matchup_identity
    original_selectbox = st.selectbox
    original_slate_loader = nfl.load_nfl_slate

    # Scope the fallback to Passing Yards only. V8/V12/V41 all reference the
    # same nfl_hub_v25 module object, so this one temporary route gives the
    # visible selector and frozen downstream lookup the exact same full slate.
    nfl.load_nfl_slate = _load_full_slate
    chosen = _render_visible_matchup_navigation(original_selectbox)

    def selectbox_proxy(label: str, options: Any, *args: Any, **kwargs: Any):
        if str(label) == "Verified matchup" and chosen is not None:
            option_list = list(options)
            if chosen in option_list:
                return chosen
        return original_selectbox(label, options, *args, **kwargs)

    identity.resolve_matchup_identity = _resolve_matchup_identity_step7
    st.selectbox = selectbox_proxy
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        st.selectbox = original_selectbox
        identity.resolve_matchup_identity = original_resolve
        nfl.load_nfl_slate = original_slate_loader


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V42 only renders the Passing Yards market.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "VISIBLE_MATCHUP_KEY",
    "_load_full_slate",
    "_render_visible_matchup_navigation",
    "_resolve_matchup_identity_step7",
    "_verified_matchup_labels",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
