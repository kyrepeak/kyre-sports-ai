"""WNBA Rebounds V1.3.2 — precise Step 4 sparse-history repair.

Preserves the verified V1.3 Step-4 OREB/DREB role semantics. Primary history
remains the player's recent games for the current team. If a current rotation
player has fewer than three component-valid appearances there, this build
searches earlier completed WNBA games across the same season by immutable ESPN
PLAYER_ID. This handles recent trades/signings without inventing statistics or
weakening the minimum-sample gate.

No rebound projection, sportsbook input, or Monte Carlo is introduced here.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_rebounds_hub_v13 as base

MODEL_VERSION = "WNBA REBOUNDS V1.3.2 • STEP 4 VERIFIED PLAYER-HISTORY ROLE"


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


@st.cache_data(ttl=1800, show_spinner=False, max_entries=512)
def _player_components_any_team(game_id: str, game_date: str, player_ids: tuple[int, ...]) -> pd.DataFrame:
    """Return verified OREB/DREB rows for requested PLAYER_IDs from either team."""
    wanted = {int(x) for x in player_ids if int(x) > 0}
    if not wanted:
        return pd.DataFrame()
    players = base.players
    try:
        payload, _ = players.schedule_v24._request_json(
            "ESPN WNBA sparse rebound-role summary",
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
    for team_block in (payload.get("boxscore") or {}).get("players", []) or []:
        team = team_block.get("team") or {}
        tid = int(players._team_id(team) or 0)
        for group in team_block.get("statistics", []) or []:
            athletes = group.get("athletes") or []
            if not athletes:
                continue
            for item in athletes:
                athlete = item.get("athlete") or {}
                try:
                    pid = int(athlete.get("id") or 0)
                except Exception:
                    pid = 0
                if pid not in wanted or bool(item.get("didNotPlay")):
                    continue
                stats = players._summary_stat_map(group, item)
                mins = players._minutes(base._pick_stat(stats, ["MIN", "MINUTES"], np.nan))
                oreb = _num(base._pick_stat(stats, ["OREB", "OFFENSIVEREBOUNDS", "OFFENSIVE REBOUNDS", "OFFREBOUNDS"], np.nan))
                dreb = _num(base._pick_stat(stats, ["DREB", "DEFENSIVEREBOUNDS", "DEFENSIVE REBOUNDS", "DEFREBOUNDS"], np.nan))
                reb = _num(base._pick_stat(stats, ["REB", "REBOUNDS", "REBOUNDSTOTAL", "TOTALREBOUNDS", "TOTAL REBOUNDS"], np.nan))
                if pd.isna(oreb) and not pd.isna(reb) and not pd.isna(dreb):
                    oreb = max(0.0, reb - dreb)
                if pd.isna(dreb) and not pd.isna(reb) and not pd.isna(oreb):
                    dreb = max(0.0, reb - oreb)
                if pd.isna(reb) and not pd.isna(oreb) and not pd.isna(dreb):
                    reb = oreb + dreb
                if _num(mins, 0.0) <= 0 or pd.isna(oreb) or pd.isna(dreb):
                    continue
                rows.append({
                    "GAME_ID": str(game_id),
                    "GAME_DATE": str(game_date),
                    "PLAYER_ID": pid,
                    "TEAM_ID_AT_GAME": tid,
                    "MIN": _num(mins, 0.0),
                    "OREB": oreb,
                    "DREB": dreb,
                    "REB": reb,
                })
            break
    return pd.DataFrame(rows)


def _summarize_player_rows(frame: pd.DataFrame) -> dict:
    if frame is None or frame.empty:
        return {"gp": 0}
    p = frame.copy()
    p["_d"] = pd.to_datetime(p.get("GAME_DATE"), errors="coerce")
    p = p.sort_values("_d", ascending=False).drop_duplicates("GAME_ID").head(10)
    mins = float(pd.to_numeric(p["MIN"], errors="coerce").fillna(0).sum())
    oreb = float(pd.to_numeric(p["OREB"], errors="coerce").fillna(0).sum())
    dreb = float(pd.to_numeric(p["DREB"], errors="coerce").fillna(0).sum())
    reb = oreb + dreb
    return {
        "gp": int(len(p)), "minutes": mins, "oreb": oreb, "dreb": dreb, "reb": reb,
        "oreb36": (36.0 * oreb / mins) if mins > 0 else np.nan,
        "dreb36": (36.0 * dreb / mins) if mins > 0 else np.nan,
        "reb36": (36.0 * reb / mins) if mins > 0 else np.nan,
        "oreb_share": (oreb / reb) if reb > 0 else np.nan,
        "dreb_share": (dreb / reb) if reb > 0 else np.nan,
        "reb_per_min": (reb / mins) if mins > 0 else np.nan,
    }


@st.cache_data(ttl=1800, show_spinner=False, max_entries=64)
def _recent_rebound_role_precise(day_str: str, team_id: int, player_ids: tuple[int, ...]):
    """Player-last-10 verified role sample with cross-team fallback by PLAYER_ID."""
    players = base.players
    day = pd.to_datetime(day_str).strftime("%Y-%m-%d")
    tid = int(team_id or 0)
    ids = tuple(sorted({int(x) for x in player_ids if int(x) > 0}))
    if not tid or not ids:
        return {}, 0, 0

    try:
        season = players._espn_season_schedule(pd.to_datetime(day).year)
    except Exception:
        season = pd.DataFrame()
    if season is None or season.empty:
        return {}, 0, 0

    season = season.copy()
    season["_d"] = pd.to_datetime(season.get("game_date"), errors="coerce")
    final = season.get("status", pd.Series("", index=season.index)).astype(str).str.upper().eq("FINAL")
    before = season["_d"] < pd.to_datetime(day)
    all_games = season.loc[before & final].sort_values("_d", ascending=False).drop_duplicates("game_id")

    team_mask = (
        pd.to_numeric(all_games.get("away_team_id"), errors="coerce").eq(tid)
        | pd.to_numeric(all_games.get("home_team_id"), errors="coerce").eq(tid)
    )
    current_games = all_games.loc[team_mask].head(24)

    collected = []
    scanned_ids = set()
    component_games = 0
    for _, game in current_games.iterrows():
        gid = str(game.get("game_id") or "")
        if not gid:
            continue
        scanned_ids.add(gid)
        frame = _player_components_any_team(gid, str(game.get("game_date") or ""), ids)
        if not frame.empty:
            component_games += 1
            collected.append(frame)

    hist = pd.concat(collected, ignore_index=True) if collected else pd.DataFrame()
    counts = hist.groupby("PLAYER_ID").size().to_dict() if not hist.empty else {}
    missing = {pid for pid in ids if int(counts.get(pid, 0)) < 3}

    # Precise fallback for recent acquisitions / sparse current-team samples.
    # Scan earlier league games only until every missing player reaches 3 verified games.
    if missing:
        for _, game in all_games.iterrows():
            gid = str(game.get("game_id") or "")
            if not gid or gid in scanned_ids:
                continue
            frame = _player_components_any_team(gid, str(game.get("game_date") or ""), tuple(sorted(missing)))
            if not frame.empty:
                collected.append(frame)
                if hist.empty:
                    hist = frame.copy()
                else:
                    hist = pd.concat([hist, frame], ignore_index=True)
                counts = hist.groupby("PLAYER_ID").size().to_dict()
                missing = {pid for pid in missing if int(counts.get(pid, 0)) < 3}
                if not missing:
                    break

    hist = pd.concat(collected, ignore_index=True) if collected else pd.DataFrame()
    result = {}
    for pid in ids:
        p = hist.loc[pd.to_numeric(hist.get("PLAYER_ID"), errors="coerce").eq(pid)].copy() if not hist.empty else pd.DataFrame()
        result[pid] = _summarize_player_rows(p)

    return result, len(current_games), component_games


# Patch V1.3 only at the history resolver; all Step-4 readiness logic remains strict.
base._recent_rebound_role = _recent_rebound_role_precise


def _versioned_markdown_132(body, *args, **kwargs):
    text = str(body)
    text = text.replace("WNBA Rebounds Command Center — V1.3", "WNBA Rebounds Command Center — V1.3.2")
    return base.impl._ORIGINAL_MARKDOWN(text, *args, **kwargs)


def _caption_132(body, *args, **kwargs):
    text = str(body)
    if text.startswith("🧲 WNBA Rebounds V1.3") or text.startswith("⏱️ WNBA Rebounds V1.2"):
        text = (
            "🧲 WNBA Rebounds V1.3.2 • Steps 1–4 active • precise PLAYER_ID history fallback • "
            "verified OREB/DREB role • no rebound projection/market/simulation yet"
        )
    return base._ORIGINAL_CAPTION(text, *args, **kwargs)


def _sparse_diagnostic():
    rows = st.session_state.get("wnba_rebounds_step4_players") or []
    if not rows or st.session_state.get("wnba_rebounds_step4_ready"):
        return
    frame = pd.DataFrame(rows)
    if frame.empty:
        return
    frame["PROJ_MIN"] = pd.to_numeric(frame.get("PROJ_MIN"), errors="coerce").fillna(0.0)
    frame["REB_ROLE_GP"] = pd.to_numeric(frame.get("REB_ROLE_GP"), errors="coerce").fillna(0).astype(int)
    fail = frame[frame["PROJ_MIN"].ge(5.0) & (frame["REB_ROLE_GP"].lt(3) | pd.to_numeric(frame.get("OREB36"), errors="coerce").isna() | pd.to_numeric(frame.get("DREB36"), errors="coerce").isna())].copy()
    if fail.empty:
        return
    fail["Player"] = fail.get("PLAYER_NAME", "Player")
    fail["Team"] = fail.get("TEAM_NAME", "")
    fail["Proj MIN"] = fail["PROJ_MIN"].round(1)
    fail["Verified GP"] = fail["REB_ROLE_GP"]
    st.warning("🔎 Exact Step-4 blocker(s) — still not bypassed or guessed:")
    st.dataframe(fail[["Player", "Team", "Proj MIN", "Verified GP"]], hide_index=True, use_container_width=True)


def render_wnba_rebounds_hub(*args, **kwargs):
    old_versioned = base._versioned_markdown
    old_caption_v13 = base._caption_v13
    base._versioned_markdown = _versioned_markdown_132
    base._caption_v13 = _caption_132
    try:
        out = base.render_wnba_rebounds_hub(*args, **kwargs)
        _sparse_diagnostic()
        return out
    finally:
        base._versioned_markdown = old_versioned
        base._caption_v13 = old_caption_v13


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
