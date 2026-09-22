"""WNBA Points V1.1 — corrected-slate adapter for the isolated Points engine.

Keeps the existing Points Monte Carlo/math intact while replacing only its WNBA
schedule and SportsGameOdds matching inputs with schedule V2.5, which assigns
slates by Eastern Time and reconciles schedule providers. Frozen PRA/MLB modules
are not modified.
"""
from __future__ import annotations

import pandas as pd
import requests

import wnba_context_v26 as context
import wnba_points_v10 as base
import wnba_pra_matchup_v30 as matchup_base
import wnba_role_v282 as role
import wnba_schedule_v25 as schedule25
import wnba_sportsgameodds_v1 as sgo1

MODEL_VERSION = "WNBA POINTS V1.1 • ET-RECONCILED SLATE"
MODEL_SCHEMA = "WNBA-POINTS-V1.1-ET-RECONCILED"
STANDARD_SIMS = base.STANDARD_SIMS
FINAL_SIMS = base.FINAL_SIMS
BATCH_SIZE = base.BATCH_SIZE
CACHE_DIR = base.CACHE_DIR
market = base.market


def _day(day):
    return pd.to_datetime(day).strftime("%Y-%m-%d")


def std_key(day):
    return f"wnba_points_v11_standard::{_day(day)}"


def final_key(day):
    return f"wnba_points_v11_final::{_day(day)}"


def source_key(day):
    return f"wnba_points_v11_restore_source::{_day(day)}"


def _browser_key(day):
    return f"kyre_sports_ai_wnba_points_v11::{_day(day)}"


def _component_key(day):
    return f"wnba_points_v11_local_get::{_day(day)}"


def _disk_path(day):
    return CACHE_DIR / f"wnba_points_v11_{_day(day)}.json.gz"


def _market_snapshot(day):
    key = sgo1.get_api_key()
    if not key:
        return sgo1._empty_result(day, "NO_API_KEY")
    try:
        schedule = schedule25.schedule_for_date(day)
    except Exception as exc:
        return sgo1._empty_result(day, "SCHEDULE_ERROR", f"{type(exc).__name__}: {exc}")
    if schedule is None or schedule.empty:
        out = sgo1._empty_result(day, "NO_WNBA_GAMES")
        out["schedule_games"] = 0
        return out

    starts_after, starts_before = sgo1._slate_window(day)
    try:
        events = sgo1._fetch_events(key, starts_after, starts_before, sgo1.get_bookmakers())
    except requests.HTTPError as exc:
        response = getattr(exc, "response", None)
        code = getattr(response, "status_code", None)
        label = f"HTTP {code}" if code else type(exc).__name__
        out = sgo1._empty_result(day, "PROVIDER_ERROR", label)
        out["schedule_games"] = int(len(schedule))
        return out
    except Exception as exc:
        out = sgo1._empty_result(day, "PROVIDER_ERROR", f"{type(exc).__name__}: {exc}")
        out["schedule_games"] = int(len(schedule))
        return out

    game_rows, prop_rows, unmatched = [], [], []
    matched = 0
    for _, row in schedule.iterrows():
        event = sgo1._match_event(events, row)
        if event is None:
            unmatched.append(f"{row.get('away_team','Away')} @ {row.get('home_team','Home')}")
            continue
        matched += 1
        game_id = row.get("game_id")
        game_rows.extend(sgo1._parse_game_lines(event, game_id))
        prop_rows.extend(sgo1._parse_props(event, game_id))

    game_df = pd.DataFrame(game_rows)
    prop_df = pd.DataFrame(prop_rows)
    state = "CONNECTED" if matched else ("NO_OPEN_WNBA_MARKETS" if not events else "MATCH_FAILURE")
    return {
        "selected_date": _day(day),
        "provider": "SportsGameOdds",
        "league": sgo1.SGO_LEAGUE_ID,
        "state": state,
        "events_received": len(events),
        "schedule_games": int(len(schedule)),
        "matched_games": matched,
        "unmatched_games": unmatched,
        "game_lines": game_df,
        "player_props": prop_df,
        "error": None,
        "bookmakers": sgo1.get_bookmakers(),
        "schedule_version": "V2.5 ET-reconciled",
    }


