"""WNBA Rebounds + Assists — Step 4 read-only opportunity/matchup context.

This module supplies descriptive R+A context only. It never creates an R+A
projection, probability, Monte Carlo result, edge, EV, qualification or ranking.

Verified/labeled inputs:
- ESPN WNBA completed-game box summaries strictly before the selected slate;
- recent team pace/efficiency from the existing WNBA context engine;
- current ESPN injury/status coverage from the existing availability layer.

Important: ESPN's verified box feed used here does not expose official tracking
metrics such as potential assists or rebound chances. We therefore show clearly
labeled box-score proxies (assist share, rebound share, team/opponent assists,
rebounds and missed-field-goal environment) and never mislabel them as tracking
stats.
"""
from __future__ import annotations

from zoneinfo import ZoneInfo
import re

import numpy as np
import pandas as pd
import streamlit as st

import wnba_players_v25 as players
import wnba_schedule_v24 as schedule24
import wnba_context_v26 as team_context
import wnba_availability_v33 as availability

ET = ZoneInfo("America/New_York")


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _safe_int(value) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _norm(value) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _made_attempt(value):
    """Parse common ESPN made-attempt strings such as 6-14."""
    if value is None:
        return np.nan, np.nan
    if isinstance(value, dict):
        made = _num(value.get("made") or value.get("value"), np.nan)
        attempts = _num(value.get("attempted") or value.get("attempts"), np.nan)
        return made, attempts
    text = str(value).strip()
    if "-" in text:
        bits = text.split("-")
        if len(bits) >= 2:
            return _num(bits[0], np.nan), _num(bits[-1], np.nan)
    return np.nan, np.nan


@st.cache_data(ttl=1800, show_spinner=False, max_entries=256)
def _team_box_for_game(game_id: str) -> pd.DataFrame:
    """Aggregate player box rows into team REB/AST/FG-miss totals."""
    try:
        payload, _ = schedule24._request_json(
            "ESPN WNBA R+A Step-4 box opportunity",
            players.ESPN_SUMMARY,
            params={"event": str(game_id)},
            timeout=8,
            attempts=2,
        )
    except Exception:
        payload = None
    if not isinstance(payload, dict):
        return pd.DataFrame()

    rows = []
    for block in (payload.get("boxscore") or {}).get("players", []) or []:
        team = block.get("team") or {}
        tid = _safe_int(players._team_id(team))
        if not tid:
            continue
        reb = ast = fgm = fga = 0.0
        reb_n = ast_n = fg_n = 0
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
                rv = _num(players._pick_stat(sm, ["REB", "REBOUNDS", "REBOUNDSTOTAL"], np.nan), np.nan)
                av = _num(players._pick_stat(sm, ["AST", "ASSISTS"], np.nan), np.nan)
                fg = players._pick_stat(sm, ["FG", "FGM-A", "FIELDGOALS"], None)
                made, attempts = _made_attempt(fg)
                if np.isfinite(rv):
                    reb += rv
                    reb_n += 1
                if np.isfinite(av):
                    ast += av
                    ast_n += 1
                if np.isfinite(made) and np.isfinite(attempts):
                    fgm += made
                    fga += attempts
                    fg_n += 1
            if athletes:
                break
        rows.append({
            "TEAM_ID": tid,
            "TEAM_NAME": str(team.get("displayName") or team.get("shortDisplayName") or team.get("name") or ""),
            "TEAM_ABBR": str(team.get("abbreviation") or ""),
            "REB": reb if reb_n else np.nan,
            "AST": ast if ast_n else np.nan,
            "FGM": fgm if fg_n else np.nan,
            "FGA": fga if fg_n else np.nan,
            "FG_MISSES": (fga - fgm) if fg_n else np.nan,
        })
    return pd.DataFrame(rows)


