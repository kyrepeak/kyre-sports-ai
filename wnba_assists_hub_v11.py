"""WNBA Assists V11 — Step 11 pace + expected possession volume.

Preserves Assists Steps 1–10 and adds only pre-projection possession context.

Step 11 rules:
- Step 10 must pass first;
- exact matchup comes only from the verified Step-2 slate;
- derive team game possessions from completed ESPN WNBA box scores using
  FGA - OREB + TOV + 0.44 * FTA, then average both teams' estimates per game;
- keep Season/L10/L5/L3 pace windows separate;
- regression-protect recent pace toward the season baseline;
- calculate expected matchup possessions from both exact teams' stable pace;
- expose possessions above/below each player's team baseline and a bounded
  pace opportunity factor as context only;
- do not convert the pace factor into a final assist projection here.

No player-vs-opponent H2H, sportsbook line, final assist projection, fair odds,
market grading or Monte Carlo is enabled by this step.
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
import wnba_assists_hub_v10 as step10
import wnba_players_v25 as players

MODEL_VERSION = "WNBA ASSISTS V11 • STEP 11 PACE + EXPECTED POSSESSION VOLUME"
_ET = ZoneInfo("America/New_York")
MIN_SEASON_GAMES = 10
PACE_FACTOR_MIN = 0.90
PACE_FACTOR_MAX = 1.10


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


def _pair(value: Any) -> tuple[float, float]:
    text = str(value or "").strip().replace("–", "-").replace("—", "-")
    if "-" not in text:
        return np.nan, np.nan
    a, b = text.split("-", 1)
    try:
        return float(a), float(b)
    except Exception:
        return np.nan, np.nan


def _stat_pair(stats: dict[str, Any], kind: str) -> tuple[float, float]:
    target = str(kind or "").upper()
    for key, value in (stats or {}).items():
        k = str(key or "").upper().replace(" ", "")
        if target == "FG" and (k == "FG" or "FIELDGOAL" in k):
            made, att = _pair(value)
            if np.isfinite(made) and np.isfinite(att):
                return made, att
        if target == "FT" and (k == "FT" or "FREETHROW" in k):
            made, att = _pair(value)
            if np.isfinite(made) and np.isfinite(att):
                return made, att

    if target == "FG":
        made = players._pick_stat(stats, ["FGM", "FIELDGOALSMADE"], np.nan)
        att = players._pick_stat(stats, ["FGA", "FIELDGOALSATTEMPTED"], np.nan)
    else:
        made = players._pick_stat(stats, ["FTM", "FREETHROWSMADE"], np.nan)
        att = players._pick_stat(stats, ["FTA", "FREETHROWSATTEMPTED"], np.nan)
    return _num(made), _num(att)


@st.cache_data(ttl=1800, show_spinner=False, max_entries=256)
def _raw_team_possessions(game_id: str, game_date: str = "") -> pd.DataFrame:
    """Return one possession-estimate row per team from a completed ESPN box score."""
    try:
        payload, _ = players.schedule_v24._request_json(
            "ESPN WNBA assists pace summary",
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
        totals = {"FGA": 0.0, "FTA": 0.0, "OREB": 0.0, "TOV": 0.0, "MIN": 0.0}
        found = 0
        for group in team_block.get("statistics", []) or []:
            athletes = group.get("athletes") or []
            if not athletes:
                continue
            for item in athletes:
                if bool(item.get("didNotPlay")):
                    continue
                stats = players._summary_stat_map(group, item)
                mins = players._minutes(players._pick_stat(stats, ["MIN", "MINUTES"], np.nan))
                _, fga = _stat_pair(stats, "FG")
                _, fta = _stat_pair(stats, "FT")
                oreb = _num(players._pick_stat(stats, ["OREB", "ORB", "OFFENSIVEREBOUNDS", "OFFENSIVEREBOUNDSTOTAL"], np.nan))
                tov = _num(players._pick_stat(stats, ["TO", "TOV", "TURNOVERS"], np.nan))
                if not np.isfinite(fga):
                    continue
                totals["FGA"] += max(0.0, _num(fga, 0.0))
                totals["FTA"] += max(0.0, _num(fta, 0.0))
                totals["OREB"] += max(0.0, _num(oreb, 0.0))
                totals["TOV"] += max(0.0, _num(tov, 0.0))
                totals["MIN"] += max(0.0, _num(mins, 0.0))
                found += 1
            if athletes:
                break
        poss = totals["FGA"] - totals["OREB"] + totals["TOV"] + 0.44 * totals["FTA"]
        # Conservative integrity bounds for a regulation/overtime WNBA box score.
        if found < 5 or totals["FGA"] < 40 or not (55.0 <= poss <= 125.0):
            continue
        rows.append({
            "GAME_ID": str(game_id),
            "GAME_DATE": str(game_date or ""),
            "TEAM_ID": tid,
            "TEAM_NAME": str(team.get("displayName") or team.get("shortDisplayName") or team.get("name") or ""),
            "FGA": totals["FGA"],
            "FTA": totals["FTA"],
            "OREB": totals["OREB"],
            "TOV": totals["TOV"],
            "RAW_POSS": poss,
        })

    frame = pd.DataFrame(rows)
    if len(frame) != 2:
        return pd.DataFrame()
    game_poss = float(pd.to_numeric(frame["RAW_POSS"], errors="coerce").mean())
    if not np.isfinite(game_poss) or not (55.0 <= game_poss <= 125.0):
        return pd.DataFrame()
    frame["GAME_POSS"] = game_poss
    return frame.reset_index(drop=True)


def _window(records: list[float], k: int | None = None) -> dict[str, float]:
    use = records if k is None else records[: min(int(k), len(records))]
    vals = [float(x) for x in use if np.isfinite(x)]
    if not vals:
        return {"games": 0, "pace": np.nan, "sd": np.nan}
    return {
        "games": len(vals),
        "pace": float(np.mean(vals)),
        "sd": float(np.std(vals, ddof=1)) if len(vals) >= 2 else 0.0,
    }


def _blend(values: list[tuple[float, float]]) -> float:
    use = [(float(v), float(w)) for v, w in values if np.isfinite(v)]
    den = sum(w for _, w in use)
    return float(sum(v * w for v, w in use) / den) if den > 0 else np.nan


def _pace_trend(recent: float, season: float) -> str:
    if not np.isfinite(recent) or not np.isfinite(season):
        return "UNKNOWN"
    diff = recent - season
    if diff >= 2.0:
        return "FASTER RECENTLY"
    if diff <= -2.0:
        return "SLOWER RECENTLY"
    return "STABLE"


@st.cache_data(ttl=1800, show_spinner=False, max_entries=8)
def _pace_history(day_str: str, team_ids: tuple[int, ...]):
    season = step4._season_schedule(pd.to_datetime(day_str).year)
    if season is None or season.empty:
        return {}, {"ready": False, "reason": "season schedule unavailable", "team_games": {}}

    games_by_team: dict[int, list[dict[str, str]]] = {}
    jobs: dict[str, str] = {}
    for tid in team_ids:
        games = step9._all_completed_team_games(season, day_str, int(tid))
        rows: list[dict[str, str]] = []
        for _, game in games.iterrows():
            gid = str(game.get("game_id") or "")
            gdate = str(game.get("game_date") or "")[:10]
            if gid:
                rows.append({"game_id": gid, "game_date": gdate})
                jobs[gid] = gdate
        games_by_team[int(tid)] = rows

    summaries: dict[str, pd.DataFrame] = {}
    if jobs:
        with ThreadPoolExecutor(max_workers=min(16, max(1, len(jobs)))) as pool:
            futures = {pool.submit(_raw_team_possessions, gid, gdate): gid for gid, gdate in jobs.items()}
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
    for tid in team_ids:
        records: list[float] = []
        for game in games_by_team.get(int(tid), []):
            frame = summaries.get(game["game_id"], pd.DataFrame())
            if frame.empty:
                continue
            team_row = frame.loc[pd.to_numeric(frame["TEAM_ID"], errors="coerce").fillna(0).astype(int).eq(int(tid))]
            if len(team_row) != 1:
                continue
            poss = _num(team_row.iloc[0].get("GAME_POSS"))
            if np.isfinite(poss):
                records.append(poss)

        counts[int(tid)] = len(records)
        season_w = _window(records, None)
        l10 = _window(records, 10)
        l5 = _window(records, 5)
        l3 = _window(records, 3)
        stable = _blend([
            (season_w["pace"], .55),
            (l10["pace"], .25),
            (l5["pace"], .12),
            (l3["pace"], .08),
        ])
        recent = _blend([(l10["pace"], .50), (l5["pace"], .30), (l3["pace"], .20)])
        history[int(tid)] = {
            "season": season_w,
            "l10": l10,
            "l5": l5,
            "l3": l3,
            "stable": stable,
            "recent": recent,
            "trend": _pace_trend(recent, season_w["pace"]),
            "source": "ESPN WNBA completed box scores • possession estimate",
        }

    ready = bool(counts and all(counts.get(int(tid), 0) >= MIN_SEASON_GAMES for tid in team_ids))
    return history, {
        "ready": ready,
        "reason": "" if ready else "one or more slate teams have fewer than 10 auditable possession-estimate games",
        "team_games": counts,
        "requested_summaries": len(jobs),
        "usable_summaries": len(summaries),
    }


def _build_step11_pace(slate: dict[str, Any], day_str: str, matchup_rows: pd.DataFrame):
    if matchup_rows is None or matchup_rows.empty:
        return pd.DataFrame(), pd.DataFrame(), {"ready": False, "reason": "no Step-10 matchup rows"}

    matchup = step9._matchups(slate)
    team_ids = tuple(sorted(matchup))
    history, hdiag = _pace_history(day_str, team_ids)
    out = matchup_rows.copy()

    for col in (
        "TEAM_PACE_SEASON", "TEAM_PACE_L10", "TEAM_PACE_L5", "TEAM_PACE_L3", "TEAM_PACE_STABLE",
        "OPP_PACE_SEASON", "OPP_PACE_L10", "OPP_PACE_L5", "OPP_PACE_L3", "OPP_PACE_STABLE",
        "EXPECTED_MATCHUP_POSS", "POSS_VS_TEAM_BASELINE", "PACE_OPPORTUNITY_FACTOR",
    ):
        out[col] = np.nan
    out["TEAM_PACE_TREND"] = "UNKNOWN"
    out["OPP_PACE_TREND"] = "UNKNOWN"
    out["PACE_SOURCE"] = ""

    meta = step3._team_meta(slate)
    team_diag: list[dict[str, Any]] = []
    all_ready = True

    for tid in team_ids:
        m = matchup.get(int(tid), {}) or {}
        oid = _safe_int(m.get("opponent_id"))
        team_h = history.get(int(tid), {}) or {}
        opp_h = history.get(int(oid), {}) or {}
        ts = team_h.get("season", {}) or {}
        tl10 = team_h.get("l10", {}) or {}
        tl5 = team_h.get("l5", {}) or {}
        tl3 = team_h.get("l3", {}) or {}
        os = opp_h.get("season", {}) or {}
        ol10 = opp_h.get("l10", {}) or {}
        ol5 = opp_h.get("l5", {}) or {}
        ol3 = opp_h.get("l3", {}) or {}

        team_stable = _num(team_h.get("stable"))
        opp_stable = _num(opp_h.get("stable"))
        expected = _blend([(team_stable, .50), (opp_stable, .50)])
        delta = expected - team_stable if np.isfinite(expected) and np.isfinite(team_stable) else np.nan
        raw_factor = expected / team_stable if np.isfinite(expected) and np.isfinite(team_stable) and team_stable > 0 else np.nan
        pace_factor = float(np.clip(raw_factor, PACE_FACTOR_MIN, PACE_FACTOR_MAX)) if np.isfinite(raw_factor) else np.nan

        team_ready = bool(
            oid > 0
            and _safe_int(ts.get("games")) >= MIN_SEASON_GAMES
            and _safe_int(os.get("games")) >= MIN_SEASON_GAMES
            and all(np.isfinite(x) for x in (team_stable, opp_stable, expected, delta, pace_factor))
        )
        all_ready = all_ready and team_ready

        mask = pd.to_numeric(out.get("TEAM_ID_NUM"), errors="coerce").fillna(0).astype(int).eq(int(tid))
        out.loc[mask, "TEAM_PACE_SEASON"] = _num(ts.get("pace"))
        out.loc[mask, "TEAM_PACE_L10"] = _num(tl10.get("pace"))
        out.loc[mask, "TEAM_PACE_L5"] = _num(tl5.get("pace"))
        out.loc[mask, "TEAM_PACE_L3"] = _num(tl3.get("pace"))
        out.loc[mask, "TEAM_PACE_STABLE"] = team_stable
        out.loc[mask, "OPP_PACE_SEASON"] = _num(os.get("pace"))
        out.loc[mask, "OPP_PACE_L10"] = _num(ol10.get("pace"))
        out.loc[mask, "OPP_PACE_L5"] = _num(ol5.get("pace"))
        out.loc[mask, "OPP_PACE_L3"] = _num(ol3.get("pace"))
        out.loc[mask, "OPP_PACE_STABLE"] = opp_stable
        out.loc[mask, "EXPECTED_MATCHUP_POSS"] = expected
        out.loc[mask, "POSS_VS_TEAM_BASELINE"] = delta
        out.loc[mask, "PACE_OPPORTUNITY_FACTOR"] = pace_factor
        out.loc[mask, "TEAM_PACE_TREND"] = str(team_h.get("trend") or "UNKNOWN")
        out.loc[mask, "OPP_PACE_TREND"] = str(opp_h.get("trend") or "UNKNOWN")
        out.loc[mask, "PACE_SOURCE"] = "ESPN WNBA box scores • FGA-OREB+TOV+0.44*FTA"

        team_diag.append({
            "Team": meta.get(int(tid), {}).get("name", str(tid)),
            "Opponent": str(m.get("opponent") or ""),
            "Season games": _safe_int(ts.get("games")),
            "Season pace": round(_num(ts.get("pace")), 1) if np.isfinite(_num(ts.get("pace"))) else np.nan,
            "L10": round(_num(tl10.get("pace")), 1) if np.isfinite(_num(tl10.get("pace"))) else np.nan,
            "L5": round(_num(tl5.get("pace")), 1) if np.isfinite(_num(tl5.get("pace"))) else np.nan,
            "L3": round(_num(tl3.get("pace")), 1) if np.isfinite(_num(tl3.get("pace"))) else np.nan,
            "Stable pace": round(team_stable, 1) if np.isfinite(team_stable) else np.nan,
            "Opponent stable": round(opp_stable, 1) if np.isfinite(opp_stable) else np.nan,
            "Expected possessions": round(expected, 1) if np.isfinite(expected) else np.nan,
            "Vs own baseline": round(delta, 1) if np.isfinite(delta) else np.nan,
            "Pace factor": round(pace_factor, 3) if np.isfinite(pace_factor) else np.nan,
            "Trend": str(team_h.get("trend") or "UNKNOWN"),
            "Gate": "PASS" if team_ready else "CHECK",
        })

    diag_frame = pd.DataFrame(team_diag)
    ready = bool(
        hdiag.get("ready") and all_ready and len(team_diag) == len(team_ids) and len(team_ids) > 0
    )
    return out, diag_frame, {
        "ready": ready,
        "reason": "" if ready else str(hdiag.get("reason") or "one or more exact matchup pace checks failed"),
        "history": hdiag,
        "teams": len(team_diag),
        "mode": "ESPN BOX-SCORE POSSESSION ESTIMATE",
    }


def _render_step11(slate: dict[str, Any], day_str: str, matchup_rows: pd.DataFrame, step10_ready: bool):
    st.markdown("### ⏱️ Step 11 — Pace + Expected Possession Volume")
    st.caption(
        "Possession-opportunity context only. Season/L10/L5/L3 pace are reconstructed from completed box scores, then recent pace is regressed toward season. Expected matchup possessions use both exact teams. The resulting pace factor is not yet multiplied into a final assist projection."
    )
    if not step10_ready:
        st.error("⛔ STEP 11 LOCKED • Step 10 has not passed, so possession context cannot run.")
        return False, pd.DataFrame()

    with st.spinner("⏱️ Building season + recent possession environment…"):
        pace_rows, team_diag, diag = _build_step11_pace(slate, day_str, matchup_rows)

    ready = bool(diag.get("ready"))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Matchup teams", int(diag.get("teams") or 0))
    c2.metric("Pace mode", "BOX-SCORE EST.")
    c3.metric("H2H", "STEP 12")
    c4.metric("Monte Carlo", "0")

    if ready:
        st.success("✅ STEP 11 PASSED • every exact slate team has season + L10/L5/L3 possession context and an auditable expected matchup possession estimate. The pace factor remains context only; no final assist projection has been created.")
    else:
        st.warning(f"⚠️ STEP 11 CHECK • {diag.get('reason') or 'pace verification incomplete'}. Step 12 remains locked.")

    if team_diag is not None and not team_diag.empty:
        st.dataframe(team_diag, hide_index=True, use_container_width=True)

    if pace_rows is not None and not pace_rows.empty and ready:
        st.session_state[f"wnba_assists_v11_pace::{day_str}"] = pace_rows.copy()

    hist = diag.get("history") or {}
    with st.expander("🧪 Step-11 pace methodology / diagnostics", expanded=False):
        st.write("• Exact teams/opponents come only from the verified Step-2 matchup.")
        st.write("• Game possessions are estimated from completed ESPN WNBA box scores: FGA - offensive rebounds + turnovers + 0.44 × FTA.")
        st.write("• Both teams' possession estimates are averaged for the game so one team's bookkeeping does not define the entire pace.")
        st.write("• Windows shown separately: Season, L10, L5 and L3.")
        st.write("• Stable pace: 55% season + 25% L10 + 12% L5 + 8% L3.")
        st.write("• Expected matchup possessions: 50% team stable pace + 50% exact-opponent stable pace.")
        st.write(f"• Context-only pace factor is bounded to {PACE_FACTOR_MIN:.2f}–{PACE_FACTOR_MAX:.2f}; it is NOT a final assist multiplier yet.")
        st.write("• H2H adjustment used: 0 — reserved for Step 12.")
        st.write("• Sportsbook lines used: 0")
        st.write("• Final assist projection created: NO")
        st.write("• Monte Carlo runs: 0")
        st.write(f"• Pace summary requests: {hist.get('requested_summaries', 0)}")
        st.write(f"• Usable possession summaries: {hist.get('usable_summaries', 0)}")

    return ready, pace_rows


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
          <div class="ks-ast-kicker">KYRE SPORTS AI • WNBA ASSISTS INTELLIGENCE • STEP 11</div>
          <div class="ks-ast-title">🎯 WNBA Assists Command Center</div>
          <div class="ks-ast-sub">Steps 1–10 remain intact. Step 11 adds only pace and expected possession volume from the exact verified matchup. H2H, sportsbook lines, final projection and simulations remain locked.</div>
          <span class="ks-ast-chip">📅 ET slate {slate_day}</span>
          <span class="ks-ast-chip">✅ Steps 1–10 preserved</span>
          <span class="ks-ast-chip">⏱️ expected possessions</span>
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
    step10_ready, position_rows = step10._render_step10(slate, slate_day, environment, step9_ready)
    step11_ready, _ = _render_step11(slate, slate_day, position_rows, step10_ready)

    if st.button("🔄 RECHECK ASSISTS STEPS 2–11", use_container_width=True, key="assists_step11_recheck"):
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
            step10._position_history,
            _pace_history,
            _raw_team_possessions,
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
        (10, "Position matchup — Guard / Wing / Big", "✅ LIVE" if step10_ready else "⚠️ CHECK", "Exact-opponent position-tagged AST/40 context"),
        (11, "Pace + expected possession volume", "✅ LIVE" if step11_ready else ("⚠️ CHECK" if step10_ready else "🔒 LOCKED"), "Season + L10/L5/L3 possession environment"),
        (12, "Player vs opponent assist history", "➡️ NEXT" if step11_ready else "🔒 LOCKED", "Descriptive H2H context"),
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
        f"⚡ WNBA Assists V11 Step 11 • Step 2 {verification or 'CHECK'} • Step 3 {'PASS' if step3_ready else 'CHECK'} • Step 4 {'PASS' if step4_ready else 'CHECK'} • Step 5 {'PASS' if step5_ready else 'CHECK'} • Step 6 {'PASS' if step6_ready else 'CHECK'} • Step 7 {'PASS' if step7_ready else 'CHECK'} • Step 8 {'PASS' if step8_ready else 'CHECK'} • Step 9 {'PASS' if step9_ready else 'CHECK'} • Step 10 {'PASS' if step10_ready else 'CHECK'} • Step 11 {'PASS' if step11_ready else 'CHECK'} • no H2H/projection/market/Monte Carlo yet"
    )


__all__ = ["MODEL_VERSION", "render_wnba_assists_hub"]
