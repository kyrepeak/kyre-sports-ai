"""WNBA PRA V2.7 — Step 4 availability + confirmed-starter verification.

Step 4 only. Keeps the verified schedule, current roster/player production and
team matchup context intact. Adds provider-reported injury designations and
explicit starter flags when they are actually published. Missing starter flags
remain PENDING; they are never inferred from minutes, recent games or reputation.

This module also hard-gates the displayed/statistical slate pool to the current
rosters by team + normalized player name so historical/traded rows cannot inflate
the active player count.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
import re
import unicodedata

import numpy as np
import pandas as pd
import streamlit as st

import wnba_context_v26 as context
import wnba_players_v25 as players
import wnba_schedule_v24 as schedule_v24

ESPN_SUMMARY = players.ESPN_SUMMARY
ESPN_TEAM_INJURIES = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/teams/{team}/injuries"


def _day_str(day=None) -> str:
    day = day or st.session_state.get("wnba_pra_v2_date") or pd.Timestamp.now().date()
    return pd.to_datetime(day).strftime("%Y-%m-%d")


def _norm_name(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]", "", text)


def _team_ids(schedule: pd.DataFrame) -> list[int]:
    if schedule is None or schedule.empty:
        return []
    ids = schedule["away_team_id"].astype(int).tolist() + schedule["home_team_id"].astype(int).tolist()
    return sorted(set(ids))


def _rosters_for_schedule(schedule: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for tid in _team_ids(schedule):
        try:
            r = players.official_roster(int(tid))
        except Exception:
            r = pd.DataFrame()
        if r is not None and not r.empty:
            r = r.copy()
            r["TEAM_ID"] = int(tid)
            frames.append(r)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _pick_stat_row(team_stats: pd.DataFrame, roster_row: pd.Series):
    if team_stats is None or team_stats.empty:
        return None
    pid = roster_row.get("PLAYER_ID")
    if pd.notna(pid) and "PLAYER_ID" in team_stats.columns:
        exact = team_stats[pd.to_numeric(team_stats["PLAYER_ID"], errors="coerce").eq(float(pid))]
        if not exact.empty:
            if "MIN" in exact.columns:
                exact = exact.assign(_m=pd.to_numeric(exact["MIN"], errors="coerce").fillna(-1)).sort_values("_m", ascending=False)
            return exact.iloc[0]
    target = _norm_name(roster_row.get("PLAYER_NAME"))
    if not target:
        return None
    names = team_stats.get("PLAYER_NAME", pd.Series(index=team_stats.index, dtype=object)).map(_norm_name)
    match = team_stats[names.eq(target)]
    if match.empty:
        return None
    if "MIN" in match.columns:
        match = match.assign(_m=pd.to_numeric(match["MIN"], errors="coerce").fillna(-1)).sort_values("_m", ascending=False)
    return match.iloc[0]


@st.cache_data(ttl=600, show_spinner=False)
def _verified_pool_for_day(day_str: str):
    day_str = _day_str(day_str)
    schedule = context.schedule_for_date(day_str)
    if schedule is None or schedule.empty:
        return pd.DataFrame(), {"state":"NO_GAMES","players":0,"roster_players":0,"teams":0,"raw_rows":0}
    try:
        raw = players.player_form_table(pd.to_datetime(day_str).year)
    except Exception:
        raw = pd.DataFrame()
    roster = _rosters_for_schedule(schedule)
    if roster is None or roster.empty:
        return pd.DataFrame(), {"state":"PROVIDER_FAILURE","players":0,"roster_players":0,"teams":len(_team_ids(schedule)),"raw_rows":len(raw)}

    rows = []
    raw = raw.copy() if raw is not None else pd.DataFrame()
    raw_cols = list(raw.columns)
    for _, rr in roster.drop_duplicates(subset=["TEAM_ID","PLAYER_NAME"], keep="first").iterrows():
        tid = int(rr.get("TEAM_ID") or 0)
        team_stats = raw[pd.to_numeric(raw.get("TEAM_ID", pd.Series(index=raw.index)), errors="coerce").eq(tid)] if not raw.empty and "TEAM_ID" in raw.columns else pd.DataFrame()
        sr = _pick_stat_row(team_stats, rr)
        base = {c: (sr.get(c) if sr is not None else np.nan) for c in raw_cols}
        for c in players.PLAYER_COLUMNS:
            base.setdefault(c, np.nan)
        for c in ["PLAYER_ID","PLAYER_NAME","TEAM_ID","TEAM_NAME","TEAM_ABBREVIATION","POSITION","ROSTER_STATUS"]:
            val = rr.get(c)
            if pd.notna(val) and str(val) != "":
                base[c] = val
        if sr is None:
            for c in ["GP","MIN","PTS","REB","AST","PRA","L10_GP","L10_MIN","L10_PTS","L10_REB","L10_AST","L10_PRA","L5_GP","L5_MIN","L5_PTS","L5_REB","L5_AST","L5_PRA"]:
                base[c] = 0.0
            base["DATA_SOURCE"] = "Current roster • no matched production row"
        rows.append(base)
    out = pd.DataFrame(rows)
    if not out.empty:
        for c in players.PLAYER_COLUMNS:
            if c not in out.columns:
                out[c] = np.nan
        out = out.reindex(columns=players.PLAYER_COLUMNS)
        out["_MIN"] = pd.to_numeric(out["MIN"], errors="coerce").fillna(0)
        out = out.sort_values(["TEAM_ID","_MIN"], ascending=[True,False]).drop(columns="_MIN").reset_index(drop=True)
    diag = {
        "state":"VERIFIED" if len(out) == len(roster.drop_duplicates(subset=["TEAM_ID","PLAYER_NAME"])) else "PARTIAL",
        "players":int(len(out)),
        "roster_players":int(len(roster.drop_duplicates(subset=["TEAM_ID","PLAYER_NAME"]))),
        "teams":int(len(_team_ids(schedule))),
        "raw_rows":int(len(raw)),
    }
    return out, diag


def player_form_table(season: int | None = None) -> pd.DataFrame:
    pool, _ = _verified_pool_for_day(_day_str())
    return pool


def slate_player_pool(schedule: pd.DataFrame, stats: pd.DataFrame) -> pd.DataFrame:
    if schedule is None or schedule.empty or stats is None or stats.empty:
        return pd.DataFrame(columns=(stats.columns if isinstance(stats, pd.DataFrame) else []))
    ids = _team_ids(schedule)
    return stats[pd.to_numeric(stats["TEAM_ID"], errors="coerce").isin(ids)].copy().reset_index(drop=True)


def team_player_pool(stats: pd.DataFrame, team_id: int) -> pd.DataFrame:
    if stats is None or stats.empty or "TEAM_ID" not in stats.columns:
        return pd.DataFrame(columns=(stats.columns if isinstance(stats, pd.DataFrame) else []))
    return stats[pd.to_numeric(stats["TEAM_ID"], errors="coerce").eq(int(team_id))].copy().reset_index(drop=True)


def player_pool_diagnostics(day: str | date) -> dict:
    _, diag = _verified_pool_for_day(_day_str(day))
    return diag


def _team_id_from_obj(team) -> int:
    try:
        return int(players._team_id(team or {}) or 0)
    except Exception:
        try:
            return int((team or {}).get("id") or 0)
        except Exception:
            return 0


def _athlete_from_item(item: dict) -> dict:
    athlete = item.get("athlete") if isinstance(item.get("athlete"), dict) else item
    return athlete if isinstance(athlete, dict) else {}


def _status_text(value) -> str:
    if isinstance(value, dict):
        value = value.get("name") or value.get("description") or value.get("type") or value.get("status")
    return str(value or "").strip()


def _normalize_designation(value: str) -> str:
    s = str(value or "").upper()
    if "OUT" in s or "INACTIVE" in s:
        return "OUT"
    if "DOUBT" in s:
        return "DOUBTFUL"
    if "QUESTION" in s or s == "Q":
        return "QUESTIONABLE"
    if "PROB" in s:
        return "PROBABLE"
    if "AVAILABLE" in s or "ACTIVE" in s:
        return "AVAILABLE"
    if "DAY-TO-DAY" in s or "DAY TO DAY" in s:
        return "DAY-TO-DAY"
    return s or "NO DESIGNATION"


def _injury_detail(item: dict) -> str:
    pieces = []
    typ = item.get("type")
    if isinstance(typ, dict):
        pieces.append(str(typ.get("description") or typ.get("name") or ""))
    elif typ:
        pieces.append(str(typ))
    for key in ("details","shortComment","longComment","description","comment"):
        val = item.get(key)
        if isinstance(val, dict):
            val = val.get("detail") or val.get("description") or val.get("text")
        if val:
            pieces.append(str(val))
    clean = []
    for p in pieces:
        p = p.strip()
        if p and p not in clean:
            clean.append(p)
    return " • ".join(clean[:3])


def _parse_injury_container(container, default_team_id=0) -> list[dict]:
    rows = []
    if not container:
        return rows
    blocks = container if isinstance(container, list) else [container]
    for block in blocks:
        if not isinstance(block, dict):
            continue
        block_tid = _team_id_from_obj(block.get("team")) or int(default_team_id or 0)
        items = block.get("injuries") or block.get("items")
        if not isinstance(items, list):
            items = [block] if block.get("athlete") else []
        for item in items:
            if not isinstance(item, dict):
                continue
            athlete = _athlete_from_item(item)
            name = athlete.get("displayName") or athlete.get("fullName") or item.get("displayName")
            if not name:
                continue
            raw_status = _status_text(item.get("status") or item.get("type") or item.get("designation"))
            rows.append({
                "TEAM_ID": block_tid,
                "PLAYER_ID": athlete.get("id") or item.get("id"),
                "PLAYER_NAME": str(name),
                "DESIGNATION": _normalize_designation(raw_status),
                "DETAIL": _injury_detail(item),
                "INJURY_SOURCE": "ESPN WNBA",
            })
    return rows


def _walk_starters(obj, team_hint=0, out=None):
    if out is None:
        out = []
    if isinstance(obj, list):
        for x in obj:
            _walk_starters(x, team_hint, out)
        return out
    if not isinstance(obj, dict):
        return out
    local_team = _team_id_from_obj(obj.get("team")) or int(team_hint or 0)
    athlete = _athlete_from_item(obj)
    starter_flag = obj.get("starter") is True or obj.get("starting") is True or athlete.get("starter") is True
    name = athlete.get("displayName") or athlete.get("fullName")
    if starter_flag and name:
        out.append({
            "TEAM_ID": local_team,
            "PLAYER_ID": athlete.get("id"),
            "PLAYER_NAME": str(name),
            "STARTER_CONFIRMED": True,
            "STARTER_SOURCE": "ESPN WNBA explicit starter flag",
        })
    for key, val in obj.items():
        if key in ("athlete","team"):
            continue
        if isinstance(val, (dict,list)):
            _walk_starters(val, local_team, out)
    return out


@st.cache_data(ttl=180, show_spinner=False)
def _event_summary(game_id: str):
    payload, meta = schedule_v24._request_json(
        "ESPN WNBA availability summary",
        ESPN_SUMMARY,
        params={"event": str(game_id)},
        timeout=7,
        attempts=2,
    )
    return payload, meta


@st.cache_data(ttl=300, show_spinner=False)
def _team_injury_feed(team_id: int):
    slug = players.TEAM_SLUGS.get(int(team_id))
    if not slug:
        return None, {"ok":False,"reason":"no team slug"}
    payload, meta = schedule_v24._request_json(
        "ESPN WNBA team injuries",
        ESPN_TEAM_INJURIES.format(team=slug),
        timeout=6,
        attempts=2,
    )
    return payload, meta


def _merge_rows(rows: list[dict], keys=("TEAM_ID","PLAYER_NAME")) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    f = pd.DataFrame(rows)
    f["_NAME"] = f["PLAYER_NAME"].map(_norm_name)
    subset = ["TEAM_ID","_NAME"]
    return f.drop_duplicates(subset=subset, keep="first").drop(columns="_NAME").reset_index(drop=True)


@st.cache_data(ttl=180, show_spinner=False)
def availability_for_game_key(game_id: str, away_id: int, home_id: int, day_str: str):
    injury_rows, starter_rows = [], []
    summary_payload, summary_meta = _event_summary(str(game_id))
    summary_connected = isinstance(summary_payload, dict)
    if summary_connected:
        injury_rows.extend(_parse_injury_container(summary_payload.get("injuries")))
        starter_rows.extend(_walk_starters(summary_payload))

    team_feed_connected = 0
    for tid in (int(away_id), int(home_id)):
        try:
            payload, meta = _team_injury_feed(tid)
        except Exception:
            payload, meta = None, {}
        if isinstance(payload, dict):
            team_feed_connected += 1
            injury_rows.extend(_parse_injury_container(payload.get("injuries") or payload, tid))

    injuries = _merge_rows(injury_rows)
    starters = _merge_rows(starter_rows)
    return {
        "injuries": injuries.to_dict("records") if not injuries.empty else [],
        "starters": starters.to_dict("records") if not starters.empty else [],
        "summary_connected": bool(summary_connected),
        "team_feeds_connected": int(team_feed_connected),
        "source": "ESPN WNBA event summary + team injury feeds",
    }


def availability_for_game(row, stats: pd.DataFrame | None = None) -> dict:
    away_id = int(row.get("away_team_id") or 0)
    home_id = int(row.get("home_team_id") or 0)
    game_id = str(row.get("game_id") or "")
    day_str = _day_str(row.get("game_date") or None)
    raw = availability_for_game_key(game_id, away_id, home_id, day_str)
    injuries = pd.DataFrame(raw.get("injuries") or [])
    starters = pd.DataFrame(raw.get("starters") or [])

    if stats is None:
        stats = player_form_table()
    pool = slate_player_pool(pd.DataFrame([row]), stats) if stats is not None else pd.DataFrame()
    rows = []
    starter_names = set()
    if not starters.empty:
        starter_names = set((int(r.TEAM_ID), _norm_name(r.PLAYER_NAME)) for _, r in starters.iterrows())
    injury_map = {}
    if not injuries.empty:
        for _, r in injuries.iterrows():
            injury_map[(int(r.get("TEAM_ID") or 0), _norm_name(r.get("PLAYER_NAME")))] = r
    for _, p in pool.iterrows():
        tid = int(p.get("TEAM_ID") or 0)
        key = (tid, _norm_name(p.get("PLAYER_NAME")))
        inj = injury_map.get(key)
        designation = str(inj.get("DESIGNATION")) if inj is not None else "NO DESIGNATION"
        detail = str(inj.get("DETAIL") or "") if inj is not None else ""
        roster_status = str(p.get("ROSTER_STATUS") or "").upper()
        if designation == "NO DESIGNATION" and ("INACTIVE" in roster_status or "OUT" in roster_status):
            designation = "INACTIVE"
            detail = "Current roster status"
        rows.append({
            "TEAM_ID": tid,
            "PLAYER_ID": p.get("PLAYER_ID"),
            "PLAYER_NAME": p.get("PLAYER_NAME"),
            "DESIGNATION": designation,
            "DETAIL": detail,
            "STARTER_CONFIRMED": key in starter_names,
            "STARTER_SOURCE": "ESPN WNBA explicit starter flag" if key in starter_names else "",
        })
    frame = pd.DataFrame(rows)
    starter_counts = {}
    for tid in (away_id, home_id):
        starter_counts[tid] = int(frame[(frame["TEAM_ID"].eq(tid)) & (frame["STARTER_CONFIRMED"].eq(True))].shape[0]) if not frame.empty else 0
    return {
        "players": frame,
        "injuries": injuries,
        "starters": starters,
        "summary_connected": raw.get("summary_connected", False),
        "team_feeds_connected": raw.get("team_feeds_connected", 0),
        "starter_counts": starter_counts,
        "source": raw.get("source"),
    }


@st.cache_data(ttl=180, show_spinner=False)
def _availability_diag_for_day(day_str: str):
    day_str = _day_str(day_str)
    schedule = context.schedule_for_date(day_str)
    stats, pool_diag = _verified_pool_for_day(day_str)
    if schedule is None or schedule.empty:
        return {"state":"NO_GAMES","selected_date":day_str,"games":0,"teams":0,"players":0,"injury_designations":0,"confirmed_starters":0,"lineups_confirmed":0,"summary_feeds":0,"team_injury_feeds":0,"pool_diag":pool_diag}
    injury_count = starter_count = lineups_confirmed = summary_feeds = team_feeds = 0
    for _, row in schedule.iterrows():
        av = availability_for_game(row, stats)
        p = av["players"]
        if not p.empty:
            injury_count += int((p["DESIGNATION"].astype(str) != "NO DESIGNATION").sum())
            starter_count += int(p["STARTER_CONFIRMED"].sum())
        summary_feeds += int(bool(av.get("summary_connected")))
        team_feeds += int(av.get("team_feeds_connected") or 0)
        counts = av.get("starter_counts") or {}
        lineups_confirmed += int(counts.get(int(row.get("away_team_id") or 0), 0) >= 5)
        lineups_confirmed += int(counts.get(int(row.get("home_team_id") or 0), 0) >= 5)
    teams = len(_team_ids(schedule))
    connected = summary_feeds > 0 or team_feeds > 0
    return {
        "state":"CONNECTED" if connected else "CHECK",
        "selected_date":day_str,
        "games":int(len(schedule)),
        "teams":int(teams),
        "players":int(len(stats)),
        "injury_designations":int(injury_count),
        "confirmed_starters":int(starter_count),
        "lineups_confirmed":int(lineups_confirmed),
        "summary_feeds":int(summary_feeds),
        "team_injury_feeds":int(team_feeds),
        "pool_diag":pool_diag,
        "source":"ESPN WNBA explicit availability/starter fields",
    }


def availability_diagnostics(day: str | date) -> dict:
    return _availability_diag_for_day(_day_str(day))


def clear_availability_cache():
    for fn in (_verified_pool_for_day, _event_summary, _team_injury_feed, availability_for_game_key, _availability_diag_for_day):
        try:
            fn.clear()
        except Exception:
            pass


# Preserve Step 1-3 interfaces.
schedule_for_date = context.schedule_for_date
schedule_diagnostics = context.schedule_diagnostics
clear_schedule_cache = context.clear_schedule_cache
current_season = context.current_season
data_health = context.data_health
empirical_profile = context.empirical_profile
game_for_team = context.game_for_team
logo_url = context.logo_url
official_roster = context.official_roster
player_game_log = context.player_game_log
context_diagnostics = context.context_diagnostics
game_context = context.game_context
clear_context_cache = context.clear_context_cache
