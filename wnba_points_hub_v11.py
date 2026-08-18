"""WNBA Points V1.2 — isolated production page + pre-simulation readiness gate.

WNBA-only development surface. The known-good PRA V3.2.1 checkpoint is frozen on
branch wnba-pra-v321-frozen-20260818 and is not modified by this module.
MLB V2.1.7 remains frozen on mlb-v217-frozen-20260818.

This page intentionally keeps Points development separate from PRA and from the
future WNBA Daily Master Card until the Points connector passes validation.
It reuses only shared verified WNBA infrastructure (schedule, roster/role,
matchup context and SportsGameOdds transport). PRA totals are never used as a
shortcut for the Points projection.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_v10 as points
import wnba_schedule_v24 as schedule

MODEL_VERSION = "WNBA POINTS V1.2 • ISOLATED PAGE • PREFLIGHT"
PRA_FROZEN_BRANCH = "wnba-pra-v321-frozen-20260818"
PRA_FROZEN_COMMIT = "5f29fc48856a198d74bcdbde47821e55e275222a"
MLB_FROZEN_BRANCH = "mlb-v217-frozen-20260818"


def _default_day():
    existing = st.session_state.get("wnba_points_date") or st.session_state.get("wnba_pra_v2_date")
    if existing:
        try:
            return pd.to_datetime(existing).date()
        except Exception:
            pass
    return datetime.now(ZoneInfo("America/New_York")).date()


def _day_string(value):
    return pd.to_datetime(value).strftime("%Y-%m-%d")


def _status_counts(day):
    diag = schedule.schedule_diagnostics(day)
    try:
        pairs, snap = points._paired_points_markets(day)
    except Exception:
        pairs, snap = pd.DataFrame(), {}
    current = points.combined_rows(day)
    games = int(diag.get("games") or 0)
    market_players = 0 if pairs is None or pairs.empty else int(pairs["player_key"].nunique())
    exact_pairs = 0 if pairs is None else int(len(pairs))
    distributions = 0 if current is None or current.empty else int(
        current[["game_id", "player_key", "line"]].drop_duplicates().shape[0]
    )
    return diag, snap, games, market_players, exact_pairs, distributions


def _readiness_snapshot(day):
    try:
        projections, pairs, snap, pmeta, lineups = points._prepare(day)
    except Exception as exc:
        return {
            "error": str(exc), "projections": pd.DataFrame(), "pairs": pd.DataFrame(),
            "preview": pd.DataFrame(), "active_games": 0, "lineups_confirmed": 0,
            "market_players": 0, "matched_players": 0, "eligible_pairs": 0,
            "empirical_players": 0, "history_players": 0, "ready": False,
        }

    projections = projections if isinstance(projections, pd.DataFrame) else pd.DataFrame()
    pairs = pairs if isinstance(pairs, pd.DataFrame) else pd.DataFrame()
    schedule_df = pmeta.get("schedule") if isinstance(pmeta, dict) else pd.DataFrame()
    schedule_df = schedule_df if isinstance(schedule_df, pd.DataFrame) else pd.DataFrame()

    if schedule_df.empty:
        active = pd.DataFrame()
    else:
        status = schedule_df.apply(
            lambda r: str(r.get("status") or r.get("status_text") or "").upper(), axis=1
        )
        active = schedule_df.loc[~status.str.contains("FINAL", na=False)].copy()

    active_ids = set(active.get("game_id", pd.Series(dtype=str)).astype(str).tolist())
    active_games = len(active_ids)
    lineups_confirmed = sum(1 for gid in active_ids if bool((lineups or {}).get(gid, False)))

    if projections.empty or pairs.empty:
        return {
            "error": "", "projections": projections, "pairs": pairs, "preview": pd.DataFrame(),
            "active_games": active_games, "lineups_confirmed": lineups_confirmed,
            "market_players": 0 if pairs.empty else int(pairs["player_key"].nunique()),
            "matched_players": 0, "eligible_pairs": 0, "empirical_players": 0,
            "history_players": 0, "ready": False,
        }

    proj_cols = ["game_id", "player_key", "PLAYER_NAME", "PROJ_PTS", "RAW_PROJ_PTS", "PROJ_MIN", "ROLE_LABEL", "context_quality"]
    proj_cols = [c for c in proj_cols if c in projections.columns]
    proj_small = projections[proj_cols].copy()
    proj_small["game_id"] = proj_small["game_id"].astype(str)
    proj_small["player_key"] = proj_small["player_key"].astype(str)

    pair_small = pairs.copy()
    pair_small["game_id"] = pair_small["game_id"].astype(str)
    pair_small["player_key"] = pair_small["player_key"].astype(str)
    if active_ids:
        pair_small = pair_small.loc[pair_small["game_id"].isin(active_ids)].copy()

    matched = pair_small.merge(proj_small, on=["game_id", "player_key"], how="inner")
    market_players = int(pair_small["player_key"].nunique()) if not pair_small.empty else 0
    matched_players = int(matched["player_key"].nunique()) if not matched.empty else 0
    eligible_pairs = int(len(matched))

    empirical_players = 0
    history_players = 0
    history_meta = {}
    if not matched.empty:
        unique_proj = matched.drop_duplicates(["game_id", "player_key"])
        for _, row in unique_proj.iterrows():
            gid = str(row.get("game_id") or "")
            pkey = str(row.get("player_key") or "")
            _, _, dmeta = points._points_distribution(row, bool((lineups or {}).get(gid, False)))
            gp = int(dmeta.get("hist_games") or 0)
            history_meta[(gid, pkey)] = dmeta
            if gp > 0:
                history_players += 1
            if gp >= 5:
                empirical_players += 1

    preview_rows = []
    if not matched.empty:
        for _, row in matched.head(16).iterrows():
            gid = str(row.get("game_id") or "")
            pkey = str(row.get("player_key") or "")
            dmeta = history_meta.get((gid, pkey), {})
            proj = float(row.get("PROJ_PTS")) if pd.notna(row.get("PROJ_PTS")) else np.nan
            line = float(row.get("line")) if pd.notna(row.get("line")) else np.nan
            try:
                freshness, _ = points.market._freshness(row.get("market_age"))
            except Exception:
                freshness = "UNKNOWN"
            preview_rows.append({
                "Player": str(row.get("PLAYER_NAME") or row.get("player_name") or "Player"),
                "Book": str(row.get("book") or ""),
                "Line": line,
                "Proj PTS": round(proj, 2) if pd.notna(proj) else np.nan,
                "Proj-Line": round(proj - line, 2) if pd.notna(proj) and pd.notna(line) else np.nan,
                "Hist GP": int(dmeta.get("hist_games") or 0),
                "Variance": "EMPIRICAL" if int(dmeta.get("hist_games") or 0) >= 5 else "FALLBACK",
                "Lineup": "CONFIRMED" if bool((lineups or {}).get(gid, False)) else "PENDING",
                "Freshness": freshness,
            })

    preview = pd.DataFrame(preview_rows)
    coverage_ok = matched_players > 0 and market_players > 0 and matched_players == market_players
    ready = bool(active_games > 0 and eligible_pairs > 0 and coverage_ok)
    return {
        "error": "", "projections": projections, "pairs": pair_small, "preview": preview,
        "active_games": active_games, "lineups_confirmed": lineups_confirmed,
        "market_players": market_players, "matched_players": matched_players,
        "eligible_pairs": eligible_pairs, "empirical_players": empirical_players,
        "history_players": history_players, "ready": ready,
    }


def _render_readiness(day):
    info = _readiness_snapshot(day)
    st.markdown("### 🧪 Pre-Simulation Readiness")
    st.caption("Only upcoming games count here. FINAL games are excluded before projection matching, simulation and grading.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Upcoming games", info["active_games"])
    c2.metric("Projection coverage", f"{info['matched_players']}/{info['market_players']}")
    c3.metric("Eligible exact pairs", info["eligible_pairs"])
    c4.metric("Empirical history", f"{info['empirical_players']}/{info['matched_players']}")

    if info.get("error"):
        st.error(f"Preflight could not complete: {info['error']}")
        return info

    if info["ready"]:
        if info["lineups_confirmed"] < info["active_games"]:
            st.warning(
                f"⚠️ PRE-LINEUP READY • {info['lineups_confirmed']}/{info['active_games']} upcoming starting fives confirmed. "
                "The 5M pass may run now, but qualified plays remain MONITOR until explicit starters publish."
            )
        else:
            st.success("✅ PRODUCTION READY • schedule, projection coverage and exact Points markets passed preflight.")
    else:
        st.warning("⚠️ NOT READY FOR 5M • resolve missing projection/market coverage before simulation.")

    if info["matched_players"] and info["empirical_players"] < info["matched_players"]:
        missing = info["matched_players"] - info["empirical_players"]
        st.caption(
            f"🧬 Historical variance: {info['empirical_players']} player(s) have ≥5 verified prior games; "
            f"{missing} would use the labeled fallback variance if simulated."
        )
    elif info["matched_players"]:
        st.caption("🧬 Historical variance: every matched Points player has ≥5 verified prior games for empirical scoring variance.")

    if not info["preview"].empty:
        with st.expander("📋 Exact Points line + projection preview", expanded=True):
            st.dataframe(info["preview"], use_container_width=True, hide_index=True)
    return info


def _render_header(day):
    diag, snap, games, market_players, exact_pairs, distributions = _status_counts(day)
    verified = str(diag.get("state") or "").upper() in {"VERIFIED", "VERIFIED_OFF_DAY"}
    api_connected = bool(snap.get("connected")) if isinstance(snap, dict) else False
    if not api_connected and isinstance(snap, dict):
        api_connected = str(snap.get("status") or "").upper() in {"CONNECTED", "OK", "READY"}

    st.markdown(
        """
