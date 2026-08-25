"""WNBA Live Games V4.1 — Step 4 summary-backed history repair.

Preserves the existing V4 renderer and Steps 1-3 exactly. This wrapper swaps only
Step 4's historical transport to wnba_live_second_half_v12. If the repaired
transport still returns zero usable games, a compact diagnostic panel is shown so
we can see whether team schedules, summaries, or quarter parsing failed instead
of silently displaying THIN / 0 GP forever.
"""
from __future__ import annotations

from html import escape
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

import wnba_live_hub_v4 as v4
import wnba_live_hub_v2 as v2
import wnba_live_second_half_v12 as hist12

ET = ZoneInfo("America/New_York")
MODEL_VERSION = "WNBA LIVE GAMES V4.1 • STEP 4 SUMMARY-BACKFILLED HISTORY"


def _diag_text(meta: dict) -> str:
    meta = meta or {}
    pieces = [
        f"SOURCE {meta.get('source') or '—'}",
        f"CANDIDATE EVENTS {int(meta.get('candidate_events') or 0)}",
        f"SUMMARY OK {int(meta.get('summaries_ok') or 0)}",
        f"SUMMARY ERRORS {int(meta.get('summary_errors') or 0)}",
        f"USABLE GAMES {int(meta.get('games') or 0)}",
    ]
    rejected = meta.get("rejected") or {}
    if rejected:
        pieces.append("REJECTED " + escape(str(rejected)))
    err = str(meta.get("error") or "").strip()
    if err:
        pieces.append("ERROR " + escape(err))
    return " • ".join(pieces)


def render_wnba_live_hub(section_header=None, status_info=None, team_logo=None, h=None):
    # Swap only the history provider used by V4's renderer.
    old_hist = v4.hist
    old_model = v4.MODEL_VERSION
    v4.hist = hist12
    v4.MODEL_VERSION = MODEL_VERSION
    try:
        v4.render_wnba_live_hub(section_header, status_info, team_logo, h)
    finally:
        v4.hist = old_hist
        v4.MODEL_VERSION = old_model

    # Diagnostic appears only when the repaired Step-4 transport still has no
    # usable sample. This is read-only and never feeds the future live model.
    now = datetime.now(ET)
    day_str = now.strftime("%Y-%m-%d")
    try:
        games, _, _ = v2._verified_live_games(day_str)
    except Exception:
        games = []
    failures = []
    for game in games:
        try:
            profiles = hist12.profiles_for_game(game, int(day_str[:4]))
        except Exception as exc:
            failures.append((game, {"error": str(exc)[:220]}))
            continue
        ap = profiles.get("away") or {}
        hp = profiles.get("home") or {}
        if int(ap.get("games") or 0) == 0 and int(hp.get("games") or 0) == 0:
            failures.append((game, profiles.get("meta") or {}))

    if failures:
        st.markdown("### 🔎 Step 4 transport diagnostic")
        for game, meta in failures:
            matchup = f"{game.get('away_team','Away')} @ {game.get('home_team','Home')}"
            st.warning(f"{matchup} • {_diag_text(meta)}")
