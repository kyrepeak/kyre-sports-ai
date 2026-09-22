"""WNBA Points V1.3 — clean isolated production command center.

WNBA-only development surface. The known-good PRA V3.2.1 checkpoint is frozen on
branch wnba-pra-v321-frozen-20260818 and is not modified by this module.
MLB V2.1.7 remains frozen on mlb-v217-frozen-20260818.

V1.3 keeps every verified game visible on the selected slate while separating
display state from model eligibility:
- FINAL games remain visible as DISPLAY ONLY and are never simulated/graded;
- upcoming games show Points market/player coverage and MODEL ELIGIBLE status;
- readiness, simulation controls, results and diagnostics are grouped cleanly.

Points uses verified WNBA schedule/roster/role/matchup infrastructure and
SportsGameOdds transport. PRA totals are never used as a shortcut for Points.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_v10 as points
import wnba_schedule_v24 as schedule

MODEL_VERSION = "WNBA POINTS V1.3 • CLEAN SLATE COMMAND CENTER"
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


def _safe_pairs(day):
    try:
        pairs, snap = points._paired_points_markets(day)
    except Exception:
        pairs, snap = pd.DataFrame(), {}
    if not isinstance(pairs, pd.DataFrame):
        pairs = pd.DataFrame()
    return pairs, snap if isinstance(snap, dict) else {}


def _slate_snapshot(day):
    try:
        games = schedule.schedule_for_date(day)
    except Exception:
        games = pd.DataFrame()
    if not isinstance(games, pd.DataFrame):
        games = pd.DataFrame()

    try:
        diag = schedule.schedule_diagnostics(day)
    except Exception:
        diag = {}

    pairs, snap = _safe_pairs(day)
    rows = []
    for _, g in games.iterrows():
        gid = str(g.get("game_id") or "")
        status_raw = str(g.get("status") or g.get("status_text") or "UNKNOWN").upper()
        is_final = "FINAL" in status_raw
        game_pairs = pairs.loc[pairs["game_id"].astype(str).eq(gid)].copy() if (not pairs.empty and "game_id" in pairs) else pd.DataFrame()
        player_count = int(game_pairs["player_key"].nunique()) if (not game_pairs.empty and "player_key" in game_pairs) else 0
        pair_count = int(len(game_pairs))
        if is_final:
            model_state = "FINAL • DISPLAY ONLY"
        elif pair_count > 0:
            model_state = "MODEL ELIGIBLE"
        else:
            model_state = "WAITING FOR POINTS MARKET"

        rows.append({
            "Matchup": f"{g.get('away_team') or 'Away'} @ {g.get('home_team') or 'Home'}",
            "Tip (ET)": str(g.get("first_tip_et") or "TBD"),
            "Venue": str(g.get("venue") or "TBD"),
            "Status": "FINAL" if is_final else str(g.get("status") or g.get("status_text") or "UPCOMING").upper(),
            "Points players": player_count,
            "Exact pairs": pair_count,
            "Model use": model_state,
            "_game_id": gid,
            "_is_final": is_final,
        })

    frame = pd.DataFrame(rows)
    total = len(frame)
    finals = int(frame["_is_final"].sum()) if not frame.empty else 0
    upcoming = total - finals
    upcoming_market_games = int(frame.loc[~frame["_is_final"], "Exact pairs"].gt(0).sum()) if not frame.empty else 0
    return {
        "games": games,
        "diag": diag,
        "pairs": pairs,
        "snapshot": snap,
        "table": frame,
        "total": total,
        "finals": finals,
        "upcoming": upcoming,
        "upcoming_market_games": upcoming_market_games,
    }


def _readiness_snapshot(day):
    try:
        projections, pairs, snap, pmeta, lineups = points._prepare(day)
    except Exception as exc:
        return {
            "error": str(exc), "preview": pd.DataFrame(), "active_games": 0,
            "lineups_confirmed": 0, "market_players": 0, "matched_players": 0,
            "eligible_pairs": 0, "empirical_players": 0, "ready": False,
        }

    projections = projections if isinstance(projections, pd.DataFrame) else pd.DataFrame()
    pairs = pairs if isinstance(pairs, pd.DataFrame) else pd.DataFrame()
    pmeta = pmeta if isinstance(pmeta, dict) else {}
    schedule_df = pmeta.get("schedule")
    schedule_df = schedule_df if isinstance(schedule_df, pd.DataFrame) else pd.DataFrame()

    if schedule_df.empty:
        active = pd.DataFrame()
    else:
        status = schedule_df.apply(lambda r: str(r.get("status") or r.get("status_text") or "").upper(), axis=1)
        active = schedule_df.loc[~status.str.contains("FINAL", na=False)].copy()

    active_ids = set(active.get("game_id", pd.Series(dtype=str)).astype(str).tolist())
    active_games = len(active_ids)
    lineups_confirmed = sum(1 for gid in active_ids if bool((lineups or {}).get(gid, False)))

    if projections.empty or pairs.empty:
        return {
            "error": "", "preview": pd.DataFrame(), "active_games": active_games,
            "lineups_confirmed": lineups_confirmed,
            "market_players": 0 if pairs.empty or "player_key" not in pairs else int(pairs["player_key"].nunique()),
            "matched_players": 0, "eligible_pairs": 0, "empirical_players": 0, "ready": False,
        }

    proj_cols = ["game_id", "player_key", "PLAYER_NAME", "PROJ_PTS", "RAW_PROJ_PTS", "PROJ_MIN", "ROLE_LABEL", "context_quality"]
    proj_small = projections[[c for c in proj_cols if c in projections.columns]].copy()
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
    history_meta = {}
    if not matched.empty:
        unique_proj = matched.drop_duplicates(["game_id", "player_key"])
        for _, row in unique_proj.iterrows():
            gid = str(row.get("game_id") or "")
            pkey = str(row.get("player_key") or "")
            _, _, dmeta = points._points_distribution(row, bool((lineups or {}).get(gid, False)))
            history_meta[(gid, pkey)] = dmeta
            if int(dmeta.get("hist_games") or 0) >= 5:
                empirical_players += 1

    preview_rows = []
    if not matched.empty:
        for _, row in matched.head(20).iterrows():
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
                "Δ": round(proj - line, 2) if pd.notna(proj) and pd.notna(line) else np.nan,
                "Hist GP": int(dmeta.get("hist_games") or 0),
                "Lineup": "CONFIRMED" if bool((lineups or {}).get(gid, False)) else "PENDING",
                "Freshness": freshness,
            })

    coverage_ok = market_players > 0 and matched_players == market_players
    ready = bool(active_games > 0 and eligible_pairs > 0 and coverage_ok)
    return {
        "error": "", "preview": pd.DataFrame(preview_rows), "active_games": active_games,
        "lineups_confirmed": lineups_confirmed, "market_players": market_players,
        "matched_players": matched_players, "eligible_pairs": eligible_pairs,
        "empirical_players": empirical_players, "ready": ready,
    }


def _render_header(day, slate):
    current = points.combined_rows(day)
    distributions = 0
    if isinstance(current, pd.DataFrame) and not current.empty:
        distributions = int(current[["game_id", "player_key", "line"]].drop_duplicates().shape[0])

    st.markdown("""
