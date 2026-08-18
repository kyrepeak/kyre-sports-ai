"""WNBA Points V1.3 — strict current-roster gate for the four-game Points stack.

This module keeps the Points projection and Monte Carlo math from V1.2 intact but
prevents the player pool fallback from treating every player seen during the
season as current. For each slate team it prefers the ESPN current roster. If
that endpoint is unavailable or implausibly broad, it derives a clearly-labelled
recent-active proxy from the team's last three completed WNBA games before the
selected date. Historical production is then strictly intersected with that
effective roster before role/minutes projections are built.

Frozen WNBA PRA V3.2.1 and MLB V2.1.7 modules are not modified.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_players_v25 as players
import wnba_points_v12 as prior
import wnba_schedule_v25 as schedule25

base = prior.base
MODEL_VERSION = "WNBA POINTS V1.3 • STRICT CURRENT-ROSTER GATE"
MODEL_SCHEMA = "WNBA-POINTS-V1.3-ET-STRICT-ROSTER"
STANDARD_SIMS = prior.STANDARD_SIMS
FINAL_SIMS = prior.FINAL_SIMS
BATCH_SIZE = prior.BATCH_SIZE
CACHE_DIR = prior.CACHE_DIR
market = prior.market
sgo = prior.sgo


def _day(day):
    return pd.to_datetime(day).strftime("%Y-%m-%d")


def std_key(day):
    return f"wnba_points_v13_standard::{_day(day)}"


def final_key(day):
    return f"wnba_points_v13_final::{_day(day)}"


def source_key(day):
    return f"wnba_points_v13_restore_source::{_day(day)}"


def _browser_key(day):
    return f"kyre_sports_ai_wnba_points_v13::{_day(day)}"


def _component_key(day):
    return f"wnba_points_v13_local_get::{_day(day)}"


def _disk_path(day):
    return CACHE_DIR / f"wnba_points_v13_{_day(day)}.json.gz"


def _team_ids(schedule: pd.DataFrame) -> set[int]:
    return prior._team_ids(schedule)


def _sanitize_current_roster(frame: pd.DataFrame) -> pd.DataFrame:
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
    # Current WNBA roster feeds should be compact. A huge result is treated as a
    # provider/history leak and is replaced by the recent-active proxy below.
    if len(out) < 5 or len(out) > 22:
        return pd.DataFrame()
    return out.reset_index(drop=True)


def _season_history(day_str: str, team_ids: set[int]) -> pd.DataFrame:
    try:
        season = players._espn_season_schedule(pd.to_datetime(day_str).year)
    except Exception:
        season = pd.DataFrame()
    if season is None or season.empty:
        return pd.DataFrame()
    before = pd.to_datetime(season["game_date"], errors="coerce") < pd.to_datetime(day_str)
    team_mask = (
        season["away_team_id"].astype(int).isin(team_ids)
        | season["home_team_id"].astype(int).isin(team_ids)
    )
    final_mask = season["status"].astype(str).str.upper().eq("FINAL")
    return season.loc[before & team_mask & final_mask].copy()


def _recent_proxy_for_team(team_id: int, history: pd.DataFrame, meta: dict) -> pd.DataFrame:
    if history is None or history.empty:
        return pd.DataFrame()
    tid = int(team_id)
    team_games = history.loc[
        history["away_team_id"].astype(int).eq(tid)
        | history["home_team_id"].astype(int).eq(tid)
    ].copy()
    if team_games.empty:
        return pd.DataFrame()
    team_games["_d"] = pd.to_datetime(team_games["game_date"], errors="coerce")
    team_games = team_games.sort_values("_d", ascending=False).drop_duplicates("game_id").head(3)

    frames = []
    for _, game in team_games.iterrows():
        try:
            box = players._espn_game_summary(str(game.get("game_id")), str(game.get("game_date") or ""))
        except Exception:
            box = pd.DataFrame()
        if box is None or box.empty or "TEAM_ID" not in box.columns:
            continue
        part = box.loc[pd.to_numeric(box["TEAM_ID"], errors="coerce").eq(tid)].copy()
        if not part.empty:
            frames.append(part)
    if not frames:
        return pd.DataFrame()

    logs = pd.concat(frames, ignore_index=True)
    logs["GAME_DATE"] = pd.to_datetime(logs["GAME_DATE"], errors="coerce")
    logs = logs.sort_values("GAME_DATE", ascending=False).drop_duplicates("PLAYER_ID", keep="first")
    rows = []
    for _, r in logs.iterrows():
        try:
            pid = int(r.get("PLAYER_ID"))
        except Exception:
            continue
        rows.append({
            "PLAYER_ID": pid,
            "PLAYER_NAME": str(r.get("PLAYER_NAME") or "Player"),
            "TEAM_ID": tid,
            "TEAM_NAME": str(meta.get("name") or r.get("TEAM_NAME") or ""),
            "TEAM_ABBREVIATION": str(meta.get("abbr") or r.get("TEAM_ABBREVIATION") or ""),
            "POSITION": str(r.get("POSITION") or ""),
            "ROSTER_STATUS": "RECENT_ACTIVE_PROXY",
            "PLAYER_ID_SOURCE": "ESPN",
            "ROSTER_SOURCE": "ESPN WNBA last-3-game active proxy",
        })
    return pd.DataFrame(rows)


def _strict_gate(frame: pd.DataFrame, roster: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty or roster is None or roster.empty:
        return pd.DataFrame()
    if not {"TEAM_ID", "PLAYER_ID"}.issubset(frame.columns) or not {"TEAM_ID", "PLAYER_ID"}.issubset(roster.columns):
        return pd.DataFrame()
    allowed = set()
    for _, r in roster.iterrows():
        try:
            allowed.add((int(r.get("TEAM_ID")), int(float(r.get("PLAYER_ID")))))
        except Exception:
            continue
    if not allowed:
        return pd.DataFrame()
    mask = []
    for _, r in frame.iterrows():
        try:
            mask.append((int(r.get("TEAM_ID")), int(float(r.get("PLAYER_ID")))) in allowed)
        except Exception:
            mask.append(False)
    return frame.loc[mask].copy().reset_index(drop=True)


@st.cache_data(ttl=600, show_spinner=False)
def corrected_player_pool(day_str: str):
    day_str = _day(day_str)
    schedule = schedule25.schedule_for_date(day_str)
    if schedule is None or schedule.empty:
        return pd.DataFrame(columns=players.PLAYER_COLUMNS), {
            "state": "NO_GAMES", "teams": 0, "players": 0,
            "official_roster_teams": 0, "proxy_roster_teams": 0,
            "missing_roster_teams": 0, "roster_players": 0,
            "source": "none",
        }

    team_ids = _team_ids(schedule)
    team_meta = players._team_meta(schedule)
    history = _season_history(day_str, team_ids)

    effective_frames = []
    official_teams = proxy_teams = 0
    team_modes = {}
    for tid in sorted(team_ids):
        meta = team_meta.get(int(tid), {})
        try:
            official = _sanitize_current_roster(
                players._espn_roster(int(tid), meta.get("name", ""), meta.get("abbr", ""))
            )
        except Exception:
            official = pd.DataFrame()
        if official is not None and not official.empty:
            effective_frames.append(official)
            official_teams += 1
            team_modes[int(tid)] = "CURRENT_ROSTER"
            continue

        proxy = _recent_proxy_for_team(int(tid), history, meta)
        if proxy is not None and not proxy.empty:
            effective_frames.append(proxy)
            proxy_teams += 1
            team_modes[int(tid)] = "RECENT_ACTIVE_PROXY"
        else:
            team_modes[int(tid)] = "MISSING"

    roster = pd.concat(effective_frames, ignore_index=True) if effective_frames else pd.DataFrame()
    if not roster.empty:
        roster = roster.drop_duplicates(["TEAM_ID", "PLAYER_ID"], keep="first")
    covered_teams = int(roster["TEAM_ID"].nunique()) if not roster.empty and "TEAM_ID" in roster.columns else 0
    missing_teams = max(0, len(team_ids) - covered_teams)

    # Prefer league player stats when healthy, but always hard-intersect with the
    # effective current roster before using them.
    try:
        primary = prior.old_players.player_form_table(pd.to_datetime(day_str).year)
    except Exception:
        primary = pd.DataFrame()
    if primary is not None and not primary.empty:
        try:
            primary = prior.guarded._guard_stats(primary)
        except Exception:
            primary = primary.copy()
            primary.columns = [str(c).upper() for c in primary.columns]
        if "TEAM_ID" in primary.columns:
            primary = primary[pd.to_numeric(primary["TEAM_ID"], errors="coerce").isin(team_ids)].copy()
            primary = _strict_gate(primary, roster)
        else:
            primary = pd.DataFrame()
        if not primary.empty:
            for c in players.PLAYER_COLUMNS:
                if c not in primary.columns:
                    primary[c] = 0.0 if c.endswith("_GP") else np.nan
            primary = primary.reindex(columns=players.PLAYER_COLUMNS)
            return primary.reset_index(drop=True), {
                "state": "VERIFIED_CURRENT" if missing_teams == 0 and proxy_teams == 0 else "ROSTER_PROXY",
                "teams": len(team_ids), "players": len(primary),
                "official_roster_teams": official_teams,
                "proxy_roster_teams": proxy_teams,
                "missing_roster_teams": missing_teams,
                "roster_players": len(roster),
                "team_modes": team_modes,
                "source": "WNBA Stats + strict current-roster gate",
            }

    rebuilt = players._aggregate_games(history, roster, team_meta) if not roster.empty else pd.DataFrame()
    if rebuilt is None:
        rebuilt = pd.DataFrame()
    rebuilt = _strict_gate(rebuilt, roster)
    if not rebuilt.empty:
        for c in players.PLAYER_COLUMNS:
            if c not in rebuilt.columns:
                rebuilt[c] = np.nan
        rebuilt = rebuilt.reindex(columns=players.PLAYER_COLUMNS)

    state = "VERIFIED_CURRENT" if missing_teams == 0 and proxy_teams == 0 else (
        "ROSTER_PROXY" if missing_teams == 0 else "ROSTER_INCOMPLETE"
    )
    return rebuilt.reset_index(drop=True), {
        "state": state,
        "teams": len(team_ids), "players": len(rebuilt),
        "official_roster_teams": official_teams,
        "proxy_roster_teams": proxy_teams,
        "missing_roster_teams": missing_teams,
        "roster_players": len(roster),
        "team_modes": team_modes,
        "source": "ESPN WNBA game summaries + strict current-roster gate" if not rebuilt.empty else "none",
    }


# Swap only the Points module's player-pool dependency. Functions inside the V1.2
# module resolve this global dynamically, so its matchup/projection math stays intact.
prior.corrected_player_pool = corrected_player_pool

base.MODEL_VERSION = MODEL_VERSION
base.MODEL_SCHEMA = MODEL_SCHEMA
base.std_key = std_key
base.final_key = final_key
base.source_key = source_key
base._browser_key = _browser_key
base._component_key = _component_key
base._disk_path = _disk_path
base._prepare = prior._prepare

corrected_contexts = prior.corrected_contexts
_paired_points_markets = prior._paired_points_markets
_prepare = prior._prepare
_points_distribution = prior._points_distribution
_finalist_units = prior._finalist_units
run_standard = base.run_standard
run_final = base.run_final
combined_rows = base.combined_rows
restore_if_missing = base.restore_if_missing
persist_if_ready = base.persist_if_ready
render_points_connector = base.render_points_connector

__all__ = [
    "MODEL_VERSION", "MODEL_SCHEMA", "STANDARD_SIMS", "FINAL_SIMS", "market", "sgo",
    "std_key", "final_key", "source_key", "corrected_player_pool", "corrected_contexts",
    "_paired_points_markets", "_prepare", "_points_distribution", "_finalist_units",
    "run_standard", "run_final", "combined_rows", "restore_if_missing",
    "persist_if_ready", "render_points_connector",
]
