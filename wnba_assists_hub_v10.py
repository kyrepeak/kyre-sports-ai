"""WNBA Assists V10 — Step 10 Guard / Wing / Big matchup context.

Preserves Assists Steps 1-9 and adds only role-sensitive positional assist
matchup context from completed WNBA box scores.

Step 10 rules:
- Step 9 must pass first;
- exact opponent comes only from the verified Step-2 matchup;
- classify the current player as Guard / Wing / Big from the verified roster
  position already carried through Steps 3-9;
- reconstruct the exact opponent's last 20 completed games from cached ESPN
  WNBA game summaries, using the historical player's game-listed position;
- calculate assists allowed per game and AST/40 to Guard / Wing / Big buckets;
- keep L20/L10/L5/L3 windows separate and regression-protect toward L20;
- expose recent-vs-L20 positional trend without pretending it is a league
  percentile or a final projection;
- preserve Step-5 creator role beside the position matchup as context only.

No pace adjustment, H2H adjustment, sportsbook line, final assist projection,
fair odds or Monte Carlo is enabled here.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

import wnba_assists_hub_v3 as step3
import wnba_assists_hub_v4 as step4
import wnba_assists_hub_v5 as step5
import wnba_assists_hub_v6 as step6
import wnba_assists_hub_v7 as step7
import wnba_assists_hub_v8 as step8
import wnba_assists_hub_v9 as step9
import wnba_players_v25 as players

MODEL_VERSION = "WNBA ASSISTS V10 • STEP 10 GUARD / WING / BIG MATCHUP"
_ET = ZoneInfo("America/New_York")
HISTORY_GAMES = 20
MIN_HISTORY_GAMES = 10
CORE_MINUTES = 10.0


def _num(value: Any, default: float = np.nan) -> float:
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _safe_int(value: Any) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _position_bucket(value: Any) -> str:
    raw = str(value or "").upper().strip().replace(" ", "")
    if not raw:
        return "UNKNOWN"
    tokens = {x for x in raw.replace("/", "-").split("-") if x}
    if any(x in tokens for x in {"C", "CENTER"}) or raw in {"PF", "FC", "F/C", "C/F", "PF/C", "C/PF"}:
        return "BIG"
    if any(x in tokens for x in {"PF", "POWERFORWARD"}):
        return "BIG"
    if any(x in tokens for x in {"SF", "F", "FORWARD"}) or raw in {"GF", "FG", "G/F", "F/G"}:
        return "WING"
    if any(x in tokens for x in {"PG", "SG", "G", "GUARD", "POINTGUARD", "SHOOTINGGUARD"}):
        return "GUARD"
    if "CENTER" in raw:
        return "BIG"
    if "FORWARD" in raw:
        return "WING"
    if "GUARD" in raw:
        return "GUARD"
    return "UNKNOWN"


def _game_bucket_record(frame: pd.DataFrame, defense_team_id: int) -> dict[str, dict[str, float]] | None:
    if frame is None or frame.empty or "TEAM_ID" not in frame.columns:
        return None
    tids = pd.to_numeric(frame["TEAM_ID"], errors="coerce").fillna(0).astype(int)
    if not tids.eq(int(defense_team_id)).any():
        return None
    offense = frame.loc[~tids.eq(int(defense_team_id))].copy()
    if offense.empty:
        return None

    record = {b: {"ast": 0.0, "min": 0.0, "players": 0.0} for b in ("GUARD", "WING", "BIG")}
    for _, row in offense.iterrows():
        bucket = _position_bucket(row.get("POSITION"))
        if bucket not in record:
            continue
        mins = max(0.0, _num(row.get("MIN"), 0.0))
        ast = max(0.0, _num(row.get("AST"), 0.0))
        if mins <= 0.0 and ast <= 0.0:
            continue
        record[bucket]["ast"] += ast
        record[bucket]["min"] += mins
        record[bucket]["players"] += 1.0

    if sum(record[b]["min"] for b in record) <= 0.0:
        return None
    return record


def _window(records: list[dict[str, dict[str, float]]], bucket: str, k: int) -> dict[str, float]:
    use = records[: min(int(k), len(records))]
    if not use:
        return {"games": 0, "bucket_games": 0, "ast_pg": np.nan, "ast40": np.nan, "minutes": 0.0}
    ast = 0.0
    mins = 0.0
    bucket_games = 0
    for rec in use:
        part = (rec or {}).get(bucket, {}) or {}
        bmin = max(0.0, _num(part.get("min"), 0.0))
        bast = max(0.0, _num(part.get("ast"), 0.0))
        if bmin > 0.0:
            bucket_games += 1
        mins += bmin
        ast += bast
    games = len(use)
    return {
        "games": games,
        "bucket_games": bucket_games,
        "ast_pg": ast / games if games > 0 else np.nan,
        "ast40": (40.0 * ast / mins) if mins > 0 else np.nan,
        "minutes": mins,
    }


def _blend(values: list[tuple[float, float]]) -> float:
    use = [(float(v), float(w)) for v, w in values if np.isfinite(v)]
    den = sum(w for _, w in use)
    return sum(v * w for v, w in use) / den if den > 0 else np.nan


def _trend_index(recent: float, baseline: float) -> float:
    if not np.isfinite(recent) or not np.isfinite(baseline) or baseline <= 0:
        return np.nan
    return 100.0 * recent / baseline


def _trend_label(index: float) -> str:
    if not np.isfinite(index):
        return "UNKNOWN"
    if index >= 108.0:
        return "EASIER RECENTLY"
    if index <= 92.0:
        return "TOUGHER RECENTLY"
    return "STABLE"


@st.cache_data(ttl=1800, show_spinner=False, max_entries=8)
def _position_history(day_str: str, defense_team_ids: tuple[int, ...]):
    season = step4._season_schedule(pd.to_datetime(day_str).year)
    if season is None or season.empty:
        return {}, {"ready": False, "reason": "season schedule unavailable", "team_games": {}}

    games_by_team: dict[int, list[dict[str, str]]] = {}
    jobs: dict[str, str] = {}
    for tid in defense_team_ids:
        games = step9._all_completed_team_games(season, day_str, int(tid)).head(HISTORY_GAMES)
        rows: list[dict[str, str]] = []
        for _, game in games.iterrows():
            gid = str(game.get("game_id") or "")
            gdate = str(game.get("game_date") or "")[:10]
            if not gid:
                continue
            rows.append({"game_id": gid, "game_date": gdate})
            jobs[gid] = gdate
        games_by_team[int(tid)] = rows

    summaries: dict[str, pd.DataFrame] = {}
    if jobs:
        # Reuses the same cached ESPN game-summary parser used by earlier Assists
        # layers. Previously fetched game IDs therefore do not require new work.
        with ThreadPoolExecutor(max_workers=min(16, max(1, len(jobs)))) as pool:
            futures = {
                pool.submit(players._espn_game_summary, gid, gdate): gid
                for gid, gdate in jobs.items()
            }
            for future in as_completed(futures):
                gid = futures[future]
                try:
                    frame = future.result()
                    if frame is not None and not frame.empty:
                        summaries[gid] = frame.copy()
                except Exception:
                    continue

    history: dict[int, dict[str, Any]] = {}
    counts: dict[int, int] = {}
    for tid in defense_team_ids:
        records: list[dict[str, dict[str, float]]] = []
        for game in games_by_team.get(int(tid), []):
            rec = _game_bucket_record(summaries.get(game["game_id"], pd.DataFrame()), int(tid))
            if rec is not None:
                records.append(rec)
        counts[int(tid)] = len(records)
        buckets: dict[str, Any] = {}
        for bucket in ("GUARD", "WING", "BIG"):
            l20 = _window(records, bucket, 20)
            l10 = _window(records, bucket, 10)
            l5 = _window(records, bucket, 5)
            l3 = _window(records, bucket, 3)
            stable_ast40 = _blend([
                (l20["ast40"], .60),
                (l10["ast40"], .20),
                (l5["ast40"], .12),
                (l3["ast40"], .08),
            ])
            stable_ast_pg = _blend([
                (l20["ast_pg"], .60),
                (l10["ast_pg"], .20),
                (l5["ast_pg"], .12),
                (l3["ast_pg"], .08),
            ])
            recent_ast40 = _blend([
                (l10["ast40"], .50),
                (l5["ast40"], .30),
                (l3["ast40"], .20),
            ])
            idx = _trend_index(recent_ast40, l20["ast40"])
            buckets[bucket] = {
                "l20": l20,
                "l10": l10,
                "l5": l5,
                "l3": l3,
                "stable_ast40": stable_ast40,
                "stable_ast_pg": stable_ast_pg,
                "recent_ast40": recent_ast40,
                "recent_vs_l20_index": idx,
                "trend": _trend_label(idx),
            }
        history[int(tid)] = {
            "games": len(records),
            "buckets": buckets,
            "source": "ESPN WNBA completed game summaries • historical listed position",
        }

    ready = bool(counts and all(counts.get(int(tid), 0) >= MIN_HISTORY_GAMES for tid in defense_team_ids))
    return history, {
        "ready": ready,
        "reason": "" if ready else "one or more exact opponents have fewer than 10 usable position-tagged games",
        "team_games": counts,
        "requested_summaries": len(jobs),
        "usable_summaries": len(summaries),
    }


def _build_step10_matchup(slate: dict[str, Any], day_str: str, environment: pd.DataFrame):
    if environment is None or environment.empty:
        return pd.DataFrame(), pd.DataFrame(), {"ready": False, "reason": "no Step-9 environment rows"}

    matchup = step9._matchups(slate)
    offense_ids = tuple(sorted(matchup))
    opponent_ids = tuple(sorted({
        int(matchup[tid]["opponent_id"])
        for tid in offense_ids
        if _safe_int(matchup[tid].get("opponent_id")) > 0
    }))
    history, hdiag = _position_history(day_str, opponent_ids)

    out = environment.copy()
    out["POSITION_BUCKET"] = out.get("POSITION", pd.Series("", index=out.index)).map(_position_bucket)
    for col in (
        "OPP_POS_AST_PG_L20", "OPP_POS_AST_PG_L10", "OPP_POS_AST_PG_L5", "OPP_POS_AST_PG_L3",
        "OPP_POS_AST40_L20", "OPP_POS_AST40_L10", "OPP_POS_AST40_L5", "OPP_POS_AST40_L3",
        "OPP_POS_AST40_STABLE", "OPP_POS_AST_PG_STABLE", "OPP_POS_RECENT_INDEX",
    ):
        out[col] = np.nan
    out["OPP_POS_TREND"] = "UNKNOWN"
    out["ROLE_POSITION_CONTEXT"] = ""
    out["POSITION_MATCHUP_SOURCE"] = ""

    meta = step3._team_meta(slate)
    team_rows: list[dict[str, Any]] = []
    all_ready = True
    core_total = 0
    core_covered = 0

    for tid in offense_ids:
        team_mask = pd.to_numeric(out.get("TEAM_ID_NUM"), errors="coerce").fillna(0).astype(int).eq(int(tid))
        team = out.loc[team_mask]
        m = matchup.get(int(tid), {}) or {}
        oid = _safe_int(m.get("opponent_id"))
        opp_hist = history.get(int(oid), {}) or {}
        buckets = opp_hist.get("buckets", {}) or {}
        games = int(opp_hist.get("games") or 0)

        core = team.loc[pd.to_numeric(team.get("PROJ_MIN"), errors="coerce").fillna(0.0).ge(CORE_MINUTES)]
        team_core = len(core)
        team_covered = 0
        for idx, row in team.iterrows():
            bucket = str(row.get("POSITION_BUCKET") or "UNKNOWN")
            b = buckets.get(bucket, {}) if bucket in {"GUARD", "WING", "BIG"} else {}
            l20 = b.get("l20", {}) or {}
            l10 = b.get("l10", {}) or {}
            l5 = b.get("l5", {}) or {}
            l3 = b.get("l3", {}) or {}
            stable40 = _num(b.get("stable_ast40"))
            stable_pg = _num(b.get("stable_ast_pg"))
            trend_index = _num(b.get("recent_vs_l20_index"))
            source = str(opp_hist.get("source") or "")

            out.at[idx, "OPP_POS_AST_PG_L20"] = _num(l20.get("ast_pg"))
            out.at[idx, "OPP_POS_AST_PG_L10"] = _num(l10.get("ast_pg"))
            out.at[idx, "OPP_POS_AST_PG_L5"] = _num(l5.get("ast_pg"))
            out.at[idx, "OPP_POS_AST_PG_L3"] = _num(l3.get("ast_pg"))
            out.at[idx, "OPP_POS_AST40_L20"] = _num(l20.get("ast40"))
            out.at[idx, "OPP_POS_AST40_L10"] = _num(l10.get("ast40"))
            out.at[idx, "OPP_POS_AST40_L5"] = _num(l5.get("ast40"))
            out.at[idx, "OPP_POS_AST40_L3"] = _num(l3.get("ast40"))
            out.at[idx, "OPP_POS_AST40_STABLE"] = stable40
            out.at[idx, "OPP_POS_AST_PG_STABLE"] = stable_pg
            out.at[idx, "OPP_POS_RECENT_INDEX"] = trend_index
            out.at[idx, "OPP_POS_TREND"] = str(b.get("trend") or "UNKNOWN")
            role = str(row.get("CREATION_ROLE") or "UNCLASSIFIED")
            out.at[idx, "ROLE_POSITION_CONTEXT"] = f"{role} • {bucket}"
            out.at[idx, "POSITION_MATCHUP_SOURCE"] = source

            is_core = _num(row.get("PROJ_MIN"), 0.0) >= CORE_MINUTES
            covered = bool(
                bucket in {"GUARD", "WING", "BIG"}
                and np.isfinite(stable40)
                and np.isfinite(_num(l20.get("ast40")))
                and int(l20.get("bucket_games") or 0) >= MIN_HISTORY_GAMES
            )
            if is_core:
                core_total += 1
                if covered:
                    core_covered += 1
                    team_covered += 1

        team_ready = bool(
            games >= MIN_HISTORY_GAMES
            and team_core > 0
            and team_covered == team_core
        )
        all_ready = all_ready and team_ready
        guard = buckets.get("GUARD", {}) or {}
        wing = buckets.get("WING", {}) or {}
        big = buckets.get("BIG", {}) or {}
        team_rows.append({
            "Team": meta.get(int(tid), {}).get("name", str(tid)),
            "Opponent": str(m.get("opponent") or ""),
            "Usable opponent games": games,
            "Guard stable AST/40": round(_num(guard.get("stable_ast40")), 2) if np.isfinite(_num(guard.get("stable_ast40"))) else np.nan,
            "Wing stable AST/40": round(_num(wing.get("stable_ast40")), 2) if np.isfinite(_num(wing.get("stable_ast40"))) else np.nan,
            "Big stable AST/40": round(_num(big.get("stable_ast40")), 2) if np.isfinite(_num(big.get("stable_ast40"))) else np.nan,
            "Core position coverage": f"{team_covered}/{team_core}",
            "Gate": "PASS" if team_ready else "CHECK",
        })

    team_diag = pd.DataFrame(team_rows)
    ready = bool(
        hdiag.get("ready")
        and all_ready
        and len(team_rows) == len(offense_ids)
        and len(offense_ids) > 0
        and core_total > 0
        and core_covered == core_total
    )
    return out, team_diag, {
        "ready": ready,
        "reason": "" if ready else str(hdiag.get("reason") or "one or more core rotation players lack exact position matchup coverage"),
        "history": hdiag,
        "teams": len(team_rows),
        "core_players": core_total,
        "core_covered": core_covered,
        "mode": "ESPN POSITION-TAGGED BOX SCORES",
    }


def _render_step10(slate: dict[str, Any], day_str: str, environment: pd.DataFrame, step9_ready: bool):
    st.markdown("### 🧩 Step 10 — Position Matchup: Guard / Wing / Big")
    st.caption(
        "Role-sensitive matchup context only. Each current player is mapped to Guard, Wing or Big, then matched against the exact opponent's position-tagged assist allowance. L20/L10/L5/L3 remain visible and the stable signal regresses toward L20. This is not yet an assist projection."
    )
    if not step9_ready:
        st.error("⛔ STEP 10 LOCKED • Step 9 has not passed, so role/position matchup context cannot run.")
        return False, pd.DataFrame()

    with st.spinner("🧩 Building Guard / Wing / Big opponent assist context…"):
        matchup_rows, team_diag, diag = _build_step10_matchup(slate, day_str, environment)

    ready = bool(diag.get("ready"))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Core rotation", int(diag.get("core_players") or 0))
    c2.metric("Position covered", f"{int(diag.get('core_covered') or 0)}/{int(diag.get('core_players') or 0)}")
    c3.metric("History mode", "L20 + recent")
    c4.metric("Monte Carlo", "0")

    if ready:
        st.success("✅ STEP 10 PASSED • every core rotation player has an exact Guard/Wing/Big classification and an auditable same-position assist environment from the verified opponent. No pace, H2H, sportsbook or final projection adjustment has been applied.")
    else:
        st.warning(f"⚠️ STEP 10 CHECK • {diag.get('reason') or 'position matchup verification incomplete'}. Step 11 remains locked.")

    if team_diag is not None and not team_diag.empty:
        st.dataframe(team_diag, hide_index=True, use_container_width=True)

    if matchup_rows is not None and not matchup_rows.empty:
        view = matchup_rows.loc[pd.to_numeric(matchup_rows.get("PROJ_MIN"), errors="coerce").fillna(0.0).ge(CORE_MINUTES)].copy()
        if not view.empty:
            view["Player"] = view.get("PLAYER_NAME", pd.Series("", index=view.index)).astype(str)
            view["Team"] = view.get("TEAM_ABBREVIATION", pd.Series("", index=view.index)).astype(str)
            view["Opponent"] = view.get("OPPONENT", pd.Series("", index=view.index)).astype(str)
            view["Pos"] = view.get("POSITION", pd.Series("", index=view.index)).astype(str)
            view["Bucket"] = view.get("POSITION_BUCKET", pd.Series("", index=view.index)).astype(str)
            view["Creator role"] = view.get("CREATION_ROLE", pd.Series("", index=view.index)).astype(str)
            view["Proj min"] = pd.to_numeric(view.get("PROJ_MIN"), errors="coerce").round(1)
            view["L20 AST/40"] = pd.to_numeric(view.get("OPP_POS_AST40_L20"), errors="coerce").round(2)
            view["L10 AST/40"] = pd.to_numeric(view.get("OPP_POS_AST40_L10"), errors="coerce").round(2)
            view["L5 AST/40"] = pd.to_numeric(view.get("OPP_POS_AST40_L5"), errors="coerce").round(2)
            view["L3 AST/40"] = pd.to_numeric(view.get("OPP_POS_AST40_L3"), errors="coerce").round(2)
            view["Stable AST/40"] = pd.to_numeric(view.get("OPP_POS_AST40_STABLE"), errors="coerce").round(2)
            view["Recent/L20 idx"] = pd.to_numeric(view.get("OPP_POS_RECENT_INDEX"), errors="coerce").round(1)
            view["Trend"] = view.get("OPP_POS_TREND", pd.Series("", index=view.index)).astype(str)
            st.dataframe(
                view[["Player", "Team", "Opponent", "Pos", "Bucket", "Creator role", "Proj min", "L20 AST/40", "L10 AST/40", "L5 AST/40", "L3 AST/40", "Stable AST/40", "Recent/L20 idx", "Trend"]],
                hide_index=True,
                use_container_width=True,
            )
        if ready:
            st.session_state[f"wnba_assists_v10_position_matchup::{day_str}"] = matchup_rows.copy()

    hist = diag.get("history") or {}
    with st.expander("🧪 Step-10 position-matchup methodology / diagnostics", expanded=False):
        st.write("• Exact opponent is inherited from Step 9 / the verified Step-2 slate only.")
        st.write("• Historical position comes from ESPN's game-listed athlete position in completed WNBA box scores.")
        st.write("• Current position comes from the verified Step-3 roster carried through the earlier Assists layers.")
        st.write("• Buckets: PG/SG/G = Guard; SF/F and hybrid G-F = Wing; PF/C and F-C = Big.")
        st.write("• Position environment uses L20/L10/L5/L3 assists allowed per game plus AST/40.")
        st.write("• Stable signal: 60% L20 + 20% L10 + 12% L5 + 8% L3.")
        st.write("• Recent-vs-L20 index is a same-opponent positional trend, NOT a league percentile.")
        st.write("• Step-5 creator role is displayed as matchup context only and does not change an assist projection yet.")
        st.write("• Pace adjustment used: 0 — reserved for Step 11.")
        st.write("• H2H adjustment used: 0 — reserved for Step 12.")
        st.write("• Sportsbook lines used: 0")
        st.write("• Monte Carlo runs: 0")
        st.write(f"• Position-history summary requests: {hist.get('requested_summaries', 0)}")
        st.write(f"• Usable cached/returned summaries: {hist.get('usable_summaries', 0)}")

    return ready, matchup_rows


def render_wnba_assists_hub(section_header=None, status_info=None, team_logo=None, h=None):
    slate_day = datetime.now(_ET).strftime("%Y-%m-%d")
    slate = step3.schedule.load_verified_wnba_slate(slate_day)
    verification = str(slate.get("verification") or "")

    st.markdown(
        """
        <style>
        .ks-ast-hero{padding:25px 27px;margin:4px 0 18px;border:1px solid rgba(56,189,248,.34);border-radius:24px;background:linear-gradient(135deg,rgba(6,28,44,.99),rgba(12,22,48,.99));box-shadow:0 14px 38px rgba(0,0,0,.16);}
        .ks-ast-kicker{color:#67e8f9;font-size:.69rem;font-weight:950;letter-spacing:.13em;text-transform:uppercase;}
        .ks-ast-title{margin-top:9px;color:#f8fafc;font-size:2.05rem;line-height:1.08;font-weight:950;}
        .ks-ast-sub{margin-top:12px;color:#9fb0c6;font-size:.91rem;line-height:1.62;font-weight:650;}
        .ks-ast-chip{display:inline-block;margin:14px 7px 0 0;padding:7px 10px;border:1px solid rgba(52,211,153,.35);border-radius:999px;background:rgba(16,185,129,.09);color:#6ee7b7;font-size:.69rem;font-weight:900;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="ks-ast-hero">
          <div class="ks-ast-kicker">KYRE SPORTS AI • WNBA ASSISTS INTELLIGENCE • STEP 10</div>
          <div class="ks-ast-title">🎯 WNBA Assists Command Center</div>
          <div class="ks-ast-sub">Steps 1–9 remain intact. Step 10 adds only Guard/Wing/Big matchup context from the exact verified opponent. Pace, H2H, sportsbook lines, final projection and simulations remain locked.</div>
          <span class="ks-ast-chip">📅 ET slate {slate_day}</span>
          <span class="ks-ast-chip">✅ Steps 1–9 preserved</span>
          <span class="ks-ast-chip">🧩 Guard / Wing / Big</span>
          <span class="ks-ast-chip">🚫 zero simulations</span>
        </div>""",
        unsafe_allow_html=True,
    )

    st.markdown("### 📅 Step 2 — Verified Daily WNBA Slate")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Selected date", slate_day)
    c2.metric("Verification", verification or "CHECK")
    c3.metric("Games found", int(slate.get("games_found", 0)))
    c4.metric("WNBA teams validated", int(slate.get("teams_validated", 0)))
    if verification == "VERIFIED":
        st.success(f"✅ STEP 2 PASSED • {slate.get('games_found', 0)} same-day WNBA game(s) verified by the preserved Step-2 reconciliation layer.")
    elif verification == "NO GAMES":
        st.info(f"ℹ️ STEP 2 VERIFIED EMPTY • No WNBA games for {slate_day} ET.")
    else:
        st.error("⛔ STEP 2 CHECK • Same-day slate verification is incomplete.")

    st.markdown("### 🩺 Step 3 — Current Rosters + Same-Day Injury / Status")
    step3_ready_ui = step3._render_step3(slate, slate_day)
    merged, step3_diag = step4._step3_snapshot(slate, slate_day)
    step3_ready = bool(step3_ready_ui and step3_diag.get("ready"))
    step4_ready, minutes = step4._render_step4(slate, slate_day, merged, step3_ready)
    step5_ready, roles = step5._render_step5(slate, slate_day, minutes, step4_ready)
    step6_ready, form = step6._render_step6(slate, slate_day, roles, step5_ready)
    step7_ready, opportunity = step7._render_step7(slate, slate_day, form, step6_ready)
    step8_ready, conversion = step8._render_step8(slate, slate_day, opportunity, step7_ready)
    step9_ready, environment = step9._render_step9(slate, slate_day, conversion, step8_ready)
    step10_ready, _ = _render_step10(slate, slate_day, environment, step9_ready)

    if st.button("🔄 RECHECK ASSISTS STEPS 2–10", use_container_width=True, key="assists_step10_recheck"):
        for fn in (
            step3.schedule.load_verified_wnba_slate,
            step3._current_rosters,
            step3._injury_feed,
            step4._season_schedule,
            step4._rotation_history,
            step5._creation_history,
            step5._official_usage_table,
            step6._season_form_pool,
            step6._recent_assist_history,
            step7._tracking_windows,
            step8._shooting_history,
            step8._raw_shooting_summary,
            step9._official_windows,
            step9._espn_environment,
            _position_history,
        ):
            try:
                fn.clear()
            except Exception:
                pass
        try:
            players._espn_roster.clear()
            players._espn_season_schedule.clear()
            players._espn_game_summary.clear()
        except Exception:
            pass
        st.rerun()

    st.markdown("### 🧱 Assists Build Order — Current")
    layers = [
        (1, "Isolated Assists page", "✅ LIVE", "Display shell preserved"),
        (2, "Verified daily WNBA slate", "✅ LIVE" if verification in {"VERIFIED", "NO GAMES"} else "⚠️ CHECK", "Exact ET date + provider reconciliation"),
        (3, "Current rosters + injuries/status", "✅ LIVE" if step3_ready else "⚠️ CHECK", "Fail-closed current identity + same-day status"),
        (4, "Projected minutes + rotation", "✅ LIVE" if step4_ready else "⚠️ CHECK", "L3/L5/L10 rotation + 200-minute team allocation"),
        (5, "Assist role + ball-handling / usage", "✅ LIVE" if step5_ready else "⚠️ CHECK", "Empirical creation responsibility + usage context"),
        (6, "Recent + season assist form", "✅ LIVE" if step6_ready else "⚠️ CHECK", "Season + L3/L5/L10 • regression protected"),
        (7, "Potential assists / passes / creation chances", "✅ LIVE" if step7_ready else "⚠️ CHECK", "Official tracking when available; honest proxy fallback"),
        (8, "Teammate shot-making + lineup conversion", "✅ LIVE" if step8_ready else "⚠️ CHECK", "Projected active finisher environment"),
        (9, "Opponent assist environment", "✅ LIVE" if step9_ready else "⚠️ CHECK", "Season + L10/L5/L3 assists allowed + AST/FGM"),
        (10, "Position matchup — Guard / Wing / Big", "✅ LIVE" if step10_ready else ("⚠️ CHECK" if step9_ready else "🔒 LOCKED"), "Exact-opponent position-tagged AST/40 context"),
        (11, "Pace + expected possession volume", "➡️ NEXT" if step10_ready else "🔒 LOCKED", "Possession opportunity adjustment"),
        (12, "Player vs opponent assist history", "🔒 LOCKED", "Descriptive H2H context"),
        (13, "Exact SportsGameOdds assist lines", "🔒 LOCKED", "Exact book / line / side only"),
        (14, "Same-book no-vig", "🔒 LOCKED", "Market math stays separate from projection"),
        (15, "Market-independent assist projection", "🔒 LOCKED", "Expected assists before market grading"),
        (16, "Uncertainty + distribution calibration", "🔒 LOCKED", "Discrete assist count distribution"),
        (17, "5M Monte Carlo + convergence / sensitivity", "🔒 LOCKED", "Actual simulations only"),
        (18, "Line-specific O/U probability + fair odds", "🔒 LOCKED", "Threshold probabilities from model distribution"),
        (19, "Model-vs-market edge + EV", "🔒 LOCKED", "Exact posted price grading"),
        (20, "Risk-adjusted qualification + Top 5", "🔒 LOCKED", "Never force five"),
    ]
    for start in range(0, len(layers), 4):
        cols = st.columns(4, gap="small")
        for col, item in zip(cols, layers[start:start + 4]):
            with col:
                st.markdown(step3._layer_card(*item), unsafe_allow_html=True)

    st.caption(
        f"⚡ WNBA Assists V10 Step 10 • Step 2 {verification or 'CHECK'} • Step 3 {'PASS' if step3_ready else 'CHECK'} • Step 4 {'PASS' if step4_ready else 'CHECK'} • Step 5 {'PASS' if step5_ready else 'CHECK'} • Step 6 {'PASS' if step6_ready else 'CHECK'} • Step 7 {'PASS' if step7_ready else 'CHECK'} • Step 8 {'PASS' if step8_ready else 'CHECK'} • Step 9 {'PASS' if step9_ready else 'CHECK'} • Step 10 {'PASS' if step10_ready else 'CHECK'} • no pace/H2H/projection/market/Monte Carlo yet"
    )


__all__ = ["MODEL_VERSION", "render_wnba_assists_hub"]
