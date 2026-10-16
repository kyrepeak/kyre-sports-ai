"""NBA Spread Page 1 — Step 7 injury + availability overlay.

This additive wrapper preserves the frozen Step-6 page implementation and
injects one descriptive injury/availability section immediately before the
existing Upcoming / Live-Final game groups.
"""
from __future__ import annotations

from html import escape

import streamlit as st

import nba_spread_page_v1 as base
from nba_spread_injury_availability_v1 import (
    INJURY_SECTION_LABEL,
    load_injury_availability_features,
)

MODEL_VERSION = "NBA_SPREAD_PAGE_V2_STEP7_INJURY_AVAILABILITY"
STEP7_HEARTBEAT = "NBA_SPREAD_STEP7_INJURY_AVAILABILITY_ACTIVE"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False


@st.cache_data(ttl=90, show_spinner=False)
def _load_injury_availability(games: list[dict]) -> dict:
    return load_injury_availability_features(games)


def _status_summary(side: dict) -> str:
    counts = dict(side.get("counts") or {})
    pieces = []
    for label in ("OUT", "DOUBTFUL", "QUESTIONABLE", "PROBABLE"):
        count = int(counts.get(label) or 0)
        if count:
            pieces.append(f"{label.title()} {count}")
    return " • ".join(pieces) if pieces else "No listed limitations"


def _player_lines(side: dict) -> str:
    players = list(side.get("players") or [])
    if not players:
        return '<div style="font-size:.68rem;color:#71869a;margin-top:6px">No listed players from the verified current snapshot.</div>'
    rows = []
    for row in players[:6]:
        name = escape(str(row.get("player_name") or "Player"))
        status = escape(str(row.get("status") or "UNKNOWN").title())
        reason = escape(str(row.get("reason") or "Reason unavailable"))
        sources = int(row.get("source_count") or 0)
        rows.append(
            '<div style="border-top:1px solid rgba(148,163,184,.10);padding:6px 0">'
            f'<div style="font-size:.72rem;font-weight:900;color:#eef6fb">{name} • {status}</div>'
            f'<div style="font-size:.64rem;color:#7890a5;margin-top:2px">{reason} • {sources} source(s)</div>'
            '</div>'
        )
    return "".join(rows)


def _injury_card(feature: dict) -> str:
    away = escape(str(feature.get("away_tricode") or "—"))
    home = escape(str(feature.get("home_tricode") or "—"))
    verification = str(feature.get("verification") or "UNAVAILABLE")
    diagnostic = escape(str(feature.get("diagnostic_state") or "SOURCE_UNAVAILABLE"))
    providers = ", ".join(str(item) for item in (feature.get("providers_consulted") or [])) or "none"
    if not verification.startswith("VERIFIED"):
        return f"""
<div data-testid="nba-spread-step7-injury-unavailable" style="border:1px dashed rgba(103,216,255,.22);border-radius:16px;
padding:13px 15px;background:#09131f;margin:12px 0">
  <div style="font-size:.78rem;font-weight:900;color:#b9dceb">{INJURY_SECTION_LABEL} unavailable • {away} @ {home}</div>
  <div style="font-size:.7rem;color:#7890a5;margin-top:4px">Current injury context fails closed on stale, conflicting, or unmatched provider evidence.</div>
  <div style="font-size:.64rem;color:#61778b;margin-top:6px">{diagnostic} • consulted: {escape(providers)}</div>
</div>
"""

    away_side = dict(feature.get("away") or {})
    home_side = dict(feature.get("home") or {})
    fallback = verification == "VERIFIED_FALLBACK"
    badge = "Verified fallback" if fallback else "Verified"
    return f"""
<div data-testid="nba-spread-step7-injury-card" style="border:1px solid rgba(103,216,255,.30);border-radius:22px;
background:linear-gradient(140deg,rgba(8,18,31,.99),rgba(10,31,49,.97));padding:18px;margin:12px 0">
  <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start">
    <div>
      <div style="font-size:.72rem;font-weight:950;letter-spacing:.1em;text-transform:uppercase;color:#67d8ff">🏥 {INJURY_SECTION_LABEL}</div>
      <div style="font-size:1.16rem;font-weight:950;color:#f8fafc;margin-top:6px">{away} @ {home}</div>
    </div>
    <div style="font-size:.65rem;font-weight:900;color:#9bdff7">{badge}</div>
  </div>
  <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:14px">
    <div style="border:1px solid rgba(148,163,184,.14);border-radius:13px;padding:10px;background:rgba(5,12,20,.45)">
      <div style="font-size:.65rem;font-weight:950;color:#dbeafe">{away} • {escape(_status_summary(away_side))}</div>
      {_player_lines(away_side)}
    </div>
    <div style="border:1px solid rgba(148,163,184,.14);border-radius:13px;padding:10px;background:rgba(5,12,20,.45)">
      <div style="font-size:.65rem;font-weight:950;color:#dbeafe">{home} • {escape(_status_summary(home_side))}</div>
      {_player_lines(home_side)}
    </div>
  </div>
  <div style="font-size:.62rem;color:#688197;margin-top:10px">INJURIES field routing only • providers consulted: {escape(providers)} • model influence 0.0</div>
</div>
"""


def _render_injury_section(upcoming_games: list[dict]) -> None:
    st.markdown(
        f'<div style="font-size:.78rem;font-weight:950;letter-spacing:.08em;text-transform:uppercase;'
        f'color:#cbd5e1;margin:18px 0 9px">🏥 {escape(INJURY_SECTION_LABEL)}</div>',
        unsafe_allow_html=True,
    )
    if not upcoming_games:
        st.markdown(
            '<div style="border:1px dashed rgba(148,163,184,.18);border-radius:15px;padding:13px 15px;'
            'color:#7f93a8;font-size:.78rem">No verified upcoming NBA games require an injury snapshot.</div>',
            unsafe_allow_html=True,
        )
        return
    payload = _load_injury_availability(upcoming_games)
    features = list(payload.get("features") or [])
    if not features:
        st.markdown(
            '<div data-testid="nba-spread-step7-injury-unavailable" style="border:1px dashed rgba(103,216,255,.22);'
            'border-radius:16px;padding:13px 15px;background:#09131f;color:#7890a5;font-size:.72rem">'
            'Current injury context unavailable. Nothing is guessed.</div>',
            unsafe_allow_html=True,
        )
        return
    for feature in features:
        st.markdown(_injury_card(feature), unsafe_allow_html=True)


_ORIGINAL_RENDER_GAME_GROUP = base._render_game_group


def render_nba_spread_page() -> None:
    st.markdown(
        f'<div data-testid="nba-spread-step7-injury-active" data-heartbeat="{STEP7_HEARTBEAT}" style="display:none!important"></div>',
        unsafe_allow_html=True,
    )
    inserted = False

    def _render_game_group(title: str, games: list[dict], empty_text: str) -> None:
        nonlocal inserted
        if not inserted:
            inserted = True
            _render_injury_section(games if title == "Upcoming" else [])
        return _ORIGINAL_RENDER_GAME_GROUP(title, games, empty_text)

    base._render_game_group = _render_game_group
    try:
        return base.render_nba_spread_page()
    finally:
        base._render_game_group = _ORIGINAL_RENDER_GAME_GROUP


__all__ = [
    "MODEL_VERSION",
    "STEP7_HEARTBEAT",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_PROBABILITY",
    "render_nba_spread_page",
]
