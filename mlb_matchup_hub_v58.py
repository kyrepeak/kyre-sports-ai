"""MLB Matchup Explorer V6.2 — Step 18 hard freeze + atomic identity render.

This wrapper fixes the remaining selector/spotlight drift without changing model math.
The authoritative identity is the exact snapshot produced by Step 16's player-ID
selector. Every downstream reader (spotlight context + Step 17 cache identity) is
forced to consume that same snapshot for the entire Streamlit rerun.

It also replaces stale prior-player spotlight content immediately while a newly
selected player's slower season/matchup data finishes loading.
"""
from __future__ import annotations

import copy
import html
from typing import Any, Callable

import streamlit as st

import mlb_matchup_hub_v45 as hero_helpers
import mlb_matchup_hub_v51 as spotlight_ui
import mlb_matchup_hub_v56 as identity_layer
import mlb_matchup_hub_v57 as current

VERSION = "MLB Matchup Hub V6.2 • Step 18 Hard Freeze + Atomic Identity"
FROZEN_MATCHUP_CHAIN = current.FROZEN_MATCHUP_CHAIN
FROZEN_STEP16_PRESENTATION = "mlb_matchup_hub_v56"
FROZEN_STEP17_PRESENTATION = "mlb_matchup_hub_v57"

_COMMITTED_KEY = "mx58_committed_identity"
_EPOCH_KEY = "mx58_selection_epoch"


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _esc(value: Any) -> str:
    return html.escape(str(value if value not in (None, "") else "—"))


def _snapshot_signature(snapshot: dict[str, Any] | None) -> tuple[int, int]:
    d = snapshot or {}
    return (_safe_int(d.get("game_pk"), 0), _safe_int(d.get("player_id"), 0))


def _reassert_snapshot(snapshot: dict[str, Any] | None) -> None:
    d = snapshot or {}
    if not d:
        return
    st.session_state["mh12_game"] = _safe_int(d.get("game_index"), 0)
    st.session_state["mh12_player"] = _safe_int(d.get("player_index"), 0)
    st.session_state["mx56_active_game_pk"] = _safe_int(d.get("game_pk"), 0)
    st.session_state["mx56_active_player_id"] = _safe_int(d.get("player_id"), 0)
    st.session_state["mx51_active_game_pk"] = _safe_int(d.get("game_pk"), 0)


