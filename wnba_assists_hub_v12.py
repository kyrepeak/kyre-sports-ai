"""WNBA Assists V12 — Step 12 player vs opponent assist history.

Preserves Assists Steps 1–11 and adds only descriptive, exact-opponent H2H
assist context. H2H never changes an assist projection in this step.

Step 12 rules:
- Step 11 must pass first;
- exact opponent comes only from the verified Step-2 matchup;
- use current ESPN player IDs already verified through the current roster;
- inspect the exact opponent's completed WNBA games and find current players by
  exact ESPN player ID, regardless of the historical team they played for;
- show current-season and recent two-season assist/minute history separately;
- measure H2H AST/game, minutes/game, AST/36, recent-L3 H2H AST and current-team
  continuity;
- explicitly label no/tiny/small samples and keep them descriptive only;
- zero H2H games is valid evidence (NO HISTORY), not a fabricated zero baseline;
- Step 13 may unlock when identity/opponent mapping is auditable even if a player
  has never faced that opponent.

No sportsbook line, no-vig math, final assist projection, fair odds, EV or
Monte Carlo is enabled here.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

import wnba_assists_hub_v11 as step11

step3 = step11.step3
step4 = step11.step4
step5 = step11.step5
step6 = step11.step6
step7 = step11.step7
step8 = step11.step8
step9 = step11.step9
step10 = step11.step10
players = step11.players

MODEL_VERSION = "WNBA ASSISTS V12 • STEP 12 PLAYER VS OPPONENT ASSIST HISTORY"
_ET = ZoneInfo("America/New_York")
CORE_MINUTES = 10.0
CURRENT_OPPONENT_GAME_CAP = 26
PRIOR_OPPONENT_GAME_CAP = 12


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


def _sample_label(games: int) -> str:
    n = int(games or 0)
    if n <= 0:
        return "NO HISTORY"
    if n <= 2:
        return "TINY SAMPLE"
    if n <= 4:
        return "SMALL SAMPLE"
    if n <= 7:
        return "MODERATE SAMPLE"
    return "LARGER SAMPLE"


def _completed_opponent_games(schedule: pd.DataFrame, opponent_id: int, cutoff: str, cap: int) -> pd.DataFrame:
    if schedule is None or schedule.empty:
        return pd.DataFrame()
    frame = schedule.copy()
    dates = pd.to_datetime(frame.get("game_date"), errors="coerce")
    cutoff_ts = pd.to_datetime(cutoff)
    final = frame.get("status", pd.Series("", index=frame.index)).astype(str).str.upper().eq("FINAL")
    away = pd.to_numeric(frame.get("away_team_id"), errors="coerce").fillna(0).astype(int).eq(int(opponent_id))
    home = pd.to_numeric(frame.get("home_team_id"), errors="coerce").fillna(0).astype(int).eq(int(opponent_id))
    out = frame.loc[final & (away | home) & dates.lt(cutoff_ts)].copy()
    if out.empty:
        return out
    out["_date"] = dates.loc[out.index]
    return out.sort_values("_date", ascending=False).drop_duplicates("game_id").head(int(cap))


@st.cache_data(ttl=1800, show_spinner=False, max_entries=8)
def _h2h_game_pool(day_str: str, opponent_ids: tuple[int, ...]):
    year = int(pd.to_datetime(day_str).year)
    current = step4._season_schedule(year)
    prior = step4._season_schedule(year - 1)

    jobs: dict[str, str] = {}
    game_meta: dict[str, dict[str, Any]] = {}
    counts: dict[int, dict[str, int]] = {}

    for oid in opponent_ids:
        cur_games = _completed_opponent_games(current, int(oid), day_str, CURRENT_OPPONENT_GAME_CAP)
        prior_cutoff = f"{year}-01-01"
        prior_games = _completed_opponent_games(prior, int(oid), prior_cutoff, PRIOR_OPPONENT_GAME_CAP)
        counts[int(oid)] = {"current": len(cur_games), "prior": len(prior_games)}
        for season_label, games in (("CURRENT", cur_games), ("PRIOR", prior_games)):
            for _, game in games.iterrows():
                gid = str(game.get("game_id") or "")
                gdate = str(game.get("game_date") or "")[:10]
                if not gid:
                    continue
                jobs[gid] = gdate
                game_meta[gid] = {
                    "season": season_label,
                    "game_date": gdate,
                    "away_team_id": _safe_int(game.get("away_team_id")),
                    "home_team_id": _safe_int(game.get("home_team_id")),
                    "opponent_id": int(oid),
                }

    summaries: dict[str, pd.DataFrame] = {}
    if jobs:
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

    return summaries, game_meta, {
        "requested_summaries": len(jobs),
        "usable_summaries": len(summaries),
        "opponent_schedule_counts": counts,
        "year": year,
        "prior_year": year - 1,
    }


def _player_history_from_pool(
    player_id: int,
    current_team_id: int,
    opponent_id: int,
    summaries: dict[str, pd.DataFrame],
    game_meta: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for gid, meta in game_meta.items():
        if _safe_int(meta.get("opponent_id")) != int(opponent_id):
            continue
        frame = summaries.get(gid, pd.DataFrame())
        if frame is None or frame.empty or "PLAYER_ID" not in frame.columns:
            continue
        pids = pd.to_numeric(frame["PLAYER_ID"], errors="coerce").fillna(0).astype(int)
        found = frame.loc[pids.eq(int(player_id))]
        if len(found) != 1:
            continue
        row = found.iloc[0]
        hist_team = _safe_int(row.get("TEAM_ID"))
        # The player row must be on the team opposite the exact opponent in this game.
        away = _safe_int(meta.get("away_team_id"))
        home = _safe_int(meta.get("home_team_id"))
        if int(opponent_id) not in {away, home} or hist_team == int(opponent_id):
            continue
        mins = max(0.0, _num(row.get("MIN"), 0.0))
        ast = max(0.0, _num(row.get("AST"), 0.0))
        if mins <= 0.0:
            continue
        rows.append({
            "game_id": gid,
            "game_date": str(meta.get("game_date") or ""),
            "season": str(meta.get("season") or ""),
            "team_id": hist_team,
            "min": mins,
            "ast": ast,
            "position": str(row.get("POSITION") or ""),
        })

    rows.sort(key=lambda x: x.get("game_date", ""), reverse=True)
    current_rows = [r for r in rows if r.get("season") == "CURRENT"]
    recent3 = rows[:3]
    gp = len(rows)
    cur_gp = len(current_rows)
    total_min = float(sum(r["min"] for r in rows))
    total_ast = float(sum(r["ast"] for r in rows))
    same_team_gp = sum(1 for r in rows if int(r.get("team_id") or 0) == int(current_team_id))
    hist_teams = sorted({int(r.get("team_id") or 0) for r in rows if int(r.get("team_id") or 0) > 0})

    if gp == 0:
        continuity = "NO H2H"
    elif same_team_gp == gp:
        continuity = "SAME CURRENT TEAM"
    elif same_team_gp > 0:
        continuity = "MIXED TEAM HISTORY"
    else:
        continuity = "PRIOR TEAM ONLY"

    return {
        "games": gp,
        "current_games": cur_gp,
        "ast_avg": total_ast / gp if gp else np.nan,
        "min_avg": total_min / gp if gp else np.nan,
        "ast36": (36.0 * total_ast / total_min) if total_min > 0 else np.nan,
        "current_ast_avg": (sum(r["ast"] for r in current_rows) / cur_gp) if cur_gp else np.nan,
        "last3_ast_avg": (sum(r["ast"] for r in recent3) / len(recent3)) if recent3 else np.nan,
        "last_date": rows[0]["game_date"] if rows else "—",
        "same_team_games": same_team_gp,
        "historical_team_ids": hist_teams,
        "continuity": continuity,
        "sample": _sample_label(gp),
        "rows": rows,
    }


def _build_step12_h2h(slate: dict[str, Any], day_str: str, pace_rows: pd.DataFrame):
    if pace_rows is None or pace_rows.empty:
        return pd.DataFrame(), pd.DataFrame(), {"ready": False, "reason": "no Step-11 pace rows"}

    matchup = step9._matchups(slate)
    opponent_ids = tuple(sorted({
        _safe_int(v.get("opponent_id")) for v in matchup.values()
        if _safe_int(v.get("opponent_id")) > 0
    }))
    summaries, game_meta, hdiag = _h2h_game_pool(day_str, opponent_ids)
    out = pace_rows.copy()

    out["H2H_GAMES_2Y"] = 0
    out["H2H_GAMES_CURRENT"] = 0
    out["H2H_AST_AVG_2Y"] = np.nan
    out["H2H_AST_AVG_CURRENT"] = np.nan
    out["H2H_MIN_AVG_2Y"] = np.nan
    out["H2H_AST36_2Y"] = np.nan
    out["H2H_LAST3_AST"] = np.nan
    out["H2H_LAST_DATE"] = "—"
    out["H2H_CURRENT_TEAM_GAMES"] = 0
    out["H2H_TEAM_CONTINUITY"] = "NO H2H"
    out["H2H_SAMPLE"] = "NO HISTORY"
    out["H2H_SOURCE"] = "ESPN WNBA completed game summaries • descriptive only"
    out["H2H_INFLUENCE"] = "0% — DESCRIPTIVE ONLY"

    core_total = 0
    core_identity_ok = 0
    players_with_history = 0
    player_rows: list[dict[str, Any]] = []

    for idx, row in out.iterrows():
        tid = _safe_int(row.get("TEAM_ID_NUM") or row.get("TEAM_ID"))
        pid = _safe_int(row.get("PLAYER_ID"))
        m = matchup.get(int(tid), {}) or {}
        oid = _safe_int(m.get("opponent_id"))
        is_core = _num(row.get("PROJ_MIN"), 0.0) >= CORE_MINUTES
        identity_ok = bool(tid > 0 and pid > 0 and oid > 0)
        if is_core:
            core_total += 1
            if identity_ok:
                core_identity_ok += 1

        hist = _player_history_from_pool(pid, tid, oid, summaries, game_meta) if identity_ok else {
            "games": 0, "current_games": 0, "ast_avg": np.nan, "current_ast_avg": np.nan,
            "min_avg": np.nan, "ast36": np.nan, "last3_ast_avg": np.nan, "last_date": "—",
            "same_team_games": 0, "continuity": "IDENTITY CHECK", "sample": "NO HISTORY",
        }
        if int(hist.get("games") or 0) > 0:
            players_with_history += 1

        out.at[idx, "H2H_GAMES_2Y"] = int(hist.get("games") or 0)
        out.at[idx, "H2H_GAMES_CURRENT"] = int(hist.get("current_games") or 0)
        out.at[idx, "H2H_AST_AVG_2Y"] = _num(hist.get("ast_avg"))
        out.at[idx, "H2H_AST_AVG_CURRENT"] = _num(hist.get("current_ast_avg"))
        out.at[idx, "H2H_MIN_AVG_2Y"] = _num(hist.get("min_avg"))
        out.at[idx, "H2H_AST36_2Y"] = _num(hist.get("ast36"))
        out.at[idx, "H2H_LAST3_AST"] = _num(hist.get("last3_ast_avg"))
        out.at[idx, "H2H_LAST_DATE"] = str(hist.get("last_date") or "—")
        out.at[idx, "H2H_CURRENT_TEAM_GAMES"] = int(hist.get("same_team_games") or 0)
        out.at[idx, "H2H_TEAM_CONTINUITY"] = str(hist.get("continuity") or "NO H2H")
        out.at[idx, "H2H_SAMPLE"] = str(hist.get("sample") or "NO HISTORY")

        if is_core:
            player_rows.append({
                "Player": str(row.get("PLAYER_NAME") or ""),
                "Team": str(row.get("TEAM_ABBREVIATION") or row.get("TEAM_NAME") or ""),
                "Opponent": str(m.get("opponent") or row.get("OPPONENT") or ""),
                "Creator role": str(row.get("CREATION_ROLE") or ""),
                "Proj min": round(_num(row.get("PROJ_MIN"), 0.0), 1),
                "2026 H2H GP": int(hist.get("current_games") or 0),
                "2Y H2H GP": int(hist.get("games") or 0),
                "H2H AST": round(_num(hist.get("ast_avg")), 2) if np.isfinite(_num(hist.get("ast_avg"))) else np.nan,
                "H2H AST/36": round(_num(hist.get("ast36")), 2) if np.isfinite(_num(hist.get("ast36"))) else np.nan,
                "H2H Min": round(_num(hist.get("min_avg")), 1) if np.isfinite(_num(hist.get("min_avg"))) else np.nan,
                "Recent H2H L3 AST": round(_num(hist.get("last3_ast_avg")), 2) if np.isfinite(_num(hist.get("last3_ast_avg"))) else np.nan,
                "Last H2H": str(hist.get("last_date") or "—"),
                "Team continuity": str(hist.get("continuity") or "NO H2H"),
                "Sample": str(hist.get("sample") or "NO HISTORY"),
                "Influence": "0% descriptive",
                "Identity": "PASS" if identity_ok else "CHECK",
            })

    ready = bool(core_total > 0 and core_identity_ok == core_total)
    return out, pd.DataFrame(player_rows), {
        "ready": ready,
        "reason": "" if ready else "one or more core players lack exact current player/team/opponent identity",
        "core_players": core_total,
        "core_identity_ok": core_identity_ok,
        "players_with_history": players_with_history,
        "requested_summaries": int(hdiag.get("requested_summaries") or 0),
        "usable_summaries": int(hdiag.get("usable_summaries") or 0),
        "year": hdiag.get("year"),
        "prior_year": hdiag.get("prior_year"),
        "opponent_schedule_counts": hdiag.get("opponent_schedule_counts", {}),
    }


def _render_step12(slate: dict[str, Any], day_str: str, pace_rows: pd.DataFrame, step11_ready: bool):
    st.markdown("### 🧾 Step 12 — Player vs Opponent Assist History")
    st.caption(
        "Descriptive H2H only. Exact current player IDs are checked against completed games involving the exact verified opponent. Small samples are labeled explicitly, and H2H has 0% influence on the eventual projection at this step."
    )
    if not step11_ready:
        st.error("⛔ STEP 12 LOCKED • Step 11 has not passed, so H2H context cannot run.")
        return False, pd.DataFrame()

    with st.spinner("🧾 Building exact-opponent player assist history…"):
        h2h_rows, view, diag = _build_step12_h2h(slate, day_str, pace_rows)

    ready = bool(diag.get("ready"))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Core rotation", int(diag.get("core_players") or 0))
    c2.metric("Identity verified", f"{int(diag.get('core_identity_ok') or 0)}/{int(diag.get('core_players') or 0)}")
    c3.metric("Players w/ H2H", int(diag.get("players_with_history") or 0))
    c4.metric("H2H projection weight", "0%")

    if ready:
        st.success("✅ STEP 12 PASSED • every core player has exact player/team/opponent identity. Available current/recent opponent history is displayed with explicit sample warnings; no H2H value is applied to a projection.")
    else:
        st.warning(f"⚠️ STEP 12 CHECK • {diag.get('reason') or 'H2H identity verification incomplete'}. Step 13 remains locked.")

    if view is not None and not view.empty:
        st.dataframe(view, hide_index=True, use_container_width=True)

    if h2h_rows is not None and not h2h_rows.empty and ready:
        st.session_state[f"wnba_assists_v12_h2h::{day_str}"] = h2h_rows.copy()

    with st.expander("🧪 Step-12 H2H methodology / diagnostics", expanded=False):
        st.write("• Exact opponent comes only from the verified same-day Step-2 matchup.")
        st.write("• Exact current player identity comes from the verified Step-3 roster carried through Steps 4–11.")
        st.write("• H2H rows are located by exact ESPN player ID inside completed opponent game summaries; fuzzy name matching is not used.")
        st.write("• Current-season opponent history and a limited previous-season lookback are shown as descriptive context.")
        st.write("• Historical team is recorded so traded/moved players are labeled PRIOR TEAM ONLY or MIXED TEAM HISTORY instead of silently treated as same-role samples.")
        st.write("• Zero H2H games = NO HISTORY. It is not converted into zero assists and does not block Step 13.")
        st.write("• Tiny/small samples are labeled and carry 0% projection influence in this step.")
        st.write("• Sportsbook lines used: 0")
        st.write("• Final assist projection created: NO")
        st.write("• Monte Carlo runs: 0")
        st.write(f"• H2H summary requests: {diag.get('requested_summaries', 0)}")
        st.write(f"• Usable H2H summaries: {diag.get('usable_summaries', 0)}")
        st.write(f"• Opponent schedule pool: {diag.get('opponent_schedule_counts', {})}")

    return ready, h2h_rows


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
          <div class="ks-ast-kicker">KYRE SPORTS AI • WNBA ASSISTS INTELLIGENCE • STEP 12</div>
          <div class="ks-ast-title">🎯 WNBA Assists Command Center</div>
          <div class="ks-ast-sub">Steps 1–11 remain intact. Step 12 adds only exact player-vs-opponent assist history with small-sample and team-continuity warnings. Sportsbook lines, no-vig math, final projection and simulations remain locked.</div>
          <span class="ks-ast-chip">📅 ET slate {slate_day}</span>
          <span class="ks-ast-chip">✅ Steps 1–11 preserved</span>
          <span class="ks-ast-chip">🧾 descriptive H2H</span>
          <span class="ks-ast-chip">🚫 H2H weight 0%</span>
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
    step11_ready, pace_rows = step11._render_step11(slate, slate_day, position_rows, step10_ready)
    step12_ready, _ = _render_step12(slate, slate_day, pace_rows, step11_ready)

    if st.button("🔄 RECHECK ASSISTS STEPS 2–12", use_container_width=True, key="assists_step12_recheck"):
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
            step11._pace_history,
            step11._raw_team_possessions,
            _h2h_game_pool,
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
        (11, "Pace + expected possession volume", "✅ LIVE" if step11_ready else "⚠️ CHECK", "Season + L10/L5/L3 possession environment"),
        (12, "Player vs opponent assist history", "✅ LIVE" if step12_ready else ("⚠️ CHECK" if step11_ready else "🔒 LOCKED"), "Exact-ID descriptive H2H • 0% projection influence"),
        (13, "Exact SportsGameOdds assist lines", "➡️ NEXT" if step12_ready else "🔒 LOCKED", "Exact book / line / side only"),
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
        f"⚡ WNBA Assists V12 Step 12 • Step 2 {verification or 'CHECK'} • Step 3 {'PASS' if step3_ready else 'CHECK'} • Step 4 {'PASS' if step4_ready else 'CHECK'} • Step 5 {'PASS' if step5_ready else 'CHECK'} • Step 6 {'PASS' if step6_ready else 'CHECK'} • Step 7 {'PASS' if step7_ready else 'CHECK'} • Step 8 {'PASS' if step8_ready else 'CHECK'} • Step 9 {'PASS' if step9_ready else 'CHECK'} • Step 10 {'PASS' if step10_ready else 'CHECK'} • Step 11 {'PASS' if step11_ready else 'CHECK'} • Step 12 {'PASS' if step12_ready else 'CHECK'} • no sportsbook/projection/market/Monte Carlo yet"
    )


__all__ = ["MODEL_VERSION", "render_wnba_assists_hub"]
