"""MLB Matchup Explorer V6.0 — Cleanup Step 16 compact strength + identity hotfix.

Presentation-only wrapper over certified Cleanup Step 14/15 assets. This layer fixes
two user-facing problems without changing model math:
1) player selection is keyed by immutable MLB player ID and the selected game's roster
   is frozen for the duration of the render, so selector/spotlight/Steps 1-12 cannot
   drift to a different player when roster ordering changes between helper calls;
2) every captured Step 1-12 card gets a compact, always-visible strength grade next to
   its existing data/readiness badge, and the research stack is tightened for mobile.

Probability, calibration, Monte Carlo, ranking, Moneyline and Step-profile math remain
owned by the frozen certified layers below this wrapper.
"""
from __future__ import annotations

import copy
from typing import Any, Callable

import streamlit as st

import mlb_matchup_hub_v14 as roster
import mlb_matchup_hub_v42 as step1
import mlb_matchup_hub_v51 as selectors
import mlb_matchup_hub_v54 as current
import mlb_matchup_hub_v55 as strength

VERSION = "MLB Matchup Hub V6.0 • Cleanup Step 16 Compact Strength + Identity"
FROZEN_MATCHUP_CHAIN = current.FROZEN_MATCHUP_CHAIN
FROZEN_STEP14_PRESENTATION = "mlb_matchup_hub_v54"
FROZEN_STEP15_PRESENTATION = "mlb_matchup_hub_v55"