class _SGOFacade:
    market_snapshot = staticmethod(_market_snapshot)
    _norm = staticmethod(sgo1._norm)


sgo = _SGOFacade()


def _points_projection_frame(day):
    schedule = schedule25.schedule_for_date(day)
    stats = role.player_form_table()
    if schedule is None or schedule.empty or stats is None or stats.empty:
        return pd.DataFrame(), {"schedule": schedule, "context_diag": {}, "availability_diag": {}}

    contexts, context_diag = context.slate_context(_day(day))
    baseline = matchup_base._baseline_from_contexts(contexts)
    try:
        availability_diag = role.availability_diagnostics(day)
    except Exception:
        availability_diag = {}

    rows = []
    for _, game in schedule.iterrows():
        status = str(game.get("status") or game.get("status_text") or "").upper()
        if "FINAL" in status:
            continue

        game_id = str(game.get("game_id") or "")
        game_ctx = contexts.get(game_id) or context.game_context(game, day) or {}
        result = role.role_projection_for_game(game, stats)

        for team_id, frame in (result.get("teams") or {}).items():
            if frame is None or frame.empty:
                continue
            try:
                is_away = int(team_id) == int(game.get("away_team_id") or 0)
            except Exception:
                is_away = False
            team_side, opp_side = ("away", "home") if is_away else ("home", "away")
            team_ctx = game_ctx.get(team_side) or {}
            opp_ctx = game_ctx.get(opp_side) or {}
            factors = matchup_base._matchup_factors(team_ctx, opp_ctx, baseline)
            team_name = game.get("away_team") if is_away else game.get("home_team")
            opponent = game.get("home_team") if is_away else game.get("away_team")

            for _, p in frame.iterrows():
                name = str(p.get("PLAYER_NAME") or "").strip()
                if not name:
                    continue
                raw_pts = max(0.0, base._num(p.get("PROJ_PTS"), 0.0))
                raw_reb = max(0.0, base._num(p.get("PROJ_REB"), 0.0))
                raw_ast = max(0.0, base._num(p.get("PROJ_AST"), 0.0))
                row = p.to_dict()
                row.update({
                    "game_id": game_id,
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
                row["PROJ_PRA"] = row["PROJ_PTS"] + row["PROJ_REB"] + row["PROJ_AST"]
                rows.append(row)

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.drop_duplicates(subset=["game_id", "player_key"], keep="first")
    return out, {
        "schedule": schedule,
        "context_diag": context_diag,
        "availability_diag": availability_diag,
        "baseline": baseline,
        "schedule_version": "V2.5 ET-reconciled",
    }


class _MatchupFacade:
    matchup_projection_frame = staticmethod(_points_projection_frame)


# Redirect only the Points module's own global dependencies. Shared PRA modules
# remain unchanged because these assignments replace references inside base only.
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

# Re-export the production connector API.
_paired_points_markets = base._paired_points_markets
_prepare = base._prepare
_points_distribution = base._points_distribution
_finalist_units = base._finalist_units
run_standard = base.run_standard
run_final = base.run_final
combined_rows = base.combined_rows
restore_if_missing = base.restore_if_missing
persist_if_ready = base.persist_if_ready
render_points_connector = base.render_points_connector

__all__ = [
    "MODEL_VERSION", "MODEL_SCHEMA", "STANDARD_SIMS", "FINAL_SIMS",
    "market", "sgo", "std_key", "final_key", "source_key",
    "_paired_points_markets", "_prepare", "_points_distribution", "_finalist_units",
    "run_standard", "run_final", "combined_rows", "restore_if_missing",
    "persist_if_ready", "render_points_connector",
]