<div style="border:1px solid #2f6381;background:linear-gradient(145deg,#091c2d,#071421);border-radius:20px;padding:16px;margin:8px 0 14px">
  <div style="font-size:10px;letter-spacing:1.35px;font-weight:950;color:#65dcff">KYRE SPORTS AI • WNBA POINTS • ISOLATED PRODUCTION PAGE</div>
  <div style="font-size:30px;font-weight:1000;color:white;margin-top:5px">🏀 WNBA Points Command Center — V1.2</div>
  <div style="font-size:12px;color:#93aabd;line-height:1.55;margin-top:7px">Points-only development surface. PRA V3.2.1 is frozen and the WNBA Daily Master Card is intentionally not fed by Points until this page passes validation.</div>
</div>
""",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Verified games", games)
    c2.metric("Points market players", market_players)
    c3.metric("Exact same-book pairs", exact_pairs)
    c4.metric("5M distributions", distributions)

    if verified:
        st.success(f"✅ WNBA schedule verified for {day} • PRA frozen • MLB frozen")
    else:
        st.warning(f"⚠️ WNBA schedule state: {diag.get('state') or 'UNKNOWN'}")

    if api_connected or exact_pairs > 0:
        st.caption("🎯 SportsGameOdds WNBA Points transport is available. Sportsbook lines grade the model only; they never move the Points projection.")
    else:
        st.caption("🎯 SportsGameOdds Points markets have not matched yet. No market is fabricated when an exact pair is unavailable.")


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.caption(
        "🏀 WNBA Points V1.2 • separate production page ACTIVE • PRA V3.2.1 frozen • "
        "SportsGameOdds WNBA • MLB V2.1.7 frozen"
    )

    selected = st.date_input(
        "WNBA Points slate date",
        value=_default_day(),
        key="wnba_points_date_control",
    )
    day = _day_string(selected)
    st.session_state["wnba_points_date"] = day

    _render_header(day)

    with st.expander("🧊 Freeze / isolation status", expanded=False):
        st.write(f"PRA checkpoint: `{PRA_FROZEN_BRANCH}` @ `{PRA_FROZEN_COMMIT[:12]}`")
        st.write(f"MLB checkpoint: `{MLB_FROZEN_BRANCH}`")
        st.write("Points work is isolated from both frozen production stacks. Shared data utilities may be read, but PRA/MLB model files are not changed by this page.")

    readiness = _render_readiness(day)
    points.render_points_connector(day)

    if readiness.get("ready"):
        st.info(
            "Phase 1 preflight passed. Run the Points 5M standard pass once; then validate convergence, empirical variance, persistence and decision gates before connecting Points to the WNBA Daily Master Card."
        )
    else:
        st.info(
            "Phase 1 rule: do not run 5M until the Points preflight shows complete upcoming projection + exact-market coverage."
        )


__all__ = [
    "MODEL_VERSION",
    "PRA_FROZEN_BRANCH",
    "PRA_FROZEN_COMMIT",
    "MLB_FROZEN_BRANCH",
    "render_wnba_points_hub",
]