def _season_games_before(day_str: str, team_id: int) -> pd.DataFrame:
    day = pd.to_datetime(day_str).normalize()
    tid = int(team_id or 0)
    if not tid:
        return pd.DataFrame()
    try:
        season = players._espn_season_schedule(int(day.year))
    except Exception:
        season = pd.DataFrame()
    if season is None or season.empty:
        return pd.DataFrame()
    dates = pd.to_datetime(season.get("game_date"), errors="coerce")
    away = pd.to_numeric(season.get("away_team_id"), errors="coerce").fillna(0).astype(int)
    home = pd.to_numeric(season.get("home_team_id"), errors="coerce").fillna(0).astype(int)
    out = season.loc[dates.lt(day) & (away.eq(tid) | home.eq(tid))].copy()
    if out.empty:
        return out
    out["_DATE"] = pd.to_datetime(out.get("game_date"), errors="coerce")
    return out.sort_values("_DATE", ascending=False).drop_duplicates("game_id", keep="first").reset_index(drop=True)


@st.cache_data(ttl=1200, show_spinner=False, max_entries=64)
def recent_team_environment(day_str: str, team_id: int, limit: int = 5) -> dict:
    """Recent box-score opportunity environment for one team."""
    tid = int(team_id or 0)
    games = _season_games_before(str(day_str), tid).head(int(limit))
    if games.empty:
        return {"state": "NO_SAMPLE", "games": 0}

    samples = []
    for _, game in games.iterrows():
        gid = str(game.get("game_id") or "")
        if not gid:
            continue
        box = _team_box_for_game(gid)
        if box is None or box.empty:
            continue
        tr = box.loc[pd.to_numeric(box.get("TEAM_ID"), errors="coerce").fillna(0).astype(int).eq(tid)]
        if tr.empty:
            continue
        away_id = _safe_int(game.get("away_team_id"))
        home_id = _safe_int(game.get("home_team_id"))
        oid = home_id if away_id == tid else away_id
        orow = box.loc[pd.to_numeric(box.get("TEAM_ID"), errors="coerce").fillna(0).astype(int).eq(oid)]
        if orow.empty:
            continue
        t, o = tr.iloc[0], orow.iloc[0]
        samples.append({
            "game_id": gid,
            "game_date": game.get("_DATE"),
            "TEAM_REB": _num(t.get("REB")),
            "TEAM_AST": _num(t.get("AST")),
            "TEAM_MISSES": _num(t.get("FG_MISSES")),
            "OPP_REB": _num(o.get("REB")),
            "OPP_AST": _num(o.get("AST")),
            "OPP_MISSES": _num(o.get("FG_MISSES")),
        })
    if not samples:
        return {"state": "NO_SAMPLE", "games": 0}
    frame = pd.DataFrame(samples)

    def avg(col):
        vals = pd.to_numeric(frame.get(col), errors="coerce").dropna()
        return float(vals.mean()) if len(vals) else np.nan

    return {
        "state": "READY",
        "games": int(len(frame)),
        "team_reb": avg("TEAM_REB"),
        "team_ast": avg("TEAM_AST"),
        "team_misses": avg("TEAM_MISSES"),
        "opp_reb": avg("OPP_REB"),
        "opp_ast": avg("OPP_AST"),
        "opp_misses": avg("OPP_MISSES"),
        "rows": frame,
    }


