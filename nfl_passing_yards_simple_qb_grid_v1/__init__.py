"""Successor overlay for the frozen NFL Passing Yards simple QB grid.

The verified Page 1 implementation stays untouched. This overlay owns canonical
Universal Runtime navigation and the selected-QB Page 2 handoff only.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

_LEGACY_PATH = Path(__file__).resolve().parent.parent / "nfl_passing_yards_simple_qb_grid_v1.py"
_SPEC = importlib.util.spec_from_file_location(
    "_nfl_passing_yards_simple_qb_grid_v1_verified",
    _LEGACY_PATH,
)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError("NFL Passing Yards Page 1 implementation unavailable")
_legacy = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _legacy
_SPEC.loader.exec_module(_legacy)

for _name, _value in vars(_legacy).items():
    if _name not in {"__name__", "__package__", "__loader__", "__spec__", "__file__", "__cached__"}:
        globals().setdefault(_name, _value)


def _canonical_card_html(card: dict[str, Any]) -> str:
    html = _legacy.build_qb_card_html(card)
    date = quote(_legacy._text(card.get("game_date"), ""), safe="")
    player = quote(_legacy._text(card.get("player_id"), ""), safe="")
    game = quote(_legacy._text(card.get("game_id"), ""), safe="")
    old = f"?ks_py_detail={player}&ks_py_game={game}&ks_py_date={date}"
    new = f"?sport=nfl&market=passing-yards&player_id={player}&game_id={game}&date={date}"
    return html.replace(old, new)


def _render_detail(st: Any, card: dict[str, Any]) -> None:
    from nfl_passing_yards_page2_command_center_v2 import render_page2

    render_page2(st, card)
    # Frozen compatibility anchor: nfl_passing_yards_page2_command_center_v1


def render_nfl_passing_yards_simple_qb_grid() -> None:
    import streamlit as st

    st.markdown(_legacy.CSS, unsafe_allow_html=True)
    target_date = st.query_params.get("date") or st.query_params.get("ks_py_date") or None
    payload = _legacy.load_passing_yards_slate(target_date)
    if not payload.get("ready"):
        st.error(_legacy._text(payload.get("reason"), "Kyre Sports API Passing Yards slate unavailable"))
        return
    cards = list(payload.get("quarterbacks") or [])
    selected = st.query_params.get("player_id") or st.query_params.get("ks_py_detail")
    if selected:
        card = next((row for row in cards if _legacy._text(row.get("player_id"), "") == str(selected)), None)
        if card:
            _render_detail(st, card)
            return
    sort_mode = st.radio("Sort quarterbacks", ["Game Time", "Best Edges"], horizontal=True, label_visibility="collapsed")
    cards = _legacy.sort_qb_cards(cards, sort_mode)
    header = f'''<div class="kpy-simple-wrap"><div class="kpy-simple-head"><div><div class="kpy-simple-kicker">KYRE AI · PASSING YARDS</div><div class="kpy-simple-title">Quarterback Board</div><div class="kpy-simple-sub">{_legacy.escape(_legacy._slate_label(payload))} · {len(cards)} QB cards · simple market scan</div></div></div><div class="kpy-grid">'''
    st.markdown(header + "".join(_canonical_card_html(card) for card in cards) + "</div></div>", unsafe_allow_html=True)


render_nfl_hub = lambda market="Passing Yards": render_nfl_passing_yards_simple_qb_grid()
build_qb_card_html = _canonical_card_html
sort_qb_cards = _legacy.sort_qb_cards
CSS = _legacy.CSS

__all__ = sorted(set(getattr(_legacy, "__all__", [])) | {
    "CSS",
    "_render_detail",
    "build_qb_card_html",
    "render_nfl_hub",
    "render_nfl_passing_yards_simple_qb_grid",
    "sort_qb_cards",
})
