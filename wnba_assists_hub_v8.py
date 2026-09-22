"""WNBA Assists V8 — Step 8 teammate shot-making + lineup conversion.

Preserves Assists Steps 1-7 and adds only the pre-matchup finishing environment
around each creator.

Step 8 rules:
- Step 7 must pass first;
- use only current Step-3 roster/status and Step-4 projected rotation players;
- rebuild each slate team's last 10 completed ESPN WNBA box scores from the raw
  game summary so shooting makes/attempts are available;
- compute L3/L5/L10 player FG%, eFG%, 2P%, 3P%, 3PA share and FGA/min;
- for every creator, calculate projected-minute + shot-volume weighted teammate
  finishing metrics EXCLUDING the creator herself;
- expose team AST/FGM context from the same completed-game sample;
- use attempt-aware shrinkage across L3/L5/L10 so tiny hot/cold samples cannot
  dominate the finishing signal;
- fail closed if the recent shooting sample or projected active lineup is not
  auditable enough for core rotation players.

This step still does NOT apply opponent defense, pace, H2H, sportsbook lines,
final assist projection, fair odds or Monte Carlo.
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
import wnba_players_v25 as players

MODEL_VERSION = "WNBA ASSISTS V8 • STEP 8 TEAMMATE SHOT-MAKING + LINEUP CONVERSION"
_ET = ZoneInfo("America/New_York")
ZERO_STATUSES = {"OUT", "INACTIVE", "DOUBTFUL"}
CORE_MINUTES = 10.0
MIN_SHOOTING_GAMES = 5


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


def _pct(made: float, att: float) -> float:
    return float(made / att) if np.isfinite(made) and np.isfinite(att) and att > 0 else np.nan


def _pair(value: Any) -> tuple[float, float]:
    text = str(value or "").strip().replace("–", "-").replace("—", "-")
    if "-" not in text:
        return np.nan, np.nan
    parts = text.split("-", 1)
    try:
        return float(parts[0]), float(parts[1])
    except Exception:
        return np.nan, np.nan


def _stat_pair(stats: dict[str, Any], three: bool = False) -> tuple[float, float]:
    # ESPN box labels are usually FG and 3PT, while internal keys can be longer.
    for key, value in (stats or {}).items():
        k = str(key or "").upper().replace(" ", "")
        is_three = ("3PT" in k) or ("THREEPOINT" in k) or ("3-PT" in k)
        if three != is_three:
            continue
        if not three and not (k == "FG" or "FIELDGOAL" in k or "FGM" in k):
            continue
        made, att = _pair(value)
        if np.isfinite(made) and np.isfinite(att):
            return made, att

    if three:
        made = players._pick_stat(stats, ["3PM", "FG3M", "THREEPOINTFIELDGOALSMADE"], np.nan)
        att = players._pick_stat(stats, ["3PA", "FG3A", "THREEPOINTFIELDGOALSATTEMPTED"], np.nan)
    else:
        made = players._pick_stat(stats, ["FGM", "FIELDGOALSMADE"], np.nan)
        att = players._pick_stat(stats, ["FGA", "FIELDGOALSATTEMPTED"], np.nan)
    return _num(made), _num(att)


@st.cache_data(ttl=1800, show_spinner=False, max_entries=128)
def _raw_shooting_summary(game_id: str, game_date: str = "") -> pd.DataFrame:
    """Raw ESPN summary parser retaining shooting fields discarded by v25."""
    try:
        payload, _ = players.schedule_v24._request_json(
            "ESPN WNBA assists conversion summary",
            players.ESPN_SUMMARY,
            params={"event": str(game_id)},
            timeout=8,
            attempts=2,
        )
    except Exception:
        payload = None
    if not isinstance(payload, dict):
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for team_block in (payload.get("boxscore") or {}).get("players", []) or []:
        team = team_block.get("team") or {}
        tid = int(players._team_id(team) or 0)
        if not tid:
            continue
        team_name = str(team.get("displayName") or team.get("shortDisplayName") or team.get("name") or "")
        team_abbr = str(team.get("abbreviation") or "")
        for group in team_block.get("statistics", []) or []:
            athletes = group.get("athletes") or []
            if not athletes:
                continue
            for item in athletes:
                if bool(item.get("didNotPlay")):
                    continue
                athlete = item.get("athlete") or {}
                pid = _safe_int(athlete.get("id"))
                if not pid:
                    continue
                stats = players._summary_stat_map(group, item)
                mins = players._minutes(players._pick_stat(stats, ["MIN", "MINUTES"], np.nan))
                fgm, fga = _stat_pair(stats, three=False)
                fg3m, fg3a = _stat_pair(stats, three=True)
                ast = _num(players._pick_stat(stats, ["AST", "ASSISTS"], np.nan))
                if not np.isfinite(fga):
                    continue
                if not np.isfinite(fgm):
                    fgm = 0.0
                if not np.isfinite(fg3a):
                    fg3a = 0.0
                if not np.isfinite(fg3m):
                    fg3m = 0.0
                fg2m = max(0.0, fgm - fg3m)
                fg2a = max(0.0, fga - fg3a)
                rows.append({
                    "GAME_DATE": str(game_date or ""),
                    "PLAYER_ID": pid,
                    "PLAYER_NAME": str(athlete.get("displayName") or athlete.get("fullName") or "Player"),
                    "TEAM_ID": tid,
                    "TEAM_NAME": team_name,
                    "TEAM_ABBREVIATION": team_abbr,
                    "MIN": _num(mins, 0.0),
                    "FGM": fgm,
                    "FGA": fga,
                    "FG3M": fg3m,
                    "FG3A": fg3a,
                    "FG2M": fg2m,
                    "FG2A": fg2a,
                    "AST": _num(ast, 0.0),
                })
            if athletes:
                break
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return frame.drop_duplicates(["PLAYER_ID", "TEAM_ID"], keep="first").reset_index(drop=True)


def _window_metrics(games: list[pd.DataFrame], pid: int, k: int) -> dict[str, float]:
    use = games[: min(k, len(games))]
    if not use:
        return {"fg": np.nan, "efg": np.nan, "p2": np.nan, "p3": np.nan, "share3": np.nan, "fga": 0.0, "min": 0.0}
    fgm = fga = m3 = a3 = m2 = a2 = mins = 0.0
    for part in use:
        row = part.loc[pd.to_numeric(part.get("PLAYER_ID"), errors="coerce").fillna(0).astype(int).eq(int(pid))]
        if row.empty:
            continue
        r = row.iloc[0]
        fgm += max(0.0, _num(r.get("FGM"), 0.0))
        fga += max(0.0, _num(r.get("FGA"), 0.0))
        m3 += max(0.0, _num(r.get("FG3M"), 0.0))
        a3 += max(0.0, _num(r.get("FG3A"), 0.0))
        m2 += max(0.0, _num(r.get("FG2M"), 0.0))
        a2 += max(0.0, _num(r.get("FG2A"), 0.0))
        mins += max(0.0, _num(r.get("MIN"), 0.0))
    return {
        "fg": _pct(fgm, fga),
        "efg": _pct(fgm + 0.5 * m3, fga),
        "p2": _pct(m2, a2),
        "p3": _pct(m3, a3),
        "share3": _pct(a3, fga),
        "fga": fga,
        "min": mins,
    }


def _blend_pct(values: list[tuple[float, float, float]], attempt_scale: float) -> float:
    """Attempt-aware L3/L5/L10 shrinkage; each tuple is pct, base weight, attempts."""
    use: list[tuple[float, float]] = []
    for value, weight, attempts in values:
        if not np.isfinite(value):
            continue
        reliability = float(np.clip(float(attempts) / max(attempt_scale, 1.0), 0.15, 1.0))
        use.append((float(value), float(weight) * reliability))
    den = sum(w for _, w in use)
    return sum(v * w for v, w in use) / den if den > 0 else np.nan


@st.cache_data(ttl=1200, show_spinner=False, max_entries=32)
def _shooting_history(day_str: str, team_ids: tuple[int, ...], roster_ids: tuple[tuple[int, tuple[int, ...]], ...]):
    season = step4._season_schedule(pd.to_datetime(day_str).year)
    if season is None or season.empty:
        return {}, {"ready": False, "reason": "season schedule unavailable", "team_games": {}}

    ids_by_team = {int(tid): tuple(int(x) for x in ids) for tid, ids in roster_ids}
    games_by_team: dict[int, list[dict[str, str]]] = {}
    jobs: dict[str, str] = {}
    for tid in team_ids:
        recent = step4._last_team_games(season, day_str, int(tid))
        rows: list[dict[str, str]] = []
        for _, game in recent.iterrows():
            gid = str(game.get("game_id") or "")
            gdate = str(game.get("game_date") or "")[:10]
            if not gid:
                continue
            rows.append({"game_id": gid, "game_date": gdate})
            jobs[gid] = gdate
        games_by_team[int(tid)] = rows

    summaries: dict[str, pd.DataFrame] = {}
    if jobs:
        with ThreadPoolExecutor(max_workers=min(12, max(1, len(jobs)))) as pool:
            futures = {pool.submit(_raw_shooting_summary, gid, gdate): gid for gid, gdate in jobs.items()}
            for future in as_completed(futures):
                gid = futures[future]
                try:
                    frame = future.result()
                    if frame is not None and not frame.empty:
                        summaries[gid] = frame.copy()
                except Exception:
                    continue

    out: dict[int, dict[str, Any]] = {}
    team_counts: dict[int, int] = {}
    for tid in team_ids:
        parts: list[pd.DataFrame] = []
        for game in games_by_team.get(int(tid), []):
            frame = summaries.get(game["game_id"])
            if frame is None or frame.empty:
                continue
            part = frame.loc[pd.to_numeric(frame.get("TEAM_ID"), errors="coerce").fillna(0).astype(int).eq(int(tid))].copy()
            if not part.empty:
                parts.append(part)
        team_counts[int(tid)] = len(parts)
        player_data: dict[int, dict[str, Any]] = {}
        for pid in ids_by_team.get(int(tid), ()):
            w3 = _window_metrics(parts, int(pid), 3)
            w5 = _window_metrics(parts, int(pid), 5)
            w10 = _window_metrics(parts, int(pid), 10)
            player_data[int(pid)] = {
                "l3": w3, "l5": w5, "l10": w10,
                "fg": _blend_pct([(w3["fg"], .15, w3["fga"]), (w5["fg"], .25, w5["fga"]), (w10["fg"], .60, w10["fga"])], 25.0),
                "efg": _blend_pct([(w3["efg"], .15, w3["fga"]), (w5["efg"], .25, w5["fga"]), (w10["efg"], .60, w10["fga"])], 25.0),
                "p2": _blend_pct([(w3["p2"], .15, max(w3["fga"] * (1 - (_num(w3["share3"], 0.0))), 0.0)), (w5["p2"], .25, max(w5["fga"] * (1 - (_num(w5["share3"], 0.0))), 0.0)), (w10["p2"], .60, max(w10["fga"] * (1 - (_num(w10["share3"], 0.0))), 0.0))], 18.0),
                "p3": _blend_pct([(w3["p3"], .15, w3["fga"] * _num(w3["share3"], 0.0)), (w5["p3"], .25, w5["fga"] * _num(w5["share3"], 0.0)), (w10["p3"], .60, w10["fga"] * _num(w10["share3"], 0.0))], 12.0),
                "share3": _blend_pct([(w3["share3"], .15, w3["fga"]), (w5["share3"], .25, w5["fga"]), (w10["share3"], .60, w10["fga"])], 25.0),
                "fga_per_min": float(w10["fga"] / w10["min"]) if w10["min"] > 1 else 0.0,
                "l10_fga": w10["fga"],
            }

        # Team assist-to-made-field-goal context across the same recent sample.
        team_fgm = float(sum(pd.to_numeric(p.get("FGM"), errors="coerce").fillna(0.0).sum() for p in parts))
        team_ast = float(sum(pd.to_numeric(p.get("AST"), errors="coerce").fillna(0.0).sum() for p in parts))
        out[int(tid)] = {
            "players": player_data,
            "games": len(parts),
            "ast_fgm": float(team_ast / team_fgm) if team_fgm > 0 else np.nan,
        }

    ready = bool(team_counts and all(team_counts.get(int(tid), 0) >= MIN_SHOOTING_GAMES for tid in team_ids))
    return out, {
        "ready": ready,
        "reason": "" if ready else "one or more slate teams have fewer than 5 usable shooting box scores",
        "team_games": team_counts,
        "requested_summaries": len(jobs),
        "usable_summaries": len(summaries),
    }


def _weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    v = pd.to_numeric(values, errors="coerce")
    w = pd.to_numeric(weights, errors="coerce").fillna(0.0)
    valid = v.notna() & w.gt(0)
    if not valid.any():
        return np.nan
    den = float(w.loc[valid].sum())
    return float((v.loc[valid] * w.loc[valid]).sum() / den) if den > 0 else np.nan


def _conversion_index(efg: float, fg: float, p2: float, p3: float, ast_fgm: float) -> float:
    score = 50.0
    if np.isfinite(efg):
        score += 125.0 * (efg - 0.50)
    if np.isfinite(fg):
        score += 35.0 * (fg - 0.43)
    if np.isfinite(p2):
        score += 25.0 * (p2 - 0.50)
    if np.isfinite(p3):
        score += 20.0 * (p3 - 0.34)
    if np.isfinite(ast_fgm):
        score += 15.0 * (ast_fgm - 0.60)
    return float(np.clip(score, 0.0, 100.0))


def _grade(index: float) -> str:
    if index >= 62:
        return "STRONG"
    if index >= 54:
        return "ABOVE AVG"
    if index >= 46:
        return "NEUTRAL"
    if index >= 38:
        return "BELOW AVG"
    return "WEAK"


def _build_step8_conversion(slate: dict[str, Any], day_str: str, opportunity: pd.DataFrame):
    if opportunity is None or opportunity.empty:
        return pd.DataFrame(), pd.DataFrame(), {"ready": False, "reason": "no Step-7 opportunity rows"}

    meta = step3._team_meta(slate)
    team_ids = tuple(sorted(int(tid) for tid in meta))
    roster_ids: list[tuple[int, tuple[int, ...]]] = []
    for tid in team_ids:
        part = opportunity.loc[pd.to_numeric(opportunity.get("TEAM_ID_NUM"), errors="coerce").fillna(0).astype(int).eq(int(tid))]
        ids = tuple(sorted({_safe_int(x) for x in part.get("PLAYER_ID", pd.Series(dtype=str)) if _safe_int(x) > 0}))
        roster_ids.append((int(tid), ids))

    history, hdiag = _shooting_history(day_str, team_ids, tuple(roster_ids))
    out = opportunity.copy()
    for c in (
        "SELF_FG_BLEND", "SELF_EFG_BLEND", "SELF_2P_BLEND", "SELF_3P_BLEND", "SELF_3PA_SHARE",
        "TEAMMATE_FG_PCT", "TEAMMATE_EFG_PCT", "TEAMMATE_2P_PCT", "TEAMMATE_3P_PCT",
        "TEAMMATE_3PA_SHARE", "TEAMMATE_SHOOTER_COVERAGE", "TEAM_AST_FGM_L10",
        "LINEUP_CONVERSION_INDEX",
    ):
        out[c] = np.nan
    out["CONVERSION_GRADE"] = "UNAVAILABLE"
    out["CONVERSION_SOURCE"] = "ESPN WNBA completed-game shooting + Step 4 projected active rotation"

    team_rows: list[dict[str, Any]] = []
    for tid, team_meta in meta.items():
        mask = pd.to_numeric(out.get("TEAM_ID_NUM"), errors="coerce").fillna(0).astype(int).eq(int(tid))
        team = out.loc[mask].copy()
        hteam = history.get(int(tid), {}) or {}
        pdata = hteam.get("players", {}) or {}
        games = int(hteam.get("games") or 0)
        ast_fgm = _num(hteam.get("ast_fgm"), np.nan)
        if team.empty:
            team_rows.append({"Team": team_meta.get("name", str(tid)), "Shooting games": games, "Active lineup": 0, "Core covered": "0/0", "Median teammate eFG%": np.nan, "AST/FGM": ast_fgm, "Gate": "CHECK"})
            continue

        for idx, row in team.iterrows():
            pid = _safe_int(row.get("PLAYER_ID"))
            info = pdata.get(pid, {}) or {}
            out.at[idx, "SELF_FG_BLEND"] = _num(info.get("fg"), np.nan)
            out.at[idx, "SELF_EFG_BLEND"] = _num(info.get("efg"), np.nan)
            out.at[idx, "SELF_2P_BLEND"] = _num(info.get("p2"), np.nan)
            out.at[idx, "SELF_3P_BLEND"] = _num(info.get("p3"), np.nan)
            out.at[idx, "SELF_3PA_SHARE"] = _num(info.get("share3"), np.nan)

        team = out.loc[mask].copy()
        status = team.get("AVAILABILITY", pd.Series("UNKNOWN", index=team.index)).astype(str).str.upper()
        proj = pd.to_numeric(team.get("PROJ_MIN"), errors="coerce").fillna(0.0)
        active = proj.gt(0.25) & ~status.isin(ZERO_STATUSES)
        core = proj.ge(CORE_MINUTES) & ~status.isin(ZERO_STATUSES)

        # Volume weight = projected minutes x recent FGA per minute. A tiny floor
        # prevents a low-volume connector from disappearing entirely.
        fga_rate = []
        for _, row in team.iterrows():
            info = pdata.get(_safe_int(row.get("PLAYER_ID")), {}) or {}
            fga_rate.append(max(0.04, _num(info.get("fga_per_min"), 0.0)))
        team["_FGA_RATE"] = fga_rate
        team["_SHOT_WEIGHT"] = proj * pd.Series(fga_rate, index=team.index)

        for idx, row in team.iterrows():
            creator_pid = _safe_int(row.get("PLAYER_ID"))
            teammates = team.loc[active & ~team.get("PLAYER_ID", pd.Series(0, index=team.index)).map(_safe_int).eq(creator_pid)].copy()
            if teammates.empty:
                continue
            w = teammates["_SHOT_WEIGHT"]
            fg = _weighted_mean(teammates["SELF_FG_BLEND"], w)
            efg = _weighted_mean(teammates["SELF_EFG_BLEND"], w)
            p2 = _weighted_mean(teammates["SELF_2P_BLEND"], w)
            p3 = _weighted_mean(teammates["SELF_3P_BLEND"], w)
            share3 = _weighted_mean(teammates["SELF_3PA_SHARE"], w)
            valid_weight = float(w.loc[pd.to_numeric(teammates["SELF_EFG_BLEND"], errors="coerce").notna()].sum())
            total_weight = float(w.sum())
            coverage = valid_weight / total_weight if total_weight > 0 else 0.0
            cindex = _conversion_index(efg, fg, p2, p3, ast_fgm)
            out.at[idx, "TEAMMATE_FG_PCT"] = fg
            out.at[idx, "TEAMMATE_EFG_PCT"] = efg
            out.at[idx, "TEAMMATE_2P_PCT"] = p2
            out.at[idx, "TEAMMATE_3P_PCT"] = p3
            out.at[idx, "TEAMMATE_3PA_SHARE"] = share3
            out.at[idx, "TEAMMATE_SHOOTER_COVERAGE"] = coverage
            out.at[idx, "TEAM_AST_FGM_L10"] = ast_fgm
            out.at[idx, "LINEUP_CONVERSION_INDEX"] = cindex
            out.at[idx, "CONVERSION_GRADE"] = _grade(cindex)

        current = out.loc[mask].copy()
        core_count = int(core.sum())
        core_ready = int(
            (
                core
                & pd.to_numeric(current["TEAMMATE_EFG_PCT"], errors="coerce").notna()
                & pd.to_numeric(current["TEAMMATE_SHOOTER_COVERAGE"], errors="coerce").fillna(0.0).ge(0.65)
            ).sum()
        )
        active_count = int(active.sum())
        median_efg = float(pd.to_numeric(current.loc[core, "TEAMMATE_EFG_PCT"], errors="coerce").median()) if core_count else np.nan
        team_ready = bool(
            games >= MIN_SHOOTING_GAMES
            and active_count >= 5
            and core_count > 0
            and core_ready == core_count
        )
        team_rows.append({
            "Team": team_meta.get("name", str(tid)),
            "Shooting games": games,
            "Active lineup": active_count,
            "Core covered": f"{core_ready}/{core_count}",
            "Median teammate eFG%": round(median_efg * 100.0, 1) if np.isfinite(median_efg) else np.nan,
            "AST/FGM": round(ast_fgm * 100.0, 1) if np.isfinite(ast_fgm) else np.nan,
            "Gate": "PASS" if team_ready else "CHECK",
        })

    team_diag = pd.DataFrame(team_rows)
    ready = bool(hdiag.get("ready") and not team_diag.empty and team_diag["Gate"].eq("PASS").all())
    return out, team_diag, {
        "ready": ready,
        "reason": "" if ready else str(hdiag.get("reason") or "one or more lineup conversion checks failed"),
        "history": hdiag,
        "players": len(out),
        "teams": len(team_diag),
        "strong": int(out.get("CONVERSION_GRADE", pd.Series(dtype=str)).eq("STRONG").sum()),
        "weak": int(out.get("CONVERSION_GRADE", pd.Series(dtype=str)).eq("WEAK").sum()),
    }


def _render_step8(slate: dict[str, Any], day_str: str, opportunity: pd.DataFrame, step7_ready: bool):
    st.markdown("### 🎯 Step 8 — Teammate Shot-Making + Lineup Conversion")
    st.caption(
        "Step 7 measures creation opportunity. Step 8 measures how well the projected active teammates finish those opportunities. The creator is excluded from her own teammate-finishing context. This is still context only — not tonight's assist projection."
    )
    if not step7_ready:
        st.error("⛔ STEP 8 LOCKED • Step 7 has not passed, so teammate-conversion context cannot run.")
        return False, pd.DataFrame()

    with st.spinner("🎯 Rebuilding recent WNBA shooting + projected teammate conversion…"):
        conversion, team_diag, diag = _build_step8_conversion(slate, day_str, opportunity)

    ready = bool(diag.get("ready"))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Teams modeled", int(diag.get("teams") or 0))
    c2.metric("Players evaluated", int(diag.get("players") or 0))
    c3.metric("Strong contexts", int(diag.get("strong") or 0))
    c4.metric("Weak contexts", int(diag.get("weak") or 0))

    if ready:
        st.success("✅ STEP 8 PASSED • every slate team has at least 5 usable recent shooting box scores, projected active-lineup coverage is valid, and every core rotation player has an auditable teammate-finishing context. No opponent or final projection adjustment has been applied.")
    else:
        st.warning(f"⚠️ STEP 8 CHECK • {diag.get('reason') or 'conversion validation incomplete'}. Step 9 remains locked.")

    if team_diag is not None and not team_diag.empty:
        st.dataframe(team_diag, hide_index=True, use_container_width=True)

    if conversion is not None and not conversion.empty:
        view = conversion.copy()
        view["Player"] = view["PLAYER_NAME"].astype(str)
        view["Team"] = view.get("TEAM_ABBREVIATION", pd.Series("", index=view.index)).astype(str)
        view["Role"] = view.get("CREATION_ROLE", pd.Series("", index=view.index)).astype(str)
        view["Proj min"] = pd.to_numeric(view.get("PROJ_MIN"), errors="coerce").round(1)
        for src, label in (
            ("TEAMMATE_FG_PCT", "Tm FG%"),
            ("TEAMMATE_EFG_PCT", "Tm eFG%"),
            ("TEAMMATE_2P_PCT", "Tm 2P%"),
            ("TEAMMATE_3P_PCT", "Tm 3P%"),
            ("TEAMMATE_3PA_SHARE", "Tm 3PA share"),
            ("TEAM_AST_FGM_L10", "Team AST/FGM"),
            ("TEAMMATE_SHOOTER_COVERAGE", "Shooter coverage"),
        ):
            view[label] = (pd.to_numeric(view[src], errors="coerce") * 100.0).round(1)
        view["Conversion index"] = pd.to_numeric(view["LINEUP_CONVERSION_INDEX"], errors="coerce").round(1)
        view["Grade"] = view["CONVERSION_GRADE"].astype(str)
        view = view.sort_values(["TEAM_ID_NUM", "CREATION_RANK", "PROJ_MIN"], ascending=[True, True, False])
        st.dataframe(
            view[["Player", "Team", "Role", "Proj min", "Tm FG%", "Tm eFG%", "Tm 2P%", "Tm 3P%", "Tm 3PA share", "Team AST/FGM", "Shooter coverage", "Conversion index", "Grade"]],
            hide_index=True,
            use_container_width=True,
        )
        if ready:
            st.session_state[f"wnba_assists_v8_conversion::{day_str}"] = conversion.copy()

    hist = diag.get("history") or {}
    with st.expander("🧪 Step-8 conversion methodology / diagnostics", expanded=False):
        st.write("• Shooting sample: last 10 completed team games before the ET slate; minimum 5 usable games per slate team.")
        st.write("• Raw ESPN game summaries are parsed specifically for FGM/FGA and 3PM/3PA; the older Step-4/6 summary table remains untouched.")
        st.write("• Player finishing uses attempt-aware L3/L5/L10 shrinkage, weighted 15% / 25% / 60% before attempt reliability.")
        st.write("• Teammate context excludes the creator herself and uses projected minutes × recent FGA/min as the finisher weight.")
        st.write("• eFG% = (FGM + 0.5 × 3PM) / FGA. 2P%, 3P%, 3PA share and team AST/FGM are shown separately.")
        st.write("• Conversion index is a context index only; it is not an expected-assists number and does not touch Step 15 projection math.")
        st.write("• Opponent defense used: 0 — reserved for Step 9.")
        st.write("• Sportsbook lines used: 0")
        st.write("• Monte Carlo runs: 0")
        st.write(f"• Shooting summary requests: {hist.get('requested_summaries', 0)}")
        st.write(f"• Usable shooting summaries: {hist.get('usable_summaries', 0)}")

    return ready, conversion


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
          <div class="ks-ast-kicker">KYRE SPORTS AI • WNBA ASSISTS INTELLIGENCE • STEP 8</div>
          <div class="ks-ast-title">🎯 WNBA Assists Command Center</div>
          <div class="ks-ast-sub">Steps 1–7 remain intact. Step 8 measures the projected active teammates' shot-making and lineup conversion around each creator. Opponent defense, pace, sportsbook lines, final projection and simulations remain locked.</div>
          <span class="ks-ast-chip">📅 ET slate {slate_day}</span>
          <span class="ks-ast-chip">✅ Steps 1–7 preserved</span>
          <span class="ks-ast-chip">🎯 teammate conversion only</span>
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
    step8_ready, _ = _render_step8(slate, slate_day, opportunity, step7_ready)

    if st.button("🔄 RECHECK ASSISTS STEPS 2–8", use_container_width=True, key="assists_step8_recheck"):
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
            _shooting_history,
            _raw_shooting_summary,
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
        (8, "Teammate shot-making + lineup conversion", "✅ LIVE" if step8_ready else ("⚠️ CHECK" if step7_ready else "🔒 LOCKED"), "Projected active finisher environment"),
        (9, "Opponent assist environment", "➡️ NEXT" if step8_ready else "🔒 LOCKED", "Opponent scheme + assists allowed"),
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
        f"⚡ WNBA Assists V8 Step 8 • Step 2 {verification or 'CHECK'} • Step 3 {'PASS' if step3_ready else 'LOCKED'} • Step 4 {'PASS' if step4_ready else 'CHECK'} • Step 5 {'PASS' if step5_ready else 'CHECK'} • Step 6 {'PASS' if step6_ready else 'CHECK'} • Step 7 {'PASS' if step7_ready else 'CHECK'} • Step 8 {'PASS' if step8_ready else 'CHECK'} • no opponent/projection/market/Monte Carlo yet"
    )


__all__ = ["MODEL_VERSION", "render_wnba_assists_hub"]
