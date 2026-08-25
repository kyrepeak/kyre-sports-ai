"""WNBA Live Games V4.3 — Step 4 rolling-date history repair.

Preserves Steps 1-3 and the existing V4 renderer. Only the Step-4 historical
transport is replaced. The history provider no longer depends on the failing
WNBA CDN or ESPN team-schedule discovery paths.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import streamlit as st

import wnba_live_hub_v4 as v4
import wnba_live_hub_v2 as v2
import wnba_live_second_half_v14 as hist14

ET = ZoneInfo("America/New_York")
MODEL_VERSION = "WNBA LIVE GAMES V4.3 • STEP 4 ESPN ROLLING-DATE HISTORY"


def _diag_text(meta: dict) -> str:
    meta = meta or {}
    scan = meta.get("scan") or {}
    pieces = [
        f"SOURCE {meta.get('source') or '—'}",
        f"CANDIDATE EVENTS {int(meta.get('candidate_events') or 0)}",
        f"SUMMARY OK {int(meta.get('summaries_ok') or 0)}",
        f"SUMMARY ERRORS {int(meta.get('summary_errors') or 0)}",
        f"USABLE GAMES {int(meta.get('games') or 0)}",
        f"DAYS SCANNED {int(scan.get('days_scanned') or 0)}",
        f"SCOREBOARD OK {int(scan.get('scoreboard_ok') or 0)}",
        f"SCOREBOARD ERRORS {int(scan.get('scoreboard_errors') or 0)}",
        f"MATCHED EVENTS {int(scan.get('matched_events') or 0)}",
    ]
    per_team = scan.get("per_team_found") or {}
    if per_team:
        pieces.append("TEAM EVENTS " + " | ".join(f"{k}: {v}" for k, v in per_team.items()))
    oldest = str(scan.get("oldest_day_scanned") or "")
    if oldest:
        pieces.append(f"OLDEST DATE {oldest}")
    rejected = meta.get("rejected") or {}
    if rejected:
        pieces.append("REJECTED " + escape(str(rejected)))
    err = str(meta.get("error") or "").strip()
    if err:
        pieces.append("ERROR " + escape(err))
    return " • ".join(pieces)


def render_wnba_live_hub(section_header=None, status_info=None, team_logo=None, h=None):
    old_hist = v4.hist
    old_model = v4.MODEL_VERSION
    v4.hist = hist14
    v4.MODEL_VERSION = MODEL_VERSION
    try:
        v4.render_wnba_live_hub(section_header, status_info, team_logo, h)
    finally:
        v4.hist = old_hist
        v4.MODEL_VERSION = old_model

    now = datetime.now(ET)
    day_str = now.strftime("%Y-%m-%d")
    try:
        games, _, _ = v2._verified_live_games(day_str)
    except Exception:
        games = []

    failures = []
    for game in games:
        try:
            profiles = hist14.profiles_for_game(game, int(day_str[:4]))
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
