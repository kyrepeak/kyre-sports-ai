"""WNBA Rebounds V1.1 — Step 2 current rosters + injury/status verification.

This layer keeps V1.0's verified Eastern-date slate intact and adds only:
- compact current rosters for every verified slate team;
- structured WNBA injury/status rows;
- conservative status normalization and source-freshness diagnostics;
- a hard gate that prevents Step 3 from opening when roster or availability
  identity is incomplete.

No rebound projection, minutes model, sportsbook grading, matchup factor or
Monte Carlo is enabled here. Frozen Points/PRA/MLB production math is untouched.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_players_v25 as players
import wnba_rebounds_hub_v10 as step1
import wnba_schedule_v24 as schedule24
import wnba_schedule_v25 as schedule

ET = ZoneInfo("America/New_York")
ESPN_INJURIES = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/injuries"
MODEL_VERSION = "WNBA REBOUNDS V1.1 • STEP 2 ROSTER + AVAILABILITY"


def _today_et():
    return datetime.now(ET).date()


def _safe_day(value) -> str:
    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now(ET).strftime("%Y-%m-%d")


def _int(value, default=0):
    try:
        return int(float(value))
    except Exception:
        return int(default)


def _norm(value) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _team_meta(frame: pd.DataFrame) -> dict:
    meta = {}
    if frame is None or frame.empty:
        return meta
    for _, row in frame.iterrows():
        for side in ("away", "home"):
            tid = _int(row.get(f"{side}_team_id"))
            if tid:
                meta[tid] = {
                    "name": str(row.get(f"{side}_team") or ""),
                    "abbr": str(row.get(f"{side}_tricode") or ""),
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
    if {"TEAM_ID", "PLAYER_ID"}.issubset(out.columns):
        out = out.drop_duplicates(["TEAM_ID", "PLAYER_ID"], keep="first")
    if len(out) < 5 or len(out) > 22:
        return pd.DataFrame()
    return out.reset_index(drop=True)


@st.cache_data(ttl=300, show_spinner=False)
def _current_rosters(day_str: str):
    frame = schedule.schedule_for_date(day_str)
    meta = _team_meta(frame)
    frames, team_modes = [], {}
    for tid in sorted(meta):
        team = meta.get(tid, {})
        try:
            roster = _sanitize_roster(
                players._espn_roster(tid, team.get("name", ""), team.get("abbr", ""))
            )
        except Exception:
            roster = pd.DataFrame()
        if roster is not None and not roster.empty:
            roster = roster.copy()
            if "ROSTER_SOURCE" not in roster.columns:
                roster["ROSTER_SOURCE"] = "ESPN WNBA current roster"
            else:
                roster["ROSTER_SOURCE"] = roster["ROSTER_SOURCE"].fillna("ESPN WNBA current roster")
            frames.append(roster)
            team_modes[tid] = "CURRENT_ROSTER"
        else:
            team_modes[tid] = "MISSING"
    roster = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not roster.empty and {"TEAM_ID", "PLAYER_ID"}.issubset(roster.columns):
        roster = roster.drop_duplicates(["TEAM_ID", "PLAYER_ID"], keep="first")
    covered = set(pd.to_numeric(roster.get("TEAM_ID"), errors="coerce").dropna().astype(int).tolist()) if not roster.empty else set()
    return roster, {
        "teams": len(meta),
        "covered_teams": len(covered),
        "missing_teams": max(0, len(meta) - len(covered)),
        "players": len(roster),
        "team_modes": team_modes,
        "source": "ESPN WNBA current roster",
    }


def _injury_status(item: dict) -> str:
    details = item.get("details") or {}
    fantasy = details.get("fantasyStatus") or {}
    text = " ".join([
        str(item.get("status") or ""),
        str(item.get("shortComment") or ""),
        str(item.get("longComment") or ""),
        str(item.get("type") or ""),
        str(details.get("type") or ""),
        str(fantasy.get("description") or ""),
        str(fantasy.get("abbreviation") or ""),
    ]).lower()
    if any(x in text for x in ("ruled out", "will miss", "out indefinitely", " out ", "status out")):
        return "OUT"
    if "doubtful" in text:
        return "DOUBTFUL"
    if "probable" in text:
        return "PROBABLE"
    if "questionable" in text:
        return "QUESTIONABLE"
    if any(x in text for x in ("day-to-day", "day to day", "gtd", "game-time decision")):
        return "QUESTIONABLE"
    if "inactive" in text:
        return "INACTIVE"
    return "REPORTED"


@st.cache_data(ttl=180, show_spinner=False)
def _injury_feed():
    payload, meta = schedule24._request_json(
        "ESPN WNBA injuries", ESPN_INJURIES, timeout=8, attempts=2
    )
    if payload is None:
        return pd.DataFrame(), dict(meta or {}), ""
    timestamp = str((payload or {}).get("timestamp") or "")
    rows = []
    for team_block in (payload or {}).get("injuries", []) or []:
        team_name = str(team_block.get("displayName") or "")
        for item in team_block.get("injuries", []) or []:
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
        frame = frame.drop_duplicates(["PLAYER_ID", "TEAM_NAME"], keep="first")
    return frame, dict(meta or {}), timestamp


def _feed_age_hours(timestamp: str):
    if not timestamp:
        return None
    try:
        ts = pd.to_datetime(timestamp, utc=True)
        return max(0.0, float((pd.Timestamp.now(tz="UTC") - ts).total_seconds() / 3600.0))
    except Exception:
        return None


def _overlay_availability(roster, injuries, slate, feed_ok):
    if roster is None or roster.empty:
        return pd.DataFrame(), pd.DataFrame()
    out = roster.copy()
    out["PLAYER_ID"] = out["PLAYER_ID"].astype(str)
    out["AVAILABILITY"] = "NOT LISTED" if feed_ok else "UNKNOWN"
    out["INJURY"] = ""
    out["INJURY_NOTE"] = ""
    out["INJURY_UPDATED"] = ""
    out["INJURY_SOURCE"] = "ESPN WNBA injuries" if feed_ok else "unavailable"
    if injuries is None or injuries.empty:
        return out, pd.DataFrame()

    slate_names, slate_abbrs = {}, {}
    for tid, meta in _team_meta(slate).items():
        slate_names[_norm(meta.get("name"))] = tid
        slate_abbrs[_norm(meta.get("abbr"))] = tid
    injuries = injuries.copy()
    injuries["_slate_team_id"] = injuries.apply(
        lambda r: slate_names.get(_norm(r.get("TEAM_NAME"))) or slate_abbrs.get(_norm(r.get("TEAM_ABBR"))) or 0,
        axis=1,
    )
    slate_inj = injuries[injuries["_slate_team_id"].astype(int).ne(0)].copy()
    idx_by_pid = {}
    for idx, row in out.iterrows():
        idx_by_pid.setdefault(str(row.get("PLAYER_ID") or ""), []).append(idx)
    unmatched = []
    for _, inj in slate_inj.iterrows():
        pid = str(inj.get("PLAYER_ID") or "")
        matched_idx = None
        for idx in idx_by_pid.get(pid, []):
            if _int(out.at[idx, "TEAM_ID"]) == _int(inj.get("_slate_team_id")):
                matched_idx = idx
                break
        if matched_idx is None:
            unmatched.append(inj.to_dict())
            continue
        out.at[matched_idx, "AVAILABILITY"] = str(inj.get("AVAILABILITY") or "REPORTED")
        out.at[matched_idx, "INJURY"] = str(inj.get("INJURY") or "")
        out.at[matched_idx, "INJURY_NOTE"] = str(inj.get("SHORT_NOTE") or "")
        out.at[matched_idx, "INJURY_UPDATED"] = str(inj.get("UPDATED") or "")
    return out, pd.DataFrame(unmatched)


def _render_step2(slate: pd.DataFrame, day: str):
    roster, rdiag = _current_rosters(day)
    injuries, imeta, timestamp = _injury_feed()
    feed_ok = bool(imeta.get("request_ok"))
    age_h = _feed_age_hours(timestamp)
    feed_fresh = bool(feed_ok and age_h is not None and age_h <= 12.0)
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

    st.markdown("## 🩺 Step 2 — Current Rosters + Injuries / Status")
    st.caption(
        "Current roster identity uses compact ESPN WNBA team rosters. Structured injury designations use the ESPN WNBA injuries feed. "
        "A player missing from the injury feed is labeled NOT LISTED, never silently converted to ACTIVE."
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Roster teams", f"{covered}/{teams}" if teams else "0/0")
    c2.metric("Current players", len(merged))
    c3.metric("Injury flags", flagged)
    c4.metric("Feed age", "—" if age_h is None else f"{age_h:.1f}h")

    if ready:
        st.success("✅ STEP 2 PASSED • every verified slate team has a compact current roster, the structured injury feed is fresh, and every slate injury row reconciles to a current-roster player.")
    elif roster_ready:
        reasons = []
        if not feed_ok:
            reasons.append("injury feed unavailable")
        elif not feed_fresh:
            reasons.append("injury feed aging/stale")
        if unknown:
            reasons.append(f"{unknown} unknown player statuses")
        if unmatched_count:
            reasons.append(f"{unmatched_count} slate injury row(s) do not reconcile to the current roster")
        st.warning("⚠️ ROSTER VERIFIED / AVAILABILITY PARTIAL • " + "; ".join(reasons or ["availability confirmation incomplete"]) + ". Step 3 remains locked.")
    else:
        st.error(f"⛔ STEP 2 BLOCKED • current-roster coverage is {covered}/{teams}; {missing} slate team(s) are missing a trustworthy compact roster. Step 3 remains locked.")

    st.caption(
        f"Roster source: {rdiag.get('source','—')} • injury source: ESPN WNBA injuries • feed timestamp: {timestamp or 'unavailable'} • "
        "official WNBA injury report remains the league-authoritative reference."
    )

    if not merged.empty:
        meta = _team_meta(slate)
        rows = []
        for tid, team in meta.items():
            part = merged[pd.to_numeric(merged["TEAM_ID"], errors="coerce").fillna(0).astype(int).eq(int(tid))]
            rows.append({
                "Team": team.get("name") or str(tid),
                "Players": len(part),
                "Flagged": int(part["AVAILABILITY"].isin(flagged_set).sum()),
                "OUT": int(part["AVAILABILITY"].eq("OUT").sum()),
                "QUESTIONABLE": int(part["AVAILABILITY"].eq("QUESTIONABLE").sum()),
                "PROBABLE": int(part["AVAILABILITY"].eq("PROBABLE").sum()),
                "Roster": "VERIFIED" if len(part) >= 5 else "CHECK",
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

        with st.expander("👥 Team-by-team current roster + availability", expanded=False):
            for tid, team in meta.items():
                team_name = str(team.get("name") or tid)
                part = merged[pd.to_numeric(merged["TEAM_ID"], errors="coerce").fillna(0).astype(int).eq(int(tid))].copy()
                st.markdown(f"#### {team_name}")
                if part.empty:
                    st.error("No current roster rows.")
                    continue
                part["Player"] = part["PLAYER_NAME"].astype(str)
                part["Pos"] = part.get("POSITION", pd.Series("", index=part.index)).astype(str)
                part["Roster status"] = part.get("ROSTER_STATUS", pd.Series("ROSTERED", index=part.index)).astype(str)
                part["Availability"] = part["AVAILABILITY"].astype(str)
                part["Injury / reason"] = part["INJURY"].astype(str)
                part["Updated"] = part["INJURY_UPDATED"].astype(str)
                st.dataframe(part[["Player", "Pos", "Roster status", "Availability", "Injury / reason", "Updated"]], hide_index=True, use_container_width=True)

    if unmatched_count:
        with st.expander("🚨 Injury rows requiring roster reconciliation", expanded=True):
            keep = [c for c in ("PLAYER_NAME", "TEAM_NAME", "AVAILABILITY", "INJURY", "SHORT_NOTE", "UPDATED") if c in unmatched.columns]
            st.dataframe(unmatched[keep], hide_index=True, use_container_width=True)

    with st.expander("🔬 Step-2 source diagnostics", expanded=False):
        st.write({
            "roster_state": "VERIFIED" if roster_ready else "CHECK",
            "roster_teams": f"{covered}/{teams}",
            "roster_players": len(merged),
            "roster_team_modes": rdiag.get("team_modes", {}),
            "injury_http": imeta.get("http"),
            "injury_request_ok": feed_ok,
            "injury_feed_timestamp": timestamp or None,
            "injury_feed_age_hours": None if age_h is None else round(age_h, 2),
            "injury_feed_fresh_under_12h": feed_fresh,
            "slate_injury_flags": flagged,
            "unknown_status_rows": unknown,
            "unmatched_slate_injury_rows": unmatched_count,
            "step2_ready": ready,
        })

    return {
        "ready": ready, "roster_ready": roster_ready, "availability_ready": availability_ready,
        "roster_players": len(merged), "teams": teams, "covered_teams": covered,
        "flagged": flagged, "unmatched": unmatched_count, "feed_age_hours": age_h,
    }


def _tracker(step1_ok: bool, step2_info: dict):
    step2_ok = bool((step2_info or {}).get("ready"))
    labels = [
        ("1", "Verified daily WNBA slate"), ("2", "Current rosters + injuries/status"),
        ("3", "Projected minutes + rotation"), ("4", "Offensive/defensive rebound role"),
        ("5", "Recent + season rebound form"), ("6", "Rebound chances/opportunities"),
        ("7", "Opponent missed-shot environment"), ("8", "Opponent rebounding allowed"),
        ("9", "Position matchup — Guard/Wing/Big"), ("10", "Pace + expected shot volume"),
        ("11", "Lineup effects / rebound competition"), ("12", "Player vs opponent rebound history"),
        ("13", "Exact SportsGameOdds rebound lines"), ("14", "Same-book no-vig"),
        ("15", "Empirical rebound variance"), ("16", "Real 5M Monte Carlo"),
        ("17", "Selective 10M finalist pass"), ("18", "BEST / STRONG / MONITOR / AVOID"),
        ("19", "Top Rebound Candidates"), ("20", "Rich cards + Why this pick?"),
        ("21", "Out-of-sample calibration ledger"), ("22", "WNBA Daily Master Card handoff"),
    ]
    rows = []
    for n, label in labels:
        if n == "1":
            status = "✅ LIVE" if step1_ok else "⛔ CHECK"
        elif n == "2":
            status = "✅ LIVE" if step2_ok else ("⚠️ ACTIVE / CHECK" if step1_ok else "🔒 LOCKED")
        elif n == "3" and step2_ok:
            status = "➡️ NEXT"
        else:
            status = "🔒 LOCKED"
        rows.append({"Step": n, "Layer": label, "Status": status})
    return pd.DataFrame(rows)


def render_wnba_rebounds_hub(section_header=None, status_info=None, _unused=None, h=None):
    st.caption("🏀 WNBA Rebounds V1.1 • Step 2 current rosters + injuries/status • no rebound projection yet • Points/PRA/MLB frozen")
    selected = st.date_input("WNBA Rebounds slate date", value=_today_et(), key="wnba_rebounds_date")
    day = _safe_day(selected)

    st.markdown(
        '''<div style="border:1px solid #27658a;border-radius:24px;padding:20px 22px;background:#071b2c;margin:10px 0 16px">
        <div style="font-size:.72rem;letter-spacing:.15em;font-weight:800;color:#5dd6ff">KYRE SPORTS AI • WNBA REBOUNDS • ISOLATED PRODUCTION PAGE</div>
        <div style="font-size:2rem;font-weight:900;color:#f7f9fc;margin-top:8px">🏀 WNBA Rebounds Command Center — V1.1</div>
        <div style="color:#9fb1c1;margin-top:8px">Steps 1–2 only: verify the Eastern-date slate, then verify current roster identity and player availability before any rebound projection is allowed to exist.</div></div>''',
        unsafe_allow_html=True,
    )

    try:
        frame = schedule.schedule_for_date(day)
        diag = schedule.schedule_diagnostics(day)
    except Exception as exc:
        frame = pd.DataFrame(columns=schedule.SCHEDULE_COLUMNS)
        diag = {"state": "PROVIDER_FAILURE", "games": 0, "teams": 0, "attempts": [], "error": str(exc)}
    if not isinstance(frame, pd.DataFrame):
        frame = pd.DataFrame(columns=schedule.SCHEDULE_COLUMNS)

    state = str((diag or {}).get("state") or "PROVIDER_FAILURE")
    games = len(frame)
    teams = set()
    if not frame.empty:
        teams.update(pd.to_numeric(frame.get("away_team_id"), errors="coerce").dropna().astype(int).tolist())
        teams.update(pd.to_numeric(frame.get("home_team_id"), errors="coerce").dropna().astype(int).tolist())
    statuses = frame.get("status", pd.Series(dtype=str)).astype(str).str.upper() if not frame.empty else pd.Series(dtype=str)
    upcoming, live, final = int(statuses.eq("UPCOMING").sum()), int(statuses.eq("LIVE").sum()), int(statuses.eq("FINAL").sum())
    step1_ok = bool(state == "VERIFIED")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Verification", "VERIFIED" if state.startswith("VERIFIED") else "CHECK")
    c2.metric("Slate games", games)
    c3.metric("WNBA teams", len(teams))
    c4.metric("Upcoming", upcoming)

    if state == "PROVIDER_FAILURE":
        st.error("❌ STEP 1 BLOCKED • WNBA schedule providers did not produce a trustworthy slate. Later Rebounds layers remain locked.")
    elif state == "VERIFIED_OFF_DAY":
        st.success(f"✅ VERIFIED WNBA OFF-DAY • {day}.")
    elif state == "VERIFIED_SINGLE_SOURCE":
        st.warning(f"⚠️ STEP 1 PARTIAL • {games} game(s) found, but only one schedule path currently confirms the slate. Step 3 remains locked.")
    else:
        confirming = len((diag or {}).get("confirming_sources", []) or [])
        st.success(f"✅ STEP 1 PASSED • {games} WNBA game(s) verified for {day} Eastern Time • {len(teams)} teams • confirmed by {confirming} schedule path(s).")

    if games:
        st.markdown("## 🗓️ Today’s Verified WNBA Rebound Slate")
        step1._render_game_cards(frame)
        table = frame.copy()
        table["Matchup"] = table["away_team"].astype(str) + " @ " + table["home_team"].astype(str)
        table["Tip (ET)"] = table["first_tip_et"].astype(str)
        table["Venue"] = table["venue"].astype(str)
        table["Status"] = table["status"].astype(str)
        table["Verified source"] = table["source"].astype(str)
        st.dataframe(table[["Matchup", "Tip (ET)", "Venue", "Status", "Verified source"]], hide_index=True, use_container_width=True)

    with st.expander("🧭 Step-1 verification details", expanded=False):
        st.write({
            "selected_date": day, "timezone_rule": (diag or {}).get("timezone_rule", "America/New_York slate date"),
            "state": state, "chosen_source": (diag or {}).get("chosen_source", "none"),
            "confirming_sources": (diag or {}).get("confirming_sources", []),
            "source_selected_counts": (diag or {}).get("source_selected_counts", {}),
            "live_games": live, "final_games": final,
        })
        source_df = step1._source_diagnostics(diag or {})
        if not source_df.empty:
            st.dataframe(source_df, hide_index=True, use_container_width=True)

    step2_info = {"ready": False, "roster_players": 0, "flagged": 0}
    if games and state.startswith("VERIFIED"):
        step2_info = _render_step2(frame, day)
    else:
        st.info("Step 2 is waiting for a verified non-empty slate.")

    if st.button("🔄 RECHECK REBOUNDS SCHEDULE + ROSTER / INJURY FEEDS", use_container_width=True, key="wnba_rebounds_recheck_v11"):
        schedule.clear_schedule_cache()
        try: _current_rosters.clear()
        except Exception: pass
        try: _injury_feed.clear()
        except Exception: pass
        st.rerun()

    st.markdown("## 🧱 Rebounds Build Order")
    st.dataframe(_tracker(step1_ok, step2_info), hide_index=True, use_container_width=True)
    if step2_info.get("ready"):
        st.success("✅ STEPS 1–2 VERIFIED • Step 3 (projected minutes + rotation) is now the next unlocked development layer. No rebound projection has been created yet.")
    else:
        st.info("Step 2 is active. Step 3 stays locked until both current-roster identity and structured availability status pass. No Rebounds projection, sportsbook grading or Monte Carlo exists yet.")

    st.session_state["wnba_rebounds_step1_state"] = state
    st.session_state["wnba_rebounds_step1_day"] = day
    st.session_state["wnba_rebounds_step1_games"] = games
    st.session_state["wnba_rebounds_step2_ready"] = bool(step2_info.get("ready"))
    st.session_state["wnba_rebounds_step2_roster_players"] = int(step2_info.get("roster_players") or 0)
    st.session_state["wnba_rebounds_step2_flagged"] = int(step2_info.get("flagged") or 0)


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
