"""MLB Matchup Explorer V5.8 — cleanup Step 14 single-source selection lock.

Presentation-only wrapper over certified Cleanup Step 13. It fixes cross-player
and cross-generation presentation drift by freezing the exact selected game/player
identity for the entire render, validating Step 11/12 profiles against that identity,
and removing the obsolete V1 Matchup Snapshot from the normal page. No probability,
calibration, Monte Carlo, ranking, router, or Moneyline math is changed.
"""
from __future__ import annotations

import html
from typing import Any

import streamlit as st

import mlb_matchup_hub_v41 as current
import mlb_matchup_hub_v45 as hero_helpers
import mlb_matchup_hub_v46 as collapse_ui
import mlb_matchup_hub_v50 as legacy_ui
import mlb_matchup_hub_v51 as step11_ui
import mlb_matchup_hub_v53 as step13_ui
import mlb_matchup_player_v22 as legacy_snapshot
import mlb_matchup_player_v35 as final_layer

VERSION = "MLB Matchup Hub V5.8 • Cleanup Step 14 Selection Lock"
FROZEN_MATCHUP_CHAIN = current.FROZEN_MATCHUP_CHAIN
FROZEN_STEP11_PRESENTATION = "mlb_matchup_hub_v51"
FROZEN_STEP13_PRESENTATION = "mlb_matchup_hub_v53"
FROZEN_V2_PRESENTATION = "mlb_matchup_hub_v41"


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _esc(value: Any) -> str:
    return html.escape(str(value if value not in (None, "") else "—"))


def _selection_identity(context: dict[str, Any]) -> dict[str, int | str]:
    row = context["row"]
    player = context["player"]
    return {
        "game_index": _safe_int(context.get("game_index"), 0),
        "player_index": _safe_int(context.get("player_index"), 0),
        "game_pk": _safe_int(row.get("game_pk"), 0),
        "player_id": _safe_int(player.get("id"), 0),
        "player_name": str(player.get("name") or "Player"),
    }


def _signature(identity: dict[str, int | str]) -> str:
    return f"g{_safe_int(identity.get('game_pk'), 0)}p{_safe_int(identity.get('player_id'), 0)}"


def _reassert_selection(identity: dict[str, int | str]) -> None:
    """Keep every legacy reader pinned to the exact selector identity for this run."""
    st.session_state["mh12_game"] = _safe_int(identity.get("game_index"), 0)
    st.session_state["mh12_player"] = _safe_int(identity.get("player_index"), 0)


def _locked_legacy_selectbox(original, identity: dict[str, int | str]):
    """Never let hidden legacy selectors reinterpret the current numeric indices."""
    game_index = _safe_int(identity.get("game_index"), 0)
    player_index = _safe_int(identity.get("player_index"), 0)

    def wrapped(label, options, *args, **kwargs):
        key = kwargs.get("key")
        values = list(options)
        if key == "mh12_game":
            return game_index if game_index in values else (values[0] if values else None)
        if key == "mh12_player":
            return player_index if player_index in values else (values[0] if values else None)
        return original(label, options, *args, **kwargs)

    return wrapped


def _profile_matches(profile: dict[str, Any] | None, identity: dict[str, int | str]) -> bool:
    """Profiles must belong to the exact MLB game PK + player ID currently selected."""
    if not profile:
        return False
    return (
        _safe_int(profile.get("game_pk"), -1) == _safe_int(identity.get("game_pk"), -2)
        and _safe_int(profile.get("player_id"), -1) == _safe_int(identity.get("player_id"), -2)
    )


def _selection_guard_css(identity: dict[str, int | str]) -> str:
    sig = _signature(identity)
    return f"""
<style>
/* Hide stale Step 13 cards immediately on a new selector run. Step 14-owned
   cards keep the certified Step 13 styling but carry an explicit selection key. */
.mx53-intro:not(.mx54-owned),.mx53-shell:not(.mx54-owned){{display:none!important}}
.mx54-result{{display:none!important}}
.mx54-result.mx54-current-{sig}{{display:block!important}}

/* The old V1/Step-4 Matchup Snapshot used a different probability generation.
   Keep that audit model in Legacy V1 only; never show it beside the V2 final. */
.mx22-snapshot{{display:none!important}}
div[data-testid="stExpander"]:has(.mx22-evidence){{display:none!important}}
</style>
"""


def _owned_scouting_html(
    context: dict[str, Any],
    identity: dict[str, int | str],
    step_html: list[str],
    raw: dict[str, Any] | None,
    final: dict[str, Any] | None,
    notices: list[str],
) -> str:
    source = step13_ui._scouting_html(context, step_html, raw, final, notices)
    source = source.replace('class="mx53-intro"', 'class="mx53-intro mx54-owned"', 1)
    source = source.replace('class="mx53-shell"', 'class="mx53-shell mx54-owned"', 1)
    return f'<div class="mx54-result mx54-current-{_signature(identity)}">{source}</div>'


def _sync_wait_html(context: dict[str, Any], identity: dict[str, int | str]) -> str:
    player = context["player"]
    return (
        f'<div class="mx54-result mx54-current-{_signature(identity)}">'
        '<div style="border:1px solid #7b6120;border-left:5px solid #e0b52d;border-radius:16px;'
        'background:#17150b;padding:12px 13px;color:#e8d287;font-size:.62rem;line-height:1.5">'
        f'🔄 Refreshing <b>{_esc(player.get("name"))}</b> only. A result from another player/game was blocked by the selection lock.'
        '</div></div>'
    )


