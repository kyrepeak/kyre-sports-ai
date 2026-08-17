"""WNBA PRA V2.8 — Step 5 projected minutes + role/usage engine.

Step 5 turns verified availability into player-level basketball inputs. It keeps
Steps 1-4 intact, then:
- projects conditional minutes from season/L10/L5 minutes,
- sets OUT/INACTIVE/DOUBTFUL players to 0,
- honors explicit starter flags without guessing starters,
- reallocates the 200 team minutes across available players,
- loads official WNBA Advanced USG% when accessible,
- estimates a conservative usage/role change when teammates are unavailable,
- projects PTS, REB and AST separately from per-minute rates.

Opponent/position defense, sportsbook lines and final Over/Under probabilities
are intentionally NOT applied in this step.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import streamlit as st

import wnba_availability_v27 as availability
import wnba_data_v21 as v21
import wnba_data_v232 as resilient

OUT_STATUSES = {"OUT", "INACTIVE", "DOUBTFUL"}
UNCERTAIN_STATUSES = {"QUESTIONABLE", "DAY-TO-DAY", "PROBABLE"}


def _day_str(day=None) -> str:
    day = day or st.session_state.get("wnba_pra_v2_date") or pd.Timestamp.now().date()
    return pd.to_datetime(day).strftime("%Y-%m-%d")


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _weighted(values, weights, fallback=0.0):
    pairs = [(float(v), float(w)) for v, w in zip(values, weights) if pd.notna(v)]
    if not pairs:
        return float(fallback)
    den = sum(w for _, w in pairs)
    return sum(v * w for v, w in pairs) / den if den else float(fallback)


def _advanced_params(season: int, last_n: int = 0) -> dict:
    params = v21._player_params(int(season), int(last_n)).copy()
    params["MeasureType"] = "Advanced"
    return params


def _normalize_usage(value):
    x = _num(value, np.nan)
    if pd.isna(x):
        return np.nan
    return x * 100.0 if abs(x) <= 1.5 else x


@st.cache_data(ttl=900, show_spinner=False)
def _advanced_usage_fetch(season: int, last_n: int = 0):
    params = _advanced_params(int(season), int(last_n))
    for host in resilient.PLAYER_HOSTS:
        try:
            payload = resilient._json_response(
                host, params=params, headers=resilient._player_headers(host), timeout=7
            )
            frame = resilient.transport.base._frame_from_result(payload)
            if frame is None or frame.empty:
                continue
            frame.columns = [str(c).upper() for c in frame.columns]
            if "PLAYER_ID" not in frame.columns or "TEAM_ID" not in frame.columns:
                continue
            keep = [c for c in ("PLAYER_ID", "TEAM_ID", "PLAYER_NAME", "MIN", "USG_PCT", "PIE") if c in frame.columns]
            frame = frame[keep].copy()
            frame["PLAYER_ID"] = pd.to_numeric(frame["PLAYER_ID"], errors="coerce")
            frame["TEAM_ID"] = pd.to_numeric(frame["TEAM_ID"], errors="coerce")
            if "USG_PCT" in frame.columns:
                frame["USG_PCT"] = frame["USG_PCT"].map(_normalize_usage)
            source = "WNBA Stats Advanced" if "wnba.com" in host else "NBA Stats LeagueID=10 Advanced fallback"
            frame["USG_SOURCE"] = source
            return frame.dropna(subset=["PLAYER_ID", "TEAM_ID"]).reset_index(drop=True), source
        except Exception:
            continue
    return pd.DataFrame(), "unavailable"


@st.cache_data(ttl=900, show_spinner=False)
def advanced_usage_table(season: int | None = None):
    season = int(season or availability.current_season())
    results, sources = {}, []
    for label, last_n in (("SEASON", 0), ("L10", 10), ("L5", 5)):
        frame, source = _advanced_usage_fetch(season, last_n)
        results[label] = frame
        if source != "unavailable":
            sources.append(source)
    base = results.get("SEASON", pd.DataFrame())
    if base.empty:
        return pd.DataFrame(), "unavailable"
    cols = [c for c in ("PLAYER_ID", "TEAM_ID", "PLAYER_NAME", "USG_PCT") if c in base.columns]
    out = base[cols].copy()
    for label in ("L10", "L5"):
        recent = results.get(label, pd.DataFrame())
        if recent is None or recent.empty or "USG_PCT" not in recent.columns:
            continue
        r = recent[["PLAYER_ID", "TEAM_ID", "USG_PCT"]].copy().rename(columns={"USG_PCT": f"{label}_USG_PCT"})
        out = out.merge(r, on=["PLAYER_ID", "TEAM_ID"], how="left")
    for c in ("USG_PCT", "L10_USG_PCT", "L5_USG_PCT"):
        if c not in out.columns:
            out[c] = np.nan
    source = " + ".join(dict.fromkeys(sources)) if sources else "unavailable"
    return out, source


def _stat_rate(row, stat: str):
    mins = [_num(row.get("MIN")), _num(row.get("L10_MIN")), _num(row.get("L5_MIN"))]
    vals = [_num(row.get(stat)), _num(row.get(f"L10_{stat}")), _num(row.get(f"L5_{stat}"))]
    rates = []
    for val, minute in zip(vals, mins):
        rates.append((val / minute) if pd.notna(val) and pd.notna(minute) and minute > 1 else np.nan)
    return _weighted(rates, [0.40, 0.35, 0.25], fallback=0.0)


def _base_minutes(row):
    season = _num(row.get("MIN"), 0.0)
    l10 = _num(row.get("L10_MIN"), np.nan)
    l5 = _num(row.get("L5_MIN"), np.nan)
    value = _weighted([season, l10, l5], [0.30, 0.40, 0.30], fallback=season)
    return float(np.clip(value, 0.0, 40.0))


def _merge_availability(pool: pd.DataFrame, av_frame: pd.DataFrame):
    if pool is None or pool.empty:
        return pd.DataFrame()
    out = pool.copy()
    out["DESIGNATION"] = "NO DESIGNATION"
    out["DETAIL"] = ""
    out["STARTER_CONFIRMED"] = False
    if av_frame is None or av_frame.empty:
        return out
    amap = {}
    for _, r in av_frame.iterrows():
        key = (int(r.get("TEAM_ID") or 0), availability._norm_name(r.get("PLAYER_NAME")))
        amap[key] = r
    for idx, p in out.iterrows():
        key = (int(p.get("TEAM_ID") or 0), availability._norm_name(p.get("PLAYER_NAME")))
        r = amap.get(key)
        if r is not None:
            out.at[idx, "DESIGNATION"] = str(r.get("DESIGNATION") or "NO DESIGNATION")
            out.at[idx, "DETAIL"] = str(r.get("DETAIL") or "")
            out.at[idx, "STARTER_CONFIRMED"] = bool(r.get("STARTER_CONFIRMED"))
    return out


def _attach_usage(pool: pd.DataFrame, usage: pd.DataFrame):
    out = pool.copy()
    for c in ("USG_PCT", "L10_USG_PCT", "L5_USG_PCT"):
        out[c] = np.nan
    if usage is None or usage.empty:
        return out
    by_id = {}
    for _, r in usage.iterrows():
        if pd.notna(r.get("PLAYER_ID")):
            by_id[(int(r.get("TEAM_ID") or 0), int(float(r.get("PLAYER_ID"))))] = r
    for idx, p in out.iterrows():
        pid = p.get("PLAYER_ID")
        if pd.isna(pid):
            continue
        r = by_id.get((int(p.get("TEAM_ID") or 0), int(float(pid))))
        if r is not None:
            for c in ("USG_PCT", "L10_USG_PCT", "L5_USG_PCT"):
                out.at[idx, c] = _num(r.get(c), np.nan)
    return out


def _redistribute_team_minutes(team: pd.DataFrame) -> pd.DataFrame:
    """Allocate exactly 200 conditional minutes across non-out current players."""
    t = team.copy()
    t["BASE_MIN"] = t.apply(_base_minutes, axis=1)
    status = t["DESIGNATION"].astype(str).str.upper()
    out_mask = status.isin(OUT_STATUSES)
    t["PROJ_MIN"] = t["BASE_MIN"]
    t.loc[out_mask, "PROJ_MIN"] = 0.0

    starter_mask = t["STARTER_CONFIRMED"].fillna(False).astype(bool) & ~out_mask
    for idx in t[starter_mask].index:
        l10 = _num(t.at[idx, "L10_MIN"], t.at[idx, "BASE_MIN"])
        l5 = _num(t.at[idx, "L5_MIN"], t.at[idx, "BASE_MIN"])
        t.at[idx, "PROJ_MIN"] = min(40.0, max(t.at[idx, "PROJ_MIN"], 0.45 * l10 + 0.55 * l5 + 0.75))

    active = ~out_mask
    if active.sum() == 0:
        return t
    vals = t.loc[active, "PROJ_MIN"].astype(float).clip(lower=0.25).copy()
    remaining_indices = list(vals.index)
    fixed = {}
    for _ in range(8):
        if not remaining_indices:
            break
        remaining_target = 200.0 - sum(fixed.values())
        base_sum = float(vals.loc[remaining_indices].sum())
        scaled = vals.loc[remaining_indices] * (remaining_target / base_sum) if base_sum > 0 else pd.Series(remaining_target / len(remaining_indices), index=remaining_indices)
        over = scaled[scaled > 40.0]
        if over.empty:
            for i, v in scaled.items():
                fixed[i] = float(max(0.0, v))
            remaining_indices = []
            break
        for i in list(over.index):
            fixed[i] = 40.0
            remaining_indices.remove(i)
    if remaining_indices:
        remaining_target = max(0.0, 200.0 - sum(fixed.values()))
        base_sum = float(vals.loc[remaining_indices].sum())
        for i in remaining_indices:
            fixed[i] = remaining_target * (float(vals.loc[i]) / base_sum) if base_sum else remaining_target / len(remaining_indices)
    for i, v in fixed.items():
        t.at[i, "PROJ_MIN"] = float(np.clip(v, 0.0, 40.0))
    t.loc[out_mask, "PROJ_MIN"] = 0.0
    return t


def _usage_baseline(row):
    season = _num(row.get("USG_PCT"), np.nan)
    l10 = _num(row.get("L10_USG_PCT"), np.nan)
    l5 = _num(row.get("L5_USG_PCT"), np.nan)
    if all(pd.isna(x) for x in (season, l10, l5)):
        return np.nan
    return _weighted([season, l10, l5], [0.45, 0.35, 0.20], fallback=season if pd.notna(season) else 0.0)


def _apply_role(team: pd.DataFrame) -> pd.DataFrame:
    t = team.copy()
    t["BASE_USG"] = t.apply(_usage_baseline, axis=1)
    status = t["DESIGNATION"].astype(str).str.upper()
    out_mask = status.isin(OUT_STATUSES)
    active = ~out_mask
    missing_minutes = float(t.loc[out_mask, "BASE_MIN"].sum())
    t["ROLE_DELTA_PCT"] = 0.0
    t["PROJ_USG"] = t["BASE_USG"]
    if active.any():
        active_usg = t.loc[active, "BASE_USG"].copy()
        if active_usg.notna().any():
            median_usg = float(active_usg.dropna().median())
            weights = active_usg.fillna(median_usg).clip(lower=8.0)
            starter_mult = pd.Series(np.where(t.loc[active, "STARTER_CONFIRMED"].fillna(False).astype(bool), 1.15, 1.0), index=weights.index)
            weights = weights * starter_mult
            weights = weights / max(float(weights.sum()), 1e-9)
            team_role_pool = min(8.0, (missing_minutes / 200.0) * 10.0)
            deltas = (weights * team_role_pool).clip(upper=4.0)
            t.loc[active, "ROLE_DELTA_PCT"] = deltas
            t.loc[active, "PROJ_USG"] = t.loc[active, "BASE_USG"] + deltas
        else:
            t.loc[active, "PROJ_USG"] = np.nan
    t.loc[out_mask, "PROJ_USG"] = 0.0
    t.loc[out_mask, "ROLE_DELTA_PCT"] = 0.0
    return t


def _project_stats(team: pd.DataFrame) -> pd.DataFrame:
    t = team.copy()
    for stat in ("PTS", "REB", "AST"):
        t[f"{stat}_RATE"] = t.apply(lambda r: _stat_rate(r, stat), axis=1)
    usage_ratio = pd.Series(1.0, index=t.index, dtype=float)
    valid = pd.to_numeric(t["BASE_USG"], errors="coerce").gt(1) & pd.to_numeric(t["PROJ_USG"], errors="coerce").gt(0)
    usage_ratio.loc[valid] = (
        pd.to_numeric(t.loc[valid, "PROJ_USG"], errors="coerce") / pd.to_numeric(t.loc[valid, "BASE_USG"], errors="coerce")
    ).clip(0.80, 1.25)
    t["USG_RATIO"] = usage_ratio
    t["PROJ_PTS"] = t["PTS_RATE"] * t["PROJ_MIN"] * np.power(t["USG_RATIO"], 0.85)
    t["PROJ_REB"] = t["REB_RATE"] * t["PROJ_MIN"] * np.power(t["USG_RATIO"], 0.08)
    t["PROJ_AST"] = t["AST_RATE"] * t["PROJ_MIN"] * np.power(t["USG_RATIO"], 0.45)
    status = t["DESIGNATION"].astype(str).str.upper()
    out_mask = status.isin(OUT_STATUSES)
    for c in ("PROJ_PTS", "PROJ_REB", "PROJ_AST"):
        t.loc[out_mask, c] = 0.0
        t[c] = pd.to_numeric(t[c], errors="coerce").fillna(0.0).clip(lower=0.0)
    t["PROJ_PRA"] = t["PROJ_PTS"] + t["PROJ_REB"] + t["PROJ_AST"]
    t["MIN_DELTA"] = t["PROJ_MIN"] - t["BASE_MIN"]
    t["ROLE_LABEL"] = np.where(
        out_mask, "OUT",
        np.where(t["STARTER_CONFIRMED"].fillna(False).astype(bool), "CONFIRMED STARTER",
                 np.where(status.isin(UNCERTAIN_STATUSES), "STATUS UNCERTAIN", "ACTIVE")),
    )
    return t


def role_projection_for_game(row, stats: pd.DataFrame | None = None) -> dict:
    if stats is None:
        stats = availability.player_form_table()
    av = availability.availability_for_game(row, stats)
    av_frame = av.get("players") if isinstance(av, dict) else pd.DataFrame()
    game_pool = availability.slate_player_pool(pd.DataFrame([row]), stats)
    usage, usage_source = advanced_usage_table(pd.to_datetime(_day_str(row.get("game_date"))).year)
    pool = _attach_usage(_merge_availability(game_pool, av_frame), usage)
    teams = {}
    for tid in (int(row.get("away_team_id") or 0), int(row.get("home_team_id") or 0)):
        part = pool[pd.to_numeric(pool["TEAM_ID"], errors="coerce").eq(tid)].copy()
        if part.empty:
            teams[tid] = part
            continue
        part = _redistribute_team_minutes(part)
        part = _apply_role(part)
        part = _project_stats(part)
        teams[tid] = part.sort_values(["PROJ_MIN", "PROJ_PRA"], ascending=False).reset_index(drop=True)
    return {"teams": teams, "usage_source": usage_source, "availability_source": av.get("source") if isinstance(av, dict) else "—"}


@st.cache_data(ttl=180, show_spinner=False)
def _role_diag_for_day(day_str: str):
    day_str = _day_str(day_str)
    schedule = availability.schedule_for_date(day_str)
    stats = availability.player_form_table()
    if schedule is None or schedule.empty:
        return {"state":"NO_GAMES","selected_date":day_str,"games":0,"teams":0,"players":0,"out_applied":0,"uncertain":0,"starter_flags":0,"usage_players":0,"team_minutes_ok":0,"usage_source":"unavailable"}
    total_players = out_applied = uncertain = starter_flags = usage_players = team_minutes_ok = team_seen = 0
    usage_sources = []
    for _, row in schedule.iterrows():
        result = role_projection_for_game(row, stats)
        usage_sources.append(result.get("usage_source") or "unavailable")
        for _, frame in result["teams"].items():
            team_seen += 1
            if frame is None or frame.empty:
                continue
            total_players += len(frame)
            status = frame["DESIGNATION"].astype(str).str.upper()
            out_applied += int(status.isin(OUT_STATUSES).sum())
            uncertain += int(status.isin(UNCERTAIN_STATUSES).sum())
            starter_flags += int(frame["STARTER_CONFIRMED"].fillna(False).sum())
            usage_players += int(pd.to_numeric(frame["BASE_USG"], errors="coerce").notna().sum())
            if abs(float(frame["PROJ_MIN"].sum()) - 200.0) <= 0.5:
                team_minutes_ok += 1
    source = " + ".join(dict.fromkeys(x for x in usage_sources if x != "unavailable")) or "unavailable"
    state = "VERIFIED" if total_players and team_minutes_ok == team_seen else "PARTIAL"
    return {"state":state,"selected_date":day_str,"games":int(len(schedule)),"teams":int(team_seen),"players":int(total_players),"out_applied":int(out_applied),"uncertain":int(uncertain),"starter_flags":int(starter_flags),"usage_players":int(usage_players),"team_minutes_ok":int(team_minutes_ok),"usage_source":source}


def role_diagnostics(day: str | date) -> dict:
    return _role_diag_for_day(_day_str(day))


def clear_role_cache():
    for fn in (_advanced_usage_fetch, advanced_usage_table, _role_diag_for_day):
        try:
            fn.clear()
        except Exception:
            pass


schedule_for_date = availability.schedule_for_date
schedule_diagnostics = availability.schedule_diagnostics
clear_schedule_cache = availability.clear_schedule_cache
current_season = availability.current_season
data_health = availability.data_health
empirical_profile = availability.empirical_profile
game_for_team = availability.game_for_team
logo_url = availability.logo_url
official_roster = availability.official_roster
player_game_log = availability.player_game_log
player_form_table = availability.player_form_table
slate_player_pool = availability.slate_player_pool
team_player_pool = availability.team_player_pool
availability_for_game = availability.availability_for_game
availability_diagnostics = availability.availability_diagnostics
context_diagnostics = availability.context_diagnostics
game_context = availability.game_context
