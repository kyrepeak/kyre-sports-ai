"""WNBA Assists V5 — Step 5 assist role + ball-handling / usage context.

Preserves Assists Steps 1-4 and adds only creator-role classification.

Step 5 deliberately does NOT project assists. It identifies who owns creation:
- current Step-3 roster/status gate only;
- Step-4 projected rotation only;
- last 10 completed team box scores, with current-roster players absent from a
  verified box score treated as 0 assists/minutes for that game;
- recency-weighted current-roster assist responsibility (50% L3 / 30% L5 /
  20% L10);
- assist rate per 36 and projected-minute context;
- optional official WNBA Advanced USG% when the public stats endpoint responds;
- an explicitly labeled box-score offensive-involvement proxy when official
  USG% is unavailable;
- conservative PRIMARY / SECONDARY / CONNECTOR / LOW-CREATION role labels;
- vacated-creation signals when OUT/INACTIVE/DOUBTFUL teammates historically
  carried assist responsibility.

Potential assists, passes/touches, teammate conversion, matchup, sportsbook
lines, assist projections and Monte Carlo remain locked for later steps.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import streamlit as st

import wnba_assists_hub_v3 as step3
import wnba_assists_hub_v4 as step4
import wnba_players_v25 as players

MODEL_VERSION = "WNBA ASSISTS V5 • STEP 5 CREATION ROLE + USAGE CONTEXT"
_ET = ZoneInfo("America/New_York")
ZERO_STATUSES = {"OUT", "INACTIVE", "DOUBTFUL"}
RISK_STATUSES = {"QUESTIONABLE", "PROBABLE", "REPORTED"}
MIN_ROLE_GAMES = 5
WNBA_ADVANCED_URL = "https://stats.wnba.com/stats/leaguedashplayerstats"


def _num(value: Any, default: float = 0.0) -> float:
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _day(value: Any) -> str:
    return pd.to_datetime(value).strftime("%Y-%m-%d")


def _safe_pid(value: Any) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _normalize_usage(value: Any) -> float:
    x = _num(value, np.nan)
    if pd.isna(x):
        return np.nan
    return float(x * 100.0 if abs(x) <= 1.5 else x)


@st.cache_data(ttl=900, show_spinner=False, max_entries=4)
def _official_usage_table(season: int) -> tuple[pd.DataFrame, str]:
    """Optional isolated official Advanced USG% read. Failure never crashes Step 5."""
    params = {
        "College": "", "Conference": "", "Country": "", "DateFrom": "", "DateTo": "",
        "Division": "", "DraftPick": "", "DraftYear": "", "GameScope": "", "GameSegment": "",
        "Height": "", "LastNGames": 0, "LeagueID": "10", "Location": "", "MeasureType": "Advanced",
        "Month": 0, "OpponentTeamID": 0, "Outcome": "", "PORound": 0, "PaceAdjust": "N",
        "PerMode": "PerGame", "Period": 0, "PlayerExperience": "", "PlayerPosition": "",
        "PlusMinus": "N", "Rank": "N", "Season": str(int(season)), "SeasonSegment": "",
        "SeasonType": "Regular Season", "ShotClockRange": "", "StarterBench": "", "TeamID": 0,
        "VsConference": "", "VsDivision": "", "Weight": "",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
        "Accept": "application/json,text/plain,*/*",
        "Origin": "https://www.wnba.com",
        "Referer": "https://www.wnba.com/",
    }
    try:
        response = requests.get(WNBA_ADVANCED_URL, params=params, headers=headers, timeout=5)
        response.raise_for_status()
        payload = response.json()
        sets = payload.get("resultSets") or payload.get("resultSet") or []
        if isinstance(sets, dict):
            sets = [sets]
        chosen = None
        for item in sets if isinstance(sets, list) else []:
            headers_row = item.get("headers") or []
            if "PLAYER_ID" in headers_row and "USG_PCT" in headers_row:
                chosen = item
                break
        if not chosen:
            return pd.DataFrame(), "unavailable"
        cols = chosen.get("headers") or []
        rows = chosen.get("rowSet") or []
        frame = pd.DataFrame(rows, columns=cols)
        if frame.empty or not {"PLAYER_ID", "TEAM_ID", "USG_PCT"}.issubset(frame.columns):
            return pd.DataFrame(), "unavailable"
        keep = [c for c in ("PLAYER_ID", "TEAM_ID", "PLAYER_NAME", "USG_PCT") if c in frame.columns]
        frame = frame[keep].copy()
        frame["PLAYER_ID"] = pd.to_numeric(frame["PLAYER_ID"], errors="coerce").fillna(0).astype(int)
        frame["TEAM_ID"] = pd.to_numeric(frame["TEAM_ID"], errors="coerce").fillna(0).astype(int)
        frame["USG_PCT"] = frame["USG_PCT"].map(_normalize_usage)
        frame = frame[(frame["PLAYER_ID"] > 0) & (frame["TEAM_ID"] > 0)].drop_duplicates(["TEAM_ID", "PLAYER_ID"])
        return frame.reset_index(drop=True), "WNBA Stats Advanced USG%"
    except Exception:
        return pd.DataFrame(), "unavailable"


@st.cache_data(ttl=900, show_spinner=False, max_entries=32)
def _creation_history(
    day_str: str,
    team_ids: tuple[int, ...],
    roster_ids: tuple[tuple[int, tuple[int, ...]], ...],
):
    """Last-10 assist responsibility and offensive involvement for current rosters."""
    day_str = _day(day_str)
    season = step4._season_schedule(pd.to_datetime(day_str).year)
    if season is None or season.empty:
        return {}, {"ready": False, "reason": "season schedule unavailable", "team_games": {}}

    ids_by_team = {int(tid): tuple(int(x) for x in ids) for tid, ids in roster_ids}
    games_by_team: dict[int, list[dict[str, str]]] = {}
    jobs: dict[str, str] = {}
    for tid in team_ids:
        games = step4._last_team_games(season, day_str, int(tid))
        rows: list[dict[str, str]] = []
        for _, g in games.iterrows():
            gid = str(g.get("game_id") or "")
            gdate = str(g.get("game_date") or "")[:10]
            if not gid:
                continue
            rows.append({"game_id": gid, "game_date": gdate})
            jobs[gid] = gdate
        games_by_team[int(tid)] = rows

    summaries: dict[str, pd.DataFrame] = {}
    if jobs:
        with ThreadPoolExecutor(max_workers=min(12, max(1, len(jobs)))) as pool:
            futures = {
                pool.submit(players._espn_game_summary, gid, gdate): gid
                for gid, gdate in jobs.items()
            }
            for future in as_completed(futures):
                gid = futures[future]
                try:
                    box = future.result()
                    if box is not None and not box.empty:
                        summaries[gid] = box.copy()
                except Exception:
                    continue

    history: dict[int, dict[str, Any]] = {}
    team_counts: dict[int, int] = {}
    for tid in team_ids:
        current_ids = set(ids_by_team.get(int(tid), ()))
        game_rows: list[dict[str, Any]] = []
        for game in games_by_team.get(int(tid), []):
            box = summaries.get(game["game_id"])
            if box is None or box.empty or "TEAM_ID" not in box.columns:
                continue
            part = box.loc[pd.to_numeric(box["TEAM_ID"], errors="coerce").eq(int(tid))].copy()
            if part.empty:
                continue
            ast_map: dict[int, float] = {}
            min_map: dict[int, float] = {}
            pts_map: dict[int, float] = {}
            for _, row in part.iterrows():
                pid = _safe_pid(row.get("PLAYER_ID"))
                if not pid:
                    continue
                ast_map[pid] = max(0.0, _num(row.get("AST"), 0.0))
                min_map[pid] = max(0.0, _num(row.get("MIN"), 0.0))
                pts_map[pid] = max(0.0, _num(row.get("PTS"), 0.0))
            team_ast = float(sum(ast_map.values()))
            current_ast = float(sum(v for pid, v in ast_map.items() if pid in current_ids))
            game_rows.append({
                "ast": ast_map,
                "min": min_map,
                "pts": pts_map,
                "team_ast": team_ast,
                "current_ast": current_ast,
            })

        n = len(game_rows)
        team_counts[int(tid)] = n
        player_data: dict[int, dict[str, Any]] = {}
        for pid in current_ids:
            ast_vals = [float(g["ast"].get(pid, 0.0)) for g in game_rows]
            min_vals = [float(g["min"].get(pid, 0.0)) for g in game_rows]
            pts_vals = [float(g["pts"].get(pid, 0.0)) for g in game_rows]

            def _share(k: int) -> float:
                use = game_rows[: min(k, n)]
                den = float(sum(g["current_ast"] for g in use))
                num = float(sum(g["ast"].get(pid, 0.0) for g in use))
                return num / den if den > 0 else 0.0

            l3_share = _share(3)
            l5_share = _share(5)
            l10_share = _share(10)
            blended_share = 0.50 * l3_share + 0.30 * l5_share + 0.20 * l10_share
            total_ast = float(sum(ast_vals))
            total_min = float(sum(min_vals))
            total_pts = float(sum(pts_vals))
            ast36 = 36.0 * total_ast / total_min if total_min > 0 else 0.0
            involvement36 = 36.0 * (total_pts + 1.50 * total_ast) / total_min if total_min > 0 else 0.0
            player_data[int(pid)] = {
                "games": n,
                "appearances": int(sum(m > 0.25 for m in min_vals)),
                "l3_share": l3_share,
                "l5_share": l5_share,
                "l10_share": l10_share,
                "blend_share": blended_share,
                "ast36": ast36,
                "involvement36": involvement36,
                "ast_total": total_ast,
                "minutes_total": total_min,
            }

        team_ast_total = float(sum(g["team_ast"] for g in game_rows))
        current_ast_total = float(sum(g["current_ast"] for g in game_rows))
        coverage = current_ast_total / team_ast_total if team_ast_total > 0 else 0.0
        history[int(tid)] = {
            "players": player_data,
            "games": n,
            "team_ast_total": team_ast_total,
            "current_ast_total": current_ast_total,
            "current_roster_ast_coverage": coverage,
        }

    ready = bool(team_counts and all(team_counts.get(int(tid), 0) >= MIN_ROLE_GAMES for tid in team_ids))
    return history, {
        "ready": ready,
        "reason": "" if ready else "one or more slate teams have fewer than 5 usable role-history games",
        "team_games": team_counts,
        "unique_summaries": len(summaries),
        "requested_summaries": len(jobs),
    }


def _proxy_usage(team: pd.DataFrame) -> pd.Series:
    """Explicitly estimated offensive-involvement context, not official USG%."""
    load = pd.to_numeric(team["INVOLVEMENT36"], errors="coerce").fillna(0.0)
    active = pd.to_numeric(team["PROJ_MIN"], errors="coerce").fillna(0.0).gt(0.25)
    usable = load[active & load.gt(0)]
    if usable.empty:
        return pd.Series(np.nan, index=team.index, dtype=float)
    mean = float(usable.mean())
    sd = max(float(usable.std(ddof=0)), 1.0)
    z = (load - mean) / sd
    return (20.0 + 4.5 * z).clip(8.0, 35.0)


def _role_label(rank: int, share: float, ast36: float, proj_min: float) -> str:
    if proj_min <= 0.25:
        return "OUT / DNP"
    if rank == 1 and (share >= 0.22 or ast36 >= 5.5):
        return "PRIMARY CREATOR"
    if rank <= 2 and (share >= 0.10 or ast36 >= 3.5):
        return "SECONDARY CREATOR"
    if share >= 0.055 or ast36 >= 2.25:
        return "CONNECTOR"
    return "LOW-CREATION"


def _ball_handling_label(role: str, position: str) -> str:
    pos = str(position or "").upper()
    if role == "PRIMARY CREATOR":
        return "PRIMARY ON-BALL"
    if role == "SECONDARY CREATOR":
        return "SECONDARY ON-BALL"
    if role == "CONNECTOR":
        return "CONNECTOR / SHARED"
    if "G" in pos:
        return "LOW-CREATION GUARD"
    return "MOSTLY OFF-BALL"


def _build_step5_roles(
    slate: dict[str, Any],
    day_str: str,
    minutes: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    if minutes is None or minutes.empty:
        return pd.DataFrame(), pd.DataFrame(), {"ready": False, "reason": "no Step-4 minutes rows"}

    meta = step3._team_meta(slate)
    team_ids = tuple(sorted(int(tid) for tid in meta))
    roster_ids: list[tuple[int, tuple[int, ...]]] = []
    for tid in team_ids:
        part = minutes.loc[pd.to_numeric(minutes.get("TEAM_ID_NUM"), errors="coerce").fillna(0).astype(int).eq(int(tid))]
        ids = tuple(sorted({_safe_pid(x) for x in part.get("PLAYER_ID", pd.Series(dtype=str)) if _safe_pid(x) > 0}))
        roster_ids.append((int(tid), ids))

    history, hdiag = _creation_history(day_str, team_ids, tuple(roster_ids))
    usage, usage_source = _official_usage_table(pd.to_datetime(day_str).year)
    usage_map: dict[tuple[int, int], float] = {}
    if usage is not None and not usage.empty:
        for _, row in usage.iterrows():
            usage_map[(int(row["TEAM_ID"]), int(row["PLAYER_ID"]))] = _num(row.get("USG_PCT"), np.nan)

    frames: list[pd.DataFrame] = []
    team_rows: list[dict[str, Any]] = []
    for tid in team_ids:
        team = minutes.loc[pd.to_numeric(minutes.get("TEAM_ID_NUM"), errors="coerce").fillna(0).astype(int).eq(int(tid))].copy()
        if team.empty:
            team_rows.append({"Team": meta.get(tid, {}).get("name", str(tid)), "Role games": 0, "Roster AST coverage": 0.0, "Primary": "—", "Vacated share": 0.0, "Usage source": usage_source, "Gate": "CHECK"})
            continue

        pdata = (history.get(int(tid), {}) or {}).get("players", {})
        shares: list[float] = []
        l3s: list[float] = []
        l5s: list[float] = []
        l10s: list[float] = []
        ast36s: list[float] = []
        inv36s: list[float] = []
        role_games: list[int] = []
        role_apps: list[int] = []
        official_usg: list[float] = []
        for _, row in team.iterrows():
            pid = _safe_pid(row.get("PLAYER_ID"))
            info = pdata.get(pid, {})
            shares.append(_num(info.get("blend_share"), 0.0))
            l3s.append(_num(info.get("l3_share"), 0.0))
            l5s.append(_num(info.get("l5_share"), 0.0))
            l10s.append(_num(info.get("l10_share"), 0.0))
            ast36s.append(_num(info.get("ast36"), 0.0))
            inv36s.append(_num(info.get("involvement36"), 0.0))
            role_games.append(int(info.get("games") or 0))
            role_apps.append(int(info.get("appearances") or 0))
            official_usg.append(usage_map.get((int(tid), pid), np.nan))

        team["L3_ROSTER_AST_SHARE"] = l3s
        team["L5_ROSTER_AST_SHARE"] = l5s
        team["L10_ROSTER_AST_SHARE"] = l10s
        team["CREATION_SHARE"] = shares
        team["AST36_ROLE"] = ast36s
        team["INVOLVEMENT36"] = inv36s
        team["ROLE_GAMES"] = role_games
        team["ROLE_APPEARANCES"] = role_apps
        team["OFFICIAL_USG"] = official_usg
        proxy = _proxy_usage(team)
        team["USAGE_CONTEXT"] = team["OFFICIAL_USG"].where(team["OFFICIAL_USG"].notna(), proxy)
        team["USAGE_SOURCE"] = np.where(team["OFFICIAL_USG"].notna(), "WNBA Advanced USG%", "Box-score involvement proxy")

        # Role score is only for within-team creator classification; it is not an assist projection.
        active = pd.to_numeric(team["PROJ_MIN"], errors="coerce").fillna(0.0).gt(0.25)
        ast36 = pd.to_numeric(team["AST36_ROLE"], errors="coerce").fillna(0.0)
        max_ast36 = max(float(ast36[active].max()) if active.any() else 0.0, 0.1)
        min_share = pd.to_numeric(team["PROJ_MIN"], errors="coerce").fillna(0.0) / 200.0
        team["ROLE_SCORE"] = (
            0.65 * pd.to_numeric(team["CREATION_SHARE"], errors="coerce").fillna(0.0)
            + 0.20 * (ast36 / max_ast36)
            + 0.15 * min_share
        )
        team.loc[~active, "ROLE_SCORE"] = -1.0
        team["CREATION_RANK"] = 0
        ranked = team.loc[active].sort_values("ROLE_SCORE", ascending=False)
        for rank, idx in enumerate(ranked.index, start=1):
            team.at[idx, "CREATION_RANK"] = rank

        team["CREATION_ROLE"] = [
            _role_label(
                int(r.get("CREATION_RANK") or 0),
                _num(r.get("CREATION_SHARE"), 0.0),
                _num(r.get("AST36_ROLE"), 0.0),
                _num(r.get("PROJ_MIN"), 0.0),
            )
            for _, r in team.iterrows()
        ]
        team["BALL_HANDLING_ROLE"] = [
            _ball_handling_label(r.get("CREATION_ROLE"), r.get("POSITION"))
            for _, r in team.iterrows()
        ]

        status = team.get("AVAILABILITY", pd.Series("UNKNOWN", index=team.index)).astype(str).str.upper()
        vacated_share = float(pd.to_numeric(team.loc[status.isin(ZERO_STATUSES), "CREATION_SHARE"], errors="coerce").fillna(0.0).sum())
        team["VACATED_CREATION_SHARE"] = vacated_share
        team["ROLE_SHIFT"] = "STABLE"
        team.loc[status.isin(ZERO_STATUSES), "ROLE_SHIFT"] = "OUT / ZERO"
        if vacated_share >= 0.04:
            top_active = team.loc[active & ~status.isin(ZERO_STATUSES)].sort_values("ROLE_SCORE", ascending=False).head(2).index
            team.loc[top_active, "ROLE_SHIFT"] = "UP — VACATED CREATION"
        team.loc[status.isin(RISK_STATUSES) & active, "ROLE_SHIFT"] = team.loc[status.isin(RISK_STATUSES) & active, "ROLE_SHIFT"].astype(str) + " • STATUS RISK"

        hteam = history.get(int(tid), {}) or {}
        games = int(hteam.get("games") or 0)
        coverage = _num(hteam.get("current_roster_ast_coverage"), 0.0)
        rotation = team.loc[active]
        core_missing = int(rotation.loc[pd.to_numeric(rotation["PROJ_MIN"], errors="coerce").fillna(0.0).ge(20.0), "ROLE_APPEARANCES"].lt(2).sum()) if not rotation.empty else 0
        primary_rows = team.loc[team["CREATION_ROLE"].eq("PRIMARY CREATOR")]
        if primary_rows.empty and not ranked.empty:
            # Do not invent a primary label if the evidence threshold is not met.
            primary = str(ranked.iloc[0].get("PLAYER_NAME") or "—") + " (top, not primary-threshold)"
        elif not primary_rows.empty:
            primary = str(primary_rows.iloc[0].get("PLAYER_NAME") or "—")
        else:
            primary = "—"

        team_ready = bool(
            games >= MIN_ROLE_GAMES
            and coverage >= 0.55
            and not rotation.empty
            and core_missing == 0
            and pd.to_numeric(rotation["CREATION_SHARE"], errors="coerce").notna().all()
            and pd.to_numeric(rotation["AST36_ROLE"], errors="coerce").notna().all()
        )
        team_rows.append({
            "Team": meta.get(tid, {}).get("name", str(tid)),
            "Role games": games,
            "Roster AST coverage": round(coverage * 100.0, 1),
            "Primary / top creator": primary,
            "Vacated share": round(vacated_share * 100.0, 1),
            "Core without evidence": core_missing,
            "Usage source": "Official + fallback" if team["OFFICIAL_USG"].notna().any() else "Box-score proxy",
            "Gate": "PASS" if team_ready else "CHECK",
        })
        frames.append(team)

    roles = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    team_diag = pd.DataFrame(team_rows)
    ready = bool(hdiag.get("ready") and not team_diag.empty and team_diag["Gate"].eq("PASS").all())
    return roles, team_diag, {
        "ready": ready,
        "reason": "" if ready else str(hdiag.get("reason") or "one or more team creator-role checks failed"),
        "history": hdiag,
        "usage_source": usage_source,
        "official_usage_players": int(roles["OFFICIAL_USG"].notna().sum()) if not roles.empty else 0,
        "players": len(roles),
        "active_players": int(pd.to_numeric(roles.get("PROJ_MIN"), errors="coerce").fillna(0.0).gt(0.25).sum()) if not roles.empty else 0,
        "primary_creators": int(roles.get("CREATION_ROLE", pd.Series(dtype=str)).eq("PRIMARY CREATOR").sum()) if not roles.empty else 0,
        "secondary_creators": int(roles.get("CREATION_ROLE", pd.Series(dtype=str)).eq("SECONDARY CREATOR").sum()) if not roles.empty else 0,
    }


def _render_step5(slate: dict[str, Any], day_str: str, minutes: pd.DataFrame, step4_ready: bool) -> tuple[bool, pd.DataFrame]:
    st.markdown("### 🎛️ Step 5 — Assist Role + Ball-Handling / Usage")
    st.caption(
        "This layer classifies creation responsibility only. It does not project an assist total. Role evidence comes from current-roster assist share, assist rate, projected minutes and optional official WNBA Advanced USG%. Tracking touches/passes remain reserved for Step 7."
    )
    if not step4_ready:
        st.error("⛔ STEP 5 LOCKED • Step 4 has not passed, so creator-role classification cannot run.")
        return False, pd.DataFrame()

    with st.spinner("🎛️ Building last-10 creator responsibility + usage context…"):
        roles, team_diag, diag = _build_step5_roles(slate, day_str, minutes)

    ready = bool(diag.get("ready"))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active rotation", int(diag.get("active_players") or 0))
    c2.metric("Primary creators", int(diag.get("primary_creators") or 0))
    c3.metric("Secondary creators", int(diag.get("secondary_creators") or 0))
    c4.metric("Official USG rows", int(diag.get("official_usage_players") or 0))

    if ready:
        st.success("✅ STEP 5 PASSED • every slate team has usable recent creator-role evidence, current-roster assist coverage clears the integrity gate, and projected rotation players have auditable creation classifications. No assist projection has been created yet.")
    else:
        st.warning(f"⚠️ STEP 5 CHECK • {diag.get('reason') or 'creator-role validation incomplete'}. Step 6 remains locked.")

    if team_diag is not None and not team_diag.empty:
        st.dataframe(team_diag, hide_index=True, use_container_width=True)

    if roles is not None and not roles.empty:
        view = roles.copy()
        view["Player"] = view["PLAYER_NAME"].astype(str)
        view["Team"] = view.get("TEAM_ABBREVIATION", pd.Series("", index=view.index)).astype(str)
        view["Pos"] = view.get("POSITION", pd.Series("", index=view.index)).astype(str)
        view["Status"] = view.get("AVAILABILITY", pd.Series("", index=view.index)).astype(str)
        view["Proj min"] = pd.to_numeric(view["PROJ_MIN"], errors="coerce").round(1)
        view["Creation share"] = (pd.to_numeric(view["CREATION_SHARE"], errors="coerce").fillna(0.0) * 100.0).round(1)
        view["AST/36 role"] = pd.to_numeric(view["AST36_ROLE"], errors="coerce").round(1)
        view["Usage ctx"] = pd.to_numeric(view["USAGE_CONTEXT"], errors="coerce").round(1)
        view["Usage source"] = view["USAGE_SOURCE"].astype(str)
        view["Creator role"] = view["CREATION_ROLE"].astype(str)
        view["Ball handling"] = view["BALL_HANDLING_ROLE"].astype(str)
        view["Role shift"] = view["ROLE_SHIFT"].astype(str)
        view = view.sort_values(["TEAM_ID_NUM", "CREATION_RANK", "PROJ_MIN"], ascending=[True, True, False])
        st.dataframe(
            view[["Player", "Team", "Pos", "Status", "Proj min", "Creation share", "AST/36 role", "Usage ctx", "Usage source", "Creator role", "Ball handling", "Role shift"]],
            hide_index=True,
            use_container_width=True,
        )
        if ready:
            st.session_state[f"wnba_assists_v5_roles::{day_str}"] = roles.copy()

    hist = diag.get("history") or {}
    with st.expander("🧠 Step-5 role methodology / diagnostics", expanded=False):
        st.write("• Role window: last 10 completed team games before the ET slate.")
        st.write("• Current-roster player absent from a verified box score = 0 assists/minutes for that game.")
        st.write("• Creation share: 50% L3 + 30% L5 + 20% L10 current-roster assist responsibility.")
        st.write("• AST/36 is supporting role evidence; it is not the Step-6 assist-form projection.")
        st.write("• Official WNBA Advanced USG% is optional context only. If unavailable, the UI explicitly labels a box-score offensive-involvement proxy.")
        st.write("• PRIMARY/SECONDARY/CONNECTOR labels are within-team empirical classifications, not tracking-data claims.")
        st.write("• Vacated creation from OUT/INACTIVE/DOUBTFUL teammates creates an UP role-shift signal for the top active creators; no assist total is adjusted yet.")
        st.write("• Potential assists / passes / touches used: 0 — reserved for Step 7.")
        st.write("• Sportsbook lines used: 0")
        st.write("• Monte Carlo runs: 0")
        st.write(f"• Historical summary requests: {hist.get('requested_summaries', 0)}")
        st.write(f"• Usable unique summaries: {hist.get('unique_summaries', 0)}")
        st.write(f"• Official usage source: {diag.get('usage_source', 'unavailable')}")

    return ready, roles


def render_wnba_assists_hub(section_header=None, status_info=None, team_logo=None, h=None):
    slate_day = datetime.now(_ET).strftime("%Y-%m-%d")
    slate = step3.schedule.load_verified_wnba_slate(slate_day)
    verification = str(slate.get("verification") or "")

    st.markdown(
        """
        <style>
        .ks-ast-hero{padding:25px 27px;margin:4px 0 18px;border:1px solid rgba(56,189,248,.34);border-radius:24px;
          background:linear-gradient(135deg,rgba(6,28,44,.99),rgba(12,22,48,.99));box-shadow:0 14px 38px rgba(0,0,0,.16);}
        .ks-ast-kicker{color:#67e8f9;font-size:.69rem;font-weight:950;letter-spacing:.13em;text-transform:uppercase;}
        .ks-ast-title{margin-top:9px;color:#f8fafc;font-size:2.05rem;line-height:1.08;font-weight:950;}
        .ks-ast-sub{margin-top:12px;color:#9fb0c6;font-size:.91rem;line-height:1.62;font-weight:650;}
        .ks-ast-chip{display:inline-block;margin:14px 7px 0 0;padding:7px 10px;border:1px solid rgba(52,211,153,.35);
          border-radius:999px;background:rgba(16,185,129,.09);color:#6ee7b7;font-size:.69rem;font-weight:900;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="ks-ast-hero">
          <div class="ks-ast-kicker">KYRE SPORTS AI • WNBA ASSISTS INTELLIGENCE • STEP 5</div>
          <div class="ks-ast-title">🎯 WNBA Assists Command Center</div>
          <div class="ks-ast-sub">Steps 1–4 remain intact. Step 5 identifies primary and secondary creators from verified recent team responsibility, assist rate, rotation and usage context. It still does not create an assist projection.</div>
          <span class="ks-ast-chip">📅 ET slate {slate_day}</span>
          <span class="ks-ast-chip">✅ Steps 1–4 preserved</span>
          <span class="ks-ast-chip">🎛️ creator role only</span>
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
    step5_ready, _ = _render_step5(slate, slate_day, minutes, step4_ready)

    if st.button("🔄 RECHECK ASSISTS STEPS 2–5", use_container_width=True, key="assists_step5_recheck"):
        step3.schedule.load_verified_wnba_slate.clear()
        step3._current_rosters.clear()
        step3._injury_feed.clear()
        step4._season_schedule.clear()
        step4._rotation_history.clear()
        _creation_history.clear()
        _official_usage_table.clear()
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
        (4, "Projected minutes + rotation", "✅ LIVE" if step4_ready else ("⚠️ CHECK" if step3_ready else "🔒 LOCKED"), "L3/L5/L10 rotation + 200-minute team allocation"),
        (5, "Assist role + ball-handling / usage", "✅ LIVE" if step5_ready else ("⚠️ CHECK" if step4_ready else "🔒 LOCKED"), "Empirical creation responsibility + usage context"),
        (6, "Recent + season assist form", "➡️ NEXT" if step5_ready else "🔒 LOCKED", "Minute-normalized, regression protected"),
        (7, "Potential assists / passes / creation chances", "🔒 LOCKED", "Opportunity layer before conversion"),
        (8, "Teammate shot-making + lineup conversion", "🔒 LOCKED", "Who finishes the created chances"),
        (9, "Opponent assist environment", "🔒 LOCKED", "Opponent scheme + assists allowed"),
        (10, "Position matchup — Guard / Wing / Big", "🔒 LOCKED", "Role-sensitive matchup context"),
        (11, "Pace + expected possession volume", "🔒 LOCKED", "Possession opportunity adjustment"),
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
        f"⚡ WNBA Assists V5 Step 5 • Step 2 {verification or 'CHECK'} • Step 3 {'PASS' if step3_ready else 'LOCKED'} • Step 4 {'PASS' if step4_ready else 'CHECK'} • Step 5 {'PASS' if step5_ready else 'CHECK'} • no assist projection/market/Monte Carlo yet"
    )


__all__ = ["MODEL_VERSION", "render_wnba_assists_hub"]