def player_role_profile(logs: pd.DataFrame, team_id: int, season_min=np.nan) -> dict:
    if logs is None or logs.empty:
        return {"state": "NO_SAMPLE"}
    season = logs.copy()
    l10 = season.head(10)
    l5 = season.head(5)

    def avg(frame, col):
        vals = pd.to_numeric(frame.get(col), errors="coerce").dropna()
        return float(vals.mean()) if len(vals) else np.nan

    min_season = _num(season_min, avg(season, "MIN"))
    min_l10 = avg(l10, "MIN")
    min_l5 = avg(l5, "MIN")
    min_sd10_vals = pd.to_numeric(l10.get("MIN"), errors="coerce").dropna()
    min_sd10 = float(min_sd10_vals.std(ddof=0)) if len(min_sd10_vals) >= 2 else np.nan

    l5_min_total = float(pd.to_numeric(l5.get("MIN"), errors="coerce").fillna(0).sum())
    l5_ra_total = float(pd.to_numeric(l5.get("RA"), errors="coerce").fillna(0).sum())
    ra36 = 36.0 * l5_ra_total / l5_min_total if l5_min_total > 0 else np.nan

    team_reb_total = team_ast_total = player_reb_total = player_ast_total = 0.0
    share_games = 0
    for _, game in l5.iterrows():
        box = _team_box_for_game(str(game.get("game_id") or ""))
        if box is None or box.empty:
            continue
        tr = box.loc[pd.to_numeric(box.get("TEAM_ID"), errors="coerce").fillna(0).astype(int).eq(int(team_id or 0))]
        if tr.empty:
            continue
        t = tr.iloc[0]
        tre = _num(t.get("REB"), np.nan)
        tas = _num(t.get("AST"), np.nan)
        pre = _num(game.get("REB"), np.nan)
        pas = _num(game.get("AST"), np.nan)
        if np.isfinite(tre) and np.isfinite(tas) and np.isfinite(pre) and np.isfinite(pas):
            team_reb_total += tre
            team_ast_total += tas
            player_reb_total += pre
            player_ast_total += pas
            share_games += 1
    reb_share = player_reb_total / team_reb_total if team_reb_total > 0 else np.nan
    ast_share = player_ast_total / team_ast_total if team_ast_total > 0 else np.nan

    delta = min_l5 - min_season if np.isfinite(min_l5) and np.isfinite(min_season) else np.nan
    if np.isfinite(delta) and delta >= 2.0:
        role, role_cls = "EXPANDING", "good"
    elif np.isfinite(delta) and delta <= -2.0:
        role, role_cls = "REDUCED", "warn"
    else:
        role, role_cls = "STEADY", "mid"

    return {
        "state": "READY",
        "season_min": min_season,
        "l10_min": min_l10,
        "l5_min": min_l5,
        "l10_min_sd": min_sd10,
        "l5_ra36": ra36,
        "l5_reb_share": reb_share,
        "l5_ast_share": ast_share,
        "share_games": int(share_games),
        "role": role,
        "role_cls": role_cls,
        "games": int(len(season)),
    }


def recent_advanced(day_str: str, team_id: int, limit: int = 5) -> dict:
    """Reuse existing verified possession engine with a recent-five window."""
    day = pd.to_datetime(day_str).normalize()
    try:
        games = team_context._season_team_games(int(day.year))
    except Exception:
        games = pd.DataFrame()
    if games is None or games.empty:
        return {"PACE": np.nan, "ORTG": np.nan, "DRTG": np.nan, "games": 0}
    games = games.loc[pd.to_datetime(games.get("GAME_DATE"), errors="coerce").lt(day)].copy()
    try:
        adv = team_context._advanced_summary(games, int(team_id or 0), int(limit))
    except Exception:
        adv = {}
    return {
        "PACE": _num((adv or {}).get("PACE_L10")),
        "ORTG": _num((adv or {}).get("ORTG_L10")),
        "DRTG": _num((adv or {}).get("DRTG_L10")),
        "games": int((adv or {}).get("ADV_GAMES", 0) or 0),
    }


def _find_game(day_str: str, game_id: str, team_id: int, opponent_id: int):
    try:
        slate = schedule24.schedule_for_date(str(day_str))
    except Exception:
        slate = pd.DataFrame()
    if slate is None or slate.empty:
        return None
    gid = str(game_id or "")
    if gid:
        match = slate.loc[slate.get("game_id", "").astype(str).eq(gid)]
        if not match.empty:
            return match.iloc[0]
    away = pd.to_numeric(slate.get("away_team_id"), errors="coerce").fillna(0).astype(int)
    home = pd.to_numeric(slate.get("home_team_id"), errors="coerce").fillna(0).astype(int)
    pair = ((away.eq(int(team_id or 0)) & home.eq(int(opponent_id or 0))) |
            (away.eq(int(opponent_id or 0)) & home.eq(int(team_id or 0))))
    match = slate.loc[pair]
    return match.iloc[0] if not match.empty else None


