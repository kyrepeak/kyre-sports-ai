"""WNBA Rebounds V1.8 — Step 9 position matchup context.

Extends verified V1.7.1 without changing Steps 1-8.

Step-9 goals:
- Classify each modeled player into Guard / Wing / Big using the verified current
  roster POSITION already carried through the Rebounds pipeline.
- Build each opponent's positional rebound-capture composition from already-
  verified Step-5/Step-6 player data. No new network request is introduced.
- Combine that positional competition context with the already-verified Step-7
  missed-shot environment and Step-8 rebound-allowed context to create a clearly
  labeled position-context index.
- This index is context only. It is NOT yet applied to a player projection.
- Pace remains deferred to Step 10. Sportsbook lines and Monte Carlo remain off.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd
import streamlit as st

import wnba_rebounds_hub_v171 as base

MODEL_VERSION = "WNBA REBOUNDS V1.8 • STEP 9 POSITION MATCHUP — GUARD/WING/BIG"


def _num(value, default=np.nan):
    try:
        if value is None or value == "":
            return default
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _position_bucket(value: str) -> str:
    """Collapse ESPN/NBA-style positions into Guard / Wing / Big.

    Hybrid rules are intentionally deterministic:
    - G, PG, SG => Guard
    - G-F / F-G / SF / F => Wing
    - F-C / C-F / PF / C => Big
    Unknown positions stay CHECK rather than being guessed.
    """
    text = str(value or "").upper().strip()
    compact = re.sub(r"[^A-Z]", "", text)

    if compact in {"PG", "SG", "G", "POINTGUARD", "SHOOTINGGUARD"}:
        return "Guard"
    if compact in {"SF", "F", "GF", "FG", "SMALLFORWARD", "FORWARD"}:
        return "Wing"
    if compact in {"PF", "C", "FC", "CF", "POWERFORWARD", "CENTER"}:
        return "Big"

    # Conservative token fallback for full-name or uncommon hybrid strings.
    if "CENTER" in compact or compact.endswith("C"):
        return "Big"
    if "POWERFORWARD" in compact:
        return "Big"
    if "SMALLFORWARD" in compact:
        return "Wing"
    if "GUARD" in compact:
        return "Guard"
    if "FORWARD" in compact:
        return "Wing"
    return "CHECK"


def _player_capture_value(row: pd.Series) -> float:
    """Use already-verified Step-6/Step-5 rebound infrastructure only."""
    for key in (
        "STEP6_MIN_SCALED_REB",
        "OPP_BASELINE_MIN_SCALED_REB",
    ):
        val = _num(row.get(key))
        if np.isfinite(val) and val >= 0:
            return float(val)

    rate = _num(row.get("STEP6_BASELINE_REB36"))
    if not np.isfinite(rate):
        rate = _num(row.get("FORM_STABILIZED_REB36"))
    mins = _num(row.get("PROJ_MIN"), 0.0)
    if np.isfinite(rate) and rate >= 0 and mins > 0:
        return float(rate * mins / 36.0)
    return np.nan


def _team_position_profile(players: pd.DataFrame) -> pd.DataFrame:
    if players is None or players.empty:
        return pd.DataFrame()

    frame = players.copy()
    frame["PROJ_MIN"] = pd.to_numeric(frame.get("PROJ_MIN"), errors="coerce").fillna(0.0)
    frame = frame[frame["PROJ_MIN"].ge(5.0)].copy()
    if frame.empty:
        return pd.DataFrame()

    frame["Position bucket"] = frame.get("POSITION", "").map(_position_bucket)
    frame["Capture baseline"] = frame.apply(_player_capture_value, axis=1)
    frame = frame[
        frame["Position bucket"].isin(["Guard", "Wing", "Big"])
        & pd.to_numeric(frame["Capture baseline"], errors="coerce").notna()
    ].copy()
    if frame.empty:
        return pd.DataFrame()

    rows = []
    for team, part in frame.groupby("TEAM_NAME", sort=False):
        total = float(pd.to_numeric(part["Capture baseline"], errors="coerce").sum())
        for bucket in ("Guard", "Wing", "Big"):
            b = part[part["Position bucket"].eq(bucket)]
            capture = float(pd.to_numeric(b["Capture baseline"], errors="coerce").sum())
            rows.append({
                "Team": str(team),
                "Position": bucket,
                "Rotation players": int(len(b)),
                "Capture baseline": capture,
                "Capture share": capture / total if total > 0 else np.nan,
            })
    return pd.DataFrame(rows)


def _team_lookup(records, key, value_key):
    out = {}
    for row in records or []:
        name = str(row.get(key) or "")
        if not name:
            continue
        out[name] = _num(row.get(value_key))
    return out


def _opponent_lookup(records):
    out = {}
    for row in records or []:
        team = str(row.get("Team") or "")
        opp = str(row.get("Opponent") or "")
        if team and opp:
            out[team] = opp
    return out


def _build_step9():
    player_records = (
        st.session_state.get("wnba_rebounds_step6_players")
        or st.session_state.get("wnba_rebounds_step5_players")
        or []
    )
    players = pd.DataFrame(player_records)
    step7 = st.session_state.get("wnba_rebounds_step7_teams") or []
    step8 = st.session_state.get("wnba_rebounds_step8_teams") or []

    if players.empty:
        return pd.DataFrame(), pd.DataFrame(), {
            "ready": False,
            "players": 0,
            "covered": 0,
            "reason": "no verified Step-5/6 player frame",
        }

    profile = _team_position_profile(players)
    if profile.empty:
        return pd.DataFrame(), pd.DataFrame(), {
            "ready": False,
            "players": 0,
            "covered": 0,
            "reason": "no verified positional rebound profile",
        }

    opp_map = _opponent_lookup(step8 or step7)
    miss_idx = _team_lookup(step7, "Team", "Slate miss index")
    allowed_idx = _team_lookup(step8, "Team", "Rebound-allowed index")

    # Slate-relative average opponent capture share by bucket.
    bucket_avg = {}
    for bucket, part in profile.groupby("Position"):
        vals = pd.to_numeric(part["Capture share"], errors="coerce")
        bucket_avg[bucket] = float(vals.mean()) if vals.notna().any() else np.nan

    prof_key = {
        (str(r["Team"]), str(r["Position"])): r
        for _, r in profile.iterrows()
    }

    frame = players.copy()
    frame["PROJ_MIN"] = pd.to_numeric(frame.get("PROJ_MIN"), errors="coerce").fillna(0.0)
    frame = frame[frame["PROJ_MIN"].ge(5.0)].copy()
    frame["Position bucket"] = frame.get("POSITION", "").map(_position_bucket)

    rows = []
    for _, row in frame.iterrows():
        team = str(row.get("TEAM_NAME") or "")
        opp = str(opp_map.get(team) or "")
        bucket = str(row.get("Position bucket") or "CHECK")
        p = prof_key.get((opp, bucket), {}) if opp and bucket != "CHECK" else {}
        opp_share = _num(p.get("Capture share"))
        avg_share = _num(bucket_avg.get(bucket))

        # >1 means opponent concentrates more rebound capture in this player's
        # bucket than the slate norm, i.e. more same-zone competition.
        competition_idx = (
            opp_share / avg_share
            if np.isfinite(opp_share) and np.isfinite(avg_share) and avg_share > 0
            else np.nan
        )

        env = np.nan
        m = _num(miss_idx.get(team))
        a = _num(allowed_idx.get(team))
        if np.isfinite(m) and np.isfinite(a) and m > 0 and a > 0:
            env = m * a

        # Position context is a diagnostic ratio only; it is not applied to a
        # projection in Step 9. >1 = more favorable relative context.
        pos_context = (
            env / competition_idx
            if np.isfinite(env) and np.isfinite(competition_idx) and competition_idx > 0
            else np.nan
        )

        covered = bool(
            bucket in {"Guard", "Wing", "Big"}
            and bool(opp)
            and np.isfinite(opp_share)
            and np.isfinite(competition_idx)
            and np.isfinite(pos_context)
        )
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

    # Team/bucket board keeps the underlying positional composition visible.
    board = profile.copy()
    board["Capture share"] = pd.to_numeric(board["Capture share"], errors="coerce")

    return out, board, {
        "ready": ready,
        "players": int(len(out)),
        "covered": covered,
        "teams": int(profile["Team"].nunique()) if not profile.empty else 0,
        "method": "verified roster position + already-built rebound capture composition",
    }


def _render_step9():
    frame, board, info = _build_step9()
    st.session_state["wnba_rebounds_step9_ready"] = bool(info.get("ready"))
    st.session_state["wnba_rebounds_step9_players"] = (
        frame.to_dict("records") if not frame.empty else []
    )

    st.markdown("## 🧭 Step 9 — Position Matchup: Guard / Wing / Big")
    st.caption(
        "This layer classifies each modeled player by verified roster position, then measures how the opponent's "
        "rotation concentrates rebound capture across Guard/Wing/Big groups. It reuses already-verified Steps 5-8 data, "
        "so Step 9 adds no normal-load network requests. The position-context index is diagnostic only and does not yet "
        "change a player rebound projection. Pace remains deferred to Step 10."
    )

    a, b, c, d = st.columns(4)
    a.metric("Player checks", f"{info.get('covered',0)}/{info.get('players',0)}")
    b.metric("Profiled teams", info.get("teams", 0))
    c.metric("Buckets", "G / W / B")
    d.metric("New network", "NONE")

    if info.get("ready"):
        st.success(
            "✅ STEP 9 PASSED • every modeled rotation player has a verified Guard/Wing/Big bucket, opponent positional "
            "capture profile, and matchup-context index. Step 10 (pace + expected shot volume) is unlocked. "
            "No final player rebound projection exists yet."
        )
    else:
        st.error(
            "⛔ STEP 9 CHECK • at least one modeled rotation player lacks verified position/opponent positional context. "
            "Step 10 remains locked; unknown positions are not guessed."
        )

    if not frame.empty:
        display = frame.copy()
        for col in (
            "Proj MIN", "Opp positional capture share",
            "Same-position competition index", "Step7 miss index",
            "Step8 allowed index", "Position context index",
        ):
            display[col] = pd.to_numeric(display[col], errors="coerce").round(3)
        st.dataframe(
            display[[
                "Player", "Team", "Opponent", "Raw position", "Position bucket",
                "Proj MIN", "Opp positional capture share",
                "Same-position competition index", "Position context index", "State",
            ]],
            hide_index=True,
            use_container_width=True,
        )

    with st.expander("🧭 Opponent positional rebound-capture board"):
        if board.empty:
            st.info("No verified positional team profile available.")
        else:
            b = board.copy()
            b["Capture baseline"] = pd.to_numeric(b["Capture baseline"], errors="coerce").round(2)
            b["Capture share"] = pd.to_numeric(b["Capture share"], errors="coerce").round(3)
            st.dataframe(b, hide_index=True, use_container_width=True)

    with st.expander("🧭 Step-9 methodology / diagnostics"):
        st.write({
            "source": info.get("method"),
            "new_network_requests": 0,
            "position_buckets": {
                "Guard": "G / PG / SG",
                "Wing": "F / SF / G-F / F-G",
                "Big": "PF / C / F-C / C-F",
            },
            "competition_index": "opponent same-bucket capture share / slate same-bucket average",
            "position_context_index": "(Step7 miss index × Step8 allowed index) / same-position competition index",
            "applied_to_projection": False,
            "pace_used": False,
            "sportsbook_used": False,
            "monte_carlo_used": False,
        })
        if not frame.empty and frame["State"].eq("CHECK").any():
            st.dataframe(
                frame.loc[frame["State"].eq("CHECK"), [
                    "Player", "Team", "Opponent", "Raw position", "Position bucket", "State"
                ]],
                hide_index=True,
                use_container_width=True,
            )

    st.markdown("## 🧱 Rebounds Build Order — Current")
    ready = bool(info.get("ready"))
    layers = [
        "Verified daily WNBA slate",
        "Current rosters + injuries/status",
        "Projected minutes + rotation",
        "Offensive/defensive rebound role",
        "Recent + season rebound form",
        "Rebound chances/opportunities",
        "Opponent missed-shot environment",
        "Opponent rebounding allowed",
        "Position matchup — Guard/Wing/Big",
        "Pace + expected shot volume",
    ]
    statuses = [
        "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE",
        "✅ BASELINE", "✅ LIVE", "✅ LIVE",
        "✅ LIVE" if ready else "⚠️ ACTIVE / CHECK",
        "➡️ NEXT" if ready else "🔒 LOCKED",
    ]
    st.dataframe(
        pd.DataFrame({"Step": range(1, 11), "Layer": layers, "Status": statuses}),
        hide_index=True,
        use_container_width=True,
    )
    st.caption(
        "⚡ V1.8 Step 9 only • zero new normal-load network calls • Steps 1–8 preserved • persistent fast-start retained • "
        "no sportsbook/Monte Carlo/final projected rebound output."
    )


def render_wnba_rebounds_hub(*args, **kwargs):
    out = base.render_wnba_rebounds_hub(*args, **kwargs)
    if st.session_state.get("wnba_rebounds_step8_ready"):
        _render_step9()
        # V1.7.1 writes before Step 9 exists. Save once more so Step-9 state is
        # included in the persistent reboot checkpoint without changing model math.
        try:
            base._write_snapshot()
        except Exception:
            pass
    else:
        st.info("Step 9 remains locked until Step 8 is verified.")
    return out


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
