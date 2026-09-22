"""WNBA Rebounds V1.5.1 — Step 6 speed + timezone reliability patch.

This wrapper keeps the V1.5 model logic unchanged while:
- preventing timezone crashes when the host lacks system tzdata;
- adding a session snapshot for the completed Step-6 build so repeated reruns do
  not refetch/reprocess the same official tracking data for the same slate and
  player/minute signature;
- preserving all Step 1–6 verification gates and keeping sportsbook/Monte Carlo
  logic disabled.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json

import pandas as pd
import streamlit as st

import wnba_rebounds_hub_v15 as base

MODEL_VERSION = "WNBA REBOUNDS V1.5.1 • STEP 6 FAST SNAPSHOT + TZ SAFE"

_ORIGINAL_BUILD = base._build_step6


def _safe_et_day() -> str:
    """Return the Eastern calendar day without making tzdata a hard runtime dependency."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    except Exception:
        # UTC fallback is only used when the host has no timezone database. The
        # normal slate-date selector/session value remains authoritative.
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _step5_signature(frame: pd.DataFrame, day: str) -> str:
    if frame is None or frame.empty:
        raw = {"day": str(day), "players": []}
    else:
        cols = [c for c in ["PLAYER_ID", "PLAYER_NAME", "TEAM_NAME", "PROJ_MIN"] if c in frame.columns]
        slim = frame[cols].copy() if cols else frame.copy()
        if "PROJ_MIN" in slim.columns:
            slim["PROJ_MIN"] = pd.to_numeric(slim["PROJ_MIN"], errors="coerce").round(2)
        raw = {"day": str(day), "players": slim.fillna("").to_dict("records")}
    payload = json.dumps(raw, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _build_step6_fast(step5_players: pd.DataFrame, day: str):
    """Reuse the verified Step-6 snapshot when the slate/player inputs are unchanged."""
    signature = _step5_signature(step5_players, day)
    if st.session_state.get("wnba_rebounds_step6_signature") == signature:
        p = st.session_state.get("wnba_rebounds_step6_snapshot_players")
        t = st.session_state.get("wnba_rebounds_step6_snapshot_teams")
        i = st.session_state.get("wnba_rebounds_step6_snapshot_info")
        if isinstance(p, list) and isinstance(t, list) and isinstance(i, dict):
            info = dict(i)
            info["snapshot_reused"] = True
            return pd.DataFrame(p), pd.DataFrame(t), info

    players, teams, info = _ORIGINAL_BUILD(step5_players, day)
    st.session_state["wnba_rebounds_step6_signature"] = signature
    st.session_state["wnba_rebounds_step6_snapshot_players"] = players.to_dict("records") if players is not None and not players.empty else []
    st.session_state["wnba_rebounds_step6_snapshot_teams"] = teams.to_dict("records") if teams is not None and not teams.empty else []
    st.session_state["wnba_rebounds_step6_snapshot_info"] = dict(info or {})
    return players, teams, info


def render_wnba_rebounds_hub(*args, **kwargs):
    # Seed a safe slate date before V1.5 reaches its timezone fallback path.
    if not st.session_state.get("wnba_rebounds_slate_date"):
        st.session_state["wnba_rebounds_slate_date"] = _safe_et_day()

    old_build = base._build_step6
    base._build_step6 = _build_step6_fast
    try:
        out = base.render_wnba_rebounds_hub(*args, **kwargs)
    finally:
        base._build_step6 = old_build

    if st.session_state.get("wnba_rebounds_step6_signature"):
        st.caption("⚡ V1.5.1 speed layer active • unchanged Step-6 inputs reuse the verified session snapshot instead of repeating tracking work.")
    return out


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
