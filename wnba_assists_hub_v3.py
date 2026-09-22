"""WNBA Assists V3 — Step 3 current roster + same-day availability gate.

Preserves the repaired Assists Step-2 verified Eastern-date slate and adds only:
- compact current roster identity for every verified slate team;
- structured ESPN WNBA injury/status rows;
- conservative exact identity reconciliation;
- same-day/freshness validation for the injury feed;
- a fail-closed gate that keeps Step 4 locked unless roster + status verification pass.

This module deliberately does NOT add projected minutes, assist statistics,
SportsGameOdds, market prices, projections, Monte Carlo, PRA, Points, Rebounds,
or Daily Picks production math.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_players_v25 as players
import wnba_assists_schedule_v2 as schedule

MODEL_VERSION = "WNBA ASSISTS V3 • STEP 3 ROSTER + SAME-DAY STATUS GATE"
_ET = ZoneInfo("America/New_York")
ESPN_INJURIES_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/injuries"


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return int(default)


def _norm(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _team_meta(slate: dict[str, Any]) -> dict[int, dict[str, str]]:
    meta: dict[int, dict[str, str]] = {}
    for game in (slate or {}).get("games", []) or []:
        if not isinstance(game, dict):
            continue
        for side in ("away", "home"):
            tid = _int(game.get(f"{side}_team_id"))
            if not tid:
                continue
            meta[tid] = {
                "name": str(game.get(side) or ""),
                "abbr": str(game.get(f"{side}_tricode") or ""),
            }
    return meta


def _sanitize_roster(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    out = frame.copy()
    if "ROSTER_STATUS" in out.columns:
        bad = out["ROSTER_STATUS"].astype(str).str.upper().str.contains(
            r"WAIV|RELEASE|CUT|RETIRED|TERMINATED", regex=True, na=False
        )
        out = out.loc[~bad].copy()
    required = {"TEAM_ID", "PLAYER_ID", "PLAYER_NAME"}
    if not required.issubset(out.columns):
        return pd.DataFrame()
    out["TEAM_ID"] = pd.to_numeric(out["TEAM_ID"], errors="coerce").fillna(0).astype(int)
    out["PLAYER_ID"] = out["PLAYER_ID"].astype(str)
    out = out[(out["TEAM_ID"] > 0) & out["PLAYER_ID"].ne("") & out["PLAYER_NAME"].astype(str).ne("")].copy()
    out = out.drop_duplicates(["TEAM_ID", "PLAYER_ID"], keep="first")
    # A WNBA active roster should be compact. Fail closed on obvious endpoint corruption.
    if len(out) < 5 or len(out) > 22:
        return pd.DataFrame()
    return out.reset_index(drop=True)


@st.cache_data(ttl=300, show_spinner=False)
def _current_rosters(team_rows: tuple[tuple[int, str, str], ...]):
    frames: list[pd.DataFrame] = []
    team_modes: dict[int, str] = {}
    for tid, team_name, team_abbr in team_rows:
        try:
            roster = _sanitize_roster(players._espn_roster(int(tid), team_name, team_abbr))
        except Exception:
            roster = pd.DataFrame()
        if roster is None or roster.empty:
            team_modes[int(tid)] = "MISSING"
            continue
        roster = roster.copy()
        if "ROSTER_SOURCE" not in roster.columns:
            roster["ROSTER_SOURCE"] = "ESPN WNBA current roster"
        else:
            roster["ROSTER_SOURCE"] = roster["ROSTER_SOURCE"].fillna("ESPN WNBA current roster")
        frames.append(roster)
        team_modes[int(tid)] = "CURRENT_ROSTER"

    roster = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not roster.empty:
        roster["TEAM_ID"] = pd.to_numeric(roster["TEAM_ID"], errors="coerce").fillna(0).astype(int)
        roster["PLAYER_ID"] = roster["PLAYER_ID"].astype(str)
        roster = roster.drop_duplicates(["TEAM_ID", "PLAYER_ID"], keep="first")
    covered = set(roster["TEAM_ID"].astype(int).tolist()) if not roster.empty else set()
    return roster, {
        "teams": len(team_rows),
        "covered_teams": len(covered),
        "missing_teams": max(0, len(team_rows) - len(covered)),
        "players": len(roster),
        "team_modes": team_modes,
        "source": "ESPN WNBA current roster",
    }


def _status_token(value: Any) -> str:
    if isinstance(value, dict):
        value = " ".join(
            str(value.get(k) or "")
            for k in ("name", "type", "description", "abbreviation", "displayName")
        )
    return " ".join(str(value or "").strip().lower().replace("_", " ").split())


def _pick_designation(text: str) -> str | None:
    t = f" {str(text or '').lower()} "
    if any(x in t for x in (" ruled out ", " will miss ", " won't play ", " wont play ", " out indefinitely ")):
        return "OUT"
    if " inactive " in t:
        return "INACTIVE"
    if " doubtful " in t:
        return "DOUBTFUL"
    if " questionable " in t or any(x in t for x in (" day-to-day ", " day to day ", " game-time decision ", " gtd ")):
        return "QUESTIONABLE"
    if " probable " in t:
        return "PROBABLE"
    if " out " in t:
        return "OUT"
    return None


def _injury_status(item: dict[str, Any]) -> str:
    item = item or {}
    details = item.get("details") or {}
    fantasy = details.get("fantasyStatus") or {}
    for raw in (item.get("status"), fantasy):
        label = _pick_designation(_status_token(raw))
        if label:
            return label
    narrative = " ".join(
        str(x or "")
        for x in (
            item.get("shortComment"),
            item.get("longComment"),
            item.get("type"),
            details.get("type"),
            fantasy.get("description") if isinstance(fantasy, dict) else "",
            fantasy.get("abbreviation") if isinstance(fantasy, dict) else "",
        )
    )
    return _pick_designation(_status_token(narrative)) or "REPORTED"


@st.cache_data(ttl=180, show_spinner=False)
def _injury_feed():
    payload, meta = schedule._request_json(
        "ESPN WNBA injuries", ESPN_INJURIES_URL, timeout=8, attempts=2
    )
    if payload is None:
        return pd.DataFrame(), dict(meta or {}), ""

    timestamp = str((payload or {}).get("timestamp") or "")
    rows: list[dict[str, Any]] = []
    for team_block in (payload or {}).get("injuries", []) or []:
        if not isinstance(team_block, dict):
            continue
        team_name = str(team_block.get("displayName") or "")
        for item in team_block.get("injuries", []) or []:
            if not isinstance(item, dict):
                continue
            athlete = item.get("athlete") or {}
            team = athlete.get("team") or {}
            details = item.get("details") or {}
            rows.append({
                "PLAYER_ID": str(athlete.get("id") or ""),
                "PLAYER_NAME": str(athlete.get("displayName") or athlete.get("fullName") or "Player"),
                "TEAM_NAME": str(team.get("displayName") or team_name),
                "TEAM_ABBR": str(team.get("abbreviation") or ""),
                "AVAILABILITY": _injury_status(item),
                "INJURY": str(details.get("type") or item.get("type") or ""),
                "SHORT_NOTE": str(item.get("shortComment") or ""),
                "RETURN_DATE": str(details.get("returnDate") or ""),
                "UPDATED": str(item.get("date") or timestamp),
                "SOURCE": "ESPN WNBA injuries",
            })
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.drop_duplicates(["PLAYER_ID", "TEAM_NAME", "PLAYER_NAME"], keep="first")
    return frame, dict(meta or {}), timestamp


def _feed_age_hours(timestamp: str) -> float | None:
    if not timestamp:
        return None
    try:
        ts = pd.to_datetime(timestamp, utc=True)
        return max(0.0, float((pd.Timestamp.now(tz="UTC") - ts).total_seconds() / 3600.0))
    except Exception:
        return None


def _feed_day_et(timestamp: str) -> str:
    if not timestamp:
        return ""
    try:
        return pd.to_datetime(timestamp, utc=True).tz_convert(_ET).strftime("%Y-%m-%d")
    except Exception:
        return ""


def _overlay_availability(
    roster: pd.DataFrame,
    injuries: pd.DataFrame,
    slate: dict[str, Any],
    feed_ok: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if roster is None or roster.empty:
        return pd.DataFrame(), pd.DataFrame()

    out = roster.copy()
    out["PLAYER_ID"] = out["PLAYER_ID"].astype(str)
    out["AVAILABILITY"] = "NOT LISTED" if feed_ok else "UNKNOWN"
    out["INJURY"] = ""
    out["INJURY_NOTE"] = ""
    out["INJURY_UPDATED"] = ""
    out["INJURY_SOURCE"] = "ESPN WNBA injuries" if feed_ok else "unavailable"
    out["INJURY_MATCH_MODE"] = ""
    if injuries is None or injuries.empty:
        return out, pd.DataFrame()

    slate_names: dict[str, int] = {}
    slate_abbrs: dict[str, int] = {}
    for tid, meta in _team_meta(slate).items():
        slate_names[_norm(meta.get("name"))] = tid
        slate_abbrs[_norm(meta.get("abbr"))] = tid

    inj = injuries.copy()
    inj["_slate_team_id"] = inj.apply(
        lambda r: slate_names.get(_norm(r.get("TEAM_NAME")))
        or slate_abbrs.get(_norm(r.get("TEAM_ABBR")))
        or 0,
        axis=1,
    )
    inj = inj[pd.to_numeric(inj["_slate_team_id"], errors="coerce").fillna(0).astype(int).ne(0)].copy()

    by_pid: dict[str, list[int]] = {}
    by_name_team: dict[tuple[int, str], list[int]] = {}
    for idx, row in out.iterrows():
        pid = str(row.get("PLAYER_ID") or "")
        tid = _int(row.get("TEAM_ID"))
        pname = _norm(row.get("PLAYER_NAME"))
        if pid:
            by_pid.setdefault(pid, []).append(idx)
        if tid and pname:
            by_name_team.setdefault((tid, pname), []).append(idx)

    unmatched: list[dict[str, Any]] = []
    for _, row in inj.iterrows():
        pid = str(row.get("PLAYER_ID") or "")
        tid = _int(row.get("_slate_team_id"))
        pname = _norm(row.get("PLAYER_NAME"))
        matched_idx = None
        match_mode = ""

        id_matches = [idx for idx in by_pid.get(pid, []) if _int(out.at[idx, "TEAM_ID"]) == tid]
        if len(id_matches) == 1:
            matched_idx = id_matches[0]
            match_mode = "ESPN_ID_EXACT"

        if matched_idx is None:
            name_matches = by_name_team.get((tid, pname), []) if tid and pname else []
            if len(name_matches) == 1:
                matched_idx = name_matches[0]
                match_mode = "NAME_TEAM_EXACT"

        if matched_idx is None:
            miss = row.to_dict()
            miss["MATCH_REASON"] = "NO_UNIQUE_ID_OR_EXACT_NAME_TEAM_MATCH"
            unmatched.append(miss)
            continue

        out.at[matched_idx, "AVAILABILITY"] = str(row.get("AVAILABILITY") or "REPORTED")
        out.at[matched_idx, "INJURY"] = str(row.get("INJURY") or "")
        out.at[matched_idx, "INJURY_NOTE"] = str(row.get("SHORT_NOTE") or "")
        out.at[matched_idx, "INJURY_UPDATED"] = str(row.get("UPDATED") or "")
        out.at[matched_idx, "INJURY_MATCH_MODE"] = match_mode

    return out, pd.DataFrame(unmatched)


def _layer_card(step: int, label: str, state: str, note: str = "") -> str:
    if "LIVE" in state:
        tone, border = "#6ee7b7", "rgba(52,211,153,.34)"
    elif "NEXT" in state:
        tone, border = "#67e8f9", "rgba(56,189,248,.30)"
    else:
        tone, border = "#94a3b8", "rgba(148,163,184,.22)"
    return f"""
    <div style="min-height:118px;padding:15px 16px;border:1px solid {border};border-radius:16px;
      background:linear-gradient(180deg,rgba(10,31,47,.98),rgba(7,24,38,.98));box-shadow:0 8px 24px rgba(0,0,0,.12);">
      <div style="color:#7f91aa;font-size:.65rem;font-weight:900;letter-spacing:.10em;text-transform:uppercase;">STEP {step}</div>
      <div style="margin-top:7px;color:#f8fafc;font-size:.90rem;font-weight:900;line-height:1.25;">{label}</div>
      <div style="margin-top:8px;color:{tone};font-size:.78rem;font-weight:950;">{state}</div>
      <div style="margin-top:6px;color:#7f91aa;font-size:.64rem;font-weight:700;line-height:1.35;">{note}</div>
    </div>"""


def _source_box(name: str, meta: dict[str, Any], selected: int, role: str) -> str:
    ok = bool(meta.get("ok"))
    status = meta.get("status") or "—"
    tone = "#6ee7b7" if ok else "#fbbf24"
    border = "rgba(52,211,153,.34)" if ok else "rgba(251,191,36,.35)"
    state = "PASS" if ok else "CHECK"
    return f"""
    <div style="padding:12px 14px;border:1px solid {border};border-radius:14px;background:rgba(7,24,38,.94);min-height:104px;">
      <div style="color:{tone};font-weight:950;font-size:.78rem;">{name} • {state}</div>
      <div style="margin-top:6px;color:#dbeafe;font-weight:850;font-size:.75rem;">{selected} same-day game(s)</div>
      <div style="margin-top:6px;color:#7f91aa;font-size:.66rem;font-weight:700;">HTTP {status} • {role}</div>
    </div>"""


def _render_step3(slate: dict[str, Any], slate_day: str) -> bool:
    verification = str(slate.get("verification") or "")
    if verification != "VERIFIED":
        if verification == "NO GAMES":
            st.info("ℹ️ STEP 3 IDLE • There are no verified WNBA games on this ET slate. No roster/status gate is opened and Step 4 stays locked.")
        else:
            st.error("⛔ STEP 3 LOCKED • Step 2 is not fully VERIFIED, so no roster or injury/status requests are allowed downstream.")
        return False

    meta = _team_meta(slate)
    team_rows = tuple(sorted((tid, m.get("name", ""), m.get("abbr", "")) for tid, m in meta.items()))
    roster, rdiag = _current_rosters(team_rows)
    injuries, imeta, timestamp = _injury_feed()
    feed_ok = bool(imeta.get("request_ok"))
    age_h = _feed_age_hours(timestamp)
    report_day = _feed_day_et(timestamp)
    feed_same_day = bool(report_day and report_day == slate_day)
    feed_fresh = bool(feed_ok and feed_same_day and age_h is not None and age_h <= 12.0)
    merged, unmatched = _overlay_availability(roster, injuries, slate, feed_ok)

    teams = int(rdiag.get("teams") or 0)
    covered = int(rdiag.get("covered_teams") or 0)
    missing = int(rdiag.get("missing_teams") or 0)
    roster_ready = bool(teams > 0 and covered == teams and missing == 0)
    flagged_set = {"OUT", "INACTIVE", "DOUBTFUL", "QUESTIONABLE", "PROBABLE", "REPORTED"}
    flagged = int(merged["AVAILABILITY"].isin(flagged_set).sum()) if not merged.empty else 0
    unknown = int(merged["AVAILABILITY"].eq("UNKNOWN").sum()) if not merged.empty else 0
    unmatched_count = len(unmatched)
    availability_ready = bool(feed_fresh and unknown == 0 and unmatched_count == 0)
    ready = bool(roster_ready and availability_ready)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Roster teams", f"{covered}/{teams}" if teams else "0/0")
    c2.metric("Current players", len(merged))
    c3.metric("Injury flags", flagged)
    c4.metric("Status feed age", "—" if age_h is None else f"{age_h:.1f}h")

    if ready:
        st.success("✅ STEP 3 PASSED • every verified slate team has a compact current roster, the injury/status feed is from the same ET date and fresh, and every slate injury row reconciles to exactly one current-roster player.")
    else:
        reasons: list[str] = []
        if not roster_ready:
            reasons.append(f"roster coverage {covered}/{teams}")
        if not feed_ok:
            reasons.append("injury/status feed unavailable")
        elif not feed_same_day:
            reasons.append(f"status feed date {report_day or 'unknown'} is not slate date {slate_day}")
        elif age_h is None or age_h > 12.0:
            reasons.append("injury/status feed is stale")
        if unknown:
            reasons.append(f"{unknown} unknown roster statuses")
        if unmatched_count:
            reasons.append(f"{unmatched_count} slate injury row(s) failed exact identity reconciliation")
        st.warning("⚠️ STEP 3 FAIL-CLOSED • " + "; ".join(reasons or ["verification incomplete"]) + ". Step 4 remains locked.")

    st.caption(
        f"Roster source: {rdiag.get('source', '—')} • status source: ESPN WNBA injuries • feed timestamp: {timestamp or 'unavailable'} • "
        f"feed ET date: {report_day or 'unknown'} • same-day required: YES"
    )

    if not merged.empty:
        summary_rows = []
        for tid, team in meta.items():
            part = merged[pd.to_numeric(merged["TEAM_ID"], errors="coerce").fillna(0).astype(int).eq(int(tid))]
            summary_rows.append({
                "Team": team.get("name") or str(tid),
                "Players": len(part),
                "Flagged": int(part["AVAILABILITY"].isin(flagged_set).sum()),
                "OUT": int(part["AVAILABILITY"].eq("OUT").sum()),
                "QUESTIONABLE": int(part["AVAILABILITY"].eq("QUESTIONABLE").sum()),
                "PROBABLE": int(part["AVAILABILITY"].eq("PROBABLE").sum()),
                "Roster": "VERIFIED" if len(part) >= 5 else "CHECK",
            })
        st.dataframe(pd.DataFrame(summary_rows), hide_index=True, use_container_width=True)

        with st.expander("👥 Current roster + availability by slate team", expanded=False):
            for tid, team in meta.items():
                team_name = str(team.get("name") or tid)
                part = merged[pd.to_numeric(merged["TEAM_ID"], errors="coerce").fillna(0).astype(int).eq(int(tid))].copy()
                st.markdown(f"#### {team_name}")
                if part.empty:
                    st.error("No trustworthy current-roster rows.")
                    continue
                part["Player"] = part["PLAYER_NAME"].astype(str)
                part["Pos"] = part.get("POSITION", pd.Series("", index=part.index)).astype(str)
                part["Roster status"] = part.get("ROSTER_STATUS", pd.Series("ROSTERED", index=part.index)).astype(str)
                part["Availability"] = part["AVAILABILITY"].astype(str)
                part["Injury / reason"] = part["INJURY"].astype(str)
                part["Updated"] = part["INJURY_UPDATED"].astype(str)
                st.dataframe(
                    part[["Player", "Pos", "Roster status", "Availability", "Injury / reason", "Updated"]],
                    hide_index=True,
                    use_container_width=True,
                )

    if unmatched_count:
        with st.expander("🚨 Status rows requiring identity reconciliation", expanded=True):
            keep = [c for c in ("PLAYER_NAME", "TEAM_NAME", "AVAILABILITY", "INJURY", "SHORT_NOTE", "MATCH_REASON") if c in unmatched.columns]
            st.dataframe(unmatched[keep], hide_index=True, use_container_width=True)

    return ready


def render_wnba_assists_hub(section_header=None, status_info=None, team_logo=None, h=None):
    slate_day = datetime.now(_ET).strftime("%Y-%m-%d")
    slate = schedule.load_verified_wnba_slate(slate_day)
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
          <div class="ks-ast-kicker">KYRE SPORTS AI • WNBA ASSISTS INTELLIGENCE • STEP 3</div>
          <div class="ks-ast-title">🎯 WNBA Assists Command Center</div>
          <div class="ks-ast-sub">Steps 1–2 stay intact. Step 3 adds only current roster identity plus same-day injury/status verification. The gate fails closed: projected minutes and every later assists layer remain locked unless roster and status checks pass.</div>
          <span class="ks-ast-chip">📅 ET slate {slate_day}</span>
          <span class="ks-ast-chip">👥 current rosters</span>
          <span class="ks-ast-chip">🩺 same-day status gate</span>
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

    s1, s2 = st.columns(2)
    with s1:
        st.markdown(_source_box("WNBA official CDN", slate.get("wnba_meta", {}), int(slate.get("wnba_games", 0)), "authoritative schedule"), unsafe_allow_html=True)
    with s2:
        st.markdown(_source_box("ESPN WNBA daily", slate.get("espn_meta", {}), int(slate.get("espn_games", 0)), "independent confirmation"), unsafe_allow_html=True)

    if verification == "VERIFIED":
        st.success(f"✅ STEP 2 PASSED • {slate.get('games_found', 0)} WNBA game(s) belong to the {slate_day} ET slate. The repaired provider reconciliation remains unchanged.")
    elif verification == "NO GAMES":
        st.info(f"ℹ️ STEP 2 VERIFIED EMPTY • No WNBA games were returned for {slate_day} ET.")
    else:
        st.error("⛔ STEP 2 CHECK • The same-day slate could not be fully verified. Step 3 is not allowed to query downstream player status data.")

    games = slate.get("games", [])
    if games:
        table_rows = []
        for g in games:
            table_rows.append({
                "Away": g.get("away"),
                "Home": g.get("home"),
                "Tip (ET)": g.get("tip_et"),
                "Venue": g.get("venue"),
                "Status": g.get("status"),
                "Verified Source": g.get("source"),
                "ESPN Confirmed": "YES" if g.get("espn_confirmed") else "—",
            })
        st.dataframe(table_rows, use_container_width=True, hide_index=True)

    st.markdown("### 🩺 Step 3 — Current Rosters + Same-Day Injury / Status")
    step3_ready = _render_step3(slate, slate_day)

    if st.button("🔄 RECHECK ASSISTS SCHEDULE + STATUS", use_container_width=True, key="assists_step3_recheck"):
        schedule.load_verified_wnba_slate.clear()
        _current_rosters.clear()
        _injury_feed.clear()
        try:
            players._espn_roster.clear()
        except Exception:
            pass
        st.rerun()

    st.caption(f"Checked: {slate.get('checked_at_et', '—')} • Step 2 source: {slate.get('source', 'NONE')} • Step 3 gate: {'PASSED' if step3_ready else 'LOCKED'}")

    st.markdown("### 🧱 Assists Build Order — Current")
    layers = [
        (1, "Isolated Assists page", "✅ LIVE", "Display shell preserved"),
        (2, "Verified daily WNBA slate", "✅ LIVE" if verification in {"VERIFIED", "NO GAMES"} else "⚠️ CHECK", "Exact ET date + provider reconciliation"),
        (3, "Current rosters + injuries/status", "✅ LIVE" if step3_ready else "⚠️ CHECK", "Fail-closed current identity + same-day status"),
        (4, "Projected minutes + rotation", "➡️ NEXT" if step3_ready else "🔒 LOCKED", "Still not implemented"),
        (5, "Assist role + ball-handling / usage", "🔒 LOCKED", "Primary/secondary creation responsibility"),
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
                st.markdown(_layer_card(*item), unsafe_allow_html=True)

    with st.expander("🛡️ Step-3 methodology / diagnostics", expanded=False):
        st.write("• Step 2's repaired WNBA/ESPN schedule reconciliation is imported unchanged.")
        st.write("• Current roster identity uses ESPN WNBA team rosters only for teams on the verified slate.")
        st.write("• Injury/status identity matches exact player ID + same verified team first; exact normalized name + same team is the only fallback.")
        st.write("• No fuzzy matching and no cross-team matching are allowed.")
        st.write("• The status feed must carry the same Eastern calendar date as the slate and be no older than 12 hours.")
        st.write("• A rostered player absent from the injury feed is labeled NOT LISTED, not ACTIVE.")
        st.write("• Any missing roster, stale/unavailable status feed, unknown status, or unmatched slate injury row locks Step 4.")
        st.write("• Projected-minutes requests: 0")
        st.write("• Assist-stat requests: 0")
        st.write("• SportsGameOdds requests: 0")
        st.write("• Monte Carlo runs: 0")
        st.write("• PRA / Points / Rebounds / Daily Picks production imports by this Assists layer: 0")

    st.caption("⚡ WNBA Assists V3 Step 3 • Steps 1–2 preserved • current roster + same-day status gate only • Step 4 remains locked until PASS")


__all__ = ["MODEL_VERSION", "render_wnba_assists_hub"]
