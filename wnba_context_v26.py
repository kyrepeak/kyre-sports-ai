"""WNBA PRA V2.6 — Step 3 verified matchup/team context.

Keeps V2.4 schedule verification and V2.5 player pool unchanged. Adds descriptive
team records, recent form, H2H and approximate recent pace/offensive/defensive
ratings. These values are display-only in V2.6 and do not alter PRA projections.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

import numpy as np
import pandas as pd
import streamlit as st

import wnba_players_v25 as players
import wnba_schedule_v24 as schedule_v24
import wnba_data_v22 as guarded

ESPN_SCOREBOARD = schedule_v24.ESPN_SCOREBOARD
ESPN_SUMMARY = players.ESPN_SUMMARY


def _num(value, default=np.nan):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _completed(comp: dict) -> bool:
    typ = ((comp.get("status") or {}).get("type") or {})
    return bool(
        typ.get("completed")
        or str(typ.get("state") or "").lower() == "post"
        or str(typ.get("name") or "").upper() in {"STATUS_FINAL", "FINAL"}
    )


@st.cache_data(ttl=900, show_spinner=False)
def _season_team_games(season: int) -> pd.DataFrame:
    """Return one row per team per completed WNBA game."""
    payload, _ = schedule_v24._request_json(
        "ESPN WNBA season team-context",
        ESPN_SCOREBOARD,
        params={"dates": str(int(season)), "limit": 1000},
        timeout=10,
        attempts=2,
    )
    if not isinstance(payload, dict):
        return pd.DataFrame()
    rows = []
    for event in payload.get("events", []) or []:
        comps = event.get("competitions") or []
        if not comps:
            continue
        comp = comps[0]
        if not _completed(comp):
            continue
        game_date = schedule_v24._event_date_et(comp.get("date") or event.get("date"))
        parsed = []
        for c in comp.get("competitors", []) or []:
            team = c.get("team") or {}
            tid = int(players._team_id(team) or 0)
            if not guarded._is_wnba_team_id(tid):
                continue
            score = _num(c.get("score"), np.nan)
            if pd.isna(score):
                continue
            parsed.append({
                "TEAM_ID": tid,
                "TEAM_NAME": str(team.get("displayName") or team.get("shortDisplayName") or team.get("name") or ""),
                "TEAM_ABBR": str(team.get("abbreviation") or ""),
                "SCORE": score,
                "HOME": str(c.get("homeAway") or "").lower() == "home",
            })
        if len(parsed) != 2:
            continue
        a, b = parsed
        for team, opp in ((a, b), (b, a)):
            rows.append({
                "GAME_ID": str(event.get("id") or comp.get("id") or ""),
                "GAME_DATE": game_date,
                "TEAM_ID": int(team["TEAM_ID"]),
                "TEAM_NAME": team["TEAM_NAME"],
                "TEAM_ABBR": team["TEAM_ABBR"],
                "OPP_ID": int(opp["TEAM_ID"]),
                "OPP_NAME": opp["TEAM_NAME"],
                "PF": float(team["SCORE"]),
                "PA": float(opp["SCORE"]),
                "WIN": int(team["SCORE"] > opp["SCORE"]),
                "HOME": bool(team["HOME"]),
            })
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["GAME_DATE"] = pd.to_datetime(frame["GAME_DATE"], errors="coerce")
    return frame.dropna(subset=["GAME_DATE"]).drop_duplicates(
        subset=["GAME_ID", "TEAM_ID"], keep="first"
    ).reset_index(drop=True)


def _attempts(value):
    text = str(value or "").strip()
    if "-" in text:
        try:
            return float(text.split("-")[-1])
        except Exception:
            return np.nan
    return _num(value, np.nan)


def _summary_team_possessions(payload: dict) -> pd.DataFrame:
    """Approximate possessions by summing player FGA/FTA/OREB/TO box stats."""
    if not isinstance(payload, dict):
        return pd.DataFrame()
    rows = []
    for block in (payload.get("boxscore") or {}).get("players", []) or []:
        team = block.get("team") or {}
        tid = int(players._team_id(team) or 0)
        if not guarded._is_wnba_team_id(tid):
            continue
        fga = fta = oreb = tov = 0.0
        fg_n = ft_n = 0
        seen = set()
        for group in block.get("statistics", []) or []:
            athletes = group.get("athletes") or []
            if not athletes:
                continue
            for item in athletes:
                if bool(item.get("didNotPlay")):
                    continue
                athlete = item.get("athlete") or {}
                pid = str(athlete.get("id") or "")
                if pid and pid in seen:
                    continue
                if pid:
                    seen.add(pid)
                sm = players._summary_stat_map(group, item)
                fg = players._pick_stat(sm, ["FG", "FGM-A", "FIELDGOALS"], None)
                ft = players._pick_stat(sm, ["FT", "FTM-A", "FREETHROWS"], None)
                ore = players._pick_stat(sm, ["OREB", "OR", "OFFENSIVEREBOUNDS"], None)
                to = players._pick_stat(sm, ["TO", "TOV", "TURNOVERS"], None)
                if fg is not None:
                    v = _attempts(fg)
                    if not pd.isna(v):
                        fga += v; fg_n += 1
                if ft is not None:
                    v = _attempts(ft)
                    if not pd.isna(v):
                        fta += v; ft_n += 1
                v = _num(ore, np.nan)
                if not pd.isna(v):
                    oreb += v
                v = _num(to, np.nan)
                if not pd.isna(v):
                    tov += v
            if athletes:
                break
        poss = fga + 0.44 * fta - oreb + tov if fg_n and ft_n else np.nan
        rows.append({"TEAM_ID": tid, "POSS": poss})
    return pd.DataFrame(rows)


@st.cache_data(ttl=1800, show_spinner=False)
def _game_advanced(game_id: str) -> pd.DataFrame:
    try:
        payload, _ = schedule_v24._request_json(
            "ESPN WNBA team-context summary",
            ESPN_SUMMARY,
            params={"event": str(game_id)},
            timeout=8,
            attempts=2,
        )
    except Exception:
        payload = None
    return _summary_team_possessions(payload or {})


def _record_summary(team_games: pd.DataFrame, team_id: int) -> dict:
    part = team_games[team_games["TEAM_ID"].astype(int).eq(int(team_id))].copy() if team_games is not None and not team_games.empty else pd.DataFrame()
    if part.empty:
        return {"GP":0,"W":0,"L":0,"WIN_PCT":np.nan,"L10_W":0,"L10_L":0,"L5_W":0,"L5_L":0,"PF":np.nan,"PA":np.nan,"DIFF":np.nan,"L10_PF":np.nan,"L10_PA":np.nan,"L10_DIFF":np.nan,"TEAM_NAME":""}
    part = part.sort_values("GAME_DATE", ascending=False)
    l10, l5 = part.head(10), part.head(5)
    avg = lambda f, c: float(pd.to_numeric(f[c], errors="coerce").mean()) if len(f) else np.nan
    w, gp = int(part["WIN"].sum()), int(len(part))
    return {
        "GP":gp,"W":w,"L":gp-w,"WIN_PCT":w/gp if gp else np.nan,
        "L10_W":int(l10["WIN"].sum()),"L10_L":int(len(l10)-l10["WIN"].sum()),
        "L5_W":int(l5["WIN"].sum()),"L5_L":int(len(l5)-l5["WIN"].sum()),
        "PF":avg(part,"PF"),"PA":avg(part,"PA"),"DIFF":avg(part,"PF")-avg(part,"PA"),
        "L10_PF":avg(l10,"PF"),"L10_PA":avg(l10,"PA"),"L10_DIFF":avg(l10,"PF")-avg(l10,"PA"),
        "TEAM_NAME":str(part.iloc[0].get("TEAM_NAME") or ""),
    }


def _advanced_summary(team_games: pd.DataFrame, team_id: int, limit=10) -> dict:
    if team_games is None or team_games.empty:
        return {"PACE_L10":np.nan,"ORTG_L10":np.nan,"DRTG_L10":np.nan,"ADV_GAMES":0}
    recent = team_games[team_games["TEAM_ID"].astype(int).eq(int(team_id))].sort_values("GAME_DATE", ascending=False).head(int(limit))
    if recent.empty:
        return {"PACE_L10":np.nan,"ORTG_L10":np.nan,"DRTG_L10":np.nan,"ADV_GAMES":0}
    game_ids = recent["GAME_ID"].astype(str).unique().tolist()
    adv_map = {}
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(game_ids)))) as pool:
        futures = {pool.submit(_game_advanced, gid): gid for gid in game_ids}
        for future in as_completed(futures):
            gid = futures[future]
            try:
                adv_map[gid] = future.result()
            except Exception:
                adv_map[gid] = pd.DataFrame()
    samples = []
    for _, g in recent.iterrows():
        adv = adv_map.get(str(g["GAME_ID"]))
        if adv is None or adv.empty:
            continue
        tr = adv[adv["TEAM_ID"].astype(int).eq(int(team_id))]
        orow = adv[adv["TEAM_ID"].astype(int).eq(int(g["OPP_ID"]))]
        if tr.empty or orow.empty:
            continue
        tposs = _num(tr.iloc[0].get("POSS"), np.nan)
        oposs = _num(orow.iloc[0].get("POSS"), np.nan)
        if pd.isna(tposs) or pd.isna(oposs) or tposs <= 0 or oposs <= 0:
            continue
        samples.append(((tposs+oposs)/2.0, 100.0*float(g["PF"])/tposs, 100.0*float(g["PA"])/oposs))
    if not samples:
        return {"PACE_L10":np.nan,"ORTG_L10":np.nan,"DRTG_L10":np.nan,"ADV_GAMES":0}
    arr = np.asarray(samples, dtype=float)
    return {"PACE_L10":float(np.nanmean(arr[:,0])),"ORTG_L10":float(np.nanmean(arr[:,1])),"DRTG_L10":float(np.nanmean(arr[:,2])),"ADV_GAMES":int(len(samples))}


@st.cache_data(ttl=900, show_spinner=False)
def _historical_games_through(day_str: str) -> pd.DataFrame:
    selected = pd.to_datetime(day_str)
    season = int(selected.year)
    frames = []
    for year in range(max(2023, season-3), season+1):
        try:
            f = _season_team_games(year)
        except Exception:
            f = pd.DataFrame()
        if f is not None and not f.empty:
            frames.append(f)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    return out[pd.to_datetime(out["GAME_DATE"], errors="coerce") < selected].sort_values("GAME_DATE", ascending=False).reset_index(drop=True)


def _h2h(history: pd.DataFrame, away_id: int, home_id: int, season: int) -> dict:
    if history is None or history.empty:
        return {"GAMES":0,"AWAY_W":0,"HOME_W":0,"AVG_TOTAL":np.nan,"AWAY_MARGIN":np.nan,"CURRENT_GAMES":0}
    pair = history[(history["TEAM_ID"].astype(int).eq(int(away_id))) & (history["OPP_ID"].astype(int).eq(int(home_id)))].sort_values("GAME_DATE", ascending=False).head(10)
    if pair.empty:
        return {"GAMES":0,"AWAY_W":0,"HOME_W":0,"AVG_TOTAL":np.nan,"AWAY_MARGIN":np.nan,"CURRENT_GAMES":0}
    g, aw = int(len(pair)), int(pair["WIN"].sum())
    return {
        "GAMES":g,"AWAY_W":aw,"HOME_W":g-aw,
        "AVG_TOTAL":float((pair["PF"]+pair["PA"]).mean()),
        "AWAY_MARGIN":float((pair["PF"]-pair["PA"]).mean()),
        "CURRENT_GAMES":int((pd.to_datetime(pair["GAME_DATE"], errors="coerce").dt.year == int(season)).sum()),
    }


@st.cache_data(ttl=900, show_spinner=False)
def slate_context(day_str: str):
    day_str = pd.to_datetime(day_str).strftime("%Y-%m-%d")
    selected, season = pd.to_datetime(day_str), int(pd.to_datetime(day_str).year)
    schedule = players.schedule_for_date(day_str)
    if schedule is None or schedule.empty:
        return {}, {"state":"NO_GAMES","selected_date":day_str,"games":0,"teams":0,"records_verified":0,"advanced_teams":0,"advanced_games":0,"h2h_samples":0,"source":"none"}
    try:
        season_games = _season_team_games(season)
    except Exception:
        season_games = pd.DataFrame()
    if season_games is not None and not season_games.empty:
        season_games = season_games[pd.to_datetime(season_games["GAME_DATE"], errors="coerce") < selected].copy()
    history = _historical_games_through(day_str)
    contexts = {}
    records_verified = advanced_teams = advanced_games = h2h_samples = 0
    for _, game in schedule.iterrows():
        away_id, home_id = int(game["away_team_id"]), int(game["home_team_id"])
        away, home = _record_summary(season_games, away_id), _record_summary(season_games, home_id)
        away.update(_advanced_summary(season_games, away_id, 10))
        home.update(_advanced_summary(season_games, home_id, 10))
        h2h = _h2h(history, away_id, home_id, season)
        key = str(game.get("game_id") or f"{away_id}-{home_id}")
        contexts[key] = {"away":away,"home":home,"h2h":h2h,"source":"ESPN WNBA season scoreboard + game summaries"}
        records_verified += int(away.get("GP",0)>0) + int(home.get("GP",0)>0)
        for obj in (away, home):
            if int(obj.get("ADV_GAMES",0) or 0)>0:
                advanced_teams += 1; advanced_games += int(obj.get("ADV_GAMES",0) or 0)
        h2h_samples += int(h2h.get("GAMES",0) or 0)
    teams = len(set(schedule["away_team_id"].astype(int).tolist()+schedule["home_team_id"].astype(int).tolist()))
    state = "VERIFIED" if records_verified == teams else "PARTIAL"
    return contexts, {"state":state,"selected_date":day_str,"games":int(len(schedule)),"teams":int(teams),"records_verified":int(records_verified),"advanced_teams":int(advanced_teams),"advanced_games":int(advanced_games),"h2h_samples":int(h2h_samples),"source":"ESPN WNBA season scoreboard + game summaries"}


def game_context(row, day: str | date | None = None) -> dict:
    day = day or st.session_state.get("wnba_pra_v2_date") or pd.Timestamp.now().date()
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")
    contexts, _ = slate_context(day_str)
    key = str(row.get("game_id") or f"{int(row.get('away_team_id') or 0)}-{int(row.get('home_team_id') or 0)}")
    return contexts.get(key, {})


def context_diagnostics(day: str | date) -> dict:
    _, diag = slate_context(pd.to_datetime(day).strftime("%Y-%m-%d"))
    return diag


def clear_context_cache():
    for fn in (_season_team_games, _game_advanced, _historical_games_through, slate_context):
        try:
            fn.clear()
        except Exception:
            pass


# Preserve Step 1 + Step 2 interfaces.
schedule_for_date = players.schedule_for_date
schedule_diagnostics = players.schedule_diagnostics
clear_schedule_cache = players.clear_schedule_cache
current_season = players.current_season
data_health = players.data_health
empirical_profile = players.empirical_profile
game_for_team = players.game_for_team
logo_url = players.logo_url
official_roster = players.official_roster
player_diagnostics = players.player_diagnostics
player_form_table = players.player_form_table
player_game_log = players.player_game_log
slate_player_pool = players.slate_player_pool
team_player_pool = players.team_player_pool
