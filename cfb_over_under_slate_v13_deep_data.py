"""CFB Over/Under Slate V13 Deep Data — current-evidence reconciliation.

This orchestration feeds reconciled current team/game evidence through the
already-frozen model engines in their original order. Model formulas, caps,
weights, Step-12 integrity checks and final selection thresholds are unchanged.

Pipeline
--------
reconciled current profiles
-> frozen raw total model
-> frozen Step 3 matchup
-> frozen Step 4 pace
-> frozen Step 5 explosive proxy
-> frozen Step 6 red zone
-> frozen Step 7 third down
-> frozen Step 8 turnover volatility
-> frozen Step 9 environment math using post-12 identity recovery
-> frozen Step 10 history math/context using post-12 H2H recovery
-> frozen Step 11 form/schedule-strength gate
-> frozen Step 12 certification
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Mapping

import streamlit as st

import cfb_over_under_data_recovery_v1 as recovery
import cfb_over_under_deep_data_reconciliation_v1 as deep_data
import cfb_over_under_environment_engine_v1 as environment_engine
import cfb_over_under_explosive_engine_v1 as explosive_engine
import cfb_over_under_final_v1 as final_model
import cfb_over_under_form_strength_engine_v1 as form_engine
import cfb_over_under_history_engine_v1 as history_engine
import cfb_over_under_matchup_engine_v1 as matchup_engine
import cfb_over_under_model_v1 as raw_model
import cfb_over_under_pace_engine_v1 as pace_engine
import cfb_over_under_red_zone_engine_v1 as red_zone_engine
import cfb_over_under_slate_v11 as frozen_step12
import cfb_over_under_third_down_engine_v1 as third_down_engine
import cfb_over_under_turnover_engine_v1 as turnover_engine

MODEL_VERSION = "CFB OVER/UNDER SLATE V13 • DEEP CURRENT-DATA RECONCILIATION"
FROZEN_STEP12_CERTIFIER = "cfb_over_under_slate_v11"
MAX_WORKERS = 2


def _identity(game: Mapping[str, Any]) -> str:
    return str(game.get("identity_key") or game.get("game_id") or "")


@st.cache_data(ttl=120, show_spinner=False)
def analyze_game(
    game: Mapping[str, Any],
    as_of_day: str,
    analysis_line: float,
) -> dict[str, Any]:
    evidence, team_diag = deep_data.reconcile_matchup(game, as_of_day)
    game2 = dict(evidence.get("game") or game)
    away = dict(evidence.get("away") or {})
    home = dict(evidence.get("home") or {})

    # Frozen raw model.
    raw0 = raw_model.project_matchup(
        game2,
        away,
        home,
        float(analysis_line),
    )
    final0 = final_model.synthesize(game2, raw0)
    out: dict[str, Any] = {
        "game": game2,
        "away": away,
        "home": home,
        "raw": dict(raw0),
        "final": dict(final0),
        "team_diag": dict(team_diag),
        "analysis_line": float(analysis_line),
    }

    # Frozen Step 3 offense-vs-defense.
    matchup = matchup_engine.build_matchup_engine(game2, away, home)
    raw3 = matchup_engine.apply_to_raw(raw0, matchup)
    out.update({
        "raw": dict(raw3),
        "final": dict(final_model.synthesize(game2, raw3)),
        "base_raw": dict(raw0),
        "matchup_engine": dict(matchup),
        "analysis_line_matchup_weight": 0.0,
    })

    # Frozen Step 4 pace.
    pace = pace_engine.build_pace_engine(game2, away, home)
    raw4 = pace_engine.apply_to_raw(raw3, pace)
    out.update({
        "raw": dict(raw4),
        "final": dict(final_model.synthesize(game2, raw4)),
        "step3_raw": dict(raw3),
        "pace_engine": dict(pace),
        "analysis_line_pace_weight": 0.0,
    })

    # Frozen Step 5 explosive proxy.
    explosive = explosive_engine.build_explosive_engine(game2, away, home)
    raw5 = explosive_engine.apply_to_raw(raw4, explosive)
    out.update({
        "raw": dict(raw5),
        "final": dict(final_model.synthesize(game2, raw5)),
        "step4_raw": dict(raw4),
        "explosive_engine": dict(explosive),
        "analysis_line_explosive_weight": 0.0,
    })

    # Frozen Step 6 red zone.
    red_zone = red_zone_engine.build_red_zone_engine(game2, away, home)
    raw6 = red_zone_engine.apply_to_raw(raw5, red_zone)
    out.update({
        "raw": dict(raw6),
        "final": dict(final_model.synthesize(game2, raw6)),
        "step5_raw": dict(raw5),
        "red_zone_engine": dict(red_zone),
        "analysis_line_red_zone_weight": 0.0,
    })

    # Frozen Step 7 third-down drive sustain.
    third_down = third_down_engine.build_third_down_engine(game2, away, home)
    raw7 = third_down_engine.apply_to_raw(raw6, third_down)
    out.update({
        "raw": dict(raw7),
        "final": dict(final_model.synthesize(game2, raw7)),
        "step6_raw": dict(raw6),
        "third_down_engine": dict(third_down),
        "analysis_line_third_down_weight": 0.0,
    })

    # Frozen Step 8 turnover volatility.
    turnover = turnover_engine.build_turnover_engine(game2, away, home)
    raw8 = turnover_engine.apply_to_raw(raw7, turnover)
    out.update({
        "raw": dict(raw8),
        "final": dict(final_model.synthesize(game2, raw8)),
        "step7_raw": dict(raw7),
        "turnover_engine": dict(turnover),
        "analysis_line_turnover_weight": 0.0,
        "projected_total_turnover_weight": 0.0,
    })

    # Frozen Step 9 environment math, with already-certified provider recovery.
    environment = recovery.build_environment_engine(game2, away, home)
    raw9 = environment_engine.apply_to_raw(raw8, environment)
    out.update({
        "raw": dict(raw9),
        "final": dict(final_model.synthesize(game2, raw9)),
        "step8_raw": dict(raw8),
        "environment_engine": dict(environment),
        "analysis_line_environment_weight": 0.0,
        "projected_total_environment_weight": 0.0,
        "injury_model_weight": 0.0,
    })

    # Frozen Step 10 history math/context, plus certified all-time H2H recovery.
    history = recovery.build_history_engine(
        game2,
        away,
        home,
        step9_environment=environment,
    )
    raw10 = history_engine.apply_to_raw(raw9, history)
    out.update({
        "raw": dict(raw10),
        "final": dict(final_model.synthesize(game2, raw10)),
        "step9_raw": dict(raw9),
        "history_engine": dict(history),
        "analysis_line_history_weight": 0.0,
        "projected_total_history_weight": 0.0,
        "selection_history_weight": 0.0,
    })

    # Frozen Step 11 form + schedule strength.
    form = form_engine.build_form_strength_engine(
        game2,
        away,
        home,
        step10_history=history,
    )
    raw11 = form_engine.apply_to_raw(raw10, form)
    out.update({
        "raw": dict(raw11),
        "final": dict(final_model.synthesize(game2, raw11)),
        "step10_raw": dict(raw10),
        "form_strength_engine": dict(form),
        "analysis_line_form_weight": 0.0,
        "direct_selection_form_weight": 0.0,
    })

    # Frozen Step 12 certification.
    out = frozen_step12._attach_certificate(out)
    out.update({
        "version": MODEL_VERSION,
        "game": game2,
        "away": away,
        "home": home,
        "team_diag": dict(team_diag),
        "deep_data_reconciled": True,
        "deep_data_version": deep_data.MODEL_VERSION,
        "post12_recovery_version": recovery.MODEL_VERSION,
        "analysis_line": float(analysis_line),
        "sportsbook_input_used": False,
        "market_price_used": False,
        "market_probability_used": False,
        "edge_or_ev_used": False,
        "monte_carlo_used": False,
        "new_model_formula_added": False,
    })
    return out


def scan_slate(
    games: list[Mapping[str, Any]],
    as_of_day: str,
    analysis_lines: Mapping[str, Any],
    workers: int = MAX_WORKERS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    skipped_missing_line = 0
    tasks: list[tuple[dict[str, Any], float]] = []

    for game in games:
        if not bool(
            game.get("identity_verified")
            and game.get("date_matches_query")
        ):
            continue
        identity = _identity(game)
        if not identity or identity not in analysis_lines:
            skipped_missing_line += 1
            continue
        try:
            line = float(analysis_lines[identity])
        except Exception:
            skipped_missing_line += 1
            continue
        tasks.append((dict(game), line))

    max_workers = max(1, min(int(workers), MAX_WORKERS))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(
                analyze_game,
                game,
                str(as_of_day),
                line,
            ): (game, line)
            for game, line in tasks
        }
        for future in as_completed(futures):
            game, line = futures[future]
            try:
                rows.append(future.result())
            except Exception as exc:
                errors.append({
                    "identity": _identity(game),
                    "matchup": (
                        f"{game.get('away_team')} @ {game.get('home_team')}"
                    ),
                    "analysis_line": str(line),
                    "error": f"{type(exc).__name__}: {exc}",
                })

    rows.sort(key=lambda row: (
        str((row.get("game") or {}).get("kickoff_iso") or ""),
        str((row.get("game") or {}).get("identity_key") or ""),
    ))

    final_ready = sum(
        bool((row.get("final") or {}).get("ready"))
        for row in rows
    )
    qualified = sum(
        bool((row.get("final") or {}).get("rank_eligible"))
        for row in rows
    )
    certified = sum(
        (row.get("certification") or {}).get("status") == "CERTIFIED"
        for row in rows
    )
    integrity_failed = sum(
        (row.get("certification") or {}).get("status") == "INTEGRITY_FAIL"
        for row in rows
    )
    reconciled = sum(bool(row.get("deep_data_reconciled")) for row in rows)

    return rows, {
        "version": MODEL_VERSION,
        "games_requested": len(games),
        "games_with_lines": len(tasks),
        "games_analyzed": len(rows),
        "final_ready": int(final_ready),
        "qualified_plays": int(qualified),
        "step12_certified_games": int(certified),
        "step12_integrity_failed_games": int(integrity_failed),
        "deep_data_reconciled_games": int(reconciled),
        "skipped_missing_line": skipped_missing_line,
        "errors": errors,
        "worker_count": max_workers,
        "analysis_line_projection_weight": 0.0,
        "sportsbook_input_used": False,
        "market_price_used": False,
        "market_probability_used": False,
        "edge_or_ev_used": False,
        "monte_carlo_used": False,
        "new_model_formula_added": False,
    }


def clear_scan_cache() -> None:
    try:
        analyze_game.clear()
    except Exception:
        pass
    try:
        deep_data.clear_reconciliation_cache()
    except Exception:
        pass


__all__ = [
    "FROZEN_STEP12_CERTIFIER",
    "MAX_WORKERS",
    "MODEL_VERSION",
    "analyze_game",
    "clear_scan_cache",
    "scan_slate",
]
