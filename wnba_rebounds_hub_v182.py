"""WNBA Rebounds V1.8.2 — Step 9 opponent-map/full-slate repair.

Repairs Step 9 only. Steps 1-8 and Step-9 position math remain unchanged.
The repair derives team↔opponent pairs from the verified selected-day slate and
rebuilds cached Step-7/8 context for the full slate so live/final games are not
silently dropped from the positional join.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_schedule_v24 as schedule_v24
import wnba_rebounds_hub_v16 as step7mod
import wnba_rebounds_hub_v17 as step8mod
import wnba_rebounds_hub_v18 as _impl
import wnba_rebounds_hub_v181 as safe

MODEL_VERSION = "WNBA REBOUNDS V1.8.2 • STEP 9 FULL-SLATE OPPONENT JOIN REPAIR"


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _records_lookup(records, value_key):
    out = {}
    for row in records or []:
        team = str(row.get("Team") or "")
        if team:
            out[team] = _num(row.get(value_key))
    return out


def _slate_maps(slate: pd.DataFrame):
    opp = {}
    if slate is None or slate.empty:
        return opp
    for _, r in slate.iterrows():
        away = str(r.get("away_team") or "")
        home = str(r.get("home_team") or "")
        if away and home:
            opp[away] = home
            opp[home] = away
    return opp


def _build_step9_repaired():
    player_records = (
        st.session_state.get("wnba_rebounds_step6_players")
        or st.session_state.get("wnba_rebounds_step5_players")
        or []
    )
    players = pd.DataFrame(player_records)
    if players.empty:
        return pd.DataFrame(), pd.DataFrame(), {
            "ready": False, "players": 0, "covered": 0,
            "reason": "no verified Step-5/6 player frame",
        }

    profile = _impl._team_position_profile(players)
    if profile.empty:
        return pd.DataFrame(), pd.DataFrame(), {
            "ready": False, "players": 0, "covered": 0,
            "reason": "no verified positional rebound profile",
        }

    day = str(st.session_state.get("wnba_rebounds_step1_day") or pd.Timestamp.now().strftime("%Y-%m-%d"))
    try:
        slate = schedule_v24.schedule_for_date(day)
    except Exception:
        slate = pd.DataFrame()

    # Build the matchup identity from the verified slate itself, not from Step-8
    # session rows that may have been created from an incomplete live-state view.
    opp_map = _slate_maps(slate)

    # Reconcile Step 7/8 against the same full verified slate. These builders are
    # six-hour cached, so existing team-stat payloads are reused and only missing
    # slate teams can require work.
    try:
        step7_frame, step7_info = step7mod._build_step7_cached(day, slate)
    except Exception:
        step7_frame, step7_info = pd.DataFrame(), {}
    try:
        step8_frame, step8_info = step8mod._build_step8_cached(day, slate)
    except Exception:
        step8_frame, step8_info = pd.DataFrame(), {}

    step7 = step7_frame.to_dict("records") if not step7_frame.empty else (st.session_state.get("wnba_rebounds_step7_teams") or [])
    step8 = step8_frame.to_dict("records") if not step8_frame.empty else (st.session_state.get("wnba_rebounds_step8_teams") or [])

    # Keep session snapshots synchronized with the repaired full-slate context.
    if step7:
        st.session_state["wnba_rebounds_step7_teams"] = step7
        st.session_state["wnba_rebounds_step7_ready"] = bool((step7_info or {}).get("ready", True))
    if step8:
        st.session_state["wnba_rebounds_step8_teams"] = step8
        st.session_state["wnba_rebounds_step8_ready"] = bool((step8_info or {}).get("ready", True))

    miss_idx = _records_lookup(step7, "Slate miss index")
    allowed_idx = _records_lookup(step8, "Rebound-allowed index")

    bucket_avg = {}
    for bucket, part in profile.groupby("Position"):
        vals = pd.to_numeric(part["Capture share"], errors="coerce")
        bucket_avg[bucket] = float(vals.mean()) if vals.notna().any() else np.nan

    prof_key = {(str(r["Team"]), str(r["Position"])): r for _, r in profile.iterrows()}

    frame = players.copy()
    frame["PROJ_MIN"] = pd.to_numeric(frame.get("PROJ_MIN"), errors="coerce").fillna(0.0)
    frame = frame[frame["PROJ_MIN"].ge(5.0)].copy()
    frame["Position bucket"] = frame.get("POSITION", "").map(_impl._position_bucket)

    rows = []
    for _, row in frame.iterrows():
        team = str(row.get("TEAM_NAME") or "")
        opp = str(opp_map.get(team) or "")
        bucket = str(row.get("Position bucket") or "CHECK")
        p = prof_key.get((opp, bucket), {}) if opp and bucket != "CHECK" else {}
        opp_share = _num(p.get("Capture share"))
        avg_share = _num(bucket_avg.get(bucket))
        competition_idx = opp_share / avg_share if np.isfinite(opp_share) and np.isfinite(avg_share) and avg_share > 0 else np.nan
        m = _num(miss_idx.get(team))
        a = _num(allowed_idx.get(team))
        env = m * a if np.isfinite(m) and np.isfinite(a) and m > 0 and a > 0 else np.nan
        pos_context = env / competition_idx if np.isfinite(env) and np.isfinite(competition_idx) and competition_idx > 0 else np.nan
        covered = bool(bucket in {"Guard", "Wing", "Big"} and opp and np.isfinite(opp_share) and np.isfinite(competition_idx) and np.isfinite(pos_context))
        rows.append({
            "Player": str(row.get("PLAYER_NAME") or "Player"),
            "Team": team,
            "Opponent": opp or "—",
            "Raw position": str(row.get("POSITION") or ""),
            "Position bucket": bucket,
            "Proj MIN": _num(row.get("PROJ_MIN")),
            "Opp positional capture share": opp_share,
            "Same-position competition index": competition_idx,
            "Step7 miss index": m,
            "Step8 allowed index": a,
            "Position context index": pos_context,
            "State": "VERIFIED" if covered else "CHECK",
        })

    out = pd.DataFrame(rows)
    covered = int(out["State"].eq("VERIFIED").sum()) if not out.empty else 0
    ready = bool(not out.empty and covered == len(out))
    board = profile.copy()
    board["Capture share"] = pd.to_numeric(board["Capture share"], errors="coerce")
    return out, board, {
        "ready": ready,
        "players": int(len(out)),
        "covered": covered,
        "teams": int(profile["Team"].nunique()) if not profile.empty else 0,
        "method": "verified full-slate team↔opponent join + cached Step-7/8 context",
        "slate_games": int(len(slate)),
        "slate_opponent_pairs": int(len(opp_map)),
    }


def render_wnba_rebounds_hub(*args, **kwargs):
    old = _impl._build_step9
    _impl._build_step9 = _build_step9_repaired
    try:
        out = safe.render_wnba_rebounds_hub(*args, **kwargs)
    finally:
        _impl._build_step9 = old
    st.caption(
        "⚡ V1.8.2 Step-9 repair • opponent identity comes from the verified full slate • "
        "Step-7/8 context reconciled on the same slate • no guessed opponents • no final rebound projection."
    )
    return out


def __getattr__(name):
    return getattr(_impl, name)


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
