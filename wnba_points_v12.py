"""WNBA Points V1.2 — corrected 4-game player/context handoff.

This module keeps the Points Monte Carlo/math from V1.0 intact while making every
Points-only upstream dependency use the ET-reconciled WNBA V2.5 slate:
- corrected 4-game schedule;
- current 8-team player pool;
- 8-team matchup context;
- availability/role projection using the corrected player pool;
- SportsGameOdds matching on the corrected schedule.

Frozen WNBA PRA V3.2.1 and MLB V2.1.7 modules are not modified.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_availability_v27 as availability
import wnba_context_v26 as context
import wnba_data_v22 as guarded
import wnba_data_v232 as old_players
import wnba_players_v25 as players
import wnba_points_v11 as prior
import wnba_pra_matchup_v30 as matchup_base
import wnba_pra_monte_carlo_v31 as mcbase
import wnba_role_v282 as role
import wnba_schedule_v25 as schedule25
import wnba_sportsgameodds_v1 as sgo1

base = prior.base
MODEL_VERSION = "WNBA POINTS V1.2 • 4-GAME PLAYER/CONTEXT HANDOFF"
MODEL_SCHEMA = "WNBA-POINTS-V1.2-ET-4GAME-PLAYER-CONTEXT"
STANDARD_SIMS = base.STANDARD_SIMS
FINAL_SIMS = base.FINAL_SIMS
BATCH_SIZE = base.BATCH_SIZE
CACHE_DIR = base.CACHE_DIR
market = base.market
sgo = prior.sgo


def _day(day):
    return pd.to_datetime(day).strftime("%Y-%m-%d")


def std_key(day):
    return f"wnba_points_v12_standard::{_day(day)}"


def final_key(day):
    return f"wnba_points_v12_final::{_day(day)}"


def source_key(day):
    return f"wnba_points_v12_restore_source::{_day(day)}"


def _browser_key(day):
    return f"kyre_sports_ai_wnba_points_v12::{_day(day)}"


def _component_key(day):
    return f"wnba_points_v12_local_get::{_day(day)}"


def _disk_path(day):
    return CACHE_DIR / f"wnba_points_v12_{_day(day)}.json.gz"


def _team_ids(schedule: pd.DataFrame) -> set[int]:
    if schedule is None or schedule.empty:
        return set()
    return set(
        schedule["away_team_id"].astype(int).tolist()
        + schedule["home_team_id"].astype(int).tolist()
    )


def _safe_roster_gate(primary: pd.DataFrame, roster: pd.DataFrame) -> pd.DataFrame:
    if primary is None or primary.empty or roster is None or roster.empty:
        return primary if isinstance(primary, pd.DataFrame) else pd.DataFrame()
    if not {"TEAM_ID", "PLAYER_ID"}.issubset(primary.columns) or not {"TEAM_ID", "PLAYER_ID"}.issubset(roster.columns):
        return primary
    allowed = set()
    for _, r in roster.iterrows():
        try:
            allowed.add((int(r.get("TEAM_ID")), int(float(r.get("PLAYER_ID")))))
        except Exception:
            continue
    if not allowed:
        return primary
    overlap_mask = []
    overlaps = 0
    for _, r in primary.iterrows():
        try:
            key = (int(r.get("TEAM_ID")), int(float(r.get("PLAYER_ID"))))
            ok = key in allowed
        except Exception:
            ok = False
        overlap_mask.append(ok)
        overlaps += int(ok)
    return primary.loc[overlap_mask].copy() if overlaps else primary


@st.cache_data(ttl=600, show_spinner=False)
def corrected_player_pool(day_str: str):
    """Build the current player pool from the corrected ET slate, not frozen PRA schedule state."""
    day_str = _day(day_str)
    schedule = schedule25.schedule_for_date(day_str)
    if schedule is None or schedule.empty:
        return pd.DataFrame(columns=players.PLAYER_COLUMNS), {
            "state": "NO_GAMES", "teams": 0, "players": 0, "rosters_connected": 0,
            "source": "none",
        }

    team_ids = _team_ids(schedule)
    team_meta = players._team_meta(schedule)
    roster_frames = []
    for tid in sorted(team_ids):
        meta = team_meta.get(int(tid), {})
        try:
            frame = players._espn_roster(int(tid), meta.get("name", ""), meta.get("abbr", ""))
        except Exception:
            frame = pd.DataFrame()
        if frame is not None and not frame.empty:
            roster_frames.append(frame)
    roster = pd.concat(roster_frames, ignore_index=True) if roster_frames else pd.DataFrame()

    # Primary league player table first.
    try:
        primary = old_players.player_form_table(pd.to_datetime(day_str).year)
    except Exception:
        primary = pd.DataFrame()
    if primary is not None and not primary.empty:
        try:
            primary = guarded._guard_stats(primary)
        except Exception:
            primary = primary.copy()
            primary.columns = [str(c).upper() for c in primary.columns]
        if "TEAM_ID" in primary.columns:
            primary = primary[pd.to_numeric(primary["TEAM_ID"], errors="coerce").isin(team_ids)].copy()
        else:
            primary = pd.DataFrame()
        primary = _safe_roster_gate(primary, roster)
        if primary is not None and not primary.empty:
            for c in players.PLAYER_COLUMNS:
                if c not in primary.columns:
                    primary[c] = 0.0 if c.endswith("_GP") else np.nan
            primary = primary.reindex(columns=players.PLAYER_COLUMNS)
            primary["TEAM_ID"] = pd.to_numeric(primary["TEAM_ID"], errors="coerce")
            primary = primary.dropna(subset=["TEAM_ID"]).copy()
            primary["TEAM_ID"] = primary["TEAM_ID"].astype(int)
            return primary.reset_index(drop=True), {
                "state": "VERIFIED", "teams": len(team_ids), "players": len(primary),
                "rosters_connected": len(roster_frames), "roster_players": len(roster),
                "source": "WNBA Stats LeagueID=10 + ESPN current rosters",
            }

    # Streamlit/provider fallback: reconstruct production from prior completed ESPN games.
    try:
        season_schedule = players._espn_season_schedule(pd.to_datetime(day_str).year)
    except Exception:
        season_schedule = pd.DataFrame()
    history = pd.DataFrame()
    if season_schedule is not None and not season_schedule.empty:
        before = pd.to_datetime(season_schedule["game_date"], errors="coerce") < pd.to_datetime(day_str)
        team_mask = (
            season_schedule["away_team_id"].astype(int).isin(team_ids)
            | season_schedule["home_team_id"].astype(int).isin(team_ids)
        )
        final_mask = season_schedule["status"].astype(str).str.upper().eq("FINAL")
        history = season_schedule[before & team_mask & final_mask].copy()
    rebuilt = players._aggregate_games(history, roster, team_meta)
    if rebuilt is None:
        rebuilt = pd.DataFrame()
    if not rebuilt.empty:
        for c in players.PLAYER_COLUMNS:
            if c not in rebuilt.columns:
                rebuilt[c] = np.nan
        rebuilt = rebuilt.reindex(columns=players.PLAYER_COLUMNS)
    return rebuilt.reset_index(drop=True), {
        "state": "VERIFIED" if not rebuilt.empty else "PROVIDER_FAILURE",
        "teams": len(team_ids), "players": len(rebuilt),
        "rosters_connected": len(roster_frames), "roster_players": len(roster),
        "source": "ESPN WNBA game-summary fallback" if not rebuilt.empty else "none",
    }


@st.cache_data(ttl=900, show_spinner=False)
def corrected_contexts(day_str: str):
    """Build matchup context for every game on the corrected ET slate."""
    day_str = _day(day_str)
    schedule = schedule25.schedule_for_date(day_str)
    if schedule is None or schedule.empty:
        return {}, {"state": "NO_GAMES", "games": 0, "teams": 0}
    selected = pd.to_datetime(day_str)
    season = int(selected.year)
    try:
        season_games = context._season_team_games(season)
    except Exception:
        season_games = pd.DataFrame()
    if season_games is not None and not season_games.empty:
        season_games = season_games[
            pd.to_datetime(season_games["GAME_DATE"], errors="coerce") < selected
        ].copy()
    try:
        history = context._historical_games_through(day_str)
    except Exception:
        history = pd.DataFrame()

    contexts = {}
    records_verified = advanced_teams = advanced_games = h2h_samples = 0
    for _, game in schedule.iterrows():
        away_id = int(game.get("away_team_id") or 0)
        home_id = int(game.get("home_team_id") or 0)
        away = context._record_summary(season_games, away_id)
        home = context._record_summary(season_games, home_id)
        away.update(context._advanced_summary(season_games, away_id, 10))
        home.update(context._advanced_summary(season_games, home_id, 10))
        h2h = context._h2h(history, away_id, home_id, season)
        gid = str(game.get("game_id") or f"{away_id}-{home_id}")
        contexts[gid] = {
            "away": away, "home": home, "h2h": h2h,
            "source": "ESPN WNBA season scoreboard + game summaries",
        }
        records_verified += int(away.get("GP", 0) > 0) + int(home.get("GP", 0) > 0)
        for obj in (away, home):
            if int(obj.get("ADV_GAMES", 0) or 0) > 0:
                advanced_teams += 1
                advanced_games += int(obj.get("ADV_GAMES", 0) or 0)
        h2h_samples += int(h2h.get("GAMES", 0) or 0)
    teams = len(_team_ids(schedule))
    return contexts, {
        "state": "VERIFIED" if records_verified == teams else "PARTIAL",
        "selected_date": day_str, "games": len(schedule), "teams": teams,
        "records_verified": records_verified, "advanced_teams": advanced_teams,
        "advanced_games": advanced_games, "h2h_samples": h2h_samples,
        "source": "Points-only corrected 4-game context",
    }


def _points_projection_frame(day):
    day_str = _day(day)
    schedule = schedule25.schedule_for_date(day_str)
    stats, player_diag = corrected_player_pool(day_str)
    if schedule is None or schedule.empty or stats is None or stats.empty:
        return pd.DataFrame(), {
            "schedule": schedule, "context_diag": {}, "player_diag": player_diag,
            "projection_errors": ["corrected player pool unavailable"],
        }
    if "TEAM_ID" not in stats.columns:
        return pd.DataFrame(), {
            "schedule": schedule, "context_diag": {}, "player_diag": player_diag,
            "projection_errors": ["corrected player pool missing TEAM_ID"],
        }

    contexts, context_diag = corrected_contexts(day_str)
    baseline = matchup_base._baseline_from_contexts(contexts)
    rows = []
    projection_errors = []

    for _, game in schedule.iterrows():
        status = str(game.get("status") or game.get("status_text") or "").upper()
        if "FINAL" in status:
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
                raw_pts = max(0.0, base._num(p.get("PROJ_PTS"), 0.0))
                raw_reb = max(0.0, base._num(p.get("PROJ_REB"), 0.0))
                raw_ast = max(0.0, base._num(p.get("PROJ_AST"), 0.0))
                out = p.to_dict()
                out.update({
                    "game_id": gid,
                    "game_status": status,
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
        "player_pool_version": "V1.2 corrected 8-team pool",
    }


class _MatchupFacade:
    matchup_projection_frame = staticmethod(_points_projection_frame)


def _prepare(day):
    projections, pmeta = _points_projection_frame(day)
    pairs, snap = base._paired_points_markets(day)
    schedule = pmeta.get("schedule")
    stats, _ = corrected_player_pool(_day(day))
    lineups = mcbase._lineup_map(day, schedule, stats)
    return projections, pairs, snap, pmeta, lineups


# Redirect only the isolated Points engine. Frozen PRA/MLB modules are untouched.
base.MODEL_VERSION = MODEL_VERSION
base.MODEL_SCHEMA = MODEL_SCHEMA
base.std_key = std_key
base.final_key = final_key
base.source_key = source_key
base._browser_key = _browser_key
base._component_key = _component_key
base._disk_path = _disk_path
base.sgo = sgo
base.matchup = _MatchupFacade()
base._prepare = _prepare

_paired_points_markets = base._paired_points_markets
_points_distribution = base._points_distribution
_finalist_units = base._finalist_units
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
