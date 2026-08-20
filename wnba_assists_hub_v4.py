"""WNBA Assists V4 — Step 4 rotation-aware projected minutes.

Preserves Assists Steps 1-3 and adds only playing-time / rotation modeling.

Step 4 rules:
- runs only after the Step-3 current-roster + same-day status gate passes;
- reconstructs each slate team's last 10 completed WNBA rotations before the slate;
- uses verified ESPN WNBA game summaries, cached and fetched concurrently;
- a current-roster player missing from a verified team box score counts as 0 minutes;
- blends L3/L5/L10 rotation minutes 50% / 30% / 20%;
- OUT / INACTIVE / DOUBTFUL players receive 0 projected minutes;
- QUESTIONABLE / PROBABLE players keep the neutral minutes estimate but remain risk flagged;
- regulation projections are normalized to exactly 200 team minutes with a 40-minute cap;
- Step 5 remains locked unless every slate team has usable history and a valid 200-minute allocation.

No assist role/usage, assist-rate projection, sportsbook line, market grading or Monte Carlo is enabled here.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

import wnba_assists_hub_v3 as base
import wnba_players_v25 as players

MODEL_VERSION = "WNBA ASSISTS V4 • STEP 4 ROTATION-AWARE PROJECTED MINUTES"
_ET = ZoneInfo("America/New_York")
ZERO_MIN_STATUSES = {"OUT", "INACTIVE", "DOUBTFUL"}
RISK_STATUSES = {"QUESTIONABLE", "PROBABLE", "REPORTED"}
MIN_HISTORY_GAMES = 5
TARGET_HISTORY_GAMES = 10


def _num(value: Any, default: float = 0.0) -> float:
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _day(value: Any) -> str:
    return pd.to_datetime(value).strftime("%Y-%m-%d")


def _step3_snapshot(slate: dict[str, Any], slate_day: str):
    """Rebuild the already-verified Step-3 state using V3 helpers only."""
    if str((slate or {}).get("verification") or "") != "VERIFIED":
        return pd.DataFrame(), {"ready": False, "reason": "Step 2 not VERIFIED"}

    meta = base._team_meta(slate)
    team_rows = tuple(sorted((tid, m.get("name", ""), m.get("abbr", "")) for tid, m in meta.items()))
    roster, rdiag = base._current_rosters(team_rows)
    injuries, imeta, timestamp = base._injury_feed()
    feed_ok = bool(imeta.get("request_ok"))
    age_h = base._feed_age_hours(timestamp)
    report_day = base._feed_day_et(timestamp)
    feed_same_day = bool(report_day and report_day == slate_day)
    feed_fresh = bool(feed_ok and feed_same_day and age_h is not None and age_h <= 12.0)
    merged, unmatched = base._overlay_availability(roster, injuries, slate, feed_ok)

    teams = int(rdiag.get("teams") or 0)
    covered = int(rdiag.get("covered_teams") or 0)
    missing = int(rdiag.get("missing_teams") or 0)
    roster_ready = bool(teams > 0 and covered == teams and missing == 0)
    unknown = int(merged["AVAILABILITY"].eq("UNKNOWN").sum()) if not merged.empty else 0
    unmatched_count = len(unmatched)
    availability_ready = bool(feed_fresh and unknown == 0 and unmatched_count == 0)
    ready = bool(roster_ready and availability_ready)
    return merged, {
        "ready": ready,
        "teams": teams,
        "covered": covered,
        "missing": missing,
        "feed_ok": feed_ok,
        "feed_fresh": feed_fresh,
        "feed_same_day": feed_same_day,
        "feed_age_h": age_h,
        "feed_day": report_day,
        "unknown": unknown,
        "unmatched": unmatched_count,
    }


@st.cache_data(ttl=900, show_spinner=False, max_entries=16)
def _season_schedule(season: int) -> pd.DataFrame:
    try:
        frame = players._espn_season_schedule(int(season))
        return frame.copy() if frame is not None else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _last_team_games(season: pd.DataFrame, day_str: str, team_id: int) -> pd.DataFrame:
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
    return out.sort_values("_date", ascending=False).drop_duplicates("game_id").head(TARGET_HISTORY_GAMES)


@st.cache_data(ttl=900, show_spinner=False, max_entries=32)
def _rotation_history(day_str: str, team_ids: tuple[int, ...], roster_ids: tuple[tuple[int, tuple[int, ...]], ...]):
    """Fetch last-10 team box scores once, then build current-roster minute histories."""
    day_str = _day(day_str)
    season = _season_schedule(pd.to_datetime(day_str).year)
    if season is None or season.empty:
        return {}, {"ready": False, "reason": "season schedule unavailable", "team_games": {}}

    ids_by_team = {int(tid): tuple(int(x) for x in ids) for tid, ids in roster_ids}
    games_by_team: dict[int, list[dict[str, str]]] = {}
    jobs: dict[str, str] = {}
    for tid in team_ids:
        games = _last_team_games(season, day_str, int(tid))
        rows = []
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
        workers = min(12, max(1, len(jobs)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
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
        ids = ids_by_team.get(int(tid), ())
        minute_maps: list[dict[int, float]] = []
        for game in games_by_team.get(int(tid), []):
            box = summaries.get(game["game_id"])
            if box is None or box.empty or "TEAM_ID" not in box.columns:
                continue
            part = box.loc[pd.to_numeric(box["TEAM_ID"], errors="coerce").eq(int(tid))].copy()
            if part.empty:
                continue
            minute_map: dict[int, float] = {}
            for _, row in part.iterrows():
                try:
                    pid = int(float(row.get("PLAYER_ID")))
                except Exception:
                    continue
                minute_map[pid] = max(0.0, _num(row.get("MIN"), 0.0))
            minute_maps.append(minute_map)

        n = len(minute_maps)
        team_counts[int(tid)] = n
        history[int(tid)] = {}
        for pid in ids:
            vals = [float(game_map.get(int(pid), 0.0)) for game_map in minute_maps]
            l1 = vals[0] if vals else 0.0
            l3 = float(np.mean(vals[: min(3, n)])) if n else 0.0
            l5 = float(np.mean(vals[: min(5, n)])) if n else 0.0
            l10 = float(np.mean(vals[: min(10, n)])) if n else 0.0
            sd10 = float(np.std(vals[: min(10, n)], ddof=0)) if n else 0.0
            appearances = int(sum(v > 0.25 for v in vals))
            history[int(tid)][int(pid)] = {
                "games": n,
                "l1": l1,
                "l3": l3,
                "l5": l5,
                "l10": l10,
                "sd10": sd10,
                "appearances": appearances,
            }

    ready = bool(team_counts and all(team_counts.get(int(tid), 0) >= MIN_HISTORY_GAMES for tid in team_ids))
    return history, {
        "ready": ready,
        "reason": "" if ready else "one or more slate teams have fewer than 5 usable completed-game summaries",
        "team_games": team_counts,
        "unique_summaries": len(summaries),
        "requested_summaries": len(jobs),
    }


def _normalize_200(anchors: pd.Series) -> pd.Series:
    """Proportionally allocate exactly 200 regulation minutes with a 40-minute cap."""
    vals = pd.to_numeric(anchors, errors="coerce").fillna(0.0).clip(lower=0.0)
    result = pd.Series(0.0, index=vals.index, dtype=float)
    remaining = list(vals[vals.gt(0)].index)
    fixed: dict[Any, float] = {}

    for _ in range(20):
        if not remaining:
            break
        target = max(0.0, 200.0 - sum(fixed.values()))
        denom = float(vals.loc[remaining].sum())
        scaled = vals.loc[remaining] * (target / denom) if denom > 0 else pd.Series(target / len(remaining), index=remaining)
        capped = scaled[scaled > 40.0]
        if capped.empty:
            for idx, value in scaled.items():
                fixed[idx] = float(max(0.0, value))
            remaining = []
            break
        for idx in list(capped.index):
            fixed[idx] = 40.0
            remaining.remove(idx)

    if remaining:
        target = max(0.0, 200.0 - sum(fixed.values()))
        denom = float(vals.loc[remaining].sum())
        for idx in remaining:
            fixed[idx] = target * float(vals.loc[idx]) / denom if denom > 0 else target / len(remaining)

    for idx, value in fixed.items():
        result.loc[idx] = float(np.clip(value, 0.0, 40.0))
    return result


def _rotation_tier(minutes: float) -> str:
    if minutes >= 30.0:
        return "CORE"
    if minutes >= 18.0:
        return "ROTATION"
    if minutes >= 6.0:
        return "BENCH"
    if minutes > 0.0:
        return "FRINGE"
    return "OUT / DNP"


def _minute_confidence(games: int, sd10: float, appearances: int) -> str:
    if games >= 8 and appearances >= 6 and sd10 <= 5.0:
        return "HIGH"
    if games >= 5 and appearances >= 3 and sd10 <= 9.0:
        return "MEDIUM"
    return "LOW"


def _build_projected_minutes(slate: dict[str, Any], day_str: str, merged: pd.DataFrame):
    if merged is None or merged.empty:
        return pd.DataFrame(), pd.DataFrame(), {"ready": False, "reason": "no Step-3 roster rows"}

    meta = base._team_meta(slate)
    roster = merged.copy()
    roster["TEAM_ID_NUM"] = pd.to_numeric(roster.get("TEAM_ID"), errors="coerce").fillna(0).astype(int)
    roster["AVAILABILITY"] = roster.get("AVAILABILITY", pd.Series("UNKNOWN", index=roster.index)).astype(str).str.upper()

    team_ids = tuple(sorted(int(tid) for tid in meta))
    roster_ids = []
    for tid in team_ids:
        ids = []
        part = roster.loc[roster["TEAM_ID_NUM"].eq(int(tid))]
        for value in part.get("PLAYER_ID", pd.Series(dtype=str)):
            try:
                ids.append(int(float(value)))
            except Exception:
                continue
        roster_ids.append((int(tid), tuple(sorted(set(ids)))))

    history, hdiag = _rotation_history(day_str, team_ids, tuple(roster_ids))
    player_frames: list[pd.DataFrame] = []
    team_rows: list[dict[str, Any]] = []

    for tid in team_ids:
        part = roster.loc[roster["TEAM_ID_NUM"].eq(int(tid))].copy()
        if part.empty:
            team_rows.append({"Team": meta.get(tid, {}).get("name", str(tid)), "History games": 0, "Projected total": 0.0, "Rotation players": 0, "Gate": "CHECK"})
            continue

        l1s: list[float] = []
        l3s: list[float] = []
        l5s: list[float] = []
        l10s: list[float] = []
        sds: list[float] = []
        samples: list[int] = []
        apps: list[int] = []
        anchors: list[float] = []

        for _, row in part.iterrows():
            try:
                pid = int(float(row.get("PLAYER_ID")))
            except Exception:
                pid = 0
            info = (history.get(int(tid), {}) or {}).get(pid, {})
            l1 = _num(info.get("l1"), 0.0)
            l3 = _num(info.get("l3"), 0.0)
            l5 = _num(info.get("l5"), 0.0)
            l10 = _num(info.get("l10"), 0.0)
            sd10 = _num(info.get("sd10"), 0.0)
            games = int(info.get("games") or 0)
            appearances = int(info.get("appearances") or 0)
            status = str(row.get("AVAILABILITY") or "UNKNOWN").upper()

            anchor = 0.50 * l3 + 0.30 * l5 + 0.20 * l10
            if status in ZERO_MIN_STATUSES:
                anchor = 0.0
            elif anchor < 0.35:
                anchor = 0.0

            l1s.append(l1); l3s.append(l3); l5s.append(l5); l10s.append(l10)
            sds.append(sd10); samples.append(games); apps.append(appearances); anchors.append(anchor)

        part["L1_MIN"] = l1s
        part["L3_MIN"] = l3s
        part["L5_MIN"] = l5s
        part["L10_MIN"] = l10s
        part["MIN_SD10"] = sds
        part["ROTATION_GAMES"] = samples
        part["ROTATION_APPEARANCES"] = apps
        part["MINUTE_ANCHOR"] = anchors
        part["PROJ_MIN"] = _normalize_200(part["MINUTE_ANCHOR"])
        part.loc[part["AVAILABILITY"].isin(ZERO_MIN_STATUSES), "PROJ_MIN"] = 0.0
        part["ROTATION_TIER"] = part["PROJ_MIN"].map(_rotation_tier)
        part["MINUTE_CONFIDENCE"] = [
            _minute_confidence(int(g), float(sd), int(a))
            for g, sd, a in zip(part["ROTATION_GAMES"], part["MIN_SD10"], part["ROTATION_APPEARANCES"])
        ]
        part["STATUS_RISK"] = part["AVAILABILITY"].map(lambda x: "YES" if x in RISK_STATUSES else "NO")

        proj_total = float(part["PROJ_MIN"].sum())
        rotation_players = int(part["PROJ_MIN"].gt(0.25).sum())
        history_games = int(max(part["ROTATION_GAMES"].tolist() or [0]))
        invalid_zero = int(part.loc[part["AVAILABILITY"].isin(ZERO_MIN_STATUSES), "PROJ_MIN"].gt(0.01).sum())
        team_ready = bool(
            history_games >= MIN_HISTORY_GAMES
            and rotation_players >= 5
            and abs(proj_total - 200.0) <= 0.25
            and float(part["PROJ_MIN"].max()) <= 40.001
            and invalid_zero == 0
        )
        team_rows.append({
            "Team": meta.get(tid, {}).get("name", str(tid)),
            "History games": history_games,
            "Projected total": round(proj_total, 1),
            "Rotation players": rotation_players,
            "Status-risk players": int(part["STATUS_RISK"].eq("YES").sum()),
            "Gate": "PASS" if team_ready else "CHECK",
        })
        player_frames.append(part)

    minutes = pd.concat(player_frames, ignore_index=True) if player_frames else pd.DataFrame()
    team_diag = pd.DataFrame(team_rows)
    ready = bool(hdiag.get("ready") and not team_diag.empty and team_diag["Gate"].eq("PASS").all())
    reason = "" if ready else str(hdiag.get("reason") or "one or more team minute allocations failed validation")
    return minutes, team_diag, {
        "ready": ready,
        "reason": reason,
        "history": hdiag,
        "teams": len(team_ids),
        "players": len(minutes),
        "rotation_players": int(minutes["PROJ_MIN"].gt(0.25).sum()) if not minutes.empty else 0,
    }


def _render_step4(slate: dict[str, Any], day_str: str, merged: pd.DataFrame, step3_ready: bool) -> tuple[bool, pd.DataFrame]:
    st.markdown("### ⏱️ Step 4 — Projected Minutes + Rotation")
    st.caption(
        "Playing time is modeled before any assist-rate or sportsbook input. The anchor is 50% L3 + 30% L5 + 20% L10 team-rotation minutes, then each active team is normalized to 200 regulation minutes."
    )

    if not step3_ready:
        st.error("⛔ STEP 4 LOCKED • Step 3 has not passed, so no historical rotation data is allowed into the minutes model.")
        return False, pd.DataFrame()

    with st.spinner("⏱️ Building last-10 WNBA rotation history + projected minutes…"):
        minutes, team_diag, diag = _build_projected_minutes(slate, day_str, merged)

    ready = bool(diag.get("ready"))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Teams modeled", int(diag.get("teams") or 0))
    c2.metric("Roster players", int(diag.get("players") or 0))
    c3.metric("Projected rotation", int(diag.get("rotation_players") or 0))
    hist = diag.get("history") or {}
    c4.metric("Box scores used", int(hist.get("unique_summaries") or 0))

    if ready:
        st.success("✅ STEP 4 PASSED • every slate team has at least 5 usable completed-game rotations, unavailable players are zeroed, and every team allocates exactly 200 regulation minutes with no player above 40.")
    else:
        st.warning(f"⚠️ STEP 4 CHECK • {diag.get('reason') or 'minutes validation incomplete'}. Step 5 remains locked.")

    if team_diag is not None and not team_diag.empty:
        st.dataframe(team_diag, hide_index=True, use_container_width=True)

    if minutes is not None and not minutes.empty:
        view = minutes.copy()
        view["Player"] = view["PLAYER_NAME"].astype(str)
        view["Team"] = view.get("TEAM_ABBREVIATION", pd.Series("", index=view.index)).astype(str)
        view["Status"] = view["AVAILABILITY"].astype(str)
        view["L1"] = view["L1_MIN"].round(1)
        view["L3"] = view["L3_MIN"].round(1)
        view["L5"] = view["L5_MIN"].round(1)
        view["L10"] = view["L10_MIN"].round(1)
        view["Projected min"] = view["PROJ_MIN"].round(1)
        view["Rotation"] = view["ROTATION_TIER"].astype(str)
        view["Confidence"] = view["MINUTE_CONFIDENCE"].astype(str)
        view["Status risk"] = view["STATUS_RISK"].astype(str)
        view = view.sort_values(["TEAM_ID_NUM", "PROJ_MIN"], ascending=[True, False])
        st.dataframe(
            view[["Player", "Team", "Status", "L1", "L3", "L5", "L10", "Projected min", "Rotation", "Confidence", "Status risk"]],
            hide_index=True,
            use_container_width=True,
        )
        if ready:
            st.session_state[f"wnba_assists_v4_minutes::{day_str}"] = minutes.copy()

    with st.expander("🧮 Step-4 rotation / minutes diagnostics", expanded=False):
        st.write("• History window: last 10 completed WNBA team games before the selected ET slate.")
        st.write("• Current-roster player absent from a verified team box score = 0 minutes for that game.")
        st.write("• Minute anchor: 50% L3 + 30% L5 + 20% L10.")
        st.write("• OUT / INACTIVE / DOUBTFUL = 0 projected minutes.")
        st.write("• QUESTIONABLE / PROBABLE / other reported statuses are not automatically discounted; they are flagged as status risk.")
        st.write("• Team normalization: 200 regulation minutes, maximum 40 per player.")
        st.write("• Sportsbook lines used in minutes: 0")
        st.write("• Assist projection math used: 0")
        st.write("• Monte Carlo runs: 0")
        st.write(f"• Historical summary requests: {hist.get('requested_summaries', 0)}")
        st.write(f"• Usable unique summaries: {hist.get('unique_summaries', 0)}")

    return ready, minutes


def render_wnba_assists_hub(section_header=None, status_info=None, team_logo=None, h=None):
    slate_day = datetime.now(_ET).strftime("%Y-%m-%d")
    slate = base.schedule.load_verified_wnba_slate(slate_day)
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
          <div class="ks-ast-kicker">KYRE SPORTS AI • WNBA ASSISTS INTELLIGENCE • STEP 4</div>
          <div class="ks-ast-title">🎯 WNBA Assists Command Center</div>
          <div class="ks-ast-sub">Steps 1–3 remain intact. Step 4 models only expected court time and rotation from completed team game history. Assist role, assist production, sportsbook lines and simulations remain locked.</div>
          <span class="ks-ast-chip">📅 ET slate {slate_day}</span>
          <span class="ks-ast-chip">✅ Steps 1–3 preserved</span>
          <span class="ks-ast-chip">⏱️ rotation minutes only</span>
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
    step3_ready = base._render_step3(slate, slate_day)
    merged, step3_diag = _step3_snapshot(slate, slate_day)
    step3_ready = bool(step3_ready and step3_diag.get("ready"))

    step4_ready, _ = _render_step4(slate, slate_day, merged, step3_ready)

    if st.button("🔄 RECHECK ASSISTS STEPS 2–4", use_container_width=True, key="assists_step4_recheck"):
        base.schedule.load_verified_wnba_slate.clear()
        base._current_rosters.clear()
        base._injury_feed.clear()
        _season_schedule.clear()
        _rotation_history.clear()
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
        (5, "Assist role + ball-handling / usage", "➡️ NEXT" if step4_ready else "🔒 LOCKED", "Primary/secondary creation responsibility"),
        (6, "Recent + season assist form", "🔒 LOCKED", "Minute-normalized, regression protected"),
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
                st.markdown(base._layer_card(*item), unsafe_allow_html=True)

    st.caption(
        f"⚡ WNBA Assists V4 Step 4 • Step 2 {verification or 'CHECK'} • Step 3 {'PASS' if step3_ready else 'LOCKED'} • Step 4 {'PASS' if step4_ready else 'CHECK'} • no assist projection/market/Monte Carlo yet"
    )


__all__ = ["MODEL_VERSION", "render_wnba_assists_hub"]
