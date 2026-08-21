from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
import wnba_spread_hub_v16 as base

MODEL_VERSION = "WNBA SPREAD V1.6.1 • AVAILABILITY REPAIR"
foundation = base.foundation
availability = foundation.availability


def _num(v, default=np.nan):
    try:
        x = float(v)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _verified_flag(v):
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    return str(v).strip().lower() in {"true", "1", "yes"}


def _availability_snapshot_exact_day(day_str, schedule):
    if schedule is None or schedule.empty:
        return pd.DataFrame()
    try:
        stats, pool_diag = availability.base._verified_pool_for_day(str(day_str))
    except Exception as exc:
        stats, pool_diag = pd.DataFrame(), {"state": "FAIL", "reason": type(exc).__name__}
    if not isinstance(stats, pd.DataFrame):
        stats = pd.DataFrame()
    pool_state = str((pool_diag or {}).get("state") or "CHECK").upper()
    rows = []
    explicit = set(availability.OUT_STATUSES) | set(availability.UNCERTAIN_STATUSES) | {"ACTIVE", "AVAILABLE"}

    for _, game in schedule.iterrows():
        g = game.copy()
        g["game_date"] = str(day_str)
        away_id = int(_num(g.get("away_team_id"), 0) or 0)
        home_id = int(_num(g.get("home_team_id"), 0) or 0)
        try:
            av = availability.availability_for_game(g, stats)
        except Exception as exc:
            av = {"players": pd.DataFrame(), "starter_counts": {}, "team_status_coverage": {}, "source": type(exc).__name__}
        players = av.get("players") if isinstance(av.get("players"), pd.DataFrame) else pd.DataFrame()
        coverage = {int(k): bool(v) for k, v in (av.get("team_status_coverage") or {}).items()}
        covered_ids = {k for k, v in coverage.items() if v}
        designations = players.get("DESIGNATION", pd.Series(dtype=object)).astype(str).str.upper() if not players.empty else pd.Series(dtype=object)
        hard_out = int(designations.isin(set(availability.OUT_STATUSES)).sum()) if not designations.empty else 0
        uncertain = int(designations.isin(set(availability.UNCERTAIN_STATUSES)).sum()) if not designations.empty else 0
        unverified = 0
        for _, p in players.iterrows():
            tid = int(_num(p.get("TEAM_ID"), 0) or 0)
            designation = str(p.get("DESIGNATION") or "").upper().strip()
            if not (_verified_flag(p.get("AVAILABILITY_VERIFIED")) or tid in covered_ids or designation in explicit):
                unverified += 1
        if pool_state != "VERIFIED":
            unverified = max(1, unverified)
        starters = av.get("starter_counts") or {}
        rows.append({
            "game_id": str(g.get("game_id") or ""),
            "away": str(g.get("away_team") or "Away"),
            "home": str(g.get("home_team") or "Home"),
            "away_id": away_id,
            "home_id": home_id,
            "away_starters": int(starters.get(away_id, 0) or 0),
            "home_starters": int(starters.get(home_id, 0) or 0),
            "covered_teams": int(bool(coverage.get(away_id))) + int(bool(coverage.get(home_id))),
            "hard_out": hard_out,
            "uncertain": uncertain,
            "unverified": int(unverified),
            "pool_state": pool_state,
            "source": str(av.get("source") or "—"),
        })
    return pd.DataFrame(rows)


foundation._availability_snapshot = _availability_snapshot_exact_day


def render_wnba_spread_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.caption("🛡️ Spread V1.6.1 • exact-day availability isolation ACTIVE")
    return base.render_wnba_spread_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_spread_hub", "_availability_snapshot_exact_day"]
