"""WNBA PRA V2.5 — Step 2 verified current player pool.

Step 2 only. Keep the V2.4 verified schedule intact, then build the selected
slate's player pool from current WNBA rosters + season game production.

Priority:
1) Existing WNBA Stats LeagueID=10 player table when it is healthy.
2) If the stats host is blocked/empty in Streamlit Cloud, rebuild season/L10/L5
   P/R/A from ESPN WNBA game summaries for only the teams on the selected slate.
3) Intersect historical stat rows with the current team roster so traded/waived
   players do not leak into the selected slate pool.

This layer does NOT add injuries, projected starters, role/usage, pace, matchup
adjustments or PRA betting probabilities. Those remain later steps.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import streamlit as st

import wnba_data_v22 as guarded
import wnba_data_v232 as old_players
import wnba_schedule_v24 as schedule_v24

ET = ZoneInfo("America/New_York")
ESPN_SCOREBOARD = schedule_v24.ESPN_SCOREBOARD
ESPN_SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/summary"
ESPN_ROSTER = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/teams/{team}/roster"

TEAM_SLUGS = {
    1611661330: "atl", 1611661329: "chi", 1611661323: "con",
    1611661321: "dal", 1611661325: "ind", 1611661319: "lv",
    1611661320: "la", 1611661324: "min", 1611661313: "ny",
    1611661317: "phx", 1611661328: "sea", 1611661322: "wsh",
    1611661331: "gs", 1611661327: "por", 1611661332: "tor",
}

PLAYER_COLUMNS = [
    "PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "TEAM_NAME", "TEAM_ABBREVIATION",
    "POSITION", "GP", "MIN", "PTS", "REB", "AST", "PRA",
    "L10_GP", "L10_MIN", "L10_PTS", "L10_REB", "L10_AST", "L10_PRA",
    "L5_GP", "L5_MIN", "L5_PTS", "L5_REB", "L5_AST", "L5_PRA",
    "LAST_GAME_DATE", "ROSTER_STATUS", "DATA_SOURCE", "PLAYER_ID_SOURCE",
]


def _empty_players() -> pd.DataFrame:
    return pd.DataFrame(columns=PLAYER_COLUMNS)


def _num(value, default=np.nan):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _minutes(value):
    if value is None:
        return np.nan
    text = str(value).strip()
    if text.startswith("PT"):
        # ISO-ish values from live NBA/WNBA feeds: PT31M22.00S
        try:
            body = text[2:]
            mins = float(body.split("M")[0]) if "M" in body else 0.0
            secs = float(body.split("M", 1)[1].rstrip("S")) if "M" in body else 0.0
            return mins + secs / 60.0
        except Exception:
            return np.nan
    if ":" in text:
        try:
            m, s = text.split(":", 1)
            return float(m) + float(s) / 60.0
        except Exception:
            return np.nan
    return _num(text)


def _team_id(team: dict) -> int:
    return int(old_players._team_id(team or {}) or 0)


def _team_meta(schedule: pd.DataFrame) -> dict:
    meta = {}
    if schedule is None or schedule.empty:
        return meta
    for _, row in schedule.iterrows():
        for side in ("away", "home"):
            tid = int(row.get(f"{side}_team_id") or 0)
            meta[tid] = {
                "name": str(row.get(f"{side}_team") or ""),
                "abbr": str(row.get(f"{side}_tricode") or ""),
            }
    return meta


def _flatten_roster_athletes(payload) -> list[dict]:
    root = payload or {}
    raw = root.get("athletes") or (root.get("team") or {}).get("athletes") or []
    out = []
    stack = list(raw) if isinstance(raw, list) else []
    while stack:
        item = stack.pop(0)
        if not isinstance(item, dict):
            continue
        nested = item.get("items") or item.get("athletes")
        if isinstance(nested, list):
            stack[0:0] = nested
            continue
        athlete = item.get("athlete") if isinstance(item.get("athlete"), dict) else item
        if athlete.get("id") and (athlete.get("displayName") or athlete.get("fullName")):
            out.append(athlete)
    return out


@st.cache_data(ttl=600, show_spinner=False)
def _espn_roster(team_id: int, team_name: str = "", team_abbr: str = "") -> pd.DataFrame:
    slug = TEAM_SLUGS.get(int(team_id))
    if not slug:
        return pd.DataFrame()
    try:
        payload, meta = schedule_v24._request_json(
            "ESPN WNBA roster", ESPN_ROSTER.format(team=slug), timeout=7, attempts=2
        )
    except Exception:
        payload, meta = None, {}
    if payload is None:
        return pd.DataFrame()
    rows = []
    for athlete in _flatten_roster_athletes(payload):
        status = athlete.get("status") or {}
        status_text = str(
            status.get("name") or status.get("type") or athlete.get("status") or "ROSTERED"
        ) if isinstance(status, dict) else str(status or "ROSTERED")
        pos = athlete.get("position") or {}
        rows.append({
            "PLAYER_ID": int(athlete.get("id")),
            "PLAYER_NAME": str(athlete.get("displayName") or athlete.get("fullName") or "Player"),
            "TEAM_ID": int(team_id),
            "TEAM_NAME": team_name,
            "TEAM_ABBREVIATION": team_abbr,
            "POSITION": str(pos.get("abbreviation") or pos.get("name") or ""),
            "ROSTER_STATUS": status_text.upper() or "ROSTERED",
            "PLAYER_ID_SOURCE": "ESPN",
            "ROSTER_SOURCE": "ESPN WNBA current roster",
        })
    return pd.DataFrame(rows).drop_duplicates(subset=["PLAYER_ID"], keep="first") if rows else pd.DataFrame()


def _summary_stat_map(group: dict, athlete_row: dict) -> dict:
    labels = group.get("labels") or []
    keys = group.get("keys") or group.get("names") or []
    vals = athlete_row.get("stats") or []
    result = {}
    for i, value in enumerate(vals):
        if i < len(labels):
            result[str(labels[i]).upper()] = value
        if i < len(keys):
            result[str(keys[i]).upper()] = value
    return result


def _pick_stat(stat_map: dict, names, default=np.nan):
    for name in names:
        key = str(name).upper()
        if key in stat_map:
            return stat_map[key]
    return default


def _parse_espn_summary(payload, fallback_date="") -> pd.DataFrame:
    if not isinstance(payload, dict):
        return pd.DataFrame()
    header = payload.get("header") or {}
    comps = header.get("competitions") or []
    game_date = fallback_date
    if comps:
        game_date = schedule_v24._event_date_et(comps[0].get("date")) or fallback_date
    rows = []
    for team_block in (payload.get("boxscore") or {}).get("players", []) or []:
        team = team_block.get("team") or {}
        tid = _team_id(team)
        if not guarded._is_wnba_team_id(tid):
            continue
        team_name = str(team.get("displayName") or team.get("shortDisplayName") or team.get("name") or "")
        team_abbr = str(team.get("abbreviation") or "")
        for group in team_block.get("statistics", []) or []:
            athletes = group.get("athletes") or []
            if not athletes:
                continue
            for item in athletes:
                athlete = item.get("athlete") or {}
                if not athlete.get("id"):
                    continue
                if bool(item.get("didNotPlay")):
                    continue
                stats = _summary_stat_map(group, item)
                mins = _minutes(_pick_stat(stats, ["MIN", "MINUTES"], np.nan))
                pts = _num(_pick_stat(stats, ["PTS", "POINTS"], np.nan))
                reb = _num(_pick_stat(stats, ["REB", "REBOUNDS", "REBOUNDSTOTAL"], np.nan))
                ast = _num(_pick_stat(stats, ["AST", "ASSISTS"], np.nan))
                if all(pd.isna(x) for x in (mins, pts, reb, ast)):
                    continue
                pos = athlete.get("position") or {}
                rows.append({
                    "GAME_DATE": game_date,
                    "PLAYER_ID": int(athlete.get("id")),
                    "PLAYER_NAME": str(athlete.get("displayName") or athlete.get("fullName") or "Player"),
                    "TEAM_ID": tid,
                    "TEAM_NAME": team_name,
                    "TEAM_ABBREVIATION": team_abbr,
                    "POSITION": str(pos.get("abbreviation") or pos.get("name") or ""),
                    "MIN": mins, "PTS": pts, "REB": reb, "AST": ast,
                    "PLAYER_ID_SOURCE": "ESPN",
                })
            # ESPN generally has one game-stat group. Avoid duplicate athlete rows
            # if a second presentation group exists.
            if athletes:
                break
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return frame.drop_duplicates(subset=["GAME_DATE", "PLAYER_ID", "TEAM_ID"], keep="first")


@st.cache_data(ttl=900, show_spinner=False)
def _espn_season_schedule(season: int) -> pd.DataFrame:
    payload, _ = schedule_v24._request_json(
        "ESPN WNBA season player-pool path",
        ESPN_SCOREBOARD,
        params={"dates": str(int(season)), "limit": 1000},
        timeout=10,
        attempts=2,
    )
    if payload is None:
        return pd.DataFrame()
    frame, _ = schedule_v24._parse_espn(payload, "ESPN WNBA season")
    return frame


@st.cache_data(ttl=1800, show_spinner=False)
def _espn_game_summary(game_id: str, game_date: str = "") -> pd.DataFrame:
    try:
        payload, _ = schedule_v24._request_json(
            "ESPN WNBA game summary",
            ESPN_SUMMARY,
            params={"event": str(game_id)},
            timeout=8,
            attempts=2,
        )
        if payload is None:
            return pd.DataFrame()
        return _parse_espn_summary(payload, game_date)
    except Exception:
        return pd.DataFrame()


def _aggregate_games(games: pd.DataFrame, roster: pd.DataFrame, team_meta: dict) -> pd.DataFrame:
    if games is None or games.empty:
        # Still surface current roster players even before they have a game stat.
        if roster is None or roster.empty:
            return _empty_players()
        out = roster.copy()
        for col in ["GP", "MIN", "PTS", "REB", "AST", "PRA", "L10_GP", "L10_MIN", "L10_PTS", "L10_REB", "L10_AST", "L10_PRA", "L5_GP", "L5_MIN", "L5_PTS", "L5_REB", "L5_AST", "L5_PRA"]:
            out[col] = 0.0
        out["LAST_GAME_DATE"] = "—"
        out["DATA_SOURCE"] = "ESPN WNBA roster • no completed-game rows"
        return out.reindex(columns=PLAYER_COLUMNS)

    frames = []
    jobs = []
    for _, game in games.drop_duplicates(subset=["game_id"]).iterrows():
        jobs.append((str(game.get("game_id")), str(game.get("game_date") or "")))
    with ThreadPoolExecutor(max_workers=min(12, max(1, len(jobs)))) as pool:
        futures = {pool.submit(_espn_game_summary, gid, gdate): gid for gid, gdate in jobs}
        for future in as_completed(futures):
            try:
                frame = future.result()
                if frame is not None and not frame.empty:
                    frames.append(frame)
            except Exception:
                continue
    if not frames:
        return _aggregate_games(pd.DataFrame(), roster, team_meta)
    logs = pd.concat(frames, ignore_index=True)
    logs["GAME_DATE"] = pd.to_datetime(logs["GAME_DATE"], errors="coerce")
    for c in ("MIN", "PTS", "REB", "AST"):
        logs[c] = pd.to_numeric(logs[c], errors="coerce")
    logs = logs.dropna(subset=["PLAYER_ID", "TEAM_ID"]).copy()

    # Current-roster gate. If a team roster endpoint failed, keep its observed
    # 2026 players but label the roster status as estimated instead of silently
    # deleting the whole team.
    roster_ids_by_team = {}
    if roster is not None and not roster.empty:
        for tid, part in roster.groupby("TEAM_ID"):
            roster_ids_by_team[int(tid)] = set(part["PLAYER_ID"].astype(int).tolist())
    gated = []
    for tid, part in logs.groupby("TEAM_ID"):
        ids = roster_ids_by_team.get(int(tid))
        if ids:
            part = part[part["PLAYER_ID"].astype(int).isin(ids)].copy()
        gated.append(part)
    logs = pd.concat(gated, ignore_index=True) if gated else pd.DataFrame()

    rows = []
    if not logs.empty:
        logs = logs.sort_values("GAME_DATE", ascending=False)
        for (pid, tid), part in logs.groupby(["PLAYER_ID", "TEAM_ID"], sort=False):
            part = part.sort_values("GAME_DATE", ascending=False)
            season = part
            l10 = part.head(10)
            l5 = part.head(5)
            first = part.iloc[0]
            roster_row = pd.DataFrame()
            if roster is not None and not roster.empty:
                roster_row = roster[(roster["PLAYER_ID"].astype(str) == str(int(pid))) & (roster["TEAM_ID"].astype(str) == str(int(tid)))]
            r = roster_row.iloc[0] if not roster_row.empty else None
            meta = team_meta.get(int(tid), {})
            def avg(frame, col):
                return float(pd.to_numeric(frame[col], errors="coerce").mean()) if col in frame.columns and len(frame) else 0.0
            season_vals = {x: avg(season, x) for x in ("MIN", "PTS", "REB", "AST")}
            l10_vals = {x: avg(l10, x) for x in ("MIN", "PTS", "REB", "AST")}
            l5_vals = {x: avg(l5, x) for x in ("MIN", "PTS", "REB", "AST")}
            rows.append({
                "PLAYER_ID": int(pid),
                "PLAYER_NAME": str((r.get("PLAYER_NAME") if r is not None else first.get("PLAYER_NAME")) or "Player"),
                "TEAM_ID": int(tid),
                "TEAM_NAME": str((r.get("TEAM_NAME") if r is not None else None) or meta.get("name") or first.get("TEAM_NAME") or ""),
                "TEAM_ABBREVIATION": str((r.get("TEAM_ABBREVIATION") if r is not None else None) or meta.get("abbr") or first.get("TEAM_ABBREVIATION") or ""),
                "POSITION": str((r.get("POSITION") if r is not None else None) or first.get("POSITION") or ""),
                "GP": int(len(season)),
                "MIN": season_vals["MIN"], "PTS": season_vals["PTS"], "REB": season_vals["REB"], "AST": season_vals["AST"],
                "PRA": season_vals["PTS"] + season_vals["REB"] + season_vals["AST"],
                "L10_GP": int(len(l10)), "L10_MIN": l10_vals["MIN"], "L10_PTS": l10_vals["PTS"], "L10_REB": l10_vals["REB"], "L10_AST": l10_vals["AST"],
                "L10_PRA": l10_vals["PTS"] + l10_vals["REB"] + l10_vals["AST"],
                "L5_GP": int(len(l5)), "L5_MIN": l5_vals["MIN"], "L5_PTS": l5_vals["PTS"], "L5_REB": l5_vals["REB"], "L5_AST": l5_vals["AST"],
                "L5_PRA": l5_vals["PTS"] + l5_vals["REB"] + l5_vals["AST"],
                "LAST_GAME_DATE": part.iloc[0]["GAME_DATE"].strftime("%Y-%m-%d") if pd.notna(part.iloc[0]["GAME_DATE"]) else "—",
                "ROSTER_STATUS": str(r.get("ROSTER_STATUS") if r is not None else "CURRENT ROSTER UNVERIFIED"),
                "DATA_SOURCE": "ESPN WNBA current roster + game summaries",
                "PLAYER_ID_SOURCE": "ESPN",
            })

    out = pd.DataFrame(rows)
    # Add rostered players with no completed-game stats yet.
    if roster is not None and not roster.empty:
        existing = set(out["PLAYER_ID"].astype(int).tolist()) if not out.empty else set()
        missing = roster[~roster["PLAYER_ID"].astype(int).isin(existing)].copy()
        for _, r in missing.iterrows():
            rows.append({
                "PLAYER_ID": int(r.PLAYER_ID), "PLAYER_NAME": r.PLAYER_NAME,
                "TEAM_ID": int(r.TEAM_ID), "TEAM_NAME": r.TEAM_NAME,
                "TEAM_ABBREVIATION": r.TEAM_ABBREVIATION, "POSITION": r.POSITION,
                "GP": 0, "MIN": 0.0, "PTS": 0.0, "REB": 0.0, "AST": 0.0, "PRA": 0.0,
                "L10_GP": 0, "L10_MIN": 0.0, "L10_PTS": 0.0, "L10_REB": 0.0, "L10_AST": 0.0, "L10_PRA": 0.0,
                "L5_GP": 0, "L5_MIN": 0.0, "L5_PTS": 0.0, "L5_REB": 0.0, "L5_AST": 0.0, "L5_PRA": 0.0,
                "LAST_GAME_DATE": "—", "ROSTER_STATUS": r.ROSTER_STATUS,
                "DATA_SOURCE": "ESPN WNBA current roster • no completed-game stats", "PLAYER_ID_SOURCE": "ESPN",
            })
        out = pd.DataFrame(rows)
    if out.empty:
        return _empty_players()
    return out.reindex(columns=PLAYER_COLUMNS).sort_values(["TEAM_ID", "MIN"], ascending=[True, False]).reset_index(drop=True)


@st.cache_data(ttl=600, show_spinner=False)
def _build_selected_player_pool(day_str: str):
    day_str = pd.to_datetime(day_str).strftime("%Y-%m-%d")
    schedule = schedule_v24.schedule_for_date(day_str)
    if schedule is None or schedule.empty:
        return _empty_players(), {
            "state": "NO_GAMES", "selected_date": day_str, "teams": 0,
            "rosters_connected": 0, "roster_players": 0, "stat_rows": 0,
            "completed_games_used": 0, "source": "none",
        }
    team_meta = _team_meta(schedule)
    team_ids = set(schedule["away_team_id"].astype(int).tolist() + schedule["home_team_id"].astype(int).tolist())

    # First priority: existing WNBA Stats table. It is league guarded. We still
    # need current rosters to remove old-team/non-roster rows.
    try:
        primary = old_players.player_form_table(pd.to_datetime(day_str).year)
    except Exception:
        primary = pd.DataFrame()

    roster_frames = []
    for tid in sorted(team_ids):
        meta = team_meta.get(tid, {})
        r = _espn_roster(tid, meta.get("name", ""), meta.get("abbr", ""))
        if r is not None and not r.empty:
            roster_frames.append(r)
    roster = pd.concat(roster_frames, ignore_index=True) if roster_frames else pd.DataFrame()

    if primary is not None and not primary.empty:
        primary = guarded._guard_stats(primary)
        primary = primary[primary["TEAM_ID"].astype(int).isin(team_ids)].copy()
        if not roster.empty:
            allowed = set((int(r.TEAM_ID), int(r.PLAYER_ID)) for _, r in roster.iterrows())
            # WNBA Stats IDs and ESPN IDs can differ. Only apply the ID gate when
            # at least one primary id actually overlaps; otherwise use team gate
            # and surface roster-match diagnostics rather than deleting everyone.
            overlaps = sum((int(r.TEAM_ID), int(r.PLAYER_ID)) in allowed for _, r in primary.iterrows() if pd.notna(r.get("PLAYER_ID")))
            if overlaps:
                primary = primary[[
                    (int(r.TEAM_ID), int(r.PLAYER_ID)) in allowed for _, r in primary.iterrows()
                ]].copy()
        if not primary.empty:
            for prefix in ("", "L10_", "L5_"):
                for stat in ("PTS", "REB", "AST"):
                    col = f"{prefix}{stat}"
                    if col not in primary.columns:
                        primary[col] = np.nan
                pra_col = "PRA" if not prefix else f"{prefix}PRA"
                primary[pra_col] = sum(pd.to_numeric(primary[f"{prefix}{s}"], errors="coerce").fillna(0) for s in ("PTS", "REB", "AST"))
            primary["ROSTER_STATUS"] = "CURRENT TEAM"
            primary["DATA_SOURCE"] = primary.get("DATA_SOURCE", "WNBA Stats")
            primary["PLAYER_ID_SOURCE"] = "WNBA Stats"
            primary["LAST_GAME_DATE"] = "—"
            for c in PLAYER_COLUMNS:
                if c not in primary.columns:
                    primary[c] = 0 if c.endswith("_GP") else np.nan
            primary = primary.reindex(columns=PLAYER_COLUMNS)
            diag = {
                "state": "VERIFIED", "selected_date": day_str, "teams": len(team_ids),
                "rosters_connected": len(roster_frames), "roster_players": len(roster),
                "stat_rows": len(primary), "completed_games_used": 0,
                "source": "WNBA Stats LeagueID=10", "roster_source": "ESPN WNBA current roster",
            }
            return primary.reset_index(drop=True), diag

    # Streamlit fallback: reconstruct season averages from WNBA game summaries.
    try:
        season_schedule = _espn_season_schedule(pd.to_datetime(day_str).year)
    except Exception:
        season_schedule = pd.DataFrame()
    history = pd.DataFrame()
    if season_schedule is not None and not season_schedule.empty:
        before = pd.to_datetime(season_schedule["game_date"], errors="coerce") < pd.to_datetime(day_str)
        team_mask = season_schedule["away_team_id"].astype(int).isin(team_ids) | season_schedule["home_team_id"].astype(int).isin(team_ids)
        final_mask = season_schedule["status"].astype(str).str.upper().eq("FINAL")
        history = season_schedule[before & team_mask & final_mask].copy()
    players = _aggregate_games(history, roster, team_meta)
    state = "VERIFIED" if not players.empty else "PROVIDER_FAILURE"
    diag = {
        "state": state, "selected_date": day_str, "teams": len(team_ids),
        "rosters_connected": len(roster_frames), "roster_players": len(roster),
        "stat_rows": len(players), "completed_games_used": int(history["game_id"].nunique()) if not history.empty else 0,
        "source": "ESPN WNBA game-summary fallback" if not players.empty else "none",
        "roster_source": "ESPN WNBA current roster" if len(roster_frames) else "unavailable",
    }
    return players, diag


def player_form_table(season: int | None = None) -> pd.DataFrame:
    day = st.session_state.get("wnba_pra_v2_date")
    if day is None:
        day = pd.Timestamp.now(tz=ET).date()
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")
    with st.spinner("🏀 Verifying current WNBA rosters + season/L10/L5 player production…"):
        players, _ = _build_selected_player_pool(day_str)
    return players


def player_diagnostics(day: str | date) -> dict:
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")
    _, diag = _build_selected_player_pool(day_str)
    return diag


def clear_player_cache():
    for fn in (_build_selected_player_pool, _espn_roster, _espn_season_schedule, _espn_game_summary):
        try:
            fn.clear()
        except Exception:
            pass


def official_roster(team_id: int, season: int | None = None) -> pd.DataFrame:
    day = st.session_state.get("wnba_pra_v2_date")
    day_str = pd.to_datetime(day or pd.Timestamp.now(tz=ET).date()).strftime("%Y-%m-%d")
    schedule = schedule_v24.schedule_for_date(day_str)
    meta = _team_meta(schedule).get(int(team_id), {})
    roster = _espn_roster(int(team_id), meta.get("name", ""), meta.get("abbr", ""))
    if roster is not None and not roster.empty:
        return roster
    return old_players.official_roster(int(team_id), season)


def data_health(schedule, stats):
    health = schedule_v24.data_health(schedule, stats)
    if stats is not None and not stats.empty:
        health["WNBA player stats"] = "CONNECTED"
        health["Official rosters"] = "CONNECTED"
    return health


# Reuse verified schedule and unchanged downstream helpers.
schedule_for_date = schedule_v24.schedule_for_date
schedule_diagnostics = schedule_v24.schedule_diagnostics
clear_schedule_cache = schedule_v24.clear_schedule_cache
current_season = old_players.current_season
empirical_profile = old_players.empirical_profile
game_for_team = old_players.game_for_team
logo_url = old_players.logo_url
player_game_log = old_players.player_game_log
slate_player_pool = old_players.slate_player_pool
team_player_pool = old_players.team_player_pool
