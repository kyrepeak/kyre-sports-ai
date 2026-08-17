"""WNBA PRA V2.8.1 — finish Step 5 usage + minute safety.

Keeps V2.8's verified schedule/roster/availability engine, but fixes two gaps:
1) Advanced USG% still tries WNBA/NBA Stats first; when those hosts are blocked,
   derive an explicitly-labeled estimated USG% from ESPN WNBA box scores using
   FGA + .44*FTA + TOV and player/team minutes.
2) Injury minute redistribution uses recent-workload player caps before any
   emergency relaxation toward the 40-minute absolute ceiling.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import streamlit as st

import wnba_role_v28 as base
import wnba_players_v25 as players

OUT_STATUSES = base.OUT_STATUSES
UNCERTAIN_STATUSES = base.UNCERTAIN_STATUSES


def _attempts(value):
    if value is None:
        return np.nan
    text = str(value).strip()
    if not text:
        return np.nan
    for sep in ("-", "/"):
        if sep in text:
            try:
                return float(text.split(sep)[-1])
            except Exception:
                pass
    return base._num(text, np.nan)


def _pick_attempts(stat_map, direct, combo):
    direct_value = players._pick_stat(stat_map, direct, np.nan)
    if pd.notna(base._num(direct_value, np.nan)):
        return base._num(direct_value, np.nan)
    combo_value = players._pick_stat(stat_map, combo, np.nan)
    return _attempts(combo_value)


def _usage_rows_from_summary(payload, game_date=""):
    if not isinstance(payload, dict):
        return []
    rows = []
    for team_block in (payload.get("boxscore") or {}).get("players", []) or []:
        team = team_block.get("team") or {}
        tid = int(players._team_id(team) or 0)
        if not tid:
            continue
        team_rows = []
        for group in team_block.get("statistics", []) or []:
            athletes = group.get("athletes") or []
            if not athletes:
                continue
            for item in athletes:
                if not isinstance(item, dict) or bool(item.get("didNotPlay")):
                    continue
                athlete = item.get("athlete") or {}
                if not athlete.get("id"):
                    continue
                stat_map = players._summary_stat_map(group, item)
                minutes = players._minutes(players._pick_stat(stat_map, ["MIN", "MINUTES"], np.nan))
                if pd.isna(minutes) or minutes <= 0.5:
                    continue
                fga = _pick_attempts(stat_map, ["FGA", "FIELDGOALSATTEMPTED"], ["FG", "FGM-A", "FIELD GOALS"])
                fta = _pick_attempts(stat_map, ["FTA", "FREETHROWSATTEMPTED"], ["FT", "FTM-A", "FREE THROWS"])
                tov = base._num(players._pick_stat(stat_map, ["TO", "TOV", "TURNOVERS"], 0.0), 0.0)
                if pd.isna(fga):
                    fga = 0.0
                if pd.isna(fta):
                    fta = 0.0
                events = float(fga + 0.44 * fta + max(tov, 0.0))
                team_rows.append({
                    "GAME_DATE": game_date,
                    "TEAM_ID": tid,
                    "PLAYER_ID": int(athlete.get("id")),
                    "PLAYER_NAME": str(athlete.get("displayName") or athlete.get("fullName") or "Player"),
                    "MIN": float(minutes),
                    "EVENTS": events,
                })
            break
        if not team_rows:
            continue
        team_minutes = sum(r["MIN"] for r in team_rows)
        team_events = sum(r["EVENTS"] for r in team_rows)
        if team_events <= 0 or team_minutes <= 0:
            continue
        for r in team_rows:
            # Standard possession-based usage structure. Team minutes/5 gives
            # the five-player minutes scaling term used by conventional USG%.
            usg = 100.0 * (r["EVENTS"] * (team_minutes / 5.0)) / max(r["MIN"] * team_events, 1e-9)
            r["USG_GAME"] = float(np.clip(usg, 1.0, 50.0))
            rows.append(r)
    return rows


@st.cache_data(ttl=900, show_spinner=False)
def _espn_usage_fallback(season: int, day_str: str):
    schedule = base.availability.schedule_for_date(day_str)
    if schedule is None or schedule.empty:
        return pd.DataFrame()
    team_ids = set(schedule["away_team_id"].astype(int).tolist() + schedule["home_team_id"].astype(int).tolist())
    try:
        season_schedule = players._espn_season_schedule(int(season))
    except Exception:
        season_schedule = pd.DataFrame()
    if season_schedule is None or season_schedule.empty:
        return pd.DataFrame()
    dates = pd.to_datetime(season_schedule["game_date"], errors="coerce")
    mask = (
        dates.lt(pd.to_datetime(day_str))
        & season_schedule["status"].astype(str).str.upper().eq("FINAL")
        & (season_schedule["away_team_id"].astype(int).isin(team_ids) | season_schedule["home_team_id"].astype(int).isin(team_ids))
    )
    games = season_schedule.loc[mask, ["game_id", "game_date"]].drop_duplicates("game_id")
    if games.empty:
        return pd.DataFrame()

    rows = []
    def fetch_one(gid, gdate):
        try:
            payload, _ = players.schedule_v24._request_json(
                "ESPN WNBA usage box score",
                players.ESPN_SUMMARY,
                params={"event": str(gid)},
                timeout=8,
                attempts=2,
            )
            return _usage_rows_from_summary(payload, str(gdate))
        except Exception:
            return []

    jobs = [(str(r.game_id), str(r.game_date)) for _, r in games.iterrows()]
    with ThreadPoolExecutor(max_workers=min(10, max(1, len(jobs)))) as pool:
        futures = [pool.submit(fetch_one, gid, gdate) for gid, gdate in jobs]
        for f in as_completed(futures):
            try:
                rows.extend(f.result())
            except Exception:
                pass
    if not rows:
        return pd.DataFrame()

    logs = pd.DataFrame(rows)
    logs["GAME_DATE"] = pd.to_datetime(logs["GAME_DATE"], errors="coerce")
    logs = logs[logs["TEAM_ID"].astype(int).isin(team_ids)].sort_values("GAME_DATE", ascending=False)
    out = []
    for (tid, pid), part in logs.groupby(["TEAM_ID", "PLAYER_ID"], sort=False):
        part = part.sort_values("GAME_DATE", ascending=False)
        def wavg(frame):
            if frame.empty:
                return np.nan
            w = pd.to_numeric(frame["MIN"], errors="coerce").fillna(0).clip(lower=0)
            x = pd.to_numeric(frame["USG_GAME"], errors="coerce")
            good = x.notna() & w.gt(0)
            return float(np.average(x[good], weights=w[good])) if good.any() else np.nan
        out.append({
            "TEAM_ID": int(tid),
            "PLAYER_ID": int(pid),
            "PLAYER_NAME": str(part.iloc[0].get("PLAYER_NAME") or "Player"),
            "USG_PCT": wavg(part),
            "L10_USG_PCT": wavg(part.head(10)),
            "L5_USG_PCT": wavg(part.head(5)),
        })
    return pd.DataFrame(out)


@st.cache_data(ttl=900, show_spinner=False)
def advanced_usage_table(season: int | None = None):
    season = int(season or base.availability.current_season())
    # Preserve official Advanced Stats as first priority.
    official, source = base._ORIGINAL_ADVANCED_USAGE_TABLE(season)
    if official is not None and not official.empty:
        return official, source
    day_str = base._day_str()
    fallback = _espn_usage_fallback(season, day_str)
    if fallback is not None and not fallback.empty:
        return fallback, "ESPN WNBA box-score estimated USG%"
    return pd.DataFrame(), "unavailable"


def _minute_cap(row):
    vals = [base._num(row.get("MIN"), 0.0), base._num(row.get("L10_MIN"), np.nan), base._num(row.get("L5_MIN"), np.nan)]
    recent = max([x for x in vals if pd.notna(x)] or [0.0])
    # Normal injury bump: recent workload +3, with a modest floor for rotation
    # players. High-minute stars can reach 39-39.5 only when recent usage supports it.
    cap = max(12.0, recent + 3.0)
    if bool(row.get("STARTER_CONFIRMED")):
        cap += 0.75
    if recent >= 35.0:
        cap = min(cap, 39.5)
    else:
        cap = min(cap, 38.0)
    return float(np.clip(cap, 8.0, 39.5))


def _waterfill(weights: pd.Series, caps: pd.Series, target=200.0):
    alloc = pd.Series(0.0, index=weights.index)
    remaining = list(weights.index)
    for _ in range(20):
        if not remaining:
            break
        need = target - float(alloc.sum())
        if need <= 1e-6:
            break
        w = weights.loc[remaining].clip(lower=0.05)
        trial = need * w / max(float(w.sum()), 1e-9)
        hit = []
        for i, v in trial.items():
            room = max(0.0, float(caps.loc[i]) - float(alloc.loc[i]))
            add = min(float(v), room)
            alloc.loc[i] += add
            if room - add <= 1e-6:
                hit.append(i)
        if not hit and abs(float(alloc.sum()) - target) < 1e-4:
            break
        remaining = [i for i in remaining if i not in hit]
        if not hit and remaining:
            break
    return alloc


def _redistribute_team_minutes(team: pd.DataFrame) -> pd.DataFrame:
    t = team.copy()
    t["BASE_MIN"] = t.apply(base._base_minutes, axis=1)
    status = t["DESIGNATION"].astype(str).str.upper()
    out_mask = status.isin(OUT_STATUSES)
    active = ~out_mask
    t["PROJ_MIN"] = 0.0
    t["MIN_CAP"] = 0.0
    if not active.any():
        return t

    weights = t.loc[active, "BASE_MIN"].astype(float).clip(lower=0.35)
    starters = t.loc[active, "STARTER_CONFIRMED"].fillna(False).astype(bool)
    weights.loc[starters] *= 1.05
    caps = t.loc[active].apply(_minute_cap, axis=1)

    # If conservative caps cannot mathematically fill 200 team minutes, relax
    # them only as much as necessary, never beyond 40.
    if float(caps.sum()) < 200.0:
        deficit = 200.0 - float(caps.sum())
        room = (40.0 - caps).clip(lower=0.0)
        if float(room.sum()) > 0:
            caps = caps + deficit * room / float(room.sum())
            caps = caps.clip(upper=40.0)

    alloc = _waterfill(weights, caps, 200.0)
    if float(alloc.sum()) < 199.5:
        # Final emergency fill is transparent and still capped at 40.
        hard_caps = pd.Series(40.0, index=weights.index)
        alloc = _waterfill(weights, hard_caps, 200.0)
    t.loc[active, "PROJ_MIN"] = alloc
    t.loc[active, "MIN_CAP"] = caps.reindex(alloc.index).fillna(40.0)
    t.loc[out_mask, ["PROJ_MIN", "MIN_CAP"]] = 0.0
    return t


# Keep references to the original first-priority implementation once, then patch
# the V2.8 module globals. Its existing role_projection_for_game resolves these
# names dynamically from the module dictionary.
if not hasattr(base, "_ORIGINAL_ADVANCED_USAGE_TABLE"):
    base._ORIGINAL_ADVANCED_USAGE_TABLE = base.advanced_usage_table
base.advanced_usage_table = advanced_usage_table
base._redistribute_team_minutes = _redistribute_team_minutes

# Re-export the public API used by the V2.8 hub.
role_projection_for_game = base.role_projection_for_game
role_diagnostics = base.role_diagnostics
clear_role_cache = base.clear_role_cache
availability = base.availability
current_season = base.current_season
schedule_for_date = base.schedule_for_date
schedule_diagnostics = base.schedule_diagnostics
clear_schedule_cache = base.clear_schedule_cache
data_health = base.data_health
empirical_profile = base.empirical_profile
game_for_team = base.game_for_team
logo_url = base.logo_url
official_roster = base.official_roster
player_game_log = base.player_game_log
player_form_table = base.player_form_table
slate_player_pool = base.slate_player_pool
team_player_pool = base.team_player_pool
availability_for_game = base.availability_for_game
availability_diagnostics = base.availability_diagnostics
context_diagnostics = base.context_diagnostics
game_context = base.game_context