def availability_profile(day_str: str, player_row) -> dict:
    tid = _safe_int(player_row.get("TEAM_ID"))
    oid = _safe_int(player_row.get("opponent_team_id"))
    game = _find_game(day_str, str(player_row.get("game_id") or ""), tid, oid)
    if game is None:
        return {"state": "NO_GAME", "player_status": "STATUS CHECK"}
    away_id = _safe_int(game.get("away_team_id"))
    home_id = _safe_int(game.get("home_team_id"))
    gid = str(game.get("game_id") or "")
    try:
        raw = availability.availability_for_game_key(gid, away_id, home_id, str(day_str))
    except Exception:
        raw = {}
    injuries = pd.DataFrame((raw or {}).get("injuries") or [])
    coverage = {int(k): bool(v) for k, v in ((raw or {}).get("team_status_coverage") or {}).items()}

    player_status = "NO DESIGNATION" if coverage.get(tid, False) else "STATUS CHECK"
    detail = ""
    if not injuries.empty:
        part = injuries.loc[
            pd.to_numeric(injuries.get("TEAM_ID"), errors="coerce").fillna(0).astype(int).eq(tid)
            & injuries.get("PLAYER_NAME", pd.Series(dtype=object)).map(_norm).eq(_norm(player_row.get("PLAYER_NAME")))
        ]
        if not part.empty:
            player_status = str(part.iloc[0].get("DESIGNATION") or player_status).upper()
            detail = str(part.iloc[0].get("DETAIL") or "")

    def counts(team):
        if injuries.empty:
            return {"reports": 0, "out": 0, "uncertain": 0}
        p = injuries.loc[pd.to_numeric(injuries.get("TEAM_ID"), errors="coerce").fillna(0).astype(int).eq(int(team))]
        ds = p.get("DESIGNATION", pd.Series(dtype=object)).astype(str).str.upper()
        return {
            "reports": int(len(p)),
            "out": int(ds.isin({"OUT", "INACTIVE", "DOUBTFUL"}).sum()),
            "uncertain": int(ds.isin({"QUESTIONABLE", "DAY-TO-DAY", "PROBABLE"}).sum()),
        }

    current_day = pd.Timestamp.now(tz=ET).strftime("%Y-%m-%d")
    return {
        "state": "READY" if (raw or {}) else "CHECK",
        "player_status": player_status,
        "player_detail": detail,
        "team": counts(tid),
        "opponent": counts(oid),
        "team_covered": bool(coverage.get(tid, False)),
        "opponent_covered": bool(coverage.get(oid, False)),
        "snapshot_scope": "CURRENT SLATE" if str(day_str) == current_day else "CURRENT SNAPSHOT / NOT HISTORICAL",
        "source": str((raw or {}).get("source") or "ESPN WNBA availability"),
    }


def build_context(day_str: str, player_row, logs: pd.DataFrame) -> dict:
    tid = _safe_int(player_row.get("TEAM_ID"))
    oid = _safe_int(player_row.get("opponent_team_id"))
    team_env = recent_team_environment(str(day_str), tid, 5)
    opp_env = recent_team_environment(str(day_str), oid, 5)
    role = player_role_profile(logs, tid, player_row.get("MIN"))
    team_adv = recent_advanced(str(day_str), tid, 5)
    opp_adv = recent_advanced(str(day_str), oid, 5)
    av = availability_profile(str(day_str), player_row)

    pace_vals = [x for x in (_num(team_adv.get("PACE")), _num(opp_adv.get("PACE"))) if np.isfinite(x)]
    blended_pace = float(np.mean(pace_vals)) if pace_vals else np.nan
    assist_vals = [x for x in (_num(team_env.get("team_ast")), _num(opp_env.get("opp_ast"))) if np.isfinite(x)]
    assist_proxy = float(np.mean(assist_vals)) if assist_vals else np.nan

    valid_blocks = sum([
        str(role.get("state")) == "READY",
        str(team_env.get("state")) == "READY",
        str(opp_env.get("state")) == "READY",
        int(team_adv.get("games", 0) or 0) > 0,
        int(opp_adv.get("games", 0) or 0) > 0,
    ])
    reliability = "HIGH" if valid_blocks >= 5 else ("MEDIUM" if valid_blocks >= 3 else "LOW")

    return {
        "state": "READY" if valid_blocks >= 3 else "PARTIAL",
        "reliability": reliability,
        "role": role,
        "team_env": team_env,
        "opp_env": opp_env,
        "team_adv": team_adv,
        "opp_adv": opp_adv,
        "availability": av,
        "blended_pace": blended_pace,
        "assist_env_proxy": assist_proxy,
        "tracking_available": False,
        "source": "ESPN WNBA completed-game box summaries + existing pace/availability engines",
    }


__all__ = [
    "availability_profile", "build_context", "player_role_profile",
    "recent_advanced", "recent_team_environment",
]
