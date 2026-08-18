"""WNBA Points V1.8 — rotation-aware minutes integrity for Points only.

Fixes a Points-specific preflight failure where the frozen PRA role allocator
scaled every non-OUT current-roster player into the same 200 team minutes,
which could materially compress regular rotation players when 13-15 rostered
players were active. This module leaves frozen PRA/MLB untouched and replaces
only the isolated Points minutes handoff with a recent team-rotation anchor:

- current roster remains the V1.3 strict gate;
- actual last-3 / last-5 completed team game minutes are reconstructed from
  verified ESPN WNBA summaries, counting DNPs as zero for current-roster players;
- those recent team-rotation minutes are blended with the existing role minutes;
- OUT/INACTIVE/DOUBTFUL remain zero and confirmed starters remain protected;
- team projected minutes are re-normalized to exactly 200 with a 40-minute cap;
- PTS/REB/AST per-minute production is then recomputed before matchup factors;
- sportsbook lines never influence the minutes or projection.

Frozen WNBA PRA V3.2.1 and MLB V2.1.7 are not modified.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_players_v25 as players
import wnba_points_v13 as roster_mod
import wnba_points_v14 as prior
import wnba_pra_matchup_v30 as matchup_base
import wnba_pra_monte_carlo_v31 as mcbase
import wnba_role_v282 as role
import wnba_schedule_v25 as schedule25
import wnba_sportsgameodds_v1 as sgo1

base = prior.base
MODEL_VERSION = "WNBA POINTS V1.8 • ROTATION-AWARE MINUTES"
MODEL_SCHEMA = "WNBA-POINTS-V1.8-ROTATION-MINUTES-EMPIRICAL"
STANDARD_SIMS = prior.STANDARD_SIMS
FINAL_SIMS = prior.FINAL_SIMS
BATCH_SIZE = prior.BATCH_SIZE
CACHE_DIR = prior.CACHE_DIR
market = prior.market
sgo = prior.sgo

OUT_STATUSES = {"OUT", "INACTIVE", "DOUBTFUL"}


def _day(day):
    return pd.to_datetime(day).strftime("%Y-%m-%d")


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def std_key(day):
    return f"wnba_points_v18_standard::{_day(day)}"


def final_key(day):
    return f"wnba_points_v18_final::{_day(day)}"


def source_key(day):
    return f"wnba_points_v18_restore_source::{_day(day)}"


def _browser_key(day):
    return f"kyre_sports_ai_wnba_points_v18::{_day(day)}"


def _component_key(day):
    return f"wnba_points_v18_local_get::{_day(day)}"


def _disk_path(day):
    return CACHE_DIR / f"wnba_points_v18_{_day(day)}.json.gz"


@st.cache_data(ttl=900, show_spinner=False, max_entries=128)
def _recent_team_rotation(day_str: str, team_id: int, player_ids: tuple[int, ...]):
    """Average actual current-roster minutes across the team's last 3/5 games.

    A current-roster player absent from a verified box score receives 0 for that
    team game. That makes this a team-minute allocation signal rather than a
    conditional-on-playing player average and keeps the team total near 200.
    """
    day_str = _day(day_str)
    tid = int(team_id or 0)
    ids = tuple(sorted({int(x) for x in player_ids if int(x) > 0}))
    if not tid or not ids:
        return {}

    try:
        history = roster_mod._season_history(day_str, {tid})
    except Exception:
        history = pd.DataFrame()
    if history is None or history.empty:
        return {}

    games = history.copy()
    games["_d"] = pd.to_datetime(games["game_date"], errors="coerce")
    games = games.sort_values("_d", ascending=False).drop_duplicates("game_id").head(5)
    if games.empty:
        return {}

    minute_maps = []
    for _, game in games.iterrows():
        gid = str(game.get("game_id") or "")
        gdate = str(game.get("game_date") or "")
        if not gid:
            continue
        try:
            frame = players._espn_game_summary(gid, gdate)
        except Exception:
            frame = pd.DataFrame()
        if frame is None or frame.empty or "TEAM_ID" not in frame.columns:
            continue
        part = frame.loc[pd.to_numeric(frame["TEAM_ID"], errors="coerce").eq(tid)].copy()
        if part.empty:
            continue
        m = {}
        for _, row in part.iterrows():
            try:
                pid = int(float(row.get("PLAYER_ID")))
            except Exception:
                continue
            mins = _num(row.get("MIN"), 0.0)
            m[pid] = max(0.0, mins)
        minute_maps.append(m)

    if not minute_maps:
        return {}

    out = {}
    for pid in ids:
        vals = [float(m.get(pid, 0.0)) for m in minute_maps]
        l3 = vals[:3]
        out[pid] = {
            "games": len(vals),
            "l3": float(np.mean(l3)) if l3 else 0.0,
            "l5": float(np.mean(vals)) if vals else 0.0,
        }
    return out


def _normalize_200(anchors: pd.Series) -> pd.Series:
    """Scale non-negative anchors to exactly 200 minutes with a 40-minute cap."""
    vals = pd.to_numeric(anchors, errors="coerce").fillna(0.0).clip(lower=0.0)
    result = pd.Series(0.0, index=vals.index, dtype=float)
    remaining = list(vals[vals.gt(0)].index)
    fixed = {}
    for _ in range(10):
        if not remaining:
            break
        target = max(0.0, 200.0 - sum(fixed.values()))
        base_sum = float(vals.loc[remaining].sum())
        if base_sum <= 0:
            scaled = pd.Series(target / len(remaining), index=remaining)
        else:
            scaled = vals.loc[remaining] * (target / base_sum)
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


def _rotation_reallocate(team: pd.DataFrame, day_str: str, team_id: int) -> pd.DataFrame:
    if team is None or team.empty:
        return team
    t = team.copy()
    t["PROJ_MIN_ROLE"] = pd.to_numeric(t.get("PROJ_MIN"), errors="coerce").fillna(0.0)

    ids = []
    for value in t.get("PLAYER_ID", pd.Series(dtype=float)):
        try:
            ids.append(int(float(value)))
        except Exception:
            continue
    recent = _recent_team_rotation(day_str, int(team_id), tuple(ids))

    anchors = []
    recent_l3 = []
    recent_l5 = []
    for _, row in t.iterrows():
        try:
            pid = int(float(row.get("PLAYER_ID")))
        except Exception:
            pid = 0
        old_min = max(0.0, _num(row.get("PROJ_MIN"), _num(row.get("BASE_MIN"), 0.0)))
        info = recent.get(pid) or {}
        l3 = _num(info.get("l3"), np.nan)
        l5 = _num(info.get("l5"), np.nan)
        recent_l3.append(l3)
        recent_l5.append(l5)

        if pd.notna(l3) or pd.notna(l5):
            r3 = l3 if pd.notna(l3) else l5
            r5 = l5 if pd.notna(l5) else l3
            recent_anchor = 0.65 * max(0.0, r3) + 0.35 * max(0.0, r5)
            # Recent team rotation owns most of the signal; the old role minute
            # estimate remains a small stabilizer for returns/new acquisitions.
            anchor = 0.80 * recent_anchor + 0.20 * old_min
        else:
            anchor = old_min

        status = str(row.get("DESIGNATION") or "").upper()
        if status in OUT_STATUSES:
            anchor = 0.0
        elif bool(row.get("STARTER_CONFIRMED")):
            l10 = max(0.0, _num(row.get("L10_MIN"), old_min))
            l5_stat = max(0.0, _num(row.get("L5_MIN"), old_min))
            anchor = max(anchor, 0.45 * l10 + 0.55 * l5_stat)
        elif anchor < 0.5:
            anchor = 0.0
        anchors.append(anchor)

    t["RECENT_TEAM_L3_MIN"] = recent_l3
    t["RECENT_TEAM_L5_MIN"] = recent_l5
    t["MINUTE_ANCHOR"] = anchors
    status = t["DESIGNATION"].astype(str).str.upper() if "DESIGNATION" in t.columns else pd.Series("", index=t.index)
    active = ~status.isin(OUT_STATUSES)
    scaled = _normalize_200(t.loc[active, "MINUTE_ANCHOR"])
    t["PROJ_MIN"] = 0.0
    t.loc[active, "PROJ_MIN"] = scaled
    t.loc[~active, "PROJ_MIN"] = 0.0

    usage_ratio = pd.to_numeric(t.get("USG_RATIO", 1.0), errors="coerce").fillna(1.0).clip(0.80, 1.25)
    for stat, power in (("PTS", 0.85), ("REB", 0.08), ("AST", 0.45)):
        rate = pd.to_numeric(t.get(f"{stat}_RATE", 0.0), errors="coerce").fillna(0.0)
        t[f"PROJ_{stat}"] = rate * t["PROJ_MIN"] * np.power(usage_ratio, power)
        t.loc[~active, f"PROJ_{stat}"] = 0.0
        t[f"PROJ_{stat}"] = pd.to_numeric(t[f"PROJ_{stat}"], errors="coerce").fillna(0.0).clip(lower=0.0)
    t["PROJ_PRA"] = t["PROJ_PTS"] + t["PROJ_REB"] + t["PROJ_AST"]
    base_min = pd.to_numeric(t.get("BASE_MIN", 0.0), errors="coerce").fillna(0.0)
    t["MIN_DELTA"] = t["PROJ_MIN"] - base_min
    t["MINUTES_SOURCE"] = "POINTS recent team rotation L3/L5 + role stabilizer"
    return t


def _points_projection_frame(day):
    day_str = _day(day)
    schedule = schedule25.schedule_for_date(day_str)
    stats, player_diag = prior.corrected_player_pool(day_str)
    if schedule is None or schedule.empty or stats is None or stats.empty:
        return pd.DataFrame(), {
            "schedule": schedule, "context_diag": {}, "player_diag": player_diag,
            "projection_errors": ["corrected player pool unavailable"],
        }

    contexts, context_diag = prior.corrected_contexts(day_str)
    baseline = matchup_base._baseline_from_contexts(contexts)
    rows = []
    projection_errors = []

    for _, game in schedule.iterrows():
        status_text = str(game.get("status") or game.get("status_text") or "").upper()
        if "FINAL" in status_text:
            continue
        gid = str(game.get("game_id") or "")
        game_ctx = contexts.get(gid) or {}
        try:
            result = role.role_projection_for_game(game, stats)
        except Exception as exc:
            projection_errors.append(
                f"{game.get('away_team','Away')} @ {game.get('home_team','Home')}: {type(exc).__name__}: {exc}"
            )
            continue

        for team_id, frame in (result.get("teams") or {}).items():
            if frame is None or frame.empty:
                continue
            frame = _rotation_reallocate(frame, day_str, int(team_id))
            try:
                is_away = int(team_id) == int(game.get("away_team_id") or 0)
            except Exception:
                is_away = False
            team_side, opp_side = ("away", "home") if is_away else ("home", "away")
            factors = matchup_base._matchup_factors(
                game_ctx.get(team_side) or {}, game_ctx.get(opp_side) or {}, baseline
            )
            team_name = game.get("away_team") if is_away else game.get("home_team")
            opponent = game.get("home_team") if is_away else game.get("away_team")

            for _, p in frame.iterrows():
                name = str(p.get("PLAYER_NAME") or "").strip()
                if not name:
                    continue
                raw_pts = max(0.0, _num(p.get("PROJ_PTS"), 0.0))
                raw_reb = max(0.0, _num(p.get("PROJ_REB"), 0.0))
                raw_ast = max(0.0, _num(p.get("PROJ_AST"), 0.0))
                out = p.to_dict()
                out.update({
                    "game_id": gid,
                    "game_status": status_text,
                    "team_name": str(team_name or ""),
                    "opponent": str(opponent or ""),
                    "player_key": sgo1._norm(name),
                    "RAW_PROJ_PTS": raw_pts,
                    "RAW_PROJ_REB": raw_reb,
                    "RAW_PROJ_AST": raw_ast,
                    "RAW_PROJ_PRA": raw_pts + raw_reb + raw_ast,
                    "PROJ_PTS": raw_pts * factors["pts_factor"],
                    "PROJ_REB": raw_reb * factors["reb_factor"],
                    "PROJ_AST": raw_ast * factors["ast_factor"],
                    "POINTS_SLATE_DATE": day_str,
                    **factors,
                })
                out["PROJ_PRA"] = out["PROJ_PTS"] + out["PROJ_REB"] + out["PROJ_AST"]
                rows.append(out)

    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.drop_duplicates(subset=["game_id", "player_key"], keep="first")
    return frame, {
        "schedule": schedule,
        "context_diag": context_diag,
        "player_diag": player_diag,
        "projection_errors": projection_errors,
        "baseline": baseline,
        "schedule_version": "V2.5 ET-reconciled",
        "player_pool_version": "V1.3 strict current roster",
        "minutes_version": "V1.8 recent team rotation L3/L5",
    }


class _MatchupFacade:
    matchup_projection_frame = staticmethod(_points_projection_frame)


def _prepare(day):
    projections, pmeta = _points_projection_frame(day)
    pairs, snap = prior._paired_points_markets(day)
    schedule = pmeta.get("schedule")
    stats, _ = prior.corrected_player_pool(_day(day))
    lineups = mcbase._lineup_map(day, schedule, stats)
    return projections, pairs, snap, pmeta, lineups


# Patch only the isolated Points execution module.
base.MODEL_VERSION = MODEL_VERSION
base.MODEL_SCHEMA = MODEL_SCHEMA
base.std_key = std_key
base.final_key = final_key
base.source_key = source_key
base._browser_key = _browser_key
base._component_key = _component_key
base._disk_path = _disk_path
base.matchup = _MatchupFacade()
base._prepare = _prepare
base._points_distribution = prior._points_distribution
base.sgo = sgo

corrected_player_pool = prior.corrected_player_pool
corrected_contexts = prior.corrected_contexts
points_empirical_profile = prior.points_empirical_profile
_paired_points_markets = prior._paired_points_markets
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
    "points_empirical_profile", "_recent_team_rotation", "_rotation_reallocate",
    "_paired_points_markets", "_prepare", "_points_distribution", "_finalist_units",
    "run_standard", "run_final", "combined_rows", "restore_if_missing",
    "persist_if_ready", "render_points_connector",
]
