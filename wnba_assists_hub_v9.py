"""WNBA Assists V9 — Step 9 opponent assist environment.

Preserves Assists Steps 1–8 and adds only team-level opponent assist context.

Step 9 rules:
- Step 8 must pass first;
- map every current slate team to the exact verified opponent from Step 2;
- prefer official WNBA Opponent team stats for season/L10/L5/L3 when available;
- fall back to completed ESPN WNBA box scores when the official stats host is
  blocked or incomplete;
- measure opponent assists allowed per game and opponent AST/FGM allowed;
- keep season, L10, L5 and L3 visible separately;
- build a regression-protected environment baseline that remains anchored to
  season performance so a short hot/cold defensive stretch cannot dominate;
- Step 9 is team-level only: Guard/Wing/Big matchup context remains Step 10.

No pace, player-vs-opponent H2H, sportsbook line, final assist projection,
fair odds or Monte Carlo is enabled here.
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
import wnba_assists_hub_v5 as step5
import wnba_assists_hub_v6 as step6
import wnba_assists_hub_v7 as step7
import wnba_assists_hub_v8 as step8
import wnba_players_v25 as players

MODEL_VERSION = "WNBA ASSISTS V9 • STEP 9 OPPONENT ASSIST ENVIRONMENT"
_ET = ZoneInfo("America/New_York")
WNBA_TEAM_STATS_URL = "https://stats.wnba.com/stats/leaguedashteamstats"
MIN_SEASON_GAMES = 10


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


def _matchups(slate: dict[str, Any]) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for game in (slate or {}).get("games", []) or []:
        if not isinstance(game, dict):
            continue
        away = _safe_int(game.get("away_team_id"))
        home = _safe_int(game.get("home_team_id"))
        if away and home:
            out[away] = {
                "opponent_id": home,
                "opponent": str(game.get("home") or ""),
                "opponent_abbr": str(game.get("home_tricode") or ""),
            }
            out[home] = {
                "opponent_id": away,
                "opponent": str(game.get("away") or ""),
                "opponent_abbr": str(game.get("away_tricode") or ""),
            }
    return out


def _official_params(season: int, last_n: int) -> dict[str, Any]:
    return {
        "Conference": "", "DateFrom": "", "DateTo": "", "Division": "",
        "GameScope": "", "GameSegment": "", "LastNGames": int(last_n),
        "LeagueID": "10", "Location": "", "MeasureType": "Opponent",
        "Month": 0, "OpponentTeamID": 0, "Outcome": "", "PORound": 0,
        "PaceAdjust": "N", "PerMode": "PerGame", "Period": 0,
        "PlayerExperience": "", "PlayerPosition": "", "PlusMinus": "N",
        "Rank": "N", "Season": str(int(season)), "SeasonSegment": "",
        "SeasonType": "Regular Season", "ShotClockRange": "",
        "StarterBench": "", "TeamID": 0, "VsConference": "",
        "VsDivision": "",
    }


def _official_headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
        "Accept": "application/json,text/plain,*/*",
        "Origin": "https://www.wnba.com",
        "Referer": "https://www.wnba.com/",
    }


def _parse_official(payload: Any) -> pd.DataFrame:
    if not isinstance(payload, dict):
        return pd.DataFrame()
    sets = payload.get("resultSets") or payload.get("resultSet") or []
    if isinstance(sets, dict):
        sets = [sets]
    for item in sets if isinstance(sets, list) else []:
        cols = [str(c).upper() for c in (item.get("headers") or [])]
        rows = item.get("rowSet") or []
        if "TEAM_ID" not in cols:
            continue
        frame = pd.DataFrame(rows, columns=cols)
        ast_col = "OPP_AST" if "OPP_AST" in frame.columns else ("AST" if "AST" in frame.columns else "")
        fgm_col = "OPP_FGM" if "OPP_FGM" in frame.columns else ("FGM" if "FGM" in frame.columns else "")
        if not ast_col or not fgm_col:
            continue
        keep = [c for c in ("TEAM_ID", "TEAM_NAME", "GP", ast_col, fgm_col) if c in frame.columns]
        out = frame[keep].copy()
        out = out.rename(columns={ast_col: "OPP_AST", fgm_col: "OPP_FGM"})
        out["TEAM_ID"] = pd.to_numeric(out["TEAM_ID"], errors="coerce").fillna(0).astype(int)
        for c in ("GP", "OPP_AST", "OPP_FGM"):
            if c in out.columns:
                out[c] = pd.to_numeric(out[c], errors="coerce")
        return out[out["TEAM_ID"].gt(0)].reset_index(drop=True)
    return pd.DataFrame()


def _fetch_official_window(season: int, last_n: int) -> tuple[pd.DataFrame, str]:
    try:
        r = requests.get(
            WNBA_TEAM_STATS_URL,
            params=_official_params(season, last_n),
            headers=_official_headers(),
            timeout=5,
        )
        r.raise_for_status()
        frame = _parse_official(r.json())
        if frame.empty:
            return pd.DataFrame(), "empty"
        return frame, "ok"
    except Exception as exc:
        return pd.DataFrame(), type(exc).__name__


@st.cache_data(ttl=1200, show_spinner=False, max_entries=4)
def _official_windows(season: int):
    jobs = {"SEASON": 0, "L10": 10, "L5": 5, "L3": 3}
    frames: dict[str, pd.DataFrame] = {}
    states: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_fetch_official_window, int(season), n): label for label, n in jobs.items()}
        for future in as_completed(futures):
            label = futures[future]
            try:
                frame, state = future.result()
            except Exception as exc:
                frame, state = pd.DataFrame(), type(exc).__name__
            frames[label] = frame
            states[label] = state
    return frames, states


def _official_environment(frames: dict[str, pd.DataFrame], team_id: int) -> dict[str, Any] | None:
    result: dict[str, Any] = {}
    for label in ("SEASON", "L10", "L5", "L3"):
        frame = frames.get(label, pd.DataFrame())
        if frame is None or frame.empty:
            return None
        row = frame.loc[pd.to_numeric(frame["TEAM_ID"], errors="coerce").fillna(0).astype(int).eq(int(team_id))]
        if len(row) != 1:
            return None
        r = row.iloc[0]
        ast = _num(r.get("OPP_AST"))
        fgm = _num(r.get("OPP_FGM"))
        gp = _safe_int(r.get("GP"))
        if not np.isfinite(ast) or not np.isfinite(fgm) or fgm <= 0:
            return None
        result[label.lower()] = {
            "games": gp,
            "ast": ast,
            "fgm": fgm,
            "ast_fgm": ast / fgm,
        }
    result["source"] = "WNBA Stats • Opponent team stats"
    return result


def _all_completed_team_games(season: pd.DataFrame, day_str: str, team_id: int) -> pd.DataFrame:
    if season is None or season.empty:
        return pd.DataFrame()
    frame = season.copy()
    before = pd.to_datetime(frame.get("game_date"), errors="coerce") < pd.to_datetime(day_str)
    final = frame.get("status", pd.Series("", index=frame.index)).astype(str).str.upper().eq("FINAL")
    away = pd.to_numeric(frame.get("away_team_id"), errors="coerce").eq(int(team_id))
    home = pd.to_numeric(frame.get("home_team_id"), errors="coerce").eq(int(team_id))
    out = frame.loc[before & final & (away | home)].copy()
    if out.empty:
        return out
    out["_date"] = pd.to_datetime(out.get("game_date"), errors="coerce")
    return out.sort_values("_date", ascending=False).drop_duplicates("game_id")


def _record_from_summary(frame: pd.DataFrame, defense_team_id: int) -> dict[str, float] | None:
    if frame is None or frame.empty or "TEAM_ID" not in frame.columns:
        return None
    tids = pd.to_numeric(frame["TEAM_ID"], errors="coerce").fillna(0).astype(int)
    if not tids.eq(int(defense_team_id)).any():
        return None
    opp = frame.loc[~tids.eq(int(defense_team_id))].copy()
    if opp.empty:
        return None
    ast = float(pd.to_numeric(opp.get("AST"), errors="coerce").fillna(0.0).sum())
    fgm = float(pd.to_numeric(opp.get("FGM"), errors="coerce").fillna(0.0).sum())
    if fgm <= 0:
        return None
    return {"ast": ast, "fgm": fgm}


def _window_from_records(records: list[dict[str, float]], k: int | None = None) -> dict[str, float]:
    use = records if k is None else records[: min(k, len(records))]
    games = len(use)
    if not use:
        return {"games": 0, "ast": np.nan, "fgm": np.nan, "ast_fgm": np.nan}
    ast = float(sum(r["ast"] for r in use))
    fgm = float(sum(r["fgm"] for r in use))
    return {
        "games": games,
        "ast": ast / games,
        "fgm": fgm / games,
        "ast_fgm": ast / fgm if fgm > 0 else np.nan,
    }


@st.cache_data(ttl=1800, show_spinner=False, max_entries=8)
def _espn_environment(day_str: str, team_ids: tuple[int, ...]):
    season = step4._season_schedule(pd.to_datetime(day_str).year)
    if season is None or season.empty:
        return {}, {"ready": False, "reason": "season schedule unavailable"}

    games_by_team: dict[int, list[dict[str, str]]] = {}
    jobs: dict[str, str] = {}
    for tid in team_ids:
        games = _all_completed_team_games(season, day_str, int(tid))
        rows: list[dict[str, str]] = []
        for _, g in games.iterrows():
            gid = str(g.get("game_id") or "")
            gdate = str(g.get("game_date") or "")[:10]
            if gid:
                rows.append({"game_id": gid, "game_date": gdate})
                jobs[gid] = gdate
        games_by_team[int(tid)] = rows

    summaries: dict[str, pd.DataFrame] = {}
    if jobs:
        with ThreadPoolExecutor(max_workers=min(16, max(1, len(jobs)))) as pool:
            futures = {pool.submit(step8._raw_shooting_summary, gid, gdate): gid for gid, gdate in jobs.items()}
            for future in as_completed(futures):
                gid = futures[future]
                try:
                    frame = future.result()
                    if frame is not None and not frame.empty:
                        summaries[gid] = frame.copy()
                except Exception:
                    continue

    env: dict[int, dict[str, Any]] = {}
    counts: dict[int, int] = {}
    for tid in team_ids:
        records: list[dict[str, float]] = []
        for g in games_by_team.get(int(tid), []):
            rec = _record_from_summary(summaries.get(g["game_id"], pd.DataFrame()), int(tid))
            if rec is not None:
                records.append(rec)
        counts[int(tid)] = len(records)
        env[int(tid)] = {
            "season": _window_from_records(records, None),
            "l10": _window_from_records(records, 10),
            "l5": _window_from_records(records, 5),
            "l3": _window_from_records(records, 3),
            "source": "ESPN WNBA completed box-score fallback",
        }

    ready = bool(counts and all(counts.get(int(tid), 0) >= MIN_SEASON_GAMES for tid in team_ids))
    return env, {
        "ready": ready,
        "reason": "" if ready else "one or more opponents have fewer than 10 usable completed box scores",
        "team_games": counts,
        "requested_summaries": len(jobs),
        "usable_summaries": len(summaries),
    }


def _blend(values: list[tuple[float, float]]) -> float:
    use = [(float(v), float(w)) for v, w in values if np.isfinite(v)]
    den = sum(w for _, w in use)
    return sum(v * w for v, w in use) / den if den else np.nan


def _trend(recent: float, season: float) -> str:
    if not np.isfinite(recent) or not np.isfinite(season):
        return "UNKNOWN"
    diff = recent - season
    if diff >= 1.25:
        return "MORE ASSISTS RECENTLY"
    if diff <= -1.25:
        return "FEWER ASSISTS RECENTLY"
    return "STABLE"


def _build_step9_environment(slate: dict[str, Any], day_str: str, conversion: pd.DataFrame):
    if conversion is None or conversion.empty:
        return pd.DataFrame(), pd.DataFrame(), {"ready": False, "reason": "no Step-8 conversion rows"}

    matchup = _matchups(slate)
    offense_ids = tuple(sorted(matchup))
    opponent_ids = tuple(sorted({int(matchup[tid]["opponent_id"]) for tid in offense_ids if matchup[tid].get("opponent_id")}))
    season_year = pd.to_datetime(day_str).year

    official_frames, official_states = _official_windows(int(season_year))
    env_by_opp: dict[int, dict[str, Any]] = {}
    official_complete = True
    for oid in opponent_ids:
        env = _official_environment(official_frames, int(oid))
        if env is None or _safe_int(env.get("season", {}).get("games")) < MIN_SEASON_GAMES:
            official_complete = False
            break
        env_by_opp[int(oid)] = env

    fallback_diag: dict[str, Any] = {}
    mode = "OFFICIAL WNBA OPPONENT STATS"
    if not official_complete:
        env_by_opp, fallback_diag = _espn_environment(day_str, opponent_ids)
        mode = "ESPN BOX-SCORE FALLBACK"

    out = conversion.copy()
    out["OPPONENT_TEAM_ID"] = 0
    out["OPPONENT"] = ""
    out["OPP_AST_ALLOWED_SEASON"] = np.nan
    out["OPP_AST_ALLOWED_L10"] = np.nan
    out["OPP_AST_ALLOWED_L5"] = np.nan
    out["OPP_AST_ALLOWED_L3"] = np.nan
    out["OPP_AST_FGM_SEASON"] = np.nan
    out["OPP_AST_FGM_L10"] = np.nan
    out["OPP_AST_ENV_STABLE"] = np.nan
    out["OPP_AST_FGM_STABLE"] = np.nan
    out["OPP_AST_RECENT_TREND"] = "UNKNOWN"
    out["OPP_ENV_SOURCE"] = ""

    team_rows: list[dict[str, Any]] = []
    meta = step3._team_meta(slate)
    all_ready = True
    for tid in offense_ids:
        m = matchup.get(int(tid), {})
        oid = _safe_int(m.get("opponent_id"))
        env = env_by_opp.get(int(oid), {})
        s = env.get("season", {}) or {}
        l10 = env.get("l10", {}) or {}
        l5 = env.get("l5", {}) or {}
        l3 = env.get("l3", {}) or {}

        season_ast = _num(s.get("ast"))
        l10_ast = _num(l10.get("ast"))
        l5_ast = _num(l5.get("ast"))
        l3_ast = _num(l3.get("ast"))
        season_ratio = _num(s.get("ast_fgm"))
        l10_ratio = _num(l10.get("ast_fgm"))
        l5_ratio = _num(l5.get("ast_fgm"))
        l3_ratio = _num(l3.get("ast_fgm"))

        stable_ast = _blend([(season_ast, .55), (l10_ast, .25), (l5_ast, .12), (l3_ast, .08)])
        stable_ratio = _blend([(season_ratio, .55), (l10_ratio, .25), (l5_ratio, .12), (l3_ratio, .08)])
        recent_ast = _blend([(l10_ast, .50), (l5_ast, .30), (l3_ast, .20)])
        trend = _trend(recent_ast, season_ast)
        games = _safe_int(s.get("games"))
        team_ready = bool(
            oid > 0 and games >= MIN_SEASON_GAMES
            and all(np.isfinite(x) for x in (season_ast, l10_ast, l5_ast, l3_ast, stable_ast, stable_ratio))
        )
        all_ready = all_ready and team_ready

        mask = pd.to_numeric(out.get("TEAM_ID_NUM"), errors="coerce").fillna(0).astype(int).eq(int(tid))
        out.loc[mask, "OPPONENT_TEAM_ID"] = int(oid)
        out.loc[mask, "OPPONENT"] = str(m.get("opponent") or "")
        out.loc[mask, "OPP_AST_ALLOWED_SEASON"] = season_ast
        out.loc[mask, "OPP_AST_ALLOWED_L10"] = l10_ast
        out.loc[mask, "OPP_AST_ALLOWED_L5"] = l5_ast
        out.loc[mask, "OPP_AST_ALLOWED_L3"] = l3_ast
        out.loc[mask, "OPP_AST_FGM_SEASON"] = season_ratio
        out.loc[mask, "OPP_AST_FGM_L10"] = l10_ratio
        out.loc[mask, "OPP_AST_ENV_STABLE"] = stable_ast
        out.loc[mask, "OPP_AST_FGM_STABLE"] = stable_ratio
        out.loc[mask, "OPP_AST_RECENT_TREND"] = trend
        out.loc[mask, "OPP_ENV_SOURCE"] = str(env.get("source") or mode)

        team_rows.append({
            "Team": meta.get(int(tid), {}).get("name", str(tid)),
            "Opponent": str(m.get("opponent") or ""),
            "Season games": games,
            "Season AST allowed": round(season_ast, 1) if np.isfinite(season_ast) else np.nan,
            "L10": round(l10_ast, 1) if np.isfinite(l10_ast) else np.nan,
            "L5": round(l5_ast, 1) if np.isfinite(l5_ast) else np.nan,
            "L3": round(l3_ast, 1) if np.isfinite(l3_ast) else np.nan,
            "Stable AST env": round(stable_ast, 1) if np.isfinite(stable_ast) else np.nan,
            "Stable AST/FGM": round(stable_ratio * 100.0, 1) if np.isfinite(stable_ratio) else np.nan,
            "Recent trend": trend,
            "Source": str(env.get("source") or mode),
            "Gate": "PASS" if team_ready else "CHECK",
        })

    team_diag = pd.DataFrame(team_rows)
    ready = bool(all_ready and len(team_rows) == len(offense_ids) and len(offense_ids) > 0)
    return out, team_diag, {
        "ready": ready,
        "reason": "" if ready else "one or more exact opponent environment checks failed",
        "mode": mode,
        "official_states": official_states,
        "fallback": fallback_diag,
        "teams": len(team_rows),
    }


def _render_step9(slate: dict[str, Any], day_str: str, conversion: pd.DataFrame, step8_ready: bool):
    st.markdown("### 🛡️ Step 9 — Opponent Assist Environment")
    st.caption(
        "Team-level opponent assist context only. Season, L10, L5 and L3 assists allowed plus AST/FGM are kept separate, then regression-protected toward the season baseline. Guard/Wing/Big matchup context remains locked for Step 10."
    )
    if not step8_ready:
        st.error("⛔ STEP 9 LOCKED • Step 8 has not passed, so opponent assist context cannot run.")
        return False, pd.DataFrame()

    with st.spinner("🛡️ Verifying opponent assist environment…"):
        environment, team_diag, diag = _build_step9_environment(slate, day_str, conversion)

    ready = bool(diag.get("ready"))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Matchup teams", int(diag.get("teams") or 0))
    c2.metric("Environment mode", str(diag.get("mode") or "CHECK"))
    c3.metric("Position split", "STEP 10")
    c4.metric("Monte Carlo", "0")

    if ready:
        st.success("✅ STEP 9 PASSED • every verified slate team is mapped to the exact opponent and has season + L10/L5/L3 assist-allowed context with regression protection. No position-specific, pace or final projection adjustment has been applied.")
    else:
        st.warning(f"⚠️ STEP 9 CHECK • {diag.get('reason') or 'opponent environment incomplete'}. Step 10 remains locked.")

    if team_diag is not None and not team_diag.empty:
        st.dataframe(team_diag, hide_index=True, use_container_width=True)

    if environment is not None and not environment.empty and ready:
        st.session_state[f"wnba_assists_v9_opponent_environment::{day_str}"] = environment.copy()

    with st.expander("🧪 Step-9 opponent-environment methodology / diagnostics", expanded=False):
        st.write("• Exact opponent comes only from the verified Step-2 same-day matchup.")
        st.write("• Preferred source: WNBA Stats Opponent team stats for Season/L10/L5/L3.")
        st.write("• Fallback: completed ESPN WNBA box scores, reconstructed opponent by opponent.")
        st.write("• Stable baseline weights: 55% season, 25% L10, 12% L5, 8% L3.")
        st.write("• AST/FGM is tracked separately from raw assists allowed so made-shot volume does not masquerade as assist friendliness.")
        st.write("• No invented defensive 'scheme' labels; this step reports measurable assist environment only.")
        st.write("• Guard/Wing/Big split used: 0 — reserved for Step 10.")
        st.write("• Pace adjustment used: 0 — reserved for Step 11.")
        st.write("• Sportsbook lines used: 0")
        st.write("• Monte Carlo runs: 0")
        st.write(f"• Official request states: {diag.get('official_states', {})}")
        fallback = diag.get("fallback") or {}
        if fallback:
            st.write(f"• ESPN fallback summary requests: {fallback.get('requested_summaries', 0)}")
            st.write(f"• ESPN fallback usable summaries: {fallback.get('usable_summaries', 0)}")

    return ready, environment


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
          <div class="ks-ast-kicker">KYRE SPORTS AI • WNBA ASSISTS INTELLIGENCE • STEP 9</div>
          <div class="ks-ast-title">🎯 WNBA Assists Command Center</div>
          <div class="ks-ast-sub">Steps 1–8 remain intact. Step 9 adds only the exact opponent's measurable assist environment with season + recent regression protection. Position matchup, pace, H2H, sportsbook lines, final projection and simulations remain locked.</div>
          <span class="ks-ast-chip">📅 ET slate {slate_day}</span>
          <span class="ks-ast-chip">✅ Steps 1–8 preserved</span>
          <span class="ks-ast-chip">🛡️ opponent assist environment</span>
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
    step9_ready, _ = _render_step9(slate, slate_day, conversion, step8_ready)

    if st.button("🔄 RECHECK ASSISTS STEPS 2–9", use_container_width=True, key="assists_step9_recheck"):
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
            _official_windows,
            _espn_environment,
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
        (9, "Opponent assist environment", "✅ LIVE" if step9_ready else ("⚠️ CHECK" if step8_ready else "🔒 LOCKED"), "Season + L10/L5/L3 assists allowed + AST/FGM"),
        (10, "Position matchup — Guard / Wing / Big", "➡️ NEXT" if step9_ready else "🔒 LOCKED", "Role-sensitive matchup context"),
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
        f"⚡ WNBA Assists V9 Step 9 • Step 2 {verification or 'CHECK'} • Step 3 {'PASS' if step3_ready else 'CHECK'} • Step 4 {'PASS' if step4_ready else 'CHECK'} • Step 5 {'PASS' if step5_ready else 'CHECK'} • Step 6 {'PASS' if step6_ready else 'CHECK'} • Step 7 {'PASS' if step7_ready else 'CHECK'} • Step 8 {'PASS' if step8_ready else 'CHECK'} • Step 9 {'PASS' if step9_ready else 'CHECK'} • no position/pace/projection/market/Monte Carlo yet"
    )


__all__ = ["MODEL_VERSION", "render_wnba_assists_hub"]