def _context_from_snapshot(games_df, snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return one exact context from the committed Step 16 selector snapshot."""
    if games_df is None or games_df.empty or not snapshot:
        return None
    game_index = _safe_int(snapshot.get("game_index"), -1)
    if game_index < 0 or game_index >= len(games_df):
        return None
    row = games_df.iloc[game_index]
    if _safe_int(row.get("game_pk"), game_index) != _safe_int(snapshot.get("game_pk"), -2):
        return None

    players = copy.deepcopy(list(snapshot.get("players") or []))
    player_id = _safe_int(snapshot.get("player_id"), 0)
    if not players or player_id <= 0:
        return None
    player_index = next(
        (i for i, player in enumerate(players) if _safe_int(player.get("id"), 0) == player_id),
        None,
    )
    if player_index is None:
        return None
    return {
        "row": row,
        "players": players,
        "player": players[player_index],
        "game_index": game_index,
        "player_index": int(player_index),
    }


def _cache_context_from_snapshot(games_df, snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    """Build Step 17's cache fingerprint from the same committed identity only."""
    context = _context_from_snapshot(games_df, snapshot)
    if not context:
        return None
    row = context["row"]
    player = context["player"]
    game_pk = _safe_int(row.get("game_pk"), context["game_index"])
    player_id = _safe_int(player.get("id"), 0)
    fingerprint = (
        game_pk,
        player_id,
        str(row.get("game_date") or ""),
        str(row.get("status") or ""),
        str(row.get("first_pitch_et") or ""),
        _safe_int(row.get("away_pitcher_id"), 0),
        _safe_int(row.get("home_pitcher_id"), 0),
        str(row.get("away_pitcher") or ""),
        str(row.get("home_pitcher") or ""),
        str(player.get("source") or ""),
        _safe_int(player.get("slot"), 99),
        bool(player.get("lineup_role")),
        str(player.get("side") or ""),
        _safe_int(player.get("opponent_pitcher_id"), 0),
    )
    return {"fingerprint": fingerprint, "game_pk": game_pk, "player_id": player_id, "game_date": str(row.get("game_date") or "")}


def _capture_selector_snapshot(original: Callable[..., Any], holder: dict[str, Any]):
    def wrapped(games_df, snapshot, original_all_hitters):
        result = original(games_df, snapshot, original_all_hitters)
        if snapshot and snapshot.get("players"):
            committed = copy.deepcopy(snapshot)
            previous = tuple(st.session_state.get(_COMMITTED_KEY) or (0, 0))
            current_sig = _snapshot_signature(committed)
            holder["snapshot"] = committed
            _reassert_snapshot(committed)
            st.session_state[_COMMITTED_KEY] = current_sig
            if previous != current_sig:
                st.session_state[_EPOCH_KEY] = _safe_int(st.session_state.get(_EPOCH_KEY), 0) + 1
        return result
    return wrapped


def _strict_selected_context(original: Callable[..., Any], holder: dict[str, Any]):
    """Prevent numeric legacy indices from ever overriding the committed player ID."""
    def wrapped(games_df):
        snapshot = holder.get("snapshot")
        context = _context_from_snapshot(games_df, snapshot)
        if context:
            _reassert_snapshot(snapshot)
            return context
        return original(games_df)
    return wrapped


def _strict_cache_context(original: Callable[..., Any], holder: dict[str, Any]):
    """Prevent Step 17 session caches from reading a stale prior-player identity."""
    def wrapped(games_df):
        snapshot = holder.get("snapshot")
        context = _cache_context_from_snapshot(games_df, snapshot)
        if context:
            _reassert_snapshot(snapshot)
            return context
        return original(games_df)
    return wrapped


def _profile_matches_snapshot(profile: dict[str, Any] | None, snapshot: dict[str, Any] | None) -> bool:
    if not profile or not snapshot:
        return False
    game_pk, player_id = _snapshot_signature(snapshot)
    return (
        _safe_int(profile.get("game_pk"), -1) == game_pk
        and _safe_int(profile.get("player_id"), -1) == player_id
    )


def _syncing_spotlight_html(context: dict[str, Any]) -> str:
    player = context["player"]
    row = context["row"]
    return f'''<div class="mx49-section"><span class="mx49-star">☆</span> Player Spotlight</div>
    <div class="mx49-card" style="min-height:118px;display:flex;align-items:center">
      <div style="width:100%">
        <div class="mx49-name">{_esc(player.get('name') or 'Player')}</div>
        <div class="mx49-team">⚾ {_esc(player.get('team'))} • {_esc(player.get('position'))}</div>
        <div style="margin-top:10px;color:#7fa6c7;font-size:.62rem;font-weight:850">🔄 Syncing this exact player + game before showing any previous result…</div>
        <div style="margin-top:4px;color:#5f7d97;font-size:.48rem">Game {_safe_int(row.get('game_pk'), 0)} • MLB player {_safe_int(player.get('id'), 0)}</div>
      </div>
    </div>'''


def _atomic_spotlight(original: Callable[..., Any], holder: dict[str, Any]):
    """Replace stale prior-player DOM immediately, then render only committed identity."""
    def wrapped(slot, context, final=None):
        snapshot = holder.get("snapshot")
        strict = _context_from_snapshot(holder.get("games_df"), snapshot) if holder.get("games_df") is not None else None
        if strict:
            context = strict
            _reassert_snapshot(snapshot)
        if not context:
            return original(slot, context, None)

        if final is not None and not _profile_matches_snapshot(final, snapshot):
            final = None

        # This lightweight card is emitted before season/handedness lookups so an old
        # player's card cannot remain visible during a slow Streamlit rerun.
        if final is None:
            slot.markdown(_syncing_spotlight_html(context), unsafe_allow_html=True)
        return original(slot, context, final)
    return wrapped


def render_matchup_hub(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    if games_df is None or games_df.empty:
        return current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)

    holder: dict[str, Any] = {"games_df": games_df}
    original_selector = identity_layer._render_identity_selectors
    original_context = hero_helpers._selected_context
    original_cache_context = current._selection_context
    original_spotlight = spotlight_ui._render_spotlight

    identity_layer._render_identity_selectors = _capture_selector_snapshot(original_selector, holder)
    hero_helpers._selected_context = _strict_selected_context(original_context, holder)
    current._selection_context = _strict_cache_context(original_cache_context, holder)
    spotlight_ui._render_spotlight = _atomic_spotlight(original_spotlight, holder)
    try:
        return current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        spotlight_ui._render_spotlight = original_spotlight
        current._selection_context = original_cache_context
        hero_helpers._selected_context = original_context
        identity_layer._render_identity_selectors = original_selector


__all__ = [
    "FROZEN_MATCHUP_CHAIN",
    "FROZEN_STEP16_PRESENTATION",
    "FROZEN_STEP17_PRESENTATION",
    "VERSION",
    "_cache_context_from_snapshot",
    "_context_from_snapshot",
    "_profile_matches_snapshot",
    "_snapshot_signature",
    "render_matchup_hub",
]