_STEP16_CSS = r"""
<style>
/* Compact strength row: keep the original V2 data/readiness badge, then show one
   explicit human-readable matchup grade beside it. */
.mx56-badges{display:flex;flex-wrap:wrap;align-items:center;gap:5px;margin-top:5px}
.mx56-grade{display:inline-flex;align-items:center;justify-content:center;border-radius:999px;padding:4px 8px;font-size:.47rem;font-weight:950;letter-spacing:.045em;text-transform:uppercase;white-space:nowrap;border:1px solid}
.mx56-grade.batter{color:#8ce7aa;border-color:#2f7b50;background:#0b2418}
.mx56-grade.pitcher{color:#ff9c9c;border-color:#8c4141;background:#2c1113}
.mx56-grade.neutral{color:#e8cc72;border-color:#806a2b;background:#241f0d}
.mx56-grade.pending{color:#bdc8d2;border-color:#596674;background:#151c24}
.mx56-legend{display:flex;flex-wrap:wrap;gap:5px;align-items:center;margin:5px 0 7px;padding:6px 8px;border:1px solid #2b4055;border-radius:10px;background:#0a131d;color:#8094a8;font-size:.45rem;font-weight:850;line-height:1.35}
.mx56-legend b{color:#dce7ef}.mx56-legend .bat{color:#8ce7aa}.mx56-legend .pit{color:#ff9c9c}.mx56-legend .neu{color:#e8cc72}.mx56-legend .pen{color:#bdc8d2}

/* Tighten the finished Step cards without removing a single certified evidence row. */
.mx53-shell .mxv2-step{padding:10px 11px!important;margin:6px 0!important;border-radius:14px!important}
.mx53-shell .mxv2-top{display:flex!important;flex-wrap:wrap!important;align-items:center!important;justify-content:flex-start!important;gap:4px 6px!important}
.mx53-shell .mxv2-kicker{flex:1 1 100%!important;font-size:.56rem!important;line-height:1.25!important;letter-spacing:.085em!important}
.mx53-shell .mxv2-top>.mxv2-badge{display:none!important}
.mx53-shell .mx56-badges .mxv2-badge{display:inline-flex!important;max-width:none!important;white-space:nowrap!important;text-align:center!important;margin:0!important;padding:4px 7px!important;font-size:.46rem!important}
.mx53-shell .mxv2-lead{font-size:.90rem!important;line-height:1.28!important;margin-top:6px!important}
.mx53-shell .mxv2-status{font-size:.59rem!important;line-height:1.35!important;margin-top:3px!important}
.mx53-shell .mxv2-rule{margin:7px 0!important}
.mx53-shell .mxv2-statgrid{gap:5px!important;margin-top:0!important}
.mx53-shell .mxv2-mini{padding:7px 8px!important;border-radius:10px!important;min-height:0!important}
.mx53-shell .mxv2-mini span{font-size:.42rem!important;line-height:1.2!important}
.mx53-shell .mxv2-mini b{font-size:.78rem!important;line-height:1.2!important;margin-top:3px!important}
.mx53-shell .mxv2-row{font-size:.61rem!important;line-height:1.42!important;margin:4px 0!important}
.mx53-shell .mxv2-muted{font-size:.52rem!important;line-height:1.38!important}
.mx53-shell .mxv2-pitchhead,.mx53-shell .mxv2-bphead,.mx53-shell .mxv2-formhead{font-size:.48rem!important;margin:5px 0!important}
.mx53-shell .mxv2-pitchrow,.mx53-shell .mxv2-bprow,.mx53-shell .mxv2-formrow{gap:5px!important;padding:6px!important;border-radius:9px!important}

/* Slightly tighten the area around the Deep Matchup Research block as well. */
div[data-testid="stExpander"]:has(.mx54-owned) details > summary{min-height:44px!important;padding-top:7px!important;padding-bottom:7px!important}
.mx53-shell{padding-top:13px!important;padding-bottom:14px!important}
.mx53-player{margin-bottom:9px!important}.mx53-verified{margin-bottom:8px!important}
.mx53-final{margin-top:9px!important}

@media(max-width:640px){
  .mx56-grade{font-size:.42rem;padding:4px 7px;letter-spacing:.025em}
  .mx56-legend{font-size:.40rem;padding:5px 7px;margin:4px 0 6px}
  .mx53-shell .mxv2-step{padding:9px 9px!important;margin:5px 0!important;border-radius:13px!important}
  .mx53-shell .mxv2-kicker{font-size:.53rem!important}
  .mx53-shell .mxv2-lead{font-size:.84rem!important}
  .mx53-shell .mxv2-status{font-size:.56rem!important}
  .mx53-shell .mxv2-row{font-size:.58rem!important;line-height:1.38!important}
  .mx53-shell .mxv2-muted{font-size:.49rem!important}
  .mx53-shell .mxv2-mini{padding:6px 7px!important}
  .mx53-shell .mxv2-mini b{font-size:.73rem!important}
}
</style>
"""


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _player_id(player: dict[str, Any]) -> int:
    return _safe_int(player.get("id"), 0)


def _player_id_index(players: list[dict[str, Any]]) -> dict[int, int]:
    """Map immutable MLB player IDs to the original-list index frozen V2 expects."""
    out: dict[int, int] = {}
    for index, player in enumerate(players or []):
        pid = _player_id(player)
        if pid > 0 and pid not in out:
            out[pid] = index
    return out


def _stable_roster_wrapper(
    original: Callable[[Any], list[dict[str, Any]]],
    snapshot: dict[str, Any],
):
    """Return the exact selected-game roster snapshot for the rest of this render."""
    def wrapped(row):
        game_pk = _safe_int(row.get("game_pk"), -1)
        if game_pk == _safe_int(snapshot.get("game_pk"), -2) and snapshot.get("players"):
            return copy.deepcopy(snapshot["players"])
        return original(row)
    return wrapped


