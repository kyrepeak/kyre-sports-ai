"""WNBA Rebounds V1.2 — Steps 1-3 verified slate, availability, and rotation minutes.

This module keeps the Step-1 schedule and Step-2 identity-safe injury overlay,
then adds only the Rebounds projected-minutes / rotation layer.

Step 3 rules:
- use only current-roster players from the verified Step-2 gate;
- reconstruct each team's last 10 completed WNBA rotations before the slate;
- a current-roster player missing from a verified box score counts as 0 minutes;
- blend L3/L5/L10 team-rotation minutes (50/30/20) as the playing-time anchor;
- OUT / INACTIVE / DOUBTFUL players receive 0 projected minutes;
- QUESTIONABLE / PROBABLE are not silently discounted; they remain status risks;
- normalize each active team to exactly 200 regulation minutes with a 40-min cap;
- sportsbook lines never influence minutes;
- no rebound projection, market grading, variance, or Monte Carlo exists yet.

Frozen WNBA Points/PRA and MLB production math is untouched.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_players_v25 as players
import wnba_rebounds_hub_v11 as base

MODEL_VERSION = "WNBA REBOUNDS V1.2 • STEP 3 ROTATION MINUTES"
ZERO_MIN_STATUSES = {"OUT", "INACTIVE", "DOUBTFUL"}
_ORIGINAL_STEP2 = base._render_step2
_ORIGINAL_TRACKER = base._tracker
_ORIGINAL_MARKDOWN = st.markdown


def _status_token(value) -> str:
    if isinstance(value, dict):
        value = " ".join(
            str(value.get(k) or "")
            for k in ("name", "type", "description", "abbreviation", "displayName")
        )
    return " ".join(str(value or "").strip().lower().replace("_", " ").split())


def _pick_designation(text: str):
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


def _injury_status(item: dict) -> str:
    """Prefer ESPN structured availability, then provider narrative."""
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
            item.get("shortComment"), item.get("longComment"), item.get("type"),
            details.get("type"),
            fantasy.get("description") if isinstance(fantasy, dict) else "",
            fantasy.get("abbreviation") if isinstance(fantasy, dict) else "",
        )
    )
    return _pick_designation(_status_token(narrative)) or "REPORTED"


def _overlay_availability(roster, injuries, slate, feed_ok):
    """Conservative injury-to-current-roster reconciliation."""
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

    slate_names, slate_abbrs = {}, {}
    for tid, meta in base._team_meta(slate).items():
        slate_names[base._norm(meta.get("name"))] = tid
        slate_abbrs[base._norm(meta.get("abbr"))] = tid

    inj = injuries.copy()
    inj["_slate_team_id"] = inj.apply(
        lambda r: slate_names.get(base._norm(r.get("TEAM_NAME")))
        or slate_abbrs.get(base._norm(r.get("TEAM_ABBR"))) or 0,
        axis=1,
    )
    inj = inj[inj["_slate_team_id"].astype(int).ne(0)].copy()

    by_pid, by_name_team = {}, {}
    for idx, row in out.iterrows():
        pid = str(row.get("PLAYER_ID") or "")
        tid = base._int(row.get("TEAM_ID"))
        pname = base._norm(row.get("PLAYER_NAME"))
        if pid:
            by_pid.setdefault(pid, []).append(idx)
        if tid and pname:
            by_name_team.setdefault((tid, pname), []).append(idx)

    unmatched = []
    for _, row in inj.iterrows():
        pid = str(row.get("PLAYER_ID") or "")
        tid = base._int(row.get("_slate_team_id"))
        pname = base._norm(row.get("PLAYER_NAME"))
        matched_idx, match_mode = None, ""
        id_matches = [idx for idx in by_pid.get(pid, []) if base._int(out.at[idx, "TEAM_ID"]) == tid]
        if len(id_matches) == 1:
            matched_idx, match_mode = id_matches[0], "ESPN_ID_EXACT"
        if matched_idx is None:
            name_matches = by_name_team.get((tid, pname), []) if tid and pname else []
            if len(name_matches) == 1:
                matched_idx, match_mode = name_matches[0], "NAME_TEAM_EXACT"
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


def _day(value) -> str:
    return pd.to_datetime(value).strftime("%Y-%m-%d")


def _num(value, default=0.0):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


@st.cache_data(ttl=900, show_spinner=False, max_entries=64)
def _recent_rotation(day_str: str, team_id: int, player_ids: tuple[int, ...]):
    """Return current-roster L1/L3/L5/L10 minutes from verified team games."""
    day_str = _day(day_str)
    tid = int(team_id or 0)
    ids = tuple(sorted({int(x) for x in player_ids if int(x) > 0}))
    if not tid or not ids:
        return {}, 0

    try:
        season = players._espn_season_schedule(pd.to_datetime(day_str).year)
    except Exception:
        season = pd.DataFrame()
    if season is None or season.empty:
        return {}, 0

    before = pd.to_datetime(season.get("game_date"), errors="coerce") < pd.to_datetime(day_str)
    final = season.get("status", pd.Series("", index=season.index)).astype(str).str.upper().eq("FINAL")
    team_mask = (
        pd.to_numeric(season.get("away_team_id"), errors="coerce").eq(tid)
        | pd.to_numeric(season.get("home_team_id"), errors="coerce").eq(tid)
    )
    games = season.loc[before & final & team_mask].copy()
    if games.empty:
        return {}, 0
    games["_d"] = pd.to_datetime(games["game_date"], errors="coerce")
    games = games.sort_values("_d", ascending=False).drop_duplicates("game_id").head(10)

    minute_maps = []
    for _, game in games.iterrows():
        gid = str(game.get("game_id") or "")
        gdate = str(game.get("game_date") or "")
        if not gid:
            continue
        try:
            box = players._espn_game_summary(gid, gdate)
        except Exception:
            box = pd.DataFrame()
        if box is None or box.empty or "TEAM_ID" not in box.columns:
            continue
        part = box.loc[pd.to_numeric(box["TEAM_ID"], errors="coerce").eq(tid)].copy()
        if part.empty:
            continue
        m = {}
        for _, row in part.iterrows():
            try:
                pid = int(float(row.get("PLAYER_ID")))
            except Exception:
                continue
            m[pid] = max(0.0, _num(row.get("MIN"), 0.0))
        minute_maps.append(m)

    n = len(minute_maps)
    if not n:
        return {}, 0
    result = {}
    for pid in ids:
        vals = [float(m.get(pid, 0.0)) for m in minute_maps]
        result[pid] = {
            "games": n,
            "l1": vals[0] if vals else 0.0,
            "l3": float(np.mean(vals[: min(3, n)])),
            "l5": float(np.mean(vals[: min(5, n)])),
            "l10": float(np.mean(vals[: min(10, n)])),
        }
    return result, n


def _normalize_200(anchors: pd.Series) -> pd.Series:
    vals = pd.to_numeric(anchors, errors="coerce").fillna(0.0).clip(lower=0.0)
    result = pd.Series(0.0, index=vals.index, dtype=float)
    remaining = list(vals[vals.gt(0)].index)
    fixed = {}
    for _ in range(12):
        if not remaining:
            break
        target = max(0.0, 200.0 - sum(fixed.values()))
        denom = float(vals.loc[remaining].sum())
        scaled = (
            vals.loc[remaining] * (target / denom)
            if denom > 0 else pd.Series(target / len(remaining), index=remaining)
        )
        over = scaled[scaled > 40.0]
        if over.empty:
            for idx, value in scaled.items():
                fixed[idx] = float(max(0.0, value))
            remaining = []
            break
        for idx in list(over.index):
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


def _build_step3_minutes(slate: pd.DataFrame, day: str, merged: pd.DataFrame):
    if merged is None or merged.empty:
        return pd.DataFrame(), pd.DataFrame(), {"ready": False, "reason": "no current-roster rows"}
    roster = merged.copy()
    roster["TEAM_ID_NUM"] = pd.to_numeric(roster.get("TEAM_ID"), errors="coerce").fillna(0).astype(int)
    roster["AVAILABILITY"] = roster.get("AVAILABILITY", pd.Series("UNKNOWN", index=roster.index)).astype(str).str.upper()
    meta = base._team_meta(slate)
    player_frames, team_rows = [], []

    for tid, team_meta in meta.items():
        part = roster.loc[roster["TEAM_ID_NUM"].eq(int(tid))].copy()
        ids = []
        for value in part.get("PLAYER_ID", pd.Series(dtype=str)):
            try:
                ids.append(int(float(value)))
            except Exception:
                pass
        recent, game_count = _recent_rotation(day, int(tid), tuple(ids))
        anchors = []
        l1s, l3s, l5s, l10s, samples = [], [], [], [], []
        for _, row in part.iterrows():
            try:
                pid = int(float(row.get("PLAYER_ID")))
            except Exception:
                pid = 0
            info = recent.get(pid) or {}
            l1 = _num(info.get("l1"), 0.0)
            l3 = _num(info.get("l3"), 0.0)
            l5 = _num(info.get("l5"), 0.0)
            l10 = _num(info.get("l10"), 0.0)
            status = str(row.get("AVAILABILITY") or "UNKNOWN").upper()
            anchor = 0.50 * l3 + 0.30 * l5 + 0.20 * l10
            if status in ZERO_MIN_STATUSES:
                anchor = 0.0
            elif anchor < 0.35:
                anchor = 0.0
            anchors.append(anchor)
            l1s.append(l1); l3s.append(l3); l5s.append(l5); l10s.append(l10); samples.append(game_count)

        part["L1_MIN"] = l1s
        part["L3_MIN"] = l3s
        part["L5_MIN"] = l5s
        part["L10_MIN"] = l10s
        part["ROTATION_GAMES"] = samples
        part["MINUTE_ANCHOR"] = anchors
        active = ~part["AVAILABILITY"].isin(ZERO_MIN_STATUSES)
        part["PROJ_MIN"] = 0.0
        scaled = _normalize_200(part.loc[active, "MINUTE_ANCHOR"])
        part.loc[active, "PROJ_MIN"] = scaled
        part.loc[~active, "PROJ_MIN"] = 0.0
        part["MIN_DELTA_L5"] = part["PROJ_MIN"] - part["L5_MIN"]
        part["ROTATION_STATUS"] = np.where(
            part["AVAILABILITY"].isin(ZERO_MIN_STATUSES), "ZERO — STATUS",
            np.where(part["PROJ_MIN"].ge(24.0), "CORE", np.where(part["PROJ_MIN"].ge(10.0), "ROTATION", "FRINGE"))
        )
        player_frames.append(part)

        team_total = float(part["PROJ_MIN"].sum())
        zero_status_ok = bool(part.loc[part["AVAILABILITY"].isin(ZERO_MIN_STATUSES), "PROJ_MIN"].abs().le(1e-9).all())
        range_ok = bool(part["PROJ_MIN"].between(0.0, 40.0).all())
        sample_ok = bool(game_count >= 3)
        total_ok = bool(abs(team_total - 200.0) <= 0.05)
        team_ready = bool(sample_ok and total_ok and zero_status_ok and range_ok)
        team_rows.append({
            "Team": team_meta.get("name") or str(tid),
            "Roster": len(part),
            "Rotation": int(part["PROJ_MIN"].ge(5.0).sum()),
            "Recent games": game_count,
            "Projected MIN": round(team_total, 1),
            "Status-zero": "PASS" if zero_status_ok else "FAIL",
            "State": "VERIFIED" if team_ready else "CHECK",
        })

    players_out = pd.concat(player_frames, ignore_index=True) if player_frames else pd.DataFrame()
    teams_out = pd.DataFrame(team_rows)
    expected_teams = len(meta)
    ready_teams = int(teams_out["State"].eq("VERIFIED").sum()) if not teams_out.empty else 0
    ready = bool(expected_teams > 0 and ready_teams == expected_teams and not players_out.empty)
    return players_out, teams_out, {
        "ready": ready,
        "teams": expected_teams,
        "ready_teams": ready_teams,
        "players": len(players_out),
        "rotation_players": int(players_out["PROJ_MIN"].ge(5.0).sum()) if not players_out.empty else 0,
        "zero_status_players": int(players_out["AVAILABILITY"].isin(ZERO_MIN_STATUSES).sum()) if not players_out.empty else 0,
        "source": "ESPN WNBA completed box scores • current-roster L3/L5/L10 rotation",
    }


def _render_step3(slate: pd.DataFrame, day: str, merged: pd.DataFrame):
    players_out, teams_out, info = _build_step3_minutes(slate, day, merged)
    st.markdown("## ⏱️ Step 3 — Projected Minutes + Rotation")
    st.caption(
        "Projected playing time is built before any rebound rate exists. Current-roster L3/L5/L10 team rotations are blended 50/30/20, "
        "DNPs count as zero, OUT/INACTIVE/DOUBTFUL stay at zero, and every active team must reconcile to exactly 200 minutes. Sportsbook lines are not inputs."
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Team-minute checks", f"{info.get('ready_teams',0)}/{info.get('teams',0)}")
    c2.metric("Roster players", info.get("players", 0))
    c3.metric("Rotation ≥5 MIN", info.get("rotation_players", 0))
    c4.metric("Team target", "200")

    if info.get("ready"):
        st.success("✅ STEP 3 PASSED • all slate teams reconcile to 200 projected regulation minutes with status-zero and 40-minute-cap checks passing.")
    else:
        st.error("⛔ STEP 3 CHECK • at least one team's verified recent-rotation sample or minute reconciliation failed. Step 4 remains locked.")

    if not teams_out.empty:
        st.dataframe(teams_out, hide_index=True, use_container_width=True)
    if not players_out.empty:
        show = players_out.copy()
        show["Player"] = show.get("PLAYER_NAME", pd.Series("Player", index=show.index)).astype(str)
        show["Team"] = show.get("TEAM_NAME", pd.Series("", index=show.index)).astype(str)
        show["Pos"] = show.get("POSITION", pd.Series("", index=show.index)).astype(str)
        show["Availability"] = show["AVAILABILITY"].astype(str)
        show["L3"] = pd.to_numeric(show["L3_MIN"], errors="coerce").round(1)
        show["L5"] = pd.to_numeric(show["L5_MIN"], errors="coerce").round(1)
        show["L10"] = pd.to_numeric(show["L10_MIN"], errors="coerce").round(1)
        show["Proj MIN"] = pd.to_numeric(show["PROJ_MIN"], errors="coerce").round(1)
        show["Δ vs L5"] = pd.to_numeric(show["MIN_DELTA_L5"], errors="coerce").round(1)
        show["Rotation role"] = show["ROTATION_STATUS"].astype(str)
        with st.expander("👟 Player projected-minute board", expanded=False):
            st.dataframe(
                show[["Player", "Team", "Pos", "Availability", "L3", "L5", "L10", "Proj MIN", "Δ vs L5", "Rotation role"]],
                hide_index=True,
                use_container_width=True,
            )
            st.caption("QUESTIONABLE/PROBABLE are displayed as uncertainty flags but are not silently discounted at Step 3. Later lineup effects can alter the final rotation only when verified evidence arrives.")

    st.session_state["wnba_rebounds_step3_ready"] = bool(info.get("ready"))
    st.session_state["wnba_rebounds_step3_players"] = players_out.to_dict("records") if not players_out.empty else []
    st.session_state["wnba_rebounds_step3_team_checks"] = teams_out.to_dict("records") if not teams_out.empty else []
    return info


def _step2_plus_minutes(slate: pd.DataFrame, day: str):
    info = _ORIGINAL_STEP2(slate, day)
    if not bool((info or {}).get("ready")):
        st.info("🔒 Step 3 remains locked until the Step-2 current-roster + availability gate passes.")
        out = dict(info or {})
        out["step3_ready"] = False
        return out

    roster, _ = base._current_rosters(day)
    injuries, imeta, _ = base._injury_feed()
    merged, _ = base._overlay_availability(roster, injuries, slate, bool((imeta or {}).get("request_ok")))
    step3 = _render_step3(slate, day, merged)
    out = dict(info or {})
    out["step3_ready"] = bool(step3.get("ready"))
    out["step3_info"] = step3
    return out


def _tracker(step1_ok: bool, step2_info: dict):
    step2_ok = bool((step2_info or {}).get("ready"))
    step3_ok = bool((step2_info or {}).get("step3_ready"))
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
        elif n == "3":
            status = "✅ LIVE" if step3_ok else ("➡️ NEXT" if step2_ok else "🔒 LOCKED")
        elif n == "4" and step3_ok:
            status = "➡️ NEXT"
        else:
            status = "🔒 LOCKED"
        rows.append({"Step": n, "Layer": label, "Status": status})
    return pd.DataFrame(rows)


def _versioned_markdown(body, *args, **kwargs):
    text = str(body)
    if "WNBA Rebounds Command Center — V1.1" in text:
        text = text.replace("WNBA Rebounds Command Center — V1.1", "WNBA Rebounds Command Center — V1.2")
        text = text.replace(
            "Steps 1–2 only: verify the Eastern-date slate, then verify current roster identity and player availability before any rebound projection is allowed to exist.",
            "Steps 1–3 verified: slate, current roster/availability, then rotation-aware projected minutes. No rebound-rate projection is allowed until these foundations pass."
        )
    return _ORIGINAL_MARKDOWN(text, *args, **kwargs)


def render_wnba_rebounds_hub(section_header=None, status_info=None, _unused=None, h=None):
    base._injury_status = _injury_status
    base._overlay_availability = _overlay_availability
    base._render_step2 = _step2_plus_minutes
    base._tracker = _tracker

    key = "wnba_rebounds_v12_cache_refresh_done"
    if not st.session_state.get(key):
        try:
            base._injury_feed.clear()
        except Exception:
            pass
        try:
            base._current_rosters.clear()
        except Exception:
            pass
        try:
            _recent_rotation.clear()
        except Exception:
            pass
        st.session_state[key] = True

    st.caption("⏱️ WNBA Rebounds V1.2 • Steps 1–3 active • identity-safe availability + L3/L5/L10 rotation minutes • no rebound projection yet")
    old_markdown = st.markdown
    st.markdown = _versioned_markdown
    try:
        base.render_wnba_rebounds_hub(section_header, status_info, _unused, h)
    finally:
        st.markdown = old_markdown


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
