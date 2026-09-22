"""WNBA Assists V6 — Step 6 recent + season assist form.

Preserves Assists Steps 1–5 and adds only empirical assist-form context.

Step 6 rules:
- current Step-3 roster/status gate and Step-4 projected rotation only;
- Step-5 creator-role classifications must pass first;
- season assists/minutes come from the existing verified selected-player pool;
- L3/L5/L10 assist form is rebuilt from completed ESPN WNBA game summaries;
- a current-roster player absent from a verified team box score counts as 0
  assists/minutes for that game;
- exposes AST/game, AST/36, recent trend and game-to-game volatility;
- regression-protected form rate shrinks noisy recent AST/36 back toward the
  season baseline using recent minute exposure;
- exact player-id + team match is preferred; exact normalized name + team is
  the only season-table fallback;
- this is still descriptive form, NOT a final assist projection.

Potential assists/passes, teammate conversion, opponent matchup, sportsbook
lines, fair odds and Monte Carlo remain locked for later steps.
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
import wnba_players_v25 as players

MODEL_VERSION = "WNBA ASSISTS V6 • STEP 6 RECENT + SEASON ASSIST FORM"
_ET = ZoneInfo("America/New_York")
ZERO_STATUSES = {"OUT", "INACTIVE", "DOUBTFUL"}
MIN_FORM_GAMES = 5
CORE_MINUTES = 10.0


def _num(value: Any, default: float = 0.0) -> float:
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _safe_pid(value: Any) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _norm(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _day(value: Any) -> str:
    return pd.to_datetime(value).strftime("%Y-%m-%d")


@st.cache_data(ttl=900, show_spinner=False, max_entries=8)
def _season_form_pool(day_str: str):
    """Existing verified season/L10/L5 player pool, used only for season baseline."""
    day_str = _day(day_str)
    try:
        frame, diag = players._build_selected_player_pool(day_str)
    except Exception as exc:
        return pd.DataFrame(), {"state": "PROVIDER_FAILURE", "reason": type(exc).__name__}
    if frame is None:
        frame = pd.DataFrame()
    return frame.copy(), dict(diag or {})


@st.cache_data(ttl=900, show_spinner=False, max_entries=32)
def _recent_assist_history(
    day_str: str,
    team_ids: tuple[int, ...],
    roster_ids: tuple[tuple[int, tuple[int, ...]], ...],
):
    """Build current-roster L3/L5/L10 raw assist form from verified team games."""
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

    history: dict[int, dict[int, dict[str, Any]]] = {}
    team_counts: dict[int, int] = {}
    for tid in team_ids:
        minute_maps: list[dict[int, float]] = []
        assist_maps: list[dict[int, float]] = []
        for game in games_by_team.get(int(tid), []):
            box = summaries.get(game["game_id"])
            if box is None or box.empty or "TEAM_ID" not in box.columns:
                continue
            part = box.loc[pd.to_numeric(box["TEAM_ID"], errors="coerce").eq(int(tid))].copy()
            if part.empty:
                continue
            mm: dict[int, float] = {}
            aa: dict[int, float] = {}
            for _, row in part.iterrows():
                pid = _safe_pid(row.get("PLAYER_ID"))
                if not pid:
                    continue
                mm[pid] = max(0.0, _num(row.get("MIN"), 0.0))
                aa[pid] = max(0.0, _num(row.get("AST"), 0.0))
            minute_maps.append(mm)
            assist_maps.append(aa)

        n = len(minute_maps)
        team_counts[int(tid)] = n
        history[int(tid)] = {}
        for pid in ids_by_team.get(int(tid), ()):
            mins = [float(m.get(int(pid), 0.0)) for m in minute_maps]
            asts = [float(a.get(int(pid), 0.0)) for a in assist_maps]

            def _window(k: int) -> dict[str, float]:
                kk = min(k, n)
                if kk <= 0:
                    return {"ast_pg": 0.0, "min_pg": 0.0, "ast36": 0.0, "ast_sum": 0.0, "min_sum": 0.0}
                a = asts[:kk]
                m = mins[:kk]
                asum = float(sum(a))
                msum = float(sum(m))
                return {
                    "ast_pg": asum / kk,
                    "min_pg": msum / kk,
                    "ast36": 36.0 * asum / msum if msum > 1.0 else 0.0,
                    "ast_sum": asum,
                    "min_sum": msum,
                }

            w3 = _window(3)
            w5 = _window(5)
            w10 = _window(10)
            mean10 = float(np.mean(asts[: min(10, n)])) if n else 0.0
            sd10 = float(np.std(asts[: min(10, n)], ddof=0)) if n else 0.0
            history[int(tid)][int(pid)] = {
                "games": n,
                "appearances": int(sum(m > 0.25 for m in mins)),
                "last_ast": asts[0] if asts else 0.0,
                "l3_ast": w3["ast_pg"], "l3_min": w3["min_pg"], "l3_ast36": w3["ast36"],
                "l5_ast": w5["ast_pg"], "l5_min": w5["min_pg"], "l5_ast36": w5["ast36"],
                "l10_ast": w10["ast_pg"], "l10_min": w10["min_pg"], "l10_ast36": w10["ast36"],
                "l10_min_sum": w10["min_sum"],
                "mean10": mean10,
                "sd10": sd10,
            }

    ready = bool(team_counts and all(team_counts.get(int(tid), 0) >= MIN_FORM_GAMES for tid in team_ids))
    return history, {
        "ready": ready,
        "reason": "" if ready else "one or more slate teams have fewer than 5 usable assist-form games",
        "team_games": team_counts,
        "requested_summaries": len(jobs),
        "unique_summaries": len(summaries),
    }


def _season_lookup(pool: pd.DataFrame):
    by_id: dict[tuple[int, int], pd.Series] = {}
    by_name: dict[tuple[int, str], list[pd.Series]] = {}
    if pool is None or pool.empty:
        return by_id, by_name
    for _, row in pool.iterrows():
        tid = _safe_pid(row.get("TEAM_ID"))
        pid = _safe_pid(row.get("PLAYER_ID"))
        name = _norm(row.get("PLAYER_NAME"))
        if tid and pid:
            by_id[(tid, pid)] = row
        if tid and name:
            by_name.setdefault((tid, name), []).append(row)
    return by_id, by_name


def _stabilized_rate(season_rate: float, recent_rate: float, recent_minutes: float) -> tuple[float, float]:
    """Shrink recent rate toward season using exposure; output is form, not projection."""
    season_ok = np.isfinite(season_rate) and season_rate >= 0.0
    recent_ok = np.isfinite(recent_rate) and recent_rate >= 0.0
    if not season_ok and not recent_ok:
        return np.nan, 0.0
    if not season_ok:
        return float(recent_rate), 1.0
    if not recent_ok or recent_minutes <= 1.0:
        return float(season_rate), 0.0
    # 180 recent minutes acts like roughly 5-6 starter games of stabilizing prior.
    alpha = float(np.clip(recent_minutes / (recent_minutes + 180.0), 0.10, 0.62))
    return float((1.0 - alpha) * season_rate + alpha * recent_rate), alpha


def _trend_label(diff36: float) -> str:
    if diff36 >= 1.25:
        return "UP"
    if diff36 <= -1.25:
        return "DOWN"
    return "STABLE"


def _volatility_label(mean_ast: float, sd_ast: float) -> str:
    cv = sd_ast / max(mean_ast, 1.0)
    if sd_ast <= 1.25 and cv <= 0.55:
        return "LOW"
    if sd_ast <= 2.25 and cv <= 0.95:
        return "MEDIUM"
    return "HIGH"


def _build_step6_form(
    slate: dict[str, Any],
    day_str: str,
    roles: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    if roles is None or roles.empty:
        return pd.DataFrame(), pd.DataFrame(), {"ready": False, "reason": "no Step-5 role rows"}

    meta = step3._team_meta(slate)
    team_ids = tuple(sorted(int(tid) for tid in meta))
    roster_ids: list[tuple[int, tuple[int, ...]]] = []
    for tid in team_ids:
        part = roles.loc[pd.to_numeric(roles.get("TEAM_ID_NUM"), errors="coerce").fillna(0).astype(int).eq(int(tid))]
        ids = tuple(sorted({_safe_pid(x) for x in part.get("PLAYER_ID", pd.Series(dtype=str)) if _safe_pid(x) > 0}))
        roster_ids.append((int(tid), ids))

    history, hdiag = _recent_assist_history(day_str, team_ids, tuple(roster_ids))
    season_pool, sdiag = _season_form_pool(day_str)
    by_id, by_name = _season_lookup(season_pool)

    frames: list[pd.DataFrame] = []
    team_rows: list[dict[str, Any]] = []
    for tid in team_ids:
        team = roles.loc[pd.to_numeric(roles.get("TEAM_ID_NUM"), errors="coerce").fillna(0).astype(int).eq(int(tid))].copy()
        if team.empty:
            team_rows.append({"Team": meta.get(tid, {}).get("name", str(tid)), "Form games": 0, "Core players": 0, "Core baselines": 0, "High volatility": 0, "Gate": "CHECK"})
            continue

        pdata = history.get(int(tid), {}) or {}
        season_ast: list[float] = []
        season_min: list[float] = []
        season_gp: list[int] = []
        season_ast36: list[float] = []
        season_match: list[str] = []
        l3_ast: list[float] = []
        l5_ast: list[float] = []
        l10_ast: list[float] = []
        l3_ast36: list[float] = []
        l5_ast36: list[float] = []
        l10_ast36: list[float] = []
        l10_minutes: list[float] = []
        last_ast: list[float] = []
        sd10s: list[float] = []
        appearances: list[int] = []
        form_games: list[int] = []
        stabilized: list[float] = []
        recent_weight: list[float] = []
        trend: list[str] = []
        volatility: list[str] = []

        for _, row in team.iterrows():
            pid = _safe_pid(row.get("PLAYER_ID"))
            info = pdata.get(pid, {})
            srow = by_id.get((int(tid), pid))
            match_mode = "PLAYER_ID+TEAM" if srow is not None else ""
            if srow is None:
                candidates = by_name.get((int(tid), _norm(row.get("PLAYER_NAME"))), [])
                if len(candidates) == 1:
                    srow = candidates[0]
                    match_mode = "NAME+TEAM"

            if srow is not None:
                sast = _num(srow.get("AST"), 0.0)
                smin = _num(srow.get("MIN"), 0.0)
                sgp = int(_num(srow.get("GP"), 0.0))
                srate = 36.0 * sast / smin if smin > 1.0 else np.nan
            else:
                sast, smin, sgp, srate = np.nan, np.nan, 0, np.nan

            r3 = _num(info.get("l3_ast36"), np.nan)
            r5 = _num(info.get("l5_ast36"), np.nan)
            r10 = _num(info.get("l10_ast36"), np.nan)
            recent_parts = [(r3, 0.50), (r5, 0.30), (r10, 0.20)]
            valid_parts = [(v, w) for v, w in recent_parts if np.isfinite(v) and v >= 0]
            recent_rate = sum(v * w for v, w in valid_parts) / sum(w for _, w in valid_parts) if valid_parts else np.nan
            stab, alpha = _stabilized_rate(srate, recent_rate, _num(info.get("l10_min_sum"), 0.0))
            diff = (recent_rate - srate) if np.isfinite(recent_rate) and np.isfinite(srate) else 0.0
            mean10 = _num(info.get("mean10"), 0.0)
            sd10 = _num(info.get("sd10"), 0.0)

            season_ast.append(sast); season_min.append(smin); season_gp.append(sgp); season_ast36.append(srate); season_match.append(match_mode or "UNMATCHED")
            l3_ast.append(_num(info.get("l3_ast"), 0.0)); l5_ast.append(_num(info.get("l5_ast"), 0.0)); l10_ast.append(_num(info.get("l10_ast"), 0.0))
            l3_ast36.append(r3); l5_ast36.append(r5); l10_ast36.append(r10); l10_minutes.append(_num(info.get("l10_min_sum"), 0.0))
            last_ast.append(_num(info.get("last_ast"), 0.0)); sd10s.append(sd10); appearances.append(int(info.get("appearances") or 0)); form_games.append(int(info.get("games") or 0))
            stabilized.append(stab); recent_weight.append(alpha); trend.append(_trend_label(diff)); volatility.append(_volatility_label(mean10, sd10))

        team["SEASON_AST"] = season_ast
        team["SEASON_MIN"] = season_min
        team["SEASON_GP"] = season_gp
        team["SEASON_AST36"] = season_ast36
        team["SEASON_MATCH"] = season_match
        team["LAST_AST"] = last_ast
        team["L3_AST"] = l3_ast
        team["L5_AST"] = l5_ast
        team["L10_AST"] = l10_ast
        team["L3_AST36"] = l3_ast36
        team["L5_AST36"] = l5_ast36
        team["L10_AST36"] = l10_ast36
        team["L10_FORM_MINUTES"] = l10_minutes
        team["FORM_GAMES"] = form_games
        team["FORM_APPEARANCES"] = appearances
        team["AST_SD10"] = sd10s
        team["STABILIZED_AST36_FORM"] = stabilized
        team["RECENT_FORM_WEIGHT"] = recent_weight
        team["FORM_TREND"] = trend
        team["FORM_VOLATILITY"] = volatility

        status = team.get("AVAILABILITY", pd.Series("UNKNOWN", index=team.index)).astype(str).str.upper()
        proj_min = pd.to_numeric(team.get("PROJ_MIN"), errors="coerce").fillna(0.0)
        core = proj_min.ge(CORE_MINUTES) & ~status.isin(ZERO_STATUSES)
        core_count = int(core.sum())
        core_baselines = int(
            (
                pd.to_numeric(team.loc[core, "STABILIZED_AST36_FORM"], errors="coerce").notna()
                & team.loc[core, "FORM_GAMES"].astype(int).ge(MIN_FORM_GAMES)
                & (
                    pd.to_numeric(team.loc[core, "SEASON_MIN"], errors="coerce").fillna(0.0).gt(1.0)
                    | pd.to_numeric(team.loc[core, "L10_FORM_MINUTES"], errors="coerce").fillna(0.0).gt(20.0)
                )
            ).sum()
        ) if core_count else 0
        games = max([int(x) for x in team["FORM_GAMES"].tolist()] or [0])
        high_vol = int(team.loc[core, "FORM_VOLATILITY"].eq("HIGH").sum()) if core_count else 0
        team_ready = bool(games >= MIN_FORM_GAMES and core_count > 0 and core_baselines == core_count)
        team_rows.append({
            "Team": meta.get(tid, {}).get("name", str(tid)),
            "Form games": games,
            "Core players": core_count,
            "Core baselines": core_baselines,
            "High volatility": high_vol,
            "Gate": "PASS" if team_ready else "CHECK",
        })
        frames.append(team)

    form = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    team_diag = pd.DataFrame(team_rows)
    ready = bool(hdiag.get("ready") and not team_diag.empty and team_diag["Gate"].eq("PASS").all())
    reason = "" if ready else str(hdiag.get("reason") or "one or more team assist-form checks failed")
    return form, team_diag, {
        "ready": ready,
        "reason": reason,
        "history": hdiag,
        "season_diag": sdiag,
        "season_rows": len(season_pool),
        "players": len(form),
        "core_players": int(pd.to_numeric(form.get("PROJ_MIN"), errors="coerce").fillna(0.0).ge(CORE_MINUTES).sum()) if not form.empty else 0,
        "high_volatility": int(form.get("FORM_VOLATILITY", pd.Series(dtype=str)).eq("HIGH").sum()) if not form.empty else 0,
        "name_fallbacks": int(form.get("SEASON_MATCH", pd.Series(dtype=str)).eq("NAME+TEAM").sum()) if not form.empty else 0,
    }


def _render_step6(slate: dict[str, Any], day_str: str, roles: pd.DataFrame, step5_ready: bool) -> tuple[bool, pd.DataFrame]:
    st.markdown("### 📈 Step 6 — Recent + Season Assist Form")
    st.caption(
        "Season and recent assist production are measured before opportunity/tracking data or matchup adjustments. The stabilized AST/36 form rate is regression-protected descriptive evidence — it is not tonight's assist projection."
    )
    if not step5_ready:
        st.error("⛔ STEP 6 LOCKED • Step 5 has not passed, so assist-form grading cannot run.")
        return False, pd.DataFrame()

    with st.spinner("📈 Building season + L3/L5/L10 assist form with regression protection…"):
        form, team_diag, diag = _build_step6_form(slate, day_str, roles)

    ready = bool(diag.get("ready"))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Form players", int(diag.get("players") or 0))
    c2.metric("Core rotation", int(diag.get("core_players") or 0))
    c3.metric("High volatility", int(diag.get("high_volatility") or 0))
    c4.metric("Season name fallbacks", int(diag.get("name_fallbacks") or 0))

    if ready:
        st.success("✅ STEP 6 PASSED • every core rotation player has usable recent assist form plus a regression-protected season/recent rate. Short hot/cold stretches are not allowed to replace the longer baseline. No final assist projection exists yet.")
    else:
        st.warning(f"⚠️ STEP 6 CHECK • {diag.get('reason') or 'assist-form validation incomplete'}. Step 7 remains locked.")

    if team_diag is not None and not team_diag.empty:
        st.dataframe(team_diag, hide_index=True, use_container_width=True)

    if form is not None and not form.empty:
        view = form.copy()
        view["Player"] = view["PLAYER_NAME"].astype(str)
        view["Team"] = view.get("TEAM_ABBREVIATION", pd.Series("", index=view.index)).astype(str)
        view["Role"] = view.get("CREATION_ROLE", pd.Series("", index=view.index)).astype(str)
        view["Proj min"] = pd.to_numeric(view["PROJ_MIN"], errors="coerce").round(1)
        view["Season AST"] = pd.to_numeric(view["SEASON_AST"], errors="coerce").round(1)
        view["L3 AST"] = pd.to_numeric(view["L3_AST"], errors="coerce").round(1)
        view["L5 AST"] = pd.to_numeric(view["L5_AST"], errors="coerce").round(1)
        view["L10 AST"] = pd.to_numeric(view["L10_AST"], errors="coerce").round(1)
        view["Season AST/36"] = pd.to_numeric(view["SEASON_AST36"], errors="coerce").round(2)
        view["Stable AST/36 form"] = pd.to_numeric(view["STABILIZED_AST36_FORM"], errors="coerce").round(2)
        view["Recent weight"] = (pd.to_numeric(view["RECENT_FORM_WEIGHT"], errors="coerce").fillna(0.0) * 100.0).round(0).astype(int).astype(str) + "%"
        view["Trend"] = view["FORM_TREND"].astype(str)
        view["Volatility"] = view["FORM_VOLATILITY"].astype(str)
        view["Season match"] = view["SEASON_MATCH"].astype(str)
        view = view.sort_values(["TEAM_ID_NUM", "CREATION_RANK", "PROJ_MIN"], ascending=[True, True, False])
        st.dataframe(
            view[["Player", "Team", "Role", "Proj min", "Season AST", "L3 AST", "L5 AST", "L10 AST", "Season AST/36", "Stable AST/36 form", "Recent weight", "Trend", "Volatility", "Season match"]],
            hide_index=True,
            use_container_width=True,
        )
        if ready:
            st.session_state[f"wnba_assists_v6_form::{day_str}"] = form.copy()

    hist = diag.get("history") or {}
    with st.expander("📊 Step-6 form methodology / diagnostics", expanded=False):
        st.write("• Season baseline is the existing verified selected-player season table, intersected back to the Step-5 current roster.")
        st.write("• Season identity: exact player ID + team first; exact normalized player name + same team is the only fallback.")
        st.write("• Recent form: completed team games only; current-roster player absent from a verified box score counts as 0 assists/minutes for that game.")
        st.write("• Recent windows displayed: L3, L5 and L10 assists per game plus AST/36.")
        st.write("• Regression protection: recency-weighted AST/36 is shrunk toward season AST/36 according to actual L10 minute exposure; recent weight is capped at 62%.")
        st.write("• Trend is descriptive recent AST/36 versus season AST/36, not a forecast multiplier.")
        st.write("• Volatility is based on the last-10 game-level assist standard deviation / relative dispersion.")
        st.write("• Potential assists / passes / touches used: 0 — Step 7 remains responsible for opportunity data.")
        st.write("• Teammate shot conversion used: 0")
        st.write("• Opponent matchup used: 0")
        st.write("• Sportsbook lines used: 0")
        st.write("• Monte Carlo runs: 0")
        st.write(f"• Historical summary requests: {hist.get('requested_summaries', 0)}")
        st.write(f"• Usable unique summaries: {hist.get('unique_summaries', 0)}")
        st.write(f"• Season-form source state: {(diag.get('season_diag') or {}).get('state', 'unknown')}")

    return ready, form


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
          <div class="ks-ast-kicker">KYRE SPORTS AI • WNBA ASSISTS INTELLIGENCE • STEP 6</div>
          <div class="ks-ast-title">🎯 WNBA Assists Command Center</div>
          <div class="ks-ast-sub">Steps 1–5 remain intact. Step 6 adds season and L3/L5/L10 assist form with explicit regression protection. Opportunity tracking, teammate conversion, matchup, sportsbook lines and simulations remain locked.</div>
          <span class="ks-ast-chip">📅 ET slate {slate_day}</span>
          <span class="ks-ast-chip">✅ Steps 1–5 preserved</span>
          <span class="ks-ast-chip">📈 assist form only</span>
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
    step6_ready, _ = _render_step6(slate, slate_day, roles, step5_ready)

    if st.button("🔄 RECHECK ASSISTS STEPS 2–6", use_container_width=True, key="assists_step6_recheck"):
        step3.schedule.load_verified_wnba_slate.clear()
        step3._current_rosters.clear()
        step3._injury_feed.clear()
        step4._season_schedule.clear()
        step4._rotation_history.clear()
        step5._creation_history.clear()
        step5._official_usage_table.clear()
        _recent_assist_history.clear()
        _season_form_pool.clear()
        try:
            players._espn_roster.clear()
            players._espn_season_schedule.clear()
            players._espn_game_summary.clear()
            players._build_selected_player_pool.clear()
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
        (6, "Recent + season assist form", "✅ LIVE" if step6_ready else ("⚠️ CHECK" if step5_ready else "🔒 LOCKED"), "Season + L3/L5/L10 • regression protected"),
        (7, "Potential assists / passes / creation chances", "➡️ NEXT" if step6_ready else "🔒 LOCKED", "Opportunity layer before conversion"),
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
        f"⚡ WNBA Assists V6 Step 6 • Step 2 {verification or 'CHECK'} • Step 3 {'PASS' if step3_ready else 'LOCKED'} • Step 4 {'PASS' if step4_ready else 'CHECK'} • Step 5 {'PASS' if step5_ready else 'CHECK'} • Step 6 {'PASS' if step6_ready else 'CHECK'} • no opportunity/market/Monte Carlo yet"
    )


__all__ = ["MODEL_VERSION", "render_wnba_assists_hub"]