def _render_identity_selectors(
    games_df,
    snapshot: dict[str, Any],
    original_all_hitters: Callable[[Any], list[dict[str, Any]]],
) -> int:
    """Render one game selector + one player-ID selector and freeze the roster order."""
    options = list(range(len(games_df)))
    prior_game = _safe_int(st.session_state.get("mh12_game", 0), 0)
    if prior_game not in options:
        prior_game = 0
    if st.session_state.get("mx56_game") not in options:
        # Respect the already-certified Step 11 game widget when migrating state.
        legacy_game = _safe_int(st.session_state.get("mx51_game", prior_game), prior_game)
        st.session_state["mx56_game"] = legacy_game if legacy_game in options else prior_game

    st.markdown(
        '<div class="mx51-finder"><div class="mx51-finder-title">⚾ Find your matchup + hitter</div>'
        '<div class="mx51-finder-sub">Pick the game, then the hitter. Player identity is locked by MLB player ID for the entire research run.</div></div>',
        unsafe_allow_html=True,
    )

    game_index = st.selectbox(
        "1️⃣ Game",
        options,
        format_func=lambda i: selectors._game_picker_label(games_df.iloc[int(i)]),
        key="mx56_game",
    )
    game_index = _safe_int(game_index, prior_game)
    st.session_state["mh12_game"] = game_index
    st.session_state["mx51_game"] = game_index

    row = games_df.iloc[game_index]
    st.markdown(selectors._selected_game_html(row), unsafe_allow_html=True)

    players = list(original_all_hitters(row) or [])
    if not players:
        st.warning("No active hitters are available for this matchup yet.")
        snapshot.clear()
        return game_index

    id_to_index = _player_id_index(players)
    ordered_indices = step1._ordered_player_indices(players)
    ordered_ids: list[int] = []
    for index in ordered_indices:
        pid = _player_id(players[int(index)])
        if pid > 0 and pid not in ordered_ids:
            ordered_ids.append(pid)
    if not ordered_ids:
        st.warning("The active roster loaded without stable MLB player IDs, so player research is waiting for the official feed.")
        snapshot.clear()
        return game_index

    game_pk = _safe_int(row.get("game_pk"), game_index)
    player_key = f"mx56_player_id_{game_pk}"
    active_pk = _safe_int(st.session_state.get("mx56_active_game_pk"), -1)
    prior_pid = _safe_int(st.session_state.get("mx56_active_player_id"), 0)

    if st.session_state.get(player_key) not in ordered_ids:
        # Reuse the prior player only when the user is still on the same MLB game.
        st.session_state[player_key] = prior_pid if active_pk == game_pk and prior_pid in ordered_ids else ordered_ids[0]

    by_id = {pid: players[index] for pid, index in id_to_index.items()}
    selected_pid = st.selectbox(
        "2️⃣ Player",
        ordered_ids,
        format_func=lambda pid: selectors._player_picker_label(by_id[int(pid)]),
        key=player_key,
        help="Player selection is keyed by MLB player ID, not a roster-list position.",
    )
    selected_pid = _safe_int(selected_pid, ordered_ids[0])
    selected_index = id_to_index[selected_pid]

    # The frozen V2 model still expects the original-list index, so write the index
    # that corresponds to the selected immutable player ID in this exact snapshot.
    st.session_state["mh12_player"] = selected_index
    st.session_state["mx51_active_game_pk"] = game_pk
    st.session_state["mx56_active_game_pk"] = game_pk
    st.session_state["mx56_active_player_id"] = selected_pid

    snapshot.clear()
    snapshot.update(
        {
            "game_pk": game_pk,
            "game_index": game_index,
            "player_id": selected_pid,
            "player_index": selected_index,
            "players": copy.deepcopy(players),
        }
    )

    st.markdown(
        '<div class="mx51-player-note">🔒 Selection lock: selector, spotlight, Steps 1–12 and final result now share this exact MLB player ID + frozen game roster snapshot.</div>',
        unsafe_allow_html=True,
    )
    return game_index


