"""WNBA Assists V7 — Step 7 potential-assist / passing opportunity layer.

Preserves Assists Steps 1–6 and adds only pre-conversion creation opportunity.

Step 7 rules:
- Step 6 must pass first;
- official WNBA Passing tracking is attempted for season/L10/L5/L3;
- when official tracking is available, surface Potential AST, passes made,
  passes received and a recency-weighted potential-assist opportunity baseline;
- official tracking rows are matched conservatively by team + exact normalized
  player name (player id is also used when compatible);
- if official tracking is unavailable, DO NOT invent passes or potential assists;
  instead expose a clearly labeled 0–100 creation-opportunity proxy derived
  only from Step-4 minutes, Step-5 creator share and Step-6 stabilized assist form;
- Step 8 remains locked until every core rotation player has an auditable
  opportunity signal (official tracking or the explicit proxy fallback).

No teammate conversion, opponent matchup, sportsbook line, assist projection,
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
import wnba_players_v25 as players

MODEL_VERSION = "WNBA ASSISTS V7 • STEP 7 CREATION OPPORTUNITY / PASSING TRACKING"
_ET = ZoneInfo("America/New_York")
WNBA_TRACKING_URL = "https://stats.wnba.com/stats/leaguedashptstats"
CORE_MINUTES = 10.0
ZERO_STATUSES = {"OUT", "INACTIVE", "DOUBTFUL"}


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


def _norm(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _tracking_params(season: int, last_n: int) -> dict[str, Any]:
    return {
        "College": "", "Conference": "", "Country": "", "DateFrom": "", "DateTo": "",
        "Division": "", "DraftPick": "", "DraftYear": "", "GameScope": "", "Height": "",
        "LastNGames": int(last_n), "LeagueID": "10", "Location": "", "Month": 0,
        "OpponentTeamID": 0, "Outcome": "", "PORound": 0, "PerMode": "PerGame",
        "Period": 0, "PlayerExperience": "", "PlayerPosition": "", "PtMeasureType": "Passing",
        "Season": str(int(season)), "SeasonSegment": "", "SeasonType": "Regular Season",
        "StarterBench": "", "TeamID": 0, "VsConference": "", "VsDivision": "", "Weight": "",
    }


def _tracking_headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
        "Accept": "application/json,text/plain,*/*",
        "Origin": "https://www.wnba.com",
        "Referer": "https://www.wnba.com/",
    }


def _parse_resultset(payload: Any) -> pd.DataFrame:
    if not isinstance(payload, dict):
        return pd.DataFrame()
    sets = payload.get("resultSets") or payload.get("resultSet") or []
    if isinstance(sets, dict):
        sets = [sets]
    for item in sets if isinstance(sets, list) else []:
        headers = item.get("headers") or []
        rows = item.get("rowSet") or []
        if "PLAYER_ID" in headers and ("POTENTIAL_AST" in headers or "PASSES_MADE" in headers):
            frame = pd.DataFrame(rows, columns=headers)
            frame.columns = [str(c).upper() for c in frame.columns]
            return frame
    return pd.DataFrame()


def _fetch_tracking_window(season: int, last_n: int) -> tuple[pd.DataFrame, str]:
    try:
        response = requests.get(
            WNBA_TRACKING_URL,
            params=_tracking_params(season, last_n),
            headers=_tracking_headers(),
            timeout=5,
        )
        response.raise_for_status()
        frame = _parse_resultset(response.json())
        if frame is None or frame.empty:
            return pd.DataFrame(), "empty"
        keep = [c for c in (
            "PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "TEAM_ABBREVIATION", "GP", "MIN",
            "PASSES_MADE", "PASSES_RECEIVED", "AST", "FT_AST", "SECONDARY_AST",
            "POTENTIAL_AST", "AST_PTS_CREATED", "AST_ADJ", "AST_TO_PASS_PCT",
            "AST_TO_PASS_PCT_ADJ",
        ) if c in frame.columns]
        frame = frame[keep].copy()
        if "PLAYER_ID" in frame.columns:
            frame["PLAYER_ID"] = pd.to_numeric(frame["PLAYER_ID"], errors="coerce").fillna(0).astype(int)
        if "TEAM_ID" in frame.columns:
            frame["TEAM_ID"] = pd.to_numeric(frame["TEAM_ID"], errors="coerce").fillna(0).astype(int)
        for c in ("GP", "MIN", "PASSES_MADE", "PASSES_RECEIVED", "AST", "POTENTIAL_AST", "AST_PTS_CREATED"):
            if c in frame.columns:
                frame[c] = pd.to_numeric(frame[c], errors="coerce")
        return frame.reset_index(drop=True), "ok"
    except Exception as exc:
        return pd.DataFrame(), type(exc).__name__


@st.cache_data(ttl=900, show_spinner=False, max_entries=4)
def _tracking_windows(season: int):
    jobs = {"SEASON": 0, "L10": 10, "L5": 5, "L3": 3}
    frames: dict[str, pd.DataFrame] = {}
    states: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_fetch_tracking_window, int(season), last_n): label for label, last_n in jobs.items()}
        for future in as_completed(futures):
            label = futures[future]
            try:
                frame, state = future.result()
            except Exception as exc:
                frame, state = pd.DataFrame(), type(exc).__name__
            frames[label] = frame
            states[label] = state
    usable = [label for label, frame in frames.items() if frame is not None and not frame.empty]
    return frames, {
        "mode": "OFFICIAL_TRACKING" if usable else "PROXY_ONLY",
        "usable_windows": usable,
        "states": states,
        "source": "WNBA Stats Passing tracking" if usable else "unavailable",
    }


def _tracking_lookup(frame: pd.DataFrame):
    by_id: dict[tuple[int, int], pd.Series] = {}
    by_name_team: dict[tuple[str, str], list[pd.Series]] = {}
    by_name_tid: dict[tuple[int, str], list[pd.Series]] = {}
    if frame is None or frame.empty:
        return by_id, by_name_team, by_name_tid
    for _, row in frame.iterrows():
        tid = _safe_int(row.get("TEAM_ID"))
        pid = _safe_int(row.get("PLAYER_ID"))
        name = _norm(row.get("PLAYER_NAME"))
        abbr = _norm(row.get("TEAM_ABBREVIATION"))
        if tid and pid:
            by_id[(tid, pid)] = row
        if name and abbr:
            by_name_team.setdefault((abbr, name), []).append(row)
        if tid and name:
            by_name_tid.setdefault((tid, name), []).append(row)
    return by_id, by_name_team, by_name_tid


def _match_tracking(row: pd.Series, frame: pd.DataFrame):
    by_id, by_name_team, by_name_tid = _tracking_lookup(frame)
    tid = _safe_int(row.get("TEAM_ID_NUM") or row.get("TEAM_ID"))
    pid = _safe_int(row.get("PLAYER_ID"))
    name = _norm(row.get("PLAYER_NAME"))
    abbr = _norm(row.get("TEAM_ABBREVIATION"))
    if tid and pid and (tid, pid) in by_id:
        return by_id[(tid, pid)], "PLAYER_ID+TEAM"
    candidates = by_name_tid.get((tid, name), []) if tid and name else []
    if len(candidates) == 1:
        return candidates[0], "NAME+TEAM_ID"
    candidates = by_name_team.get((abbr, name), []) if abbr and name else []
    if len(candidates) == 1:
        return candidates[0], "NAME+TEAM_ABBR"
    return None, ""


def _weighted(values: list[tuple[float, float]]) -> float:
    use = [(float(v), float(w)) for v, w in values if np.isfinite(v) and v >= 0]
    den = sum(w for _, w in use)
    return sum(v * w for v, w in use) / den if den else np.nan


def _scale_feature(series: pd.Series) -> pd.Series:
    vals = pd.to_numeric(series, errors="coerce").fillna(0.0)
    lo, hi = float(vals.min()), float(vals.max())
    if hi - lo < 1e-9:
        return pd.Series(0.5, index=vals.index, dtype=float)
    return ((vals - lo) / (hi - lo)).clip(0.0, 1.0)


def _proxy_opportunity(team: pd.DataFrame) -> pd.Series:
    creation = _scale_feature(team.get("CREATION_SHARE", pd.Series(0.0, index=team.index)))
    form = _scale_feature(team.get("STABILIZED_AST36_FORM", pd.Series(0.0, index=team.index)))
    minutes = (pd.to_numeric(team.get("PROJ_MIN"), errors="coerce").fillna(0.0) / 40.0).clip(0.0, 1.0)
    role = team.get("CREATION_ROLE", pd.Series("", index=team.index)).astype(str).map({
        "PRIMARY CREATOR": 1.0,
        "SECONDARY CREATOR": 0.72,
        "CONNECTOR": 0.45,
        "LOW-CREATION": 0.18,
        "OUT / DNP": 0.0,
    }).fillna(0.25)
    return (100.0 * (0.45 * creation + 0.30 * form + 0.15 * minutes + 0.10 * role)).clip(0.0, 100.0)


def _build_step7_opportunity(slate: dict[str, Any], day_str: str, form: pd.DataFrame):
    if form is None or form.empty:
        return pd.DataFrame(), pd.DataFrame(), {"ready": False, "reason": "no Step-6 form rows"}

    season = pd.to_datetime(day_str).year
    windows, tdiag = _tracking_windows(int(season))
    meta = step3._team_meta(slate)
    out = form.copy()
    out["OFFICIAL_POT_AST"] = np.nan
    out["OFFICIAL_PASSES_MADE"] = np.nan
    out["OFFICIAL_PASSES_RECEIVED"] = np.nan
    out["OFFICIAL_TRACKING_AST"] = np.nan
    out["OFFICIAL_POT_AST_BLEND"] = np.nan
    out["OFFICIAL_PASSES_BLEND"] = np.nan
    out["TRACKING_MATCH"] = ""
    out["TRACKING_WINDOWS"] = ""
    out["OPPORTUNITY_MODE"] = "ESTIMATED ROLE/FORM PROXY"
    out["OPPORTUNITY_SOURCE"] = "Step 4 minutes + Step 5 creation share + Step 6 stabilized assist form"

    labels = [("SEASON", 0.25), ("L10", 0.20), ("L5", 0.25), ("L3", 0.30)]
    for idx, row in out.iterrows():
        pot_vals: list[tuple[float, float]] = []
        pass_vals: list[tuple[float, float]] = []
        match_modes: list[str] = []
        matched_windows: list[str] = []
        season_row = None
        for label, weight in labels:
            frame = windows.get(label, pd.DataFrame())
            matched, mode = _match_tracking(row, frame)
            if matched is None:
                continue
            matched_windows.append(label)
            if mode:
                match_modes.append(mode)
            pot = _num(matched.get("POTENTIAL_AST"), np.nan)
            passes = _num(matched.get("PASSES_MADE"), np.nan)
            if np.isfinite(pot):
                pot_vals.append((pot, weight))
            if np.isfinite(passes):
                pass_vals.append((passes, weight))
            if label == "SEASON":
                season_row = matched

        pot_blend = _weighted(pot_vals)
        pass_blend = _weighted(pass_vals)
        if np.isfinite(pot_blend) or np.isfinite(pass_blend):
            out.at[idx, "OFFICIAL_POT_AST_BLEND"] = pot_blend
            out.at[idx, "OFFICIAL_PASSES_BLEND"] = pass_blend
            out.at[idx, "OPPORTUNITY_MODE"] = "OFFICIAL WNBA PASSING TRACKING"
            out.at[idx, "OPPORTUNITY_SOURCE"] = "WNBA Stats Passing • recency-weighted Season/L10/L5/L3"
            out.at[idx, "TRACKING_MATCH"] = ",".join(dict.fromkeys(match_modes))
            out.at[idx, "TRACKING_WINDOWS"] = "/".join(matched_windows)
            if season_row is not None:
                out.at[idx, "OFFICIAL_POT_AST"] = _num(season_row.get("POTENTIAL_AST"), np.nan)
                out.at[idx, "OFFICIAL_PASSES_MADE"] = _num(season_row.get("PASSES_MADE"), np.nan)
                out.at[idx, "OFFICIAL_PASSES_RECEIVED"] = _num(season_row.get("PASSES_RECEIVED"), np.nan)
                out.at[idx, "OFFICIAL_TRACKING_AST"] = _num(season_row.get("AST"), np.nan)

    # Proxy is computed for everyone, but only becomes the displayed opportunity
    # signal when official tracking is unavailable for that specific player.
    out["CREATION_OPPORTUNITY_INDEX"] = 0.0
    team_rows: list[dict[str, Any]] = []
    for tid, team_meta in meta.items():
        mask = pd.to_numeric(out.get("TEAM_ID_NUM"), errors="coerce").fillna(0).astype(int).eq(int(tid))
        team = out.loc[mask].copy()
        if team.empty:
            team_rows.append({"Team": team_meta.get("name", str(tid)), "Core players": 0, "Official tracking": 0, "Proxy": 0, "Mode": "NONE", "Gate": "CHECK"})
            continue
        proxy = _proxy_opportunity(team)
        out.loc[team.index, "CREATION_OPPORTUNITY_INDEX"] = proxy
        status = team.get("AVAILABILITY", pd.Series("UNKNOWN", index=team.index)).astype(str).str.upper()
        proj = pd.to_numeric(team.get("PROJ_MIN"), errors="coerce").fillna(0.0)
        core = proj.ge(CORE_MINUTES) & ~status.isin(ZERO_STATUSES)
        official = team["OPPORTUNITY_MODE"].eq("OFFICIAL WNBA PASSING TRACKING")
        form_ok = pd.to_numeric(team.get("STABILIZED_AST36_FORM"), errors="coerce").notna()
        share_ok = pd.to_numeric(team.get("CREATION_SHARE"), errors="coerce").notna()
        auditable = official | (form_ok & share_ok)
        core_count = int(core.sum())
        core_auditable = int((core & auditable).sum())
        official_count = int((core & official).sum())
        proxy_count = int((core & ~official & auditable).sum())
        team_ready = bool(core_count > 0 and core_auditable == core_count)
        mode = "OFFICIAL" if official_count == core_count and core_count else ("MIXED" if official_count else "PROXY")
        team_rows.append({
            "Team": team_meta.get("name", str(tid)),
            "Core players": core_count,
            "Official tracking": official_count,
            "Proxy": proxy_count,
            "Auditable": core_auditable,
            "Mode": mode,
            "Gate": "PASS" if team_ready else "CHECK",
        })

    out.loc[out.get("AVAILABILITY", pd.Series("", index=out.index)).astype(str).str.upper().isin(ZERO_STATUSES), "CREATION_OPPORTUNITY_INDEX"] = 0.0
    team_diag = pd.DataFrame(team_rows)
    ready = bool(not team_diag.empty and team_diag["Gate"].eq("PASS").all())
    official_players = int(out["OPPORTUNITY_MODE"].eq("OFFICIAL WNBA PASSING TRACKING").sum())
    proxy_players = int(out["OPPORTUNITY_MODE"].eq("ESTIMATED ROLE/FORM PROXY").sum())
    return out, team_diag, {
        "ready": ready,
        "reason": "" if ready else "one or more core rotation players lack an auditable opportunity signal",
        "tracking": tdiag,
        "official_players": official_players,
        "proxy_players": proxy_players,
        "players": len(out),
        "teams": len(team_diag),
    }


def _render_step7(slate: dict[str, Any], day_str: str, form: pd.DataFrame, step6_ready: bool):
    st.markdown("### 🛰️ Step 7 — Potential Assists / Passes / Creation Chances")
    st.caption(
        "Opportunity comes before teammate conversion. Official WNBA passing tracking is used when available. When it is not available, the model does not fabricate pass or potential-assist counts — it shows a clearly labeled creation-opportunity proxy instead."
    )
    if not step6_ready:
        st.error("⛔ STEP 7 LOCKED • Step 6 has not passed, so opportunity data cannot enter the chain.")
        return False, pd.DataFrame()

    with st.spinner("🛰️ Checking WNBA passing tracking + building creation-opportunity signals…"):
        opportunity, team_diag, diag = _build_step7_opportunity(slate, day_str, form)

    ready = bool(diag.get("ready"))
    tdiag = diag.get("tracking") or {}
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Opportunity players", int(diag.get("players") or 0))
    c2.metric("Official tracking", int(diag.get("official_players") or 0))
    c3.metric("Proxy fallback", int(diag.get("proxy_players") or 0))
    c4.metric("Tracking windows", len(tdiag.get("usable_windows") or []))

    if ready and int(diag.get("official_players") or 0) > 0:
        st.success("✅ STEP 7 PASSED • core rotation players have auditable opportunity signals. Official WNBA passing tracking is active where available; unmatched players use the explicit non-tracking proxy only.")
    elif ready:
        st.success("✅ STEP 7 PASSED — FALLBACK MODE • official WNBA passing tracking is unavailable in this runtime, so no pass or potential-assist counts are invented. Every core rotation player has an auditable role/form opportunity proxy for the next layer.")
    else:
        st.warning(f"⚠️ STEP 7 CHECK • {diag.get('reason') or 'opportunity validation incomplete'}. Step 8 remains locked.")

    if team_diag is not None and not team_diag.empty:
        st.dataframe(team_diag, hide_index=True, use_container_width=True)

    if opportunity is not None and not opportunity.empty:
        view = opportunity.copy()
        view["Player"] = view["PLAYER_NAME"].astype(str)
        view["Team"] = view.get("TEAM_ABBREVIATION", pd.Series("", index=view.index)).astype(str)
        view["Role"] = view.get("CREATION_ROLE", pd.Series("", index=view.index)).astype(str)
        view["Proj min"] = pd.to_numeric(view.get("PROJ_MIN"), errors="coerce").round(1)
        view["Potential AST"] = pd.to_numeric(view["OFFICIAL_POT_AST_BLEND"], errors="coerce").round(1)
        view["Passes made"] = pd.to_numeric(view["OFFICIAL_PASSES_BLEND"], errors="coerce").round(1)
        view["Opportunity index"] = pd.to_numeric(view["CREATION_OPPORTUNITY_INDEX"], errors="coerce").round(0)
        view["Mode"] = view["OPPORTUNITY_MODE"].astype(str)
        view["Source"] = view["OPPORTUNITY_SOURCE"].astype(str)
        view = view.sort_values(["TEAM_ID_NUM", "CREATION_OPPORTUNITY_INDEX"], ascending=[True, False])
        st.dataframe(
            view[["Player", "Team", "Role", "Proj min", "Potential AST", "Passes made", "Opportunity index", "Mode", "Source"]],
            hide_index=True,
            use_container_width=True,
        )
        if ready:
            st.session_state[f"wnba_assists_v7_opportunity::{day_str}"] = opportunity.copy()

    with st.expander("🧪 Step-7 opportunity methodology / diagnostics", expanded=False):
        st.write("• Official source attempted: WNBA Stats player-tracking Passing table.")
        st.write("• Official windows: Season / L10 / L5 / L3, requested concurrently and cached.")
        st.write("• Official descriptive opportunity blend: 25% season + 20% L10 + 25% L5 + 30% L3.")
        st.write("• Exact team + player identity is required; player-id match is preferred when compatible, otherwise exact normalized name + team is used.")
        st.write("• If tracking is unavailable, Potential AST and Passes fields stay blank. They are never estimated and presented as tracking stats.")
        st.write("• Proxy index uses only Step-4 projected minutes, Step-5 creation share/role and Step-6 stabilized AST/36 form.")
        st.write("• Teammate shot conversion applied: 0 — Step 8 only.")
        st.write("• Opponent matchup adjustment: 0")
        st.write("• Sportsbook lines used: 0")
        st.write("• Monte Carlo runs: 0")
        st.write(f"• Tracking mode: {tdiag.get('mode', 'PROXY_ONLY')}")
        st.write(f"• Usable official windows: {', '.join(tdiag.get('usable_windows') or []) or 'none'}")
        st.write(f"• Window request states: {tdiag.get('states', {})}")

    return ready, opportunity


def render_wnba_assists_hub(section_header=None, status_info=None, team_logo=None, h=None):
    slate_day = datetime.now(_ET).strftime("%Y-%m-%d")
    slate = step3.schedule.load_verified_wnba_slate(slate_day)
    verification = str(slate.get("verification") or "")

    st.markdown(
        f"""
        <div style="padding:25px 27px;margin:4px 0 18px;border:1px solid rgba(56,189,248,.34);border-radius:24px;background:linear-gradient(135deg,rgba(6,28,44,.99),rgba(12,22,48,.99));box-shadow:0 14px 38px rgba(0,0,0,.16);">
          <div style="color:#67e8f9;font-size:.69rem;font-weight:950;letter-spacing:.13em;text-transform:uppercase;">KYRE SPORTS AI • WNBA ASSISTS INTELLIGENCE • STEP 7</div>
          <div style="margin-top:9px;color:#f8fafc;font-size:2.05rem;line-height:1.08;font-weight:950;">🎯 WNBA Assists Command Center</div>
          <div style="margin-top:12px;color:#9fb0c6;font-size:.91rem;line-height:1.62;font-weight:650;">Steps 1–6 remain intact. Step 7 adds opportunity only: official passing/potential-assist tracking when accessible, otherwise an explicitly labeled non-tracking creation proxy. Conversion and projections remain locked.</div>
          <span style="display:inline-block;margin:14px 7px 0 0;padding:7px 10px;border:1px solid rgba(52,211,153,.35);border-radius:999px;background:rgba(16,185,129,.09);color:#6ee7b7;font-size:.69rem;font-weight:900;">📅 ET slate {slate_day}</span>
          <span style="display:inline-block;margin:14px 7px 0 0;padding:7px 10px;border:1px solid rgba(52,211,153,.35);border-radius:999px;background:rgba(16,185,129,.09);color:#6ee7b7;font-size:.69rem;font-weight:900;">✅ Steps 1–6 preserved</span>
          <span style="display:inline-block;margin:14px 7px 0 0;padding:7px 10px;border:1px solid rgba(52,211,153,.35);border-radius:999px;background:rgba(16,185,129,.09);color:#6ee7b7;font-size:.69rem;font-weight:900;">🛰️ opportunity only</span>
          <span style="display:inline-block;margin:14px 7px 0 0;padding:7px 10px;border:1px solid rgba(52,211,153,.35);border-radius:999px;background:rgba(16,185,129,.09);color:#6ee7b7;font-size:.69rem;font-weight:900;">🚫 zero simulations</span>
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
    step7_ready, _ = _render_step7(slate, slate_day, form, step6_ready)

    if st.button("🔄 RECHECK ASSISTS STEPS 2–7", use_container_width=True, key="assists_step7_recheck"):
        step3.schedule.load_verified_wnba_slate.clear()
        step3._current_rosters.clear()
        step3._injury_feed.clear()
        step4._season_schedule.clear()
        step4._rotation_history.clear()
        step5._creation_history.clear()
        step5._official_usage_table.clear()
        step6._season_form_pool.clear()
        step6._recent_assist_history.clear()
        _tracking_windows.clear()
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
        (8, "Teammate shot-making + lineup conversion", "➡️ NEXT" if step7_ready else "🔒 LOCKED", "Who finishes the created chances"),
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
        f"⚡ WNBA Assists V7 Step 7 • Step 2 {verification or 'CHECK'} • Step 3 {'PASS' if step3_ready else 'LOCKED'} • Step 4 {'PASS' if step4_ready else 'CHECK'} • Step 5 {'PASS' if step5_ready else 'CHECK'} • Step 6 {'PASS' if step6_ready else 'CHECK'} • Step 7 {'PASS' if step7_ready else 'CHECK'} • no conversion/projection/market/Monte Carlo yet"
    )


__all__ = ["MODEL_VERSION", "render_wnba_assists_hub"]
