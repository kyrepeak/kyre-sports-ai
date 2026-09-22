"""MLB Matchup Explorer player presentation V2.2.

Presentation-only wrapper around the frozen Step 1-5 Matchup Explorer chain.
No projection, probability, calibration, ranking, selection, or fair-odds math
is implemented here.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import mlb_matchup_hub_v10 as ui
import mlb_matchup_player_v19 as v19
import mlb_matchup_player_v20 as v20
import mlb_matchup_player_v21 as frozen

VERSION = "MLB Player Intelligence V2.2 UI"
FROZEN_PLAYER_CHAIN = (
    "mlb_matchup_player_v21",
    "mlb_matchup_player_v20",
    "mlb_matchup_player_v19",
    "mlb_matchup_player_v18",
    "mlb_matchup_player_v15",
)

_TECHNICAL_CAPTION_MARKERS = (
    "MLB Player Intelligence V",
    "MLB Matchup Hub V",
    "production projection engines unchanged",
    "standalone engines unchanged",
    "Step 3 is a research verdict",
    "Step 4 modifies only the Matchup Explorer",
    "Score is context-only in V1.8",
)


def _filtered_caption(original):
    def wrapped(body: Any, *args: Any, **kwargs: Any):
        text = str(body or "")
        if any(marker in text for marker in _TECHNICAL_CAPTION_MARKERS):
            return None
        return original(body, *args, **kwargs)
    return wrapped


def _bvp_text(verdict: dict[str, Any]) -> str:
    b = verdict.get("bvp_info") or {}
    if not b.get("ab"):
        return "No history"
    return f"{int(b.get('hits') or 0)}/{int(b.get('ab') or 0)} • AVG {float(b.get('avg') or 0):.3f}"


def _render_snapshot(slot, games_df) -> None:
    player, row = v20._selected_player(games_df)
    if not player or row is None:
        return
    info = v20._current_step4_info(games_df)
    if not info:
        return
    try:
        season = int(ui._date_str(row)[:4])
        verdict = v19._verdict_score(player, season)
    except Exception:
        return

    final = float(info.get("final") or 0.0)
    baseline = float(info.get("baseline") or 0.0)
    delta = float(info.get("delta") or 0.0)
    grade, _ = frozen._grade(final, verdict.get("score"), verdict.get("reliability"))
    starter = str(player.get("opponent_pitcher") or "TBD")
    hand = str(verdict.get("hand") or "—")
    hand_label = {"R": "RHP", "L": "LHP"}.get(hand, hand)
    rel = int(verdict.get("reliability") or 0)
    deep = bool(verdict.get("deep_loaded"))
    pitch = (
        f"{verdict.get('pitch_score')}/100 • {verdict.get('pitch_label')}"
        if verdict.get("pitch_score") is not None
        else "Not loaded"
    )
    direction = "+" if delta > 0 else ""
    lineup = str(player.get("source") or "")

    with slot.container():
        st.markdown(
            f'''<div class="mx22-snapshot">
              <div class="mx22-top">
                <div>
                  <div class="mx22-eyebrow">MATCHUP SNAPSHOT</div>
                  <div class="mx22-title">{ui._esc(player.get('name'))} <span>vs {ui._esc(starter)} ({ui._esc(hand_label)})</span></div>
                </div>
                <div class="mx22-grade">{ui._esc(grade)}</div>
              </div>
              <div class="mx22-main">
                <div class="mx22-prob"><b>{final*100:.1f}%</b><span>Final Explorer 1+ Hit</span></div>
                <div class="mx22-quick">
                  <div><span>Reliability</span><b>{rel}%</b></div>
                  <div><span>Matchup</span><b>{int(verdict.get('score') or 50)}/100</b></div>
                  <div><span>Step 4</span><b>{direction}{delta*100:.1f} pts</b></div>
                </div>
              </div>
              <div class="mx22-foot">{ui._esc(lineup)} • {'Deep pitch verified' if deep else 'Fast matchup data'} • pre-matchup {baseline*100:.1f}%</div>
            </div>''',
            unsafe_allow_html=True,
        )
        with st.expander("🔎 More matchup evidence", expanded=False):
            st.markdown(
                f'''<div class="mx22-evidence">
                  <div><span>BvP</span><b>{ui._esc(_bvp_text(verdict))}</b></div>
                  <div><span>Platoon</span><b>{float(verdict.get('platoon') or 0):+.2f}</b></div>
                  <div><span>Starter form</span><b>{float(verdict.get('form') or 0):+.2f}</b></div>
                  <div><span>Deep pitch</span><b>{ui._esc(pitch)}</b></div>
                </div>''',
                unsafe_allow_html=True,
            )


def render_player_layer(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    """Render frozen Steps 1-4 plus a compact Step 5 snapshot at the top."""
    snapshot_slot = st.empty()
    original_caption = st.caption
    st.caption = _filtered_caption(original_caption)
    try:
        v20.render_player_layer(games_df, section_header, status_info, team_logo, h)
    finally:
        st.caption = original_caption
    _render_snapshot(snapshot_slot, games_df)


__all__ = ["FROZEN_PLAYER_CHAIN", "VERSION", "render_player_layer"]
