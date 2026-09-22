"""WNBA Points V1.9 — opponent position-scoring matchup layer.

Adds a Points-only positional defense residual on top of the existing V1.8
rotation-aware Points projection. The existing team-level pace + opponent DRTG
adjustment remains intact. To avoid double-counting overall defense, this layer
uses the opponent's last-10 share of points allowed to Guard/Wing/Big buckets
rather than raw points allowed alone. Hybrid positions are blended. The factor
is deliberately small/capped and becomes neutral when verified samples are
insufficient. Sportsbook lines never influence projections.

Frozen WNBA PRA V3.2.1 and MLB V2.1.7 are untouched.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_v18 as prior
import wnba_points_v13 as roster_mod
import wnba_players_v25 as players
import wnba_pra_matchup_v30 as matchup_base
import wnba_pra_monte_carlo_v31 as mcbase
import wnba_role_v282 as role
import wnba_schedule_v25 as schedule25
import wnba_sportsgameodds_v1 as sgo1

base = prior.base
MODEL_VERSION = "WNBA POINTS V1.9 • POSITION MATCHUP"
MODEL_SCHEMA = "WNBA-POINTS-V1.9-POSITION-MATCHUP-ROTATION-EMPIRICAL"
STANDARD_SIMS = prior.STANDARD_SIMS
FINAL_SIMS = prior.FINAL_SIMS
BATCH_SIZE = prior.BATCH_SIZE
CACHE_DIR = prior.CACHE_DIR
market = prior.market
sgo = prior.sgo


def _day(day):
    return pd.to_datetime(day).strftime("%Y-%m-%d")


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def std_key(day):
    return f"wnba_points_v19_standard::{_day(day)}"


def final_key(day):
    return f"wnba_points_v19_final::{_day(day)}"


def source_key(day):
    return f"wnba_points_v19_restore_source::{_day(day)}"


def _browser_key(day):
    return f"kyre_sports_ai_wnba_points_v19::{_day(day)}"


def _component_key(day):
    return f"wnba_points_v19_local_get::{_day(day)}"


def _disk_path(day):
    return CACHE_DIR / f"wnba_points_v19_{_day(day)}.json.gz"


def _position_weights(value) -> dict[str, float]:
    """Map ESPN WNBA roster positions to stable scoring-defense buckets."""
    pos = str(value or "").upper().replace(" ", "")
    if not pos:
        return {}
    if pos in {"PG", "SG", "G"}:
        return {"GUARD": 1.0}
    if pos in {"SF", "F"}:
        return {"WING": 1.0}
    if pos == "PF":
        return {"WING": 0.75, "BIG": 0.25}
    if pos == "C":
        return {"BIG": 1.0}
    if pos in {"G-F", "F-G", "GF", "FG"}:
        return {"GUARD": 0.50, "WING": 0.50}
    if pos in {"F-C", "C-F", "FC", "CF"}:
        return {"WING": 0.45, "BIG": 0.55}
    # Conservative textual fallbacks from provider full position names.
    if "CENTER" in pos:
        return {"BIG": 1.0}
    if "GUARD" in pos and "FORWARD" in pos:
        return {"GUARD": 0.50, "WING": 0.50}
    if "FORWARD" in pos and "CENTER" in pos:
        return {"WING": 0.45, "BIG": 0.55}
    if "GUARD" in pos:
        return {"GUARD": 1.0}
    if "FORWARD" in pos:
        return {"WING": 1.0}
    return {}


def _primary_bucket(weights: dict[str, float]) -> str:
    if not weights:
        return "UNKNOWN"
    return max(weights.items(), key=lambda kv: kv[1])[0]


@st.cache_data(ttl=1800, show_spinner=False, max_entries=64)
def _opponent_position_profile(day_str: str, defense_team_id: int):
    """Return opponent L10 scoring allowance shares by position bucket."""
    day_str = _day(day_str)
    tid = int(defense_team_id or 0)
    if not tid:
        return {"games": 0}
    try:
        history = roster_mod._season_history(day_str, {tid})
    except Exception:
        history = pd.DataFrame()
    if history is None or history.empty:
        return {"games": 0}

    games = history.loc[
        history["away_team_id"].astype(int).eq(tid)
        | history["home_team_id"].astype(int).eq(tid)
    ].copy()
    if games.empty:
        return {"games": 0}
    games["_d"] = pd.to_datetime(games["game_date"], errors="coerce")
    games = games.sort_values("_d", ascending=False).drop_duplicates("game_id").head(10)

    game_rows = []
    for _, game in games.iterrows():
        gid = str(game.get("game_id") or "")
        gdate = str(game.get("game_date") or "")
        if not gid:
            continue
        try:
            box = players._espn_game_summary(gid, gdate)
        except Exception:
            box = pd.DataFrame()
        if box is None or box.empty or "TEAM_ID" not in box.columns:
            continue
        opp = box.loc[~pd.to_numeric(box["TEAM_ID"], errors="coerce").eq(tid)].copy()
        if opp.empty:
            continue
        buckets = {"GUARD": 0.0, "WING": 0.0, "BIG": 0.0}
        total = 0.0
        for _, row in opp.iterrows():
            pts = max(0.0, _num(row.get("PTS"), 0.0))
            total += pts
            weights = _position_weights(row.get("POSITION"))
            for bucket, weight in weights.items():
                buckets[bucket] += pts * float(weight)
        bucket_total = float(sum(buckets.values()))
        # Unknown positions are excluded from the position-share denominator;
        # require most scoring to be position-classified before trusting game.
        if total <= 0 or bucket_total / total < 0.80:
            continue
        game_rows.append({**buckets, "TOTAL_CLASSIFIED": bucket_total})

    if not game_rows:
        return {"games": 0}
    frame = pd.DataFrame(game_rows)
    totals = frame["TOTAL_CLASSIFIED"].replace(0, np.nan)
    out = {"games": int(len(frame))}
    for bucket in ("GUARD", "WING", "BIG"):
        out[f"{bucket}_pts"] = float(frame[bucket].mean())
        out[f"{bucket}_share"] = float((frame[bucket] / totals).mean())
    return out


def _position_environment(day_str: str, schedule: pd.DataFrame):
    team_ids = set()
    if schedule is not None and not schedule.empty:
        for side in ("away", "home"):
            col = f"{side}_team_id"
            if col in schedule.columns:
                for value in schedule[col]:
                    try:
                        team_ids.add(int(value))
                    except Exception:
                        pass
    profiles = {tid: _opponent_position_profile(day_str, tid) for tid in sorted(team_ids)}
    baseline = {}
    for bucket in ("GUARD", "WING", "BIG"):
        vals = [
            _num(p.get(f"{bucket}_share"), np.nan)
            for p in profiles.values()
            if int(p.get("games") or 0) >= 5
        ]
        vals = [v for v in vals if pd.notna(v) and v > 0]
        baseline[bucket] = float(np.mean(vals)) if vals else np.nan
    return profiles, baseline


def _position_factor(position, opp_profile: dict, baseline: dict):
    weights = _position_weights(position)
    if not weights:
        return 1.0, "UNKNOWN", np.nan, np.nan, 0, "neutral • position unavailable"
    games = int((opp_profile or {}).get("games") or 0)
    if games < 5:
        return 1.0, _primary_bucket(weights), np.nan, np.nan, games, "neutral • <5 opponent games"

    player_share = 0.0
    baseline_share = 0.0
    valid_weight = 0.0
    for bucket, weight in weights.items():
        os = _num((opp_profile or {}).get(f"{bucket}_share"), np.nan)
        bs = _num((baseline or {}).get(bucket), np.nan)
        if pd.notna(os) and pd.notna(bs) and os > 0 and bs > 0:
            player_share += float(weight) * os
            baseline_share += float(weight) * bs
            valid_weight += float(weight)
    if valid_weight < 0.80 or baseline_share <= 0:
        return 1.0, _primary_bucket(weights), np.nan, np.nan, games, "neutral • incomplete bucket baseline"
    player_share /= valid_weight
    baseline_share /= valid_weight
    # Small residual only. Overall defense is already represented by L10 DRTG.
    factor = float(np.clip((player_share / baseline_share) ** 0.35, 0.965, 1.035))
    return factor, _primary_bucket(weights), player_share, baseline_share, games, "opp L10 position scoring share"


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
    pos_profiles, pos_baseline = _position_environment(day_str, schedule)
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
            frame = prior._rotation_reallocate(frame, day_str, int(team_id))
            try:
                is_away = int(team_id) == int(game.get("away_team_id") or 0)
            except Exception:
                is_away = False
            team_side, opp_side = ("away", "home") if is_away else ("home", "away")
            team_factors = matchup_base._matchup_factors(
                game_ctx.get(team_side) or {}, game_ctx.get(opp_side) or {}, baseline
            )
            team_name = game.get("away_team") if is_away else game.get("home_team")
            opponent = game.get("home_team") if is_away else game.get("away_team")
            try:
                opp_id = int(game.get("home_team_id") if is_away else game.get("away_team_id"))
            except Exception:
                opp_id = 0
            opp_profile = pos_profiles.get(opp_id) or {"games": 0}

            for _, p in frame.iterrows():
                name = str(p.get("PLAYER_NAME") or "").strip()
                if not name:
                    continue
                raw_pts = max(0.0, _num(p.get("PROJ_PTS"), 0.0))
                raw_reb = max(0.0, _num(p.get("PROJ_REB"), 0.0))
                raw_ast = max(0.0, _num(p.get("PROJ_AST"), 0.0))
                pos_factor, pos_bucket, pos_share, base_share, pos_games, pos_source = _position_factor(
                    p.get("POSITION"), opp_profile, pos_baseline
                )
                team_pts_factor = float(team_factors["pts_factor"])
                final_pts_factor = float(np.clip(team_pts_factor * pos_factor, 0.90, 1.10))
                out = p.to_dict()
                out.update({
                    "game_id": gid,
                    "game_status": status_text,
                    "team_name": str(team_name or ""),
                    "opponent": str(opponent or ""),
                    "opponent_team_id": opp_id,
                    "player_key": sgo1._norm(name),
                    "RAW_PROJ_PTS": raw_pts,
                    "RAW_PROJ_REB": raw_reb,
                    "RAW_PROJ_AST": raw_ast,
                    "RAW_PROJ_PRA": raw_pts + raw_reb + raw_ast,
                    "PROJ_PTS": raw_pts * final_pts_factor,
                    "PROJ_REB": raw_reb * team_factors["reb_factor"],
                    "PROJ_AST": raw_ast * team_factors["ast_factor"],
                    "POINTS_SLATE_DATE": day_str,
                    "team_pts_factor": team_pts_factor,
                    "position_factor": pos_factor,
                    "position_bucket": pos_bucket,
                    "position_allow_share": pos_share,
                    "position_baseline_share": base_share,
                    "position_games": pos_games,
                    "position_source": pos_source,
                    "pts_factor": final_pts_factor,
                    **{k: v for k, v in team_factors.items() if k != "pts_factor"},
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
        "position_baseline": pos_baseline,
        "position_profiles": pos_profiles,
        "schedule_version": "V2.5 ET-reconciled",
        "player_pool_version": "V1.3 strict current roster",
        "minutes_version": "V1.8 recent team rotation L3/L5",
        "position_version": "V1.9 opponent L10 position scoring-share residual",
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
    "points_empirical_profile", "_opponent_position_profile", "_points_projection_frame",
    "_paired_points_markets", "_prepare", "_points_distribution", "_finalist_units",
    "run_standard", "run_final", "combined_rows", "restore_if_missing",
    "persist_if_ready", "render_points_connector",
]