def _suppress_legacy_snapshot(slot, games_df) -> None:
    """Normal page shows one V2 final answer; the old snapshot remains in Legacy V1 audit."""
    return None


def render_matchup_hub(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    if games_df is None or games_df.empty:
        return current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)

    # Render the only user-facing selectors first, then freeze their exact original
    # game/player indices and immutable MLB identities for the rest of this run.
    st.markdown(
        step11_ui.step9._STEP9_CSS
        + step11_ui.step10._STEP10_CSS
        + step11_ui._STEP11_CSS
        + step13_ui._HOTFIX_CSS,
        unsafe_allow_html=True,
    )
    step11_ui._render_stable_selectors(games_df)
    context = hero_helpers._selected_context(games_df)
    if not context:
        st.info("Player spotlight is waiting for a verified selection.")
        return

    identity = _selection_identity(context)
    _reassert_selection(identity)
    st.markdown(_selection_guard_css(identity), unsafe_allow_html=True)

    hero_slot = st.empty()
    step11_ui._render_spotlight(hero_slot, context, None)

    captured_steps: list[str] = []
    notices: list[str] = []
    profiles: dict[str, dict[str, Any] | None] = {"raw": None, "final": None}
    capture_active = {"value": False}
    mismatch = {"value": False}

    original_selectbox = st.selectbox
    original_text_input = st.text_input
    original_markdown = st.markdown
    original_expander = st.expander
    original_caption = st.caption
    original_warning = st.warning
    original_info = st.info
    original_raw_profile = final_layer._render_step11_profile
    original_final_profile = final_layer._render_step12_profile
    original_snapshot = legacy_snapshot._render_snapshot
    legacy_markdown = legacy_ui._legacy_markdown_passthrough(original_markdown)

    def capture_markdown(body: Any, *args: Any, **kwargs: Any):
        _reassert_selection(identity)
        text = str(body or "")
        if '<div class="mxv2-step ' in text:
            capture_active["value"] = True
            captured_steps.append(text)
            return None
        if 'class="mx22-snapshot"' in text or 'class="mx22-evidence"' in text:
            return None
        return legacy_markdown(body, *args, **kwargs)

    def capture_warning(body: Any, *args: Any, **kwargs: Any):
        if capture_active["value"]:
            notices.append(str(body or ""))
            return None
        return original_warning(body, *args, **kwargs)

    def capture_info(body: Any, *args: Any, **kwargs: Any):
        if capture_active["value"]:
            notices.append(str(body or ""))
            return None
        return original_info(body, *args, **kwargs)

    def capture_raw(profile: dict[str, Any] | None) -> None:
        _reassert_selection(identity)
        if not _profile_matches(profile, identity):
            mismatch["value"] = True
            notices.append("Blocked Step 11 profile whose game/player identity did not match the active selection")
            return
        profiles["raw"] = profile
        return original_raw_profile(profile)

    def capture_final(profile: dict[str, Any] | None) -> None:
        _reassert_selection(identity)
        if mismatch["value"] or not _profile_matches(profile, identity):
            mismatch["value"] = True
            capture_active["value"] = False
            step11_ui._render_spotlight(hero_slot, context, None)
            original_markdown(_sync_wait_html(context, identity), unsafe_allow_html=True)
            return

        profiles["final"] = profile
        original_final_profile(profile)
        capture_active["value"] = False
        step11_ui._render_spotlight(hero_slot, context, profile)

        first_step = captured_steps[0] if captured_steps else ""
        selected_name = str(identity.get("player_name") or "")
        if selected_name and selected_name.lower() not in first_step.lower():
            mismatch["value"] = True
            original_markdown(_sync_wait_html(context, identity), unsafe_allow_html=True)
            return

        original_markdown(
            _owned_scouting_html(
                context,
                identity,
                captured_steps,
                profiles.get("raw"),
                profile,
                notices,
            ),
            unsafe_allow_html=True,
        )

    st.selectbox = _locked_legacy_selectbox(original_selectbox, identity)
    st.text_input = legacy_ui._legacy_text_input_passthrough(original_text_input)
    st.markdown = capture_markdown
    st.expander = collapse_ui._collapsed_expander(original_expander)
    st.caption = step13_ui._research_caption(original_caption)
    st.warning = capture_warning
    st.info = capture_info
    final_layer._render_step11_profile = capture_raw
    final_layer._render_step12_profile = capture_final
    legacy_snapshot._render_snapshot = _suppress_legacy_snapshot

    try:
        _reassert_selection(identity)
        current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        _reassert_selection(identity)
        legacy_snapshot._render_snapshot = original_snapshot
        final_layer._render_step12_profile = original_final_profile
        final_layer._render_step11_profile = original_raw_profile
        st.info = original_info
        st.warning = original_warning
        st.caption = original_caption
        st.expander = original_expander
        st.markdown = original_markdown
        st.text_input = original_text_input
        st.selectbox = original_selectbox


__all__ = [
    "FROZEN_MATCHUP_CHAIN",
    "FROZEN_STEP11_PRESENTATION",
    "FROZEN_STEP13_PRESENTATION",
    "FROZEN_V2_PRESENTATION",
    "VERSION",
    "_locked_legacy_selectbox",
    "_profile_matches",
    "_selection_identity",
    "render_matchup_hub",
]