def _display_grade(edge: dict[str, str]) -> tuple[str, str]:
    label = str((edge or {}).get("label") or "EDGE PENDING").upper()
    kind = str((edge or {}).get("kind") or "pending")
    translations = {
        "ELITE BATTER EDGE": "ELITE • BATTER",
        "STRONG BATTER EDGE": "STRONG • BATTER",
        "LEAN BATTER": "LEAN • BATTER",
        "NEUTRAL": "NEUTRAL",
        "NEUTRAL • VERIFIED": "VERIFIED • NEUTRAL",
        "NEUTRAL • PARTIAL": "PARTIAL • NEUTRAL",
        "LEAN PITCHER": "SLIGHTLY TOUGH • PITCHER",
        "STRONG PITCHER EDGE": "TOUGH • PITCHER",
        "ELITE PITCHER EDGE": "VERY TOUGH • PITCHER",
        "EDGE PENDING": "PENDING • NO EDGE",
    }
    return translations.get(label, label), kind


def _decorate_step(step_html: str) -> str:
    """Wrap the original data badge and strength grade into one guaranteed badge row."""
    edge = strength._strength_for_step(step_html)
    label, kind = _display_grade(edge)
    grade = f'<span class="mx56-grade {kind}">{label}</span>'

    import re
    match = re.search(r'(<div class="mxv2-badge">.*?</div>)', str(step_html or ""), flags=re.IGNORECASE | re.DOTALL)
    if not match:
        # Defensive fallback: if a future certified Step drops its data badge, place
        # the grade after the kicker rather than silently losing the requested read.
        kicker = re.search(r'(<div class="mxv2-kicker">.*?</div>)', str(step_html or ""), flags=re.IGNORECASE | re.DOTALL)
        if not kicker:
            return step_html
        block = f'<div class="mx56-badges">{grade}</div>'
        return step_html[: kicker.end()] + block + step_html[kicker.end() :]

    original_badge = match.group(1)
    block = f'<div class="mx56-badges">{original_badge}{grade}</div>'
    return step_html[: match.start()] + block + step_html[match.end() :]


def _owned_scouting_wrapper(original: Callable[..., str]):
    """Decorate the exact finished Step HTML at Step 14's final owned render boundary."""
    def wrapped(context, identity, step_html, raw, final, notices):
        decorated = [_decorate_step(source) for source in list(step_html or [])]
        output = original(context, identity, decorated, raw, final, notices)
        legend = (
            '<div class="mx56-legend"><b>STEP STRENGTH</b>'
            '<span class="bat">GREEN = BATTER</span>'
            '<span class="pit">RED = TOUGH / PITCHER</span>'
            '<span class="neu">GOLD = NEUTRAL</span>'
            '<span class="pen">GRAY = PENDING / NO EDGE</span></div>'
        )
        marker = '<div class="mxv2-step '
        return output.replace(marker, legend + marker, 1) if marker in output else output
    return wrapped


def render_matchup_hub(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    if games_df is None or games_df.empty:
        return current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)

    st.markdown(_STEP16_CSS, unsafe_allow_html=True)

    snapshot: dict[str, Any] = {}
    original_all_hitters = roster._all_hitters_v14
    original_selectors = selectors._render_stable_selectors
    original_owned = current._owned_scouting_html

    def render_selectors(gdf):
        return _render_identity_selectors(gdf, snapshot, original_all_hitters)

    selectors._render_stable_selectors = render_selectors
    roster._all_hitters_v14 = _stable_roster_wrapper(original_all_hitters, snapshot)
    current._owned_scouting_html = _owned_scouting_wrapper(original_owned)
    try:
        return current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        current._owned_scouting_html = original_owned
        roster._all_hitters_v14 = original_all_hitters
        selectors._render_stable_selectors = original_selectors


__all__ = [
    "FROZEN_MATCHUP_CHAIN",
    "FROZEN_STEP14_PRESENTATION",
    "FROZEN_STEP15_PRESENTATION",
    "VERSION",
    "_decorate_step",
    "_display_grade",
    "_player_id_index",
    "_render_identity_selectors",
    "_stable_roster_wrapper",
    "render_matchup_hub",
]