<div style="border:1px solid #2f6381;background:linear-gradient(145deg,#091c2d,#071421);border-radius:20px;padding:16px;margin:8px 0 14px">
  <div style="font-size:10px;letter-spacing:1.35px;font-weight:950;color:#65dcff">KYRE SPORTS AI • WNBA POINTS • ISOLATED PRODUCTION PAGE</div>
  <div style="font-size:30px;font-weight:1000;color:white;margin-top:5px">🏀 WNBA Points Command Center — V1.3</div>
  <div style="font-size:12px;color:#93aabd;line-height:1.55;margin-top:7px">Clean slate-first workflow. Every verified game stays visible; only eligible upcoming games feed the Points model. PRA V3.2.1 and MLB V2.1.7 remain frozen.</div>
</div>
""", unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Slate games", slate["total"])
    c2.metric("Upcoming", slate["upcoming"])
    c3.metric("Points market players", 0 if slate["pairs"].empty else int(slate["pairs"]["player_key"].nunique()))
    c4.metric("5M distributions", distributions)

    state = str((slate.get("diag") or {}).get("state") or "UNKNOWN").upper()
    if state in {"VERIFIED", "VERIFIED_OFF_DAY"}:
        st.success(f"✅ Verified WNBA slate • {day} • all {slate['total']} game(s) shown below")
    else:
        st.warning(f"⚠️ WNBA schedule state: {state}")


def _render_slate(slate):
    st.markdown("### 🗓️ Today’s Verified WNBA Games")
    st.caption("Every verified game is shown. FINAL games remain visible for slate completeness but are excluded from projections, simulations and grading.")
    frame = slate["table"].copy()
    if frame.empty:
        st.info("No verified WNBA games are available for the selected date.")
        return

    visible = frame[["Matchup", "Tip (ET)", "Venue", "Status", "Points players", "Exact pairs", "Model use"]]
    st.dataframe(visible, use_container_width=True, hide_index=True)

    if slate["upcoming"] > 0:
        if slate["upcoming_market_games"] == slate["upcoming"]:
            st.caption(f"🎯 SportsGameOdds Points coverage is present for all {slate['upcoming']} upcoming game(s).")
        else:
            missing = slate["upcoming"] - slate["upcoming_market_games"]
            st.warning(f"⚠️ {missing} upcoming game(s) do not yet have a matched exact Points market.")


def _render_readiness(info):
    st.markdown("### 🧪 Pre-Simulation Readiness")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Eligible games", info["active_games"])
    c2.metric("Projection coverage", f"{info['matched_players']}/{info['market_players']}")
    c3.metric("Exact eligible pairs", info["eligible_pairs"])
    c4.metric("Empirical history", f"{info['empirical_players']}/{info['matched_players']}")

    if info.get("error"):
        st.error(f"Preflight could not complete: {info['error']}")
        return

    if info["ready"]:
        if info["lineups_confirmed"] < info["active_games"]:
            st.warning(f"⚠️ PRE-LINEUP READY • {info['lineups_confirmed']}/{info['active_games']} upcoming starting fives confirmed. The 5M pass may run, but any qualified play remains MONITOR until explicit starters publish.")
        else:
            st.success("✅ PRODUCTION READY • schedule, projection coverage, exact markets and lineup checks passed.")
    else:
        st.warning("⚠️ NOT READY FOR 5M • missing projection or exact-market coverage must be resolved first.")

    if info["matched_players"]:
        if info["empirical_players"] == info["matched_players"]:
            st.caption("🧬 Every matched Points player has ≥5 verified prior games for empirical scoring variance.")
        else:
            missing = info["matched_players"] - info["empirical_players"]
            st.caption(f"🧬 {info['empirical_players']} matched player(s) have empirical ≥5-game scoring history; {missing} would use clearly labeled fallback variance.")

    if isinstance(info["preview"], pd.DataFrame) and not info["preview"].empty:
        with st.expander("📋 Exact Points line + projection preview", expanded=False):
            st.dataframe(info["preview"], use_container_width=True, hide_index=True)


def _fmt_pct(v):
    try:
        return f"{100 * float(v):.1f}%"
    except Exception:
        return "—"


def _render_production(day, readiness):
    st.markdown("### 🚀 Points Production")
    st.caption("Points-only projection → exact SportsGameOdds line → empirical scoring variance → actual 5M Monte Carlo → no-vig grading.")

    if points.restore_if_missing(day):
        st.toast("💾 Restored completed WNBA Points snapshot — no 5M rerun required.")
        st.rerun()

    current = points.combined_rows(day)
    if not isinstance(current, pd.DataFrame) or current.empty:
        run_disabled = not bool(readiness.get("ready"))
        if st.button("🚀 RUN POINTS 5,000,000 STANDARD SIMS", use_container_width=True, disabled=run_disabled, key=f"wnba_points_run_clean_{day}"):
            prog = st.progress(0.0, text="Starting Points Monte Carlo…")
            points.run_standard(day, prog)
            prog.empty()
            points.persist_if_ready(day)
            st.rerun()

        if run_disabled:
            st.info("The 5M button stays disabled until the preflight has full upcoming projection + exact-market coverage.")
        else:
            st.info("Preflight passed. Run the 5M pass once; completed summaries persist across reloads/redeploys.")
        return

    points.persist_if_ready(day)
    src = st.session_state.get(points.source_key(day)) or "active session"
    uniq = int(current[["game_id", "player_key", "line"]].drop_duplicates().shape[0])
    qualified = int(current["model_qualified"].fillna(False).sum()) if "model_qualified" in current else 0
    final_ready = int(current["final_ready"].fillna(False).sum()) if "final_ready" in current else 0
    monitors = int(current["status"].astype(str).str.contains("MONITOR", na=False).sum()) if "status" in current else 0

    st.success(f"✅ Points production LIVE • {uniq} unique distributions • snapshot protected • source: {src}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("5M distributions", uniq)
    c2.metric("Qualified", qualified)
    c3.metric("Final ready", final_ready)
    c4.metric("Monitor", monitors)

    display = current.sort_values(["model_qualified", "model_over", "edge"], ascending=[False, False, False]).copy()
    st.markdown("#### 🏆 Points Decision Board")
    top = display.head(10)
    board = pd.DataFrame({
        "Player": top["player"], "Book": top["book"], "Line": top["line"],
        "Adj PTS": top["projection"].round(2), "MC Mean": top["sim_mean"].round(2),
        "P(Over)": top["model_over"].map(_fmt_pct), "No-vig O": top["no_vig_over"].map(_fmt_pct),
        "Edge": top["edge"].map(lambda x: "—" if pd.isna(x) else f"{100*x:+.1f} pp"),
        "Status": top["status"],
    })
    st.dataframe(board, use_container_width=True, hide_index=True)

    with st.expander("📋 Full Points model-vs-market board", expanded=False):
        full = pd.DataFrame({
            "Player": display["player"], "Book": display["book"], "Line": display["line"],
            "Adj PTS": display["projection"].round(2), "MC Mean": display["sim_mean"].round(2),
            "Median": display["sim_median"], "P(Over)": display["model_over"].map(_fmt_pct),
            "No-vig O": display["no_vig_over"].map(_fmt_pct),
            "Edge": display["edge"].map(lambda x: "—" if pd.isna(x) else f"{100*x:+.1f} pp"),
            "Freshness": display["freshness"], "Status": display["status"],
        })
        st.dataframe(full, use_container_width=True, hide_index=True)

    units = points._finalist_units(current)
    final_state = st.session_state.get(points.final_key(day)) or {}
    final_rows = final_state.get("rows")
    if units and not isinstance(final_rows, pd.DataFrame):
        if st.button("🎯 RUN POINTS 10,000,000 FINALIST PASS", use_container_width=True, key=f"wnba_points_final_clean_{day}"):
            prog = st.progress(0.0, text="Starting Points finalist Monte Carlo…")
            points.run_final(day, current, prog)
            prog.empty()
            points.persist_if_ready(day)
            st.rerun()

    with st.expander("🧪 Monte Carlo diagnostics", expanded=False):
        diag = current.drop_duplicates(["game_id", "player_key", "line"])
        diag_table = pd.DataFrame({
            "Player": diag["player"], "Line": diag["line"], "Sims": diag["sims"],
            "Batches": diag["batches"], "Seed": diag["seed"],
            "MC SE": diag["mc_se"].map(lambda x: f"{100*x:.4f} pp"),
            "Max batch Δ": diag["max_batch_diff"].map(lambda x: f"{100*x:.3f} pp"),
            "Converged": diag["converged"].map(lambda x: "YES" if x else "NO"),
            "Hist GP": diag["hist_games"], "Variance": diag["variance_source"],
        })
        st.dataframe(diag_table, use_container_width=True, hide_index=True)


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.caption("🏀 WNBA Points V1.3 • clean isolated production page • PRA V3.2.1 frozen • SportsGameOdds WNBA • MLB V2.1.7 frozen")

    selected = st.date_input("WNBA Points slate date", value=_default_day(), key="wnba_points_date_control")
    day = _day_string(selected)
    st.session_state["wnba_points_date"] = day

    slate = _slate_snapshot(day)
    _render_header(day, slate)
    _render_slate(slate)

    readiness = _readiness_snapshot(day)
    _render_readiness(readiness)

    with st.expander("🧊 Freeze / isolation status", expanded=False):
        st.write(f"PRA checkpoint: `{PRA_FROZEN_BRANCH}` @ `{PRA_FROZEN_COMMIT[:12]}`")
        st.write(f"MLB checkpoint: `{MLB_FROZEN_BRANCH}`")
        st.write("Points reads shared verified WNBA data utilities only. It does not modify frozen PRA or MLB production model files.")

    _render_production(day, readiness)
    st.caption("Phase 1: validate this isolated Points page first. Only after model coverage, 5M diagnostics, persistence and decision gates pass will Points feed the WNBA Daily Master Card.")


__all__ = ["MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH", "render_wnba_points_hub"]
